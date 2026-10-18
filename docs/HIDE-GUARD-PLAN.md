# Hide-guard: make entry-dependent guard culling editable — plan

Goal: replace the 9 hardcoded per-room "remove a guard depending on where the
player entered" routines with **one data table + one generic interpreter**, then
edit that table via a codec + editor UI (like the reconfigurable-hazards rework).

Chosen approach: **data table + interpreter** (faithful; fully editable; can add
rules to new rooms). Not proximity-auto-cull, not edit-in-place.

---

## 1. What the mechanism does today

When a room's guards spawn, `InitGuardPath2` ([Banks0123.asm:6899-6922]) calls a
per-room `HideGuardRoomN` routine ([logic/actors/hideguards.asm]) for **each**
guard actor. The routine removes **one** guard — the one sitting where the
player materialises — so you never enter a room standing on an enemy. Removal =
set `REMOVE_GUARD` (the actor is dismissed on its first logic tick,
[guard.asm:30-32]); it runs *after* path indices are assigned, so **culling
never shifts path/actor pairing**.

Inputs available to a rule (per actor):
* `D` = `NextRoomDirect` — entry direction: **1=Up(from S), 2=Down(from N),
  3=Left(from E), 4=Right(from W)**.
* `E` = `PreviousRoom` — the room you came from.
* the actor's own spawn `X` / `Y`, compared against a constant.

Every routine reduces to: *evaluate conditions → pick one target `(axis, op,
coord)` → cull the actor iff `actor.axis <op> coord`.* `op` is usually `==`
(remove the guard AT that coord) but rooms 17/18 use `!=` (remove the guard NOT
at that coord — i.e. the other one).

---

## 2. Complete rule extraction (VERIFY THIS)

Each row: the condition, and the `(axis op coord)` it selects. Rules are
evaluated top-to-bottom per room; **first matching condition wins**; if none
matches there is **no cull**. `coord` resolves to a specific guard (its spawn
X/Y); the "guard" column is that mapping for the stock actor lists.

| Room | # | Condition            | Cull target        | Guard (stock)            |
|------|---|----------------------|--------------------|--------------------------|
| 1    | 0 | `D == 1` (from S)    | `Y == B0h`         | actor @ Y=176 (south)    |
| 1    | 1 | else                 | `Y == 18h`         | actor @ Y=24 (north)     |
| 13   | 0 | `E == 137`           | `X == 88h`         | guard by SMG-room door   |
| 15   | 0 | `D == 4` (from W)    | `X == 10h`         | guard on left edge       |
| 17   | 0 | `D == 1` (from S)    | `Y != 30h`         | the non-north guard      |
| 17   | 1 | else                 | `Y == 30h`         | north guard              |
| 18   | 0 | `D == 1` (from S)    | `Y != 13h`         | the non-top guard        |
| 18   | 1 | else                 | `Y == 13h`         | top guard                |
| 19   | 0 | `E == 141`           | `Y == 78h`         | guard by cylinders door  |
| 19   | 1 | `D == 1` (from S)    | `Y == A8h`         | south guard              |
| 22   | 0 | `E == 20`            | `X == 20h`         | guard by MG-Kid door     |
| 22   | 1 | else                 | `X == F0h`         | right guard              |
| 35   | 0 | `E == 156`           | `Y == 28h`         | guard by box-item door   |
| 35   | 1 | `E == 33`            | `X == 18h`         | guard by other door      |
| 39   | 0 | `E == 242` (elev.)   | `Y == 72` (48h)    | north guard              |
| 39   | 1 | else                 | `Y == 176` (B0h)   | south guard              |

Notes: rooms 13/15/19/35 have **no else** → some entries cull nobody. Room 35's
two branches use **different axes** (Y then X). Rooms 1/17/18/22/39 always cull
exactly one guard (which one depends on entry). Room 39 is dispatched from its
own room-39 init, not `InitGuardPath2`, but the rule shape is identical.

---

## 3. Data-table format

One flat, scanned table (only 9 rooms, so no per-room index needed):

```asm
HideGuardRules:
;         room, nEntries
;           cond, val, flags, coord      (flags: b0 axis 0=Y/1=X, b1 op 0=EQ/1=NEQ)
    db  1, 2
      db  COND_DIR,  1, 0,      0B0h
      db  COND_ELSE, 0, 0,      018h
    db 13, 1
      db  COND_PREV, 137, AXIS_X, 088h
    db 17, 2
      db  COND_DIR,  1, OP_NEQ, 030h
      db  COND_ELSE, 0, 0,      030h
    ...
    db 0FFh                              ; end of table
```

Enums (add to `constants/Enums.asm`): `COND_DIR=0, COND_PREV=1, COND_ELSE=2`;
`AXIS_X=1, OP_NEQ=2` (OR-combined into the flags byte). 4 bytes/entry.

---

## 4. Generic interpreter (replaces the 9 routines)

`ApplyHideGuardRules` (new, in `hideguards.asm`), called once per guard actor
where `InitGuardPath2` currently calls `HideGuardRoomN`:

