# Codec / progression gates: make them editable — plan

Goal: replace the hardcoded "an item/door is locked until a radio call flips a
story flag" logic — plus the positional antenna-zone table — with **data tables +
generic interpreters**, then edit them through a codec + editor UI (same shape as
the [hide-guard](HIDE-GUARD-PLAN.md) and reconfigurable-hazards reworks).

Today these gates are invisible in the editor and fail *silently* when topology
changes (item never spawns, door never opens, radio goes dead). See
[SPECIAL-ROOMS.md §4](SPECIAL-ROOMS.md) for the as-shipped inventory this plan is
built from.

Chosen approach: **data table + interpreter** (faithful; fully editable; can add
gates to new rooms/items). Not "auto-derive from proximity", not "edit flags live".

---

## 1. What the mechanism does today

Three independent sub-systems, all keyed to fixed IDs, none data-authored:

### 1a. Story flags set by reading a radio text
`TextBoxExit` ([Banks0123.asm:8380-8391]) matches the `TextId` just dismissed and
sets a one-byte flag. The "codec call" is really "player read text N".

| Text ID | Flag | Effect downstream |
|---|---|---|
| 117 | `JeniRocketF` | Rocket Launcher may now spawn |
| 118 | `JeniOpenDoorF` | Compass door (room 87) may now open |
| 138 | `SchneiderCaptured` | Schneider stops being callable |

### 1b. Spawn/open gates that consume those flags
* **Rocket Launcher** — `AddRoomItems` ([addroomitems.asm:60-65]) special-cases the
  weapon *ID*: if `item == ROCKET_LAUNCHER` and `JeniRocketF == 0`, it aborts the
  whole item list (`ret`). Note it aborts, not "skip this item" — the rocket is the
  last entry in its set, so in stock data that's equivalent, but a data rework must
  preserve/repair that.
* **Compass door (room 87)** — `ChkCompassDoor` ([opendoor.asm:245-255]) stays
  `DoorLocked` until `JeniOpenDoorF`, then clears the flag (one-shot open).
* **Building-2 entrance (room 73)** — `ChkDesertDoorBuild2` needs `DoorBuild2LockedF`
  (set by the desert-security guards, not by a call). Included because it's the same
  "door gated on a flag" shape; the flag source differs.

### 1c. Antenna zone gate
`idxMapZones` ([data/musicradioconfig.asm:58]) — a **nibble-per-room** table
(`GetNibbleRoom`, one hex digit per room id). Value ≥5 ⇒ radio needs `AntennaTaken`,
for both incoming calls ([ChkRadioCalls3, Banks0123.asm:1772]) and outgoing replies
([ChkRadioReply, Banks0123.asm:11117]). Antenna pickup sets the flag and forces a
pending call ([items.asm:162-170]).

---

## 2. Complete gate extraction (VERIFY THIS)

The editable model is three tables. `Text→Flag` and `Antenna zones` are already
tables-in-spirit; the item/door gates are the ones that need lifting out of code.

### Table A — text-sets-flag (from §1a)
| # | TextId | Flag byte | Notes |
|---|--------|-----------|-------|
| 0 | 117 | JeniRocketF | |
| 1 | 118 | JeniOpenDoorF | |
| 2 | 138 | SchneiderCaptured | not a spawn gate; keep for completeness |

### Table B — spawn/open gates (from §1b)
| # | Subject | Match on | Required flag | Action when flag=0 | On use |
|---|---------|----------|---------------|--------------------|--------|
| 0 | item | ID == ROCKET_LAUNCHER | JeniRocketF | omit item | — |
| 1 | door | room == 87 | JeniOpenDoorF | keep locked | clear flag (one-shot) |
| 2 | door | room == 73 | DoorBuild2LockedF | keep locked | clear flag (one-shot) |

Generalized rule: *(subject = item-ID **or** room-ID) requires (flag) — else
(omit / stay-locked); optionally (clear flag on satisfy).* Row 0 keys on item ID;
rows 1–2 key on room ID. A clean model keys **item gates by (room, item-ID)** so the
same weapon elsewhere isn't gated, and door gates by room.

### Table C — antenna zones (from §1c)
Nibble-per-room, value ≥5 ⇒ antenna required. Already fully data; the rework only
needs to (a) surface it in the editor and (b) keep it positionally correct across
renumbering. The zone *number* also feeds area music, so it is **not** free to
change arbitrarily — only the ≥5/<5 threshold matters to the antenna gate.

---

## 3. Proposed on-ROM format

Keep it byte-identical-friendly (same discipline as `mgmap`). Two new small blobs;
Table C already exists.

