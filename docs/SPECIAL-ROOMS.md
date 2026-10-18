# Special rooms & the room-number space

The engine does **not** treat all rooms uniformly. Room behaviour is partly
data-driven (connections / doors / actors, see [04-OBJECTS-INDEX](04-OBJECTS-INDEX.md))
and partly **hardcoded by room number** in `logic/` and `Banks0123.asm`. Any
NIGHTJAR topology change that moves one of these rooms must also patch the ASM, or
the gimmick breaks. This file inventories every hardcoded room reference.

References are `file:line` into the disassembly.

---

## 1. The room-number address space

`GetNextRoomNum` ([Banks0123.asm:893](../Banks0123.asm#L893)) partitions the id
range. This is *the* map of what each id band means:

| Id band | Meaning | How the next room is found |
|---------|---------|----------------------------|
| **0–125** | Normal walkable rooms | `RoomConnections[room]` 1:1 (N/S/W/E neighbour) |
| **126–207** | Lorries & "isolated" rooms | **No connections** — reachable only through a door |
| **208–227** | Special / ladder rooms | exit table index = `room − 82` → conn slots 126–145 (`224` = first ladder room) |
| **228–239** | Undefined | — |
| **240** | First elevator | special elevator logic, **no** connections |
| **241–250** | Elevator rooms | conn index = `room − 95` → conn slots 146–155 |

So `RoomConnections` only needs **156 entries (0–155)**: the open grid (0–125)
plus the remapped special/elevator slots. Anything ≥126 that isn't an elevator or
208–227 is **door-only** — it has no spatial neighbours at all.

Ladder rooms (`224–226`) and elevators (`240–250`) also get bespoke entry handling
in `Banks0123.asm` (`cp 240`/`0F0h` elevator checks throughout sprite & transition
code). The **ladder ids are now editable** — `LADDER_FIRST`/`LADDER_LAST`/`BIG_BOSS_ROOM`
in [`constants/ladders.asm`](../constants/ladders.asm), edited via the editor's 🪜 panel.
Relocation only works under **WORLDBANK=1** (per-room connections); at WORLDBANK=0 the
208–227 exit-table remapping locks them. Even under WORLDBANK the **door-slot gap**
(rooms `LADDER_FIRST+1..239` carry no doors; elevator slots compact down by
`ELEV_DOOR_SKIP`) bounds how far the block can move up before the door table overflows
— that is the deferred [LIMITS-PLAN](LIMITS-PLAN.md) **A6** rework.

The **elevator band base is `ELEVATOR_FIRST`** (240 = 0F0h) in
[`constants/elevators.asm`](../constants/elevators.asm) — the shared constant the
"is elevator room" range checks and the ladder `ELEV_DOOR_SKIP` math both reference,
plus the long-elevator floors `LONG_ELEV_*` (247–250, derived). Editable via the 🛗
panel, but **pinned to 240**: several checks are `and 0F0h` nibble-masks (not
parameterized), so moving it off the 0xF0 boundary needs those rewritten to range
checks first (and there is no other aligned high-id slot anyway).

### 1b. Exit-table internals — how "next room on walk-off" is resolved

`GetNextRoomNum` ([Banks0123.asm:893](../Banks0123.asm#L893)) is called when the
player crosses a screen edge. It needs two inputs, both in RAM:

- **`Room`** (`#C130`) — the id of the room you are *currently* in.
- **`NextRoomDirect`** (`#C133`) — which edge you crossed: `1=Up(N) 2=Down(S) 3=Left(W) 4=Right(E)`.

The routine remaps `Room` to a **connection-slot index**, then indexes that slot by
direction:

```
        a = Room
        if a < 126           index = a            ; 0–125  → slot a (1:1)
        elif a < 208         return 0FFh          ; 126–207 door-only, NO walk-off
        elif a < 228         index = a − 82        ; 208–227 → slots 126–145
        elif a < 241         return 0FFh           ; 228–240 (240 = 1st elevator)
        else                 index = a − 95        ; 241–250 → slots 146–155  (sub 13 then sub 82)
        hl = &RoomConnections[index*4]             ; HL_4xA + add RoomConnections
        hl += (NextRoomDirect − 1)                 ; pick the N/S/W/E byte (order N,S,W,E)
        C  = (hl)                                  ; C = destination room id (0FFh = none/wall)
```

**⚠ The `0FFh` walk-off trap.** A walk-off that resolves to `0FFh` (no neighbour —
including *any* walk-off from the door-only band 126–207) falls into the `cp 0F0h`
elevator branch of `SetNextRoom` ([nextroom.asm:26](../logic/nextroom.asm#L26)) and
initializes elevator state for "room 255" → RAM trash → machine reset. Normal play
never hits it because you can only be inside a door-only room with its entry door
**open**, and the open door's enter-box teleports you before you reach the edge
(verified in emulator: rooms 115/200 blown wall). But any tool/poked state that puts
the player in such a room with the door **closed** lets them walk clean off the edge
and crash (the closed door never enters the `ChkEnterDoor` check). The map editor's
warp therefore force-opens every door in its warp chain. When authoring NIGHTJAR
maps: keep door-only room layouts sealed, or make sure a door enter-box covers every
walkable gap to a screen edge.

So **the engine always knows where to go from the `Room` variable alone** — not from
the artwork on screen. Rooms 106, 211 and 212 share *identical layouts*, but the engine
holds a distinct `Room` value for each, so each resolves a different neighbour:

| You are in (`Room`) | index used | `conn[index]` (N,S,W,E) | Walk **N** takes you to |
|---|---|---|---|
| 106 | 106 | `211,105,—,—` | 211 |
| 211 | 211−82 = 129 | `212,106,—,—` | 212 |
| 212 | 212−82 = 130 | `107,211,—,—` | 107 |

That is the `105 → 106 → 211 → 212 → 107` climb: **three different rooms, one shared
layout, three different connection records.** The engine distinguishes them purely by
`Room`; entering one (via a door or a previous walk-off) is what sets `Room` to 211/212.

**Why it works this way — two payoffs:**

1. **ROM economy.** 235 room layouts exist but `RoomConnections` has only **156
   slots**, packed exactly: `0–125` direct, `126–145` for the 20 exit-table rooms
   `208–227`, `146–155` for the 10 elevators `241–250`. Door-only rooms (126–207) and
   228–240 cost **zero** connection bytes. The `−82` / `−95` offsets are just cheap Z80
   subtractions that fold the high-id special rooms onto the spare tail of the table.
2. **Layout reuse with independent navigation.** A real grid room (e.g. 103) owns exactly
   one connection slot, so you cannot reuse *it* for extra screens. To build a multi-screen
   shaft where every screen looks the same, Konami mints new room ids (208,209,210 …),
   points their layout pointer at the existing art, and gives each its own connections from
   the borrowed slots. Layout sharing is heavy: **RoomLorry's layout is used by 18 room ids,
   RoomTableS by 16, RoomCell by 8**; `208/209/210` reuse `Room103`, `211/212` reuse `Room106`.

**⚠ The borrowed slot has a single real owner.** `conn[129]` physically lives in room 129's
(RoomCell's) record, but room 129 is in the door-only band (126–207) so it **never reads its
own connections**. The bytes in `conn[129]` were authored for **room 211**. So a connection
slot in 126–155 belongs to the exit-table/elevator room that maps onto it, *not* to the
like-numbered door room — the `RoomCell`/`RoomLorry` labels on those slots are misleading.
(Self-loops like `208.W=208 / 208.E=208` just mean "wall, no horizontal exit".) The comment
at [Banks0123.asm:906](../Banks0123.asm#L906) notes 227 is a likely-vestigial ladder slot.

---

## 2. The parachute subgraph (skydive)

Room **204** ("Bricks wall parachute" / "Big bricks wall") is the free-fall room.
Almost none of its routing comes from the door table — it is hardcoded in
[nextroom.asm](../logic/nextroom.asm) and [bridge.asm](../logic/bridge.asm).

### Flow

```
        jump trigger                fall              land (JumpRoomId)
  ┌─────────────────────┐                        ┌────────────────────┐
  │ roof 117  door 91h  │──┐                  ┌──│ JumpRoomId=else →10 │ dogs yard right
  │ bridge 45 door 5Bh* │──┼──► room 204 ──►──┼──│ JumpRoomId=1   → 5  │ 3-lorries yard
  │ bridge 46 door 81h* │──┘   (fall N floors)└──│ JumpRoomId=2   → 6  │ dogs yard left
  └─────────────────────┘                        └────────────────────┘
        *5Bh / 81h are SYNTHESIZED in code, not real doors you touch
```

### What is data vs. hardcoded

| Piece | Where | Data or code |
|---|---|---|
| The three "doors" in `DoorsRoom204` (91h→117, 81h→46, 5Bh→45) | [doors.asm:812](../data/doors.asm#L812) | **data**, but `dest` bytes are *ignored* — only used for door render/locate |
| Roof jump door 91h in room 117 | [doors.asm:620](../data/doors.asm#L620) | data (a real door you walk into) |
| Bridge "doors" 5Bh / 81h | [bridge.asm:38-47](../logic/bridge.asm#L38) | **code** — synthesized when you step off a moving bridge onto empty tiles; also sets `JumpRoomId` 1/2 |
| Destinations 117 / 45 / 46 for IDs 91h/5Bh/81h | [nextroom.asm:106-118](../logic/nextroom.asm#L106) (`ChkDoorDestination`) | **hardcoded**, overrides door table |
| Parachute on/off → `Room=204` + `HeightParachuteCnt` else death | [nextroom.asm:204-237](../logic/nextroom.asm#L204) (`ChkParachute`/`FreeFall`) | **hardcoded** |
| Fall loop (`cp 204` first thing) | [nextroom.asm:12-15](../logic/nextroom.asm#L12), `NextParachuteRoom` 246 | **hardcoded** |
| Landing room 5 / 6 / 10 by `JumpRoomId` | [nextroom.asm:262-285](../logic/nextroom.asm#L262) (`SetLandingRoom`) | **hardcoded** |
| Parachute anim & landing XY (rooms 5/6/10) | [nextroom.asm:488-573](../logic/nextroom.asm#L488) | **hardcoded** |
| Hidden doors room 5 (6Ch) / room 6 (40h) → 204 | [enterdoor.asm:64-70](../logic/doors/enterdoor.asm#L64) | data present but **engine skips them** (cut content — you can't walk into 204) |

**Rework implication:** rooms 204, 117, 45, 46, 5, 6, 10 form a fixed-*shape* cluster
(one fall room, roof + two bridge sources, three landings, two fall-floors). The
**room numbers are now editable** — they are `equ` constants in
[`constants/parachute.asm`](../constants/parachute.asm) (`PARACHUTE_ROOM`,
`PARA_SRC_*`, `PARA_LAND_*`), edited via the editor's 🪂 panel (shown when you select
any cluster room; rebuild to apply). So the cluster can be **relocated** to different
ids, but each slot must stay the right *kind* of room: the roof keeps its jump door
`91h`, the bridges stay bridge rooms (`bridge.asm` reads the same `PARA_SRC_BRIDGE*`),
and the fall room keeps the bricks-wall layout. The door ids `91h`/`5Bh`/`81h`, the
landing entry-XY (keyed to those door ids) and the fixed shape are still hardcoded.

---

## 3. Full special-room inventory

Grouped by why they're special. "—" = no extra note.

### Movement / transition specials
| Room | Role | Ref |
|---|---|---|
| 204 | Parachute free-fall ("bricks wall") | nextroom.asm:14,314 |
| 5 | 3-lorries yard; parachute landing (from bridge 45) | nextroom.asm:546,560 |
| 6 | Dogs yard left; parachute landing (from bridge 46) | nextroom.asm:549,568 |
| 10 | Dogs yard right; parachute landing (from roof) | nextroom.asm:543,552 |
| 45 | Moving bridge 1 (fall-through) | bridge.asm:17 |
| 46 | Moving bridge 2 (fall-through) | bridge.asm:20 |
| 117 | Roof — roof-jump door (91h) | nextroom.asm:108 |
| 103 | Desert — get lost here without the compass | nextroom.asm:34 |
| 119 | Big Boss room — special ladder entry | nextroom.asm:583 |
| 224–226 | Ladder rooms (224 = first, editable via `constants/ladders.asm`; relocatable under WORLDBANK=1) | Banks0123.asm `ChkExitLadders`/`ChkLadderLimits` |
| 240 | First elevator (no connections) | Banks0123.asm:988,1282 |
| 241–250 | Elevator rooms (conn = room−95) | elevatorroom.asm; Banks0123.asm:909 |
| 247 | Long underground elevator — upper floor | elevatorroom.asm:89 |
| 248,249,250 | Long underground elevator — don't-stop floors | elevatorroom.asm:69-75 |

### Hazard / gimmick rooms
Environmental hazards (dark/gas/electric/water/deep-water/**laser**) are **no longer
room-number-hardcoded** — they are per-room bits in the unified `RoomFlags` table
(cached to `CurRoomFlags` at room load) and editable in the map editor. See
[HAZARD-FLAGS-PLAN.md](HAZARD-FLAGS-PLAN.md). The rows below are the *stock seed* rooms,
kept for reference; move them freely by editing the flag, not the ASM.

The per-room properties are split across **two** bytes now: `RoomFlags` (8 bits, full)
and `RoomFlags2` (spare byte, cached to `CurRoomFlags2`). Capture lives in `RoomFlags2`
so `RoomFlags` bit5 could be reused for moving lasers.

| Room | Role | Now | Ref |
|---|---|---|---|
| 40 | Electrified floor damage (roof, building 1) | `RoomFlags` bit2 (data) | damageelectric.asm |
| 24, 25, 72 | Laser-beam rooms (`ID_LASER`; beams shown with goggles) | `RoomFlags` bit6 (data) | drawlaserbeams.asm |
| 72 | Laser beams also **sweep/move** on a timer | `RoomFlags` bit5 (data) — "moving lasers"; pair with bit6 for a moving beam room | Banks0123.asm `DrawMovingLasers` |
| 70 | First water room (before Bulldozer) | `RoomFlags` bit3 (data) | Banks0123.asm (ChkWater) |
| 111 | Building-3 basement, two **laser cameras** / door to gas room | `RoomFlags` bit7 (data) — "short camera lasers" (shorter visual **and** hitbox); a different mechanic from the beam rooms above. `ID_CAMERA_LASER` actors are placeable in any room; this bit marks which rooms shorten them | lasershot.asm; damagelaser.asm |
| 8 (etc.) | Capture trap — walking into X-zone 0C0h–0D0h captures Snake → prison | `RoomFlags2` bit0 (data); prison room editable (`CapturePrisonRoom`) | common.asm; capturescene.asm |
| (any) | Electric-floor **power switch**: floor palette color slot and destroyed-switch art VRAM-X | `ElectricColorSlot[gfx]` + `PowSwGfxSrcX[gfx]` (data, per-tileset like `ElectricTiles`) — the old `cp 40`/`cp 116` were really per-tileset; a switch now works in any room by its tileset | powerswitch.asm; Banks0123.asm `ErasePowerSw` |
| 140 | Mines / 3 sleeping guards | hardcoded (scripted) | sentinel.asm:12; snoringsymbol.asm:38 |
| 160 | Mine-detector room | hardcoded (scripted) | jetpack.asm:80 |
| 190 | Isolated basement (building 2), CARD 1 | hardcoded (scripted) | pitfall.asm:149 |

> **Note — the old "47" was a decode bug.** `DrawLaserBeams` does `sub 24 / dec a / cp 47`,
> which resolves to rooms **24, 25, 72** (its own comments say so), not 47/72. Room 47 holds
> only guards. The laser flag is seeded to 24/25/72; the mines/pitfall in 140/190 are placed
> `ID_*` **actors** (editable in the actor panel), not room-number hazards.

### Boss / event rooms
| Room | Role | Ref |
|---|---|---|
| 118 | Metal Gear | camera.asm:9 |
| 133 | Madnar / Big Boss event | madnarbigbossevent.asm:10 |
| 167 | Ellen's room (prisoner) | prisoner.asm:219 |
| 193 | Coward Duck room (prisoner) | prisoner.asm:83,222 |

### Enemy-spawn / scripted-NPC rooms
| Room | Role | Ref |
|---|---|---|
| 7 | Three lorries, building 1 (next to elevator) | guardlorry.asm:25,40 |
| 69 | Desert guards to building 2 | sentinel.asm:28,64 |
| 73 | Building 2 first room (desert security; can't open from inside) | desertsecurity.asm:16; opendoor.asm:216 |
| 127,128 | Lorry card rooms (guard alert) | guardalert.asm:15 |
| 137 | Sub Machine Gun item room | hideguards.asm:36 |
| 139 | Goggles room (guard switch) | guardswitch.asm:9 |
| 206 | Building 2, elevator east | shooter.asm:14 |
| 216 | 4th lorry in desert / entrance to building 3 | setalert.asm:21 |
| 242 | Elevator roof, building 2 | hideguards.asm:163 |

### Other room-id specials (surfaced by the ASM `cp <room>` sweep)
| Room | Role | Now | Ref |
|---|---|---|---|
| 83 | Two Arnolds (last kill drops CARD 7) | `SpecialEnemyCnt` table (data) — sets `ArnoldsCnt=2` on entry | Banks0123.asm `SetSpecialEnemyCnt` |
| 150 | Four silencer guards (last kill drops the suppressor) | `SpecialEnemyCnt` table (data) — sets `GuardSilencerCnt=4` on entry | Banks0123.asm `SetSpecialEnemyCnt` |
| 78 | Ditch / water-channel entrance room (special tile collision) | **hardcoded** | Banks0123.asm:9085 |
| 53 | Roof elevator | **hardcoded** | Banks0123.asm:9371 |

`SpecialEnemyCnt` (`db room, dw counterVar, db count`, `0FFh`-terminated) sets a
special-enemy counter on room entry — add an entry to place an Arnold/silencer-style
encounter (fixed count whose last kill drops an item) in any room.

### Data-range boundaries (not single rooms, but hardcoded cut-offs)
| Boundary | Meaning | Ref |
|---|---|---|
| 122 | First isolated/lorry room (items valid 122–217) | addroomitems.asm:19 |
| 126 | First lorry room (connection-band split) | Banks0123.asm:898; addroomitems range |
| 128 | Only the first 128 rooms have a predefined alert level | chkdiscover.asm:334 |
| 218 | From this room on, **no items** | addroomitems.asm:16 |

### Door-ID specials (room-adjacent, by door ID not room)
| Door ID | Meaning | Ref |
|---|---|---|
| 6Ch (room 5), 40h (room 6) | Hidden doors → 204, **disabled** in code | enterdoor.asm:66,69 |
| 62h | Card-1 door before Metal Gear — locks after self-destruct (no going back) | enterdoor.asm:38 |
| 0Fh logic / 10h logic | "broken wall inside room" door classes (no teleport) | enterdoor.asm:74,77 |
| 6Bh | Door to ladders from Big Boss room | nextroom.asm:307 |

---

## 4. Progression-flag & codec gates

A separate class of "special" that is **not keyed to room number** but still breaks
if you move rooms, renumber items, or re-point radio texts. These are the
codec-call / story-flag gates: an item that will not spawn, or a door that will not
open, until a radio event flips a one-byte flag; plus the antenna requirement that
silences the radio in whole map zones. None of this is map data and **none of it is
exposed in the editor today** — it is hardcoded in `logic/` + `Banks0123.asm`,
keyed to specific *text IDs*, *item IDs*, *room numbers*, and one nibble table.
See [CODEC-GATE-PLAN.md](CODEC-GATE-PLAN.md) for the plan to make it editable.

### 4a. Story flags set when a radio text is dismissed
`TextBoxExit` ([Banks0123.asm:8380-8391](../Banks0123.asm#L8380-L8391)) watches the
`TextId` just shown and sets a flag. This is the *only* place these flags turn on —
the "codec call" is really "player read text N".

| Text ID | Flag set | Unlocks | Consumer |
|---|---|---|---|
| 117 | `JeniRocketF` | Rocket Launcher spawns (its item room) | [addroomitems.asm:60-65](../logic/addroomitems.asm#L60-L65) |
| 118 | `JeniOpenDoorF` | Compass door (**room 87**) opens once | [opendoor.asm:249-254](../logic/doors/opendoor.asm#L249-L254) |
| 138 | `SchneiderCaptured` | Schneider stops being callable | [Banks0123.asm:1743-1745](../Banks0123.asm#L1743-L1745) |

### 4b. Item / door spawn gates (consume the flags above)
| Gate | Rule | Ref |
|---|---|---|
| Rocket Launcher | If item ID == `ROCKET_LAUNCHER`, skip placing it while `JeniRocketF==0`. Keyed to the **weapon ID**, not the room — any room holding a rocket launcher inherits this. | [addroomitems.asm:60-65](../logic/addroomitems.asm#L60-L65) |
| Compass door (room 87) | `ChkCompassDoor` keeps the door `DoorLocked` until `JeniOpenDoorF`, then clears the flag (one-shot). Wired to room 87 in the door-type dispatch. | [opendoor.asm:245-255](../logic/doors/opendoor.asm#L245-L255) |
| Building-2 entrance (room 73) | `ChkDesertDoorBuild2` needs `DoorBuild2LockedF` (set when the desert guards open it); can't be opened from inside. Room 73 hardcoded. | [opendoor.asm:212-235](../logic/doors/opendoor.asm#L212-L235) |

### 4c. Antenna zone gate (the "no calls until antenna" rule)
`idxMapZones` ([data/musicradioconfig.asm:58](../data/musicradioconfig.asm#L58)) is a
**nibble-per-room** table (read via `GetNibbleRoom`, one hex digit per room, in room-id
order). Its value lands in `MapZone` at [Banks0123.asm:1094-1097](../Banks0123.asm#L1094-L1097).
Any room whose zone nibble is **≥ 5** requires `AntennaTaken` for radio to work — this
gates **both** incoming calls ([ChkRadioCalls3, Banks0123.asm:1772-1778](../Banks0123.asm#L1772-L1778))
**and** outgoing replies ([ChkRadioReply, Banks0123.asm:11117-1123](../Banks0123.asm#L11117-L11123)).
Zones 0–4 = Building 1 (never need antenna); 5–A = Building 2/3 (need antenna).
Picking up the antenna sets `AntennaTaken` and force-triggers any pending call
([items.asm:162-170](../logic/items.asm#L162-L170)).

Other radio-availability conditions in the same checks (not room-keyed, listed for
completeness): Schneider frequencies never auto-call; Jennifer needs 4-star rank
(`Class==3`) and `JennifBrotherDead==0`; a per-room bit3 in the music/radio config
byte marks "a call happens in this room".

**Rework implication:** if NIGHTJAR renumbers rooms, `idxMapZones` is positional by
room id — it must be re-authored to match the new map (or the antenna gate lands on
the wrong rooms). Text IDs 117/118/138 and the `ROCKET_LAUNCHER` id are hard anchors;
the compass-door and building-2-door rooms (87, 73) are hard anchors.

---

## 5. Rework checklist

When re-wiring topology for NIGHTJAR, before moving/renumbering any room above,
confirm it is **not** in §3 or §4. If it is:

1. Keep its id fixed where possible (cheapest).
2. If it must move, grep `logic/` + `Banks0123.asm` for the old number and patch
   every `cp <id>` / range check.
3. Re-run the codec gates (`mgmap graph`, `conncheck`, `mgmove validate`) **and**
   emulator-verify the gimmick (parachute, elevator, bridge, boss trigger).
4. If any moved room carried a `idxMapZones` value ≥5, re-author that nibble table
   (§4c) so the antenna gate still lands on the right rooms.

The elevator band (240–250), parachute cluster (204/117/45/46/5/6/10) and ladder
band (224–227) are the highest-risk groups — treat them as fixed anchors. The
progression-flag gates (§4) fail *silently* (item just never appears, door never
opens, radio goes dead) — they won't show up in `mgmove validate`, so verify them
by hand.
