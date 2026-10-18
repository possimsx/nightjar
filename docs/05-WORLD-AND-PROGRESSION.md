# 05 — World Map & Progression

How the world is wired together, how doors gate it, and how progress is saved.

---

## 1. Room model

* Every room is an **8 × 6 grid of metatiles** (`data/rooms.asm`, `RoomNNN`, indexed by
  `idxRooms`). On screen that's a single non-scrolling screen; you move room-to-room.
* `data/roomtileset.asm` picks the tileset; `data/metatiles.asm` + `data/tileblocks.asm`
  expand metatiles to VDP tiles; `data/palettes.asm` sets colors.
* Reference renders of every room are in [`room_images/`](../room_images/)
  (`MGEAR1_0000.png` … `MGEAR1_0250.png`) — open these to *see* a room while editing its
  data. (They are documentation art, not built into the ROM.)

### Room connectivity (`data/roomsconnections.asm`)

4 bytes per room = **North, South, West, East** neighbor IDs. `255` (`#FF`) = wall/no exit.
Example:

```asm
db   1, 121, 255,   4    ; room 0:  N=1  S=121  W=-   E=4
```

When Snake walks off an edge, `NextRoomLogic` reads this table to find the destination room.
(Doors override this with their own `DEST_ROOM`.)

---

## 2. Zone / building layout

Room IDs cluster into areas. The clearest authoritative key is the **checkpoint table**
(`SaveStatRooms` in `logic/checkpoints.asm`) plus the comments in
`data/roomsconnections.asm`:

| Room range | Area |
|------------|------|
| 121 | **Start room** (insertion point) |
| 0–63 | **Building 1** (multiple floors; elevators at 240/241/242) |
| 64 | Exit to **desert** from Building 1 |
| 64–72, 204 | **Desert / courtyard / lorries** between B1 and B2 |
| 73–110 | **Building 2** (floors + basement; elevators 243–246) |
| 105–110, 211–212 | **Water channel** (needs Oxygen) linking B2 ↔ B3 |
| 102–103, 126–128 (→208–210) | **Desert by Building 3** (scorpions) |
| 111–119 | **Building 3** — endgame; **118 = Metal Gear**, **119 = Big Boss** (elevators 247/250) |
| 117 | **Roof** parachute jump |
| 122–125, 138–141 (→220–222) | **Dark rooms** / basement maze (need Compass + light) |
| 142–145 (→224–228) | **Escape ladders** (post-Metal-Gear) |
| 145–154 (→240–250) | **Elevator shafts** (`data/elevatorrooms.asm`, `logic/elevatorroom.asm`) |
| 213–219 | **Lorries** (truck transport puzzles) |

> Rooms with ID ≥ `#F0` (240+) are elevators and have **no enemies** (`UpdateEnemySprStr`
> is skipped for them — see `Banks0123.asm:12065`).

### Map zones & the antenna
`MapZone` (RAM) tags how "deep" you are. **Zones of value 5 or more require the Antenna**
to use the radio (you can't reach Schneider/Diane/Jennifer without it). `IsolatedRoom` marks
rooms where binoculars are disabled and shooting does **not** trigger the alarm.

---

## 3. The door system

Doors are the gates between rooms and the core of progression.

### Per-room door list (`data/doors.asm`)
`idxDoors` maps room → a `DoorsRoomNNN` list. Each door entry is **5 bytes**:

```
db  DoorID, RenderTypeID, DrawY, DrawX, DestRoom
```

`RenderTypeID` (1–14h) selects how it's drawn (north/south/west/east door, elevator door,
or a breakable wall variant). When you enter a room these become live `DOOR` structures in
`DoorsList` (`STRUCT DOOR`: `ID, CLOSED, OPEN_LOGIC_ID, RENDER_TYPE, OPEN_CNT, DRAW_Y,
DRAW_X, Y, NY, X, NX, …, DEST_ROOM`).

### Per-door open-logic (`IdDoorsLogic` in `data/doors.asm`)
One byte per **DoorID** encodes how it opens and its current default state:

```
bits 4-0 : open-logic type (see table)
bit  5   : 1 = "broken wall inside a room" (no room teleport on open)
bits 7-6 : #80 = starts open, otherwise starts closed
```

Open-logic types (dispatched in `logic/doors/opendoor.asm > ChkOpenDoor`):