```
GateTexts:              ; Table A — terminated 0FFh
        db  117, <flag_idx>
        db  118, <flag_idx>
        db  138, <flag_idx>
        db  0FFh
GateFlagPtrs:           ; flag_idx -> RAM address (JeniRocketF, JeniOpenDoorF, ...)
        dw  JeniRocketF, JeniOpenDoorF, SchneiderCaptured, DoorBuild2LockedF

GateSpawns:             ; Table B — terminated 0FFh
        ; kind(0=item,1=door), key(itemID or roomID), flag_idx, oneshot(0/1)
        db  0, ROCKET_LAUNCHER, 0, 0
        db  1, 87,              1, 1
        db  1, 73,              3, 1
        db  0FFh
```

`idxMapZones` (Table C) stays where it is.

Interpreters replace the inline checks:
* `AddRoomItems` calls `GateItemAllowed(itemID)` → walk `GateSpawns` for a matching
  item row; if found and `*flag==0`, skip. (Preserve the stock "abort vs skip"
  behaviour — safest is *skip this item, continue* and ensure data ordering matches.)
* `ChkCompassDoor` / `ChkDesertDoorBuild2` collapse into one `GateDoorAllowed(room)`
  → find door row; locked unless `*flag`; if oneshot, clear on open.
* `TextBoxExit` flag-set collapses into a `GateTexts` scan.

---

## 4. Phased delivery (mirrors hide-guard)

* **Phase 1 — prove equivalence (no ROM change).** `tools/mgcodecgate.py`: parse the
  three tables out of the ASM, and a reference model of the *current* hardcoded
  behaviour. Exhaustively assert table-driven result == original for every
  (item, room, flag-state) and every room's antenna nibble. This is the safety net
  before touching engine code — same "table == original over N cases" gate the
  hide-guard plan used.
* **Phase 2 — engine swap.** Add `GateTexts`/`GateSpawns` data + the three
  interpreters; delete the inline `cp ROCKET_LAUNCHER` / `ChkCompassDoor` /
  per-text `cp 117/118/138` bodies. Rebuild; assert byte-identical *behaviour*
  (not bytes) via emulator on the known beats: read Jennifer call → rocket appears;
  read door call → room 87 opens; enter Building 2 without antenna → radio dead,
  with antenna → calls resume.
* **Phase 3 — codec + server API.** `mgcodecgate` gains `parse_*`/`emit_*`; editor
  `server.py` gets `/api/gates` (list), `/api/gate/set|add|remove`, and
  `/api/room/<id>/zone` for the antenna nibble. Surgical, idempotent saves like the
  other codecs.