```
  scan HideGuardRules for a row whose room == (Room); else return.
  for each of its nEntries (in order):
      COND_DIR : match if val == NextRoomDirect
      COND_PREV: match if val == PreviousRoom
      COND_ELSE: always match
      on first match: hold (flags, coord); break
  if no entry matched: return (no cull).
  load actor.X or actor.Y per AXIS bit.
  EQ : cull if coord == that ; NEQ: cull if coord != that.
  cull => jp HideGuardSpr (reuse the existing removal tail).
```

`InitGuardPath2` loses its 8 `call z,HideGuardRoomN` lines and instead does a
single `call ApplyHideGuardRules` (which internally no-ops for rooms not in the
table). The room-39 caller is likewise redirected. The old `HideGuardRoomN`
label bodies are deleted; `HideGuardSpr`/`HideSprColor` tail is kept.

---

## 5. Codec `tools/mghideguard.py` + validation

Conventions as the other codecs (latin-1, mtime cache, surgical edits):
* `parse()` → `{room: [ {cond, val, axis, op, coord}, ... ]}` from `HideGuardRules`.
* `model()` — join each rule's `coord` to the room's actor list (via `mgmap`) so
  the UI shows *which guard* (and flags NEQ as "all but the guard at …").
* `set_room_rules(room, rules)` — surgical rewrite of that room's block.
* `selftest()` — byte-exact round-trip, **plus behavioural equivalence**: a
  Python transcription of the original 9 routines (`_orig_cull(room,D,E,x,y)`)
  vs the table interpreter (`_table_cull(...)`), asserted equal over every
  `room × D∈1..4 × E∈0..255 × actual-guard-coords`. This proves the rewrite
  changes no behaviour **without needing an emulator** — the safety gate before
  the ASM lands.

---

## 6. Editor UI

In the room's actor/paths panel (guards already listed there):
* **"Entry culls"** section listing the room's rules, each as
  `[when: from South ▾] remove [guard #0 ▾]` with add/remove. The guard dropdown
  is the room's path-followers; condition is Dir (N/S/E/W) or "came from room N"
  or "else". NEQ rules render as `remove all but [guard #k]`.
* Read-only cross-hint on the paths/sprite overlay: dim any guard that would be
  culled for the currently-previewed entry direction, with a toggle to preview
  each entry direction — so you *see* who disappears when entering from where.
* Ties into the actor editor: since culling is coord-keyed, moving/deleting a
  guard should warn if a rule's `coord` no longer matches any actor (stale rule).

---

## 7. Risks & phasing

The one real risk is behavioural drift in the ASM rewrite → mitigated by the
§5 equivalence selftest, which must pass before the engine change is committed.

1. **Codec + equivalence selftest first** (no ASM change): transcribe the 9
   routines and the table interpreter in Python, prove equal, and emit the
   `HideGuardRules` table text. This validates the extraction in §2.
   **DONE** — `tools/mghideguard.py`; `selftest` proves the table interpreter
   (through the real 4-byte encoding) equals a literal transcription of the 9
   routines over **all 2,073,600** `(room, dir 1-4, prev 0-255, X, Y)` cases.
   `emit` prints the ASM table; `dump` joins rules to actors. Two findings:
   (a) the packed **flags byte** needs NEQ in bit 1 (caught because the tuple
   model bypassed encoding — the proof now runs through the bytes that ship);
   (b) coord tests are **not** 1-per-actor — a rule can cull several guards
   (room 18 `Y!=13h` → 3 of 5), faithful to the engine. → §6 UI must be
   coord-based (show coord + the resolved actor set), not a single-guard pick.
2. **Engine swap**: add the table + `ApplyHideGuardRules`, delete the 9
   routines, redirect the callers. Rebuild; spot-check room 1 from N and S.
   **DONE** — `COND_*` enums in Enums.asm; `HideGuardRules` + generic
   `ApplyHideGuardRules` (reads Room/dir/prev from memory; preserves B/DE/IX;
   culls via the kept `HideGuardSpr` tail) replace the 9 routines in
   hideguards.asm; `InitGuardPath2`'s 8 calls collapse to one, and
   sentinel.asm's room-39 call is redirected. Assembles clean (128KB). The
   83-byte table is byte-exact in the ROM at 0x6158 (matches `mghideguard emit`).
   Verified live in openMSX: booted, warped into room 1 from the south →
   2 of 3 guards present, the south guard (Y=B0h) culled, no guard on the entry
   edge, no crash — the interpreter runs correctly in the real spawn pipeline.
3. **Editor UI**: rules panel + entry-preview dimming + stale-rule warning.
   **DONE** — codec read/write side (`parse_table`/`room_model`/`set_room_rules`/
   `cull_preview`, round-trip added to selftest); server `GET/POST
   /api/room/<id>/hideguards`; and a "guard culling · on entry" panel in the room
   objects tab: per-rule condition (from N/S/E/W · from room N · else) + axis/op/
   coord with a `= guard…` helper that fills the coord from an actor, live target
   resolution, a red **stale-rule** warning when a coord matches no guard, an
   entry **preview** ("entering from South → removes #0"), and add/remove/save.
   Saving rewrites only the table region (idempotent); rebuild to apply.
   Verified: codec write round-trips + rebuilds; API over HTTP; panel rendered
   headless (extracted JS) showing live targets, stale warning, and preview.