| Type | Routine | Opens when… |
|-----:|---------|-------------|
| 1 | `ChkElevatorDoor` | Walking up into an elevator / right out of one |
| 2–9 | `ChkCard1`…`ChkCard8` | Correct **card selected** + facing the door |
| A | `ChkPunchDoor` | **Punching** while facing it (Shot Gunner's door) |
| B | `ChkDoorLorry` | (lorry — effectively always open) |
| C | `ChkDesertDoorBuild2` | **Wearing Uniform** (desert guards open it) / walking south from inside |
| D | `ChkCompassDoor` | **Jennifer opens it** (`JeniOpenDoorF`) → compass room |
| E | `ChkBigBossDoor` | `OpenBigBossDoor` set (Metal Gear→Big Boss, and the escape) |
| F | `ChkPrisonWalls` | **Punch** through a cell wall (Snake's & Grey Fox's cells) |
| 10 | `ChkBasementWall` | **Plastic bomb** (or punch certain hollow walls) |

### Door state persists
`DoorOpenArray` (`#A0` bytes, one per door) records every door's open/closed status and is
part of the **saved game state** — so an unlocked door stays unlocked across checkpoints.

---

## 4. The critical path (one-line walkthrough)

Start (121/0) → grab early **Cards + Handgun/SMG** in Building 1 → **Missile** kills Machine
Gun Kid (20) and the **power box** (37) → **Grenade Launcher** kills Hind-D (50) → get
**Gas Mask / Bomb Suit / Parachute** → (likely captured → recover **BAG**, rooms 54/58) →
**Mines** kill the Tank (67) → wear the **Uniform** to enter Building 2 (69/73) → **Compass
+ Flashlight** for the dark maze → **Fire Trooper** (95), **Scorpions** w/ **Antidote**
(102/103) → **Card 7/8** (Card 8 from **Coward Duck**, 193) → **Oxygen** through the **water
channel** to Building 3 → ignore Big Boss's "turn off your MSX" (111) → **Plastic Bombs**
destroy **Metal Gear** (118) → defeat **Big Boss** (119) → **cigarettes** stretch the
self-destruct timer → escape via the **ladders** → Ending.

For the narrative attached to each step, see [03-STORY-INDEX.md](03-STORY-INDEX.md).

---

## 5. Save / continue system

There are **two** independent persistence mechanisms.

### a) Automatic checkpoints (`logic/checkpoints.asm`)
When Snake moves from a specific room A into room B, and that **(room, previousRoom) pair**
is in `SaveStatRooms`, the engine snapshots progress into `GameProgressBuffer`. After a
game-over you continue from the last checkpoint. The blocks copied (`GameDataAreas`):

| Block | Size | Contents |
|-------|------|----------|
| `Room` | 20h | room, life, class, selected weapon/item, status… |
| `PlayerControlMod` | 20h | player position/anim state |
| `MaxAmmoGun` | 50h | ammo caps & current ammo, rations |
| `DoorOpenArray` | D8h | every door's open/closed state |
| `Equipment` | 90h | full inventory + item counts |
| `GameDataArea` | A0h | event flags, boss-KO flags, alert state |

The checkpoint rooms (from `SaveStatRooms`, with the engine's own comments) double as a map
legend, e.g. *"240,3 = Elevator West 1st floor building 1"*, *"64,11 = Exit to desert from
building 1"*, *"73,69 = Entering Building 2 from desert"*, *"118,116 = Enter Metal Gear
room"*. Read that table for a labeled tour of the whole fortress.

> `MetalGear_KO` disables checkpointing — once the self-destruct is running, there's no
> saving; you commit to the escape.

### b) Tape save/load + passwords (`logic/saveload.asm`, `logic/passwords.asm`)
The Pause screen (`GS_Pause`) can save/load the same blob to **cassette** (`SaveLoadMode`
1=load/2=save) or display/enter a **password**. The last byte of `GameProgressBuffer` is a
checksum. (Historical note from the README: Turbo-R machines lack a cassette port, which is
why a password path exists.)

---

## 6. Special movement / control states

`PlayerControlMod` switches Snake's physics for special rooms (these are *engine features
tied to rooms*, useful to know when redesigning):

| Mode | Where it's used |
|------|-----------------|
| 0 Walk / 1 Punch | normal play |
| 2 Elevator | elevator shafts (240–250) |
| 4 Parachute | roof jump (117) — needs Parachute |
| 5 Air-flow | rooftop wind barrier — needs Bomb Suit |
| 6/7 Ladder walk/climb | escape ladders (224+) |
| 8 Intro | the opening infiltration scene |

In ladder rooms (≥224) and the parachute brick room (204) you **cannot** pause, use the
radio, or open the inventory (`Banks0123.asm:12114`).