* **Phase 4 — editor UI.** Room panel: an "🔒 Gate" chip on a gated item/door
  (which flag, which call unlocks it), editable — pick the flag, pick the unlocking
  TextId (reuse the radio-editor's text picker), toggle one-shot. A room-level
  "📡 Antenna required" toggle backed by the zone nibble. Cross-link: from a radio
  call that sets a flag, show "unlocks: Rocket Launcher (room 185)".

---

## 5. Risks / gotchas

* **Rocket abort-vs-skip.** The stock code `ret`s (drops the rest of the item list)
  rather than skipping one entry. Faithful only because the rocket is last in its
  set. The interpreter must either replicate the abort or guarantee ordering — cover
  this explicitly in the Phase 1 selftest.
* **One-shot doors clear their flag.** `JeniOpenDoorF` is consumed on first open, so
  the door re-locks if you leave and come back. Preserve `oneshot`; don't "fix" it.
* **`idxMapZones` is dual-purpose.** The nibble also selects **area music**
  ([Banks0123.asm:1613]). The editor's antenna toggle must edit the ≥5 threshold
  *without* silently changing which music zone a room belongs to — expose the raw
  zone value, not just a boolean, or warn on cross-threshold edits.
* **Positional table across renumbering.** Table C is indexed by room id. NIGHTJAR's
  multi-world renumbering (see [LIMITS-PLAN]) must carry/rebuild it per world, the
  same way path index/checkpoints were handled.
* **Text IDs are the real key.** Gates fire on *text id read*, so editing a call's
  text id (not just its words) in the radio editor can silently arm/disarm a gate.
  The UI cross-link in Phase 4 is what keeps that visible.

---

## 6. Status

**Phase 1 SHIPPED** — `tools/mgcodecgate.py`. Its `selftest` proves the three
table interpreters reproduce the inline ASM over **1664 cases** (every text id;
every item id × `JeniRocketF`; every room id × both door flags) and that the LIVE
`idxMapZones` table (126 bytes → 252 rooms, 91 needing the antenna) decodes with
the exact `GetNibbleRoom` order and round-trips byte-for-byte. Hand-counted zone
anchors (rooms 0/1→0, 16→1, 70→5) guard against a silent nibble-order flip. Run:
`python tools/mgcodecgate.py selftest` (also `dump`, `emit-zones`).

**Antenna zones (Table C) editable END-TO-END** — this table is already ROM data,
so it needs NO engine change and was done next (Phases 3+4 for Table C only):
* `mgcodecgate.py` — surgical single-nibble `set_zone` (minimal diff, idempotent),
  `zone_model`, proven in the selftest (setting a room changes only that room; a
  same-value write is a byte-exact no-op).
* `server.py` — `GET/POST /api/room/<id>/zone` (`room_zone`/`set_room_zone`).
* editor UI — a "📡 zone" dropdown in the room panel (zone value + name, live
  "antenna required" indicator). Verified over real HTTP + ROM rebuild.
The dropdown exposes the raw zone value (not a bare boolean) so the operator sees
that it also selects area music (the §5 dual-purpose caveat).

**Item spawn gate (Table B, items) — engine swap SHIPPED + emulator-verified.**
`addroomitems.asm` now calls a generic `ChkItemGate` (table walk over a
`GateItems` list of `item-id, dw flag`) instead of the hardcoded
`cp ROCKET_LAUNCHER / ld a,(JeniRocketF)`. CY-set = gated+locked → abort the item
list (byte-for-byte the stock rocket `ret z`). Verified with openMSX
(`tools/rockettest.tcl`) as an OLD-vs-NEW ROM A/B:
* warp to the rocket room 185 (spatial 83→E→86, then door 73), `JeniRocketF`=0 → no
  rocket; =1 → rocket at id4/y32/x64. **OLD == NEW for both.**
* `tools/wbtest.tcl` sweep (rooms 5/1/126 + the room-126 ration through the
  *ungated* path) → **OLD == NEW**, so normal item spawning is untouched.

**Text→flag (Table A) — engine swap SHIPPED + emulator-verified.** `TextBoxExit`
now `jp SetTextGateFlag` (table walk over `GateTexts`: db text-id, dw flag) instead
of the `cp 117/118/138` chain; the routine preserves BC/DE and clobbers only A/HL
(as the stock code did). Verified with openMSX (`tools/texttest.tcl`): a forced
call to `SetTextGateFlag` with A = 117/118/138 sets exactly `JeniRocketF` /
`JeniOpenDoorF` / `SchneiderCaptured` and a control id (100) sets none;
`DoorBuild2LockedF` is never touched. Call-site + text-box path neutrality proven
by `wbtest.tcl` A/B (pristine baseline vs the item+text ROM → **byte-identical**,
so the intro radio-call text still closes correctly), and the rocket A/B still
passes on the combined ROM. `mgcodecgate.parse_text_gates` asserts the live
`GateTexts` == the model.

**One-shot flag doors (Table B, doors) — engine swap SHIPPED + emulator-verified.**
The door-open dispatch keys on door LOGIC TYPE (the `JumpIndex` index), not room:
type 13 = the compass door (room 87, `JeniOpenDoorF`), type 14 = the Big Boss /
escape-ladder door (`OpenBigBossDoor`). These two routines were byte-identical
("flag set → open once + clear it, else locked"), so they collapse into one
`ChkGateDoor` interpreter over a `GateDoors` table (db type, dw flag; one-shot;
0FFh-terminated); the two stubs just load their type and `jp ChkGateDoor`. Register
footprint matches the originals (A/HL clobbered, HL left = render pointer; BC/DE
preserved). Verified with openMSX (`tools/doortest.tcl`): a forced call to
`ChkGateDoor` (after paging opendoor's segment 1 into 0x6000) with type 13/14 and
flag 0/1 → carry = locked/unlocked exactly, the one-shot flag is cleared on open,
and the two flags stay isolated. `wbtest.tcl` A/B (which enters door 101 → room
126) stays **byte-identical**, so normal door entry is untouched;
`mgcodecgate.parse_door_gates` asserts the live `GateDoors` == the model.

`ChkDesertDoorBuild2` (type 12, room-73 `DoorBuild2LockedF`) is **left hardcoded**:
it carries a room-73 directional special case ("open from inside by walking south")
and its flag is set by the desert guards, not a codec call — out of scope for a
one-shot flag door.

**Editor UI (Phase 3+4) — SHIPPED.** A "🔒 gates" toolbar modal edits all three
flag tables in one place: radio-call→flag (`GateTexts`), item→flag (`GateItems`),
door-type→flag (`GateDoors`), each with add/remove, a number field for the key, and
a flag dropdown (whitelisted to the known story flags so a write can never inject
arbitrary ASM). `mgcodecgate` gained surgical `set_text_gates` / `set_item_gates` /
`set_door_gates` (regenerate just the labelled block; keep the `ROCKET_LAUNCHER`
symbol; a same-value write is a no-op) proven by an in-memory emit→parse round-trip
in the selftest; server exposes `GET/POST /api/gates`. Antenna zones keep their
per-room 📡 control. Editing rewrites ASM, so the modal tells you to rebuild (🔧).

End-to-end verified: an edit made through the tool changes real game behaviour —
adding `text 90 → JeniRocketF` in the editor, rebuilding, then `texttest.tcl` shows
text 90 now arms `JeniRocketF` in openMSX (it does nothing on stock).

**The plan is complete:** all four gate families (antenna zones, item, text, door)
are data-driven, emulator-verified, and editable in the map editor.

## 7. General flag pool — any call → any object (prototype SHIPPED)

The named story flags (JeniRocketF, …) are a fixed set, so out of the box a gate
could only reuse an *existing* flag. To let **any radio call arm/open/spawn any
object**, there is now a general-purpose flag pool:

* `GateFlags` — a 9-byte array in `Variables.asm`, made by relabelling the
  verified-unused `UnusedVar17` (0 references; the "Not used" `REMOVE_FLAMES`
  looked free but actually has a live reference — avoid it). It sits **inside the
  saved `GameDataArea` block** (0xC600–0xC69F, saved/restored by the checkpoint
  system and zeroed by `ClearGameVars`), so pool flags **persist across save/load
  and reset on a new game with zero save-format change**. `GateFlags` = 0xC617.
* **No engine change.** The three interpreters already resolve their flag through
  a `dw` address, so a gate entry pointing at `GateFlags+0..8` just works. Only
  the tooling changed: `mgcodecgate` accepts `GateFlags+N` (whitelisted 0..8), the
  editor's flag dropdown lists "Flag 0–8 (general pool)".
* **Verified end-to-end in openMSX** (rocket/text tests generalised with a flag
  address): an item gated on `GateFlags+0` is hidden when the byte is 0 and spawns
  when it is 1; and reading text 90 (mapped to `GateFlags+0`) sets `GateFlags+0`
  while a control text sets nothing. Composed: a call reads a text → arms a pool
  flag → the gated object appears.

**Configurable display names.** Flag descriptions (Jennifer/Schneider…) and
antenna/music zone names (Building 1/2/3…) are **cosmetic only** — the ROM uses
flag addresses and zone nibble values, never the names — so they are editable
per-project overrides in `tools/editor/labels.json` (missing file = stock
defaults; blank = revert). The 🔒 gates modal has a "🏷 Rename flags & zones"
section, and an edited gate table is re-emitted with the flag's display name as a
comment (round-trip-safe). This matters for a new plot where those characters or
buildings may not exist. Managed by `mgcodecgate` (`flag_label`/`zone_name`/
`set_flag_label`/`set_zone_name`/`labels_model`), served via `GET/POST /api/labels`.

Prototype scope / next steps: 9 byte-flags (bump the array or bit-pack for 72+);
one-shot doors clear their flag, so give each door gate its own pool flag; and
"spawn" still means an item already placed in that room's set (item editor) that
the gate reveals — a "place-and-gate" convenience flow could combine the two.

## 8. Antenna requirement decoupled from the music zone (prototype SHIPPED)

Stock, "needs the antenna" was `idxMapZones nibble >= 5` — but that nibble also
selects area music, so you couldn't say "this room needs the antenna" without
also moving it to a Building-2 music group. Now the two are independent:

* `idxAntennaRooms` — a new nibble-per-room table in `data/musicradioconfig.asm`
  (read via `GetNibbleRoom`, same packing as `idxMapZones`), nonzero = needs the
  antenna. Initialised to `(zone >= 5)` so stock behaviour is identical.
* `SetRadioArea` computes a `RoomNeedsAntenna` RAM byte from it per room (9 bytes
  of code — the hand-rolled bit math overflowed the full Banks0123 segment, so it
  reuses `GetNibbleRoom`; `RoomNeedsAntenna` reuses the free `UnusedVar8`). The two
  antenna checks (`ChkRadioCalls3`, `ChkRadioReply`) test that byte instead of
  `MapZone >= 5` (a net-zero code swap). `idxMapZones` now drives **only** music.
* Editor: the room panel's zone control is now "🎵 zone" (music dropdown) plus a
  separate **"📡 needs antenna"** checkbox (`GET`/`POST /api/room/<id>/antenna`,
  `mgcodecgate.set_antenna_room` — surgical single-nibble edit).
* Verified in openMSX (`tools/antennatest.tcl`, forced call to `SetRadioArea`):
  `RoomNeedsAntenna == (MapZone>=5)` for every stock room; after flipping room 0
  (music zone 0) to need the antenna and room 73 (zone 5) to not, the runtime flag
  diverges from the zone while music is untouched; `wbtest` A/B baseline-vs-change
  is **byte-identical**.

Same pattern would decouple the antenna *threshold* elsewhere, or make other
zone-derived behaviours (area music groups, the Big-Boss `cp 4`) per-room.
