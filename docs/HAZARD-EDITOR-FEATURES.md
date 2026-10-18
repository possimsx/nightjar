# Map editor: missing hazard-room features

> **UPDATE — F1–F4 + F6 SHIPPED via the unified `RoomFlags` byte** (see
> [HAZARD-FLAGS-PLAN.md](HAZARD-FLAGS-PLAN.md)). Dark/gas/electric/water/**laser-beam** are
> now per-room flag bits with ☾☣⚡💧▦ checkboxes in the editor; electric/water have
> per-tileset tile tables; no per-hazard room limit. Laser = bit 6 (stock rooms 24/25/72,
> `ID_LASER`), replacing the `cp 24/25/72` gate in `DrawLaserBeams`; the ▦ toggle sits
> just before the 🔒 capture toggle. Remaining: laser-beam *actor* overlays and F5
> (actor-hazard overlays — polish). Room 111's camera-laser short-length special stays
> hardcoded (different mechanic).

What the editor still needs so **room-level hazards** can be authored, not just viewed.
Companion to [SPECIAL-ROOMS.md](SPECIAL-ROOMS.md) (the full hardcoded-room inventory) and
[HAZARD-FLAGS-PLAN.md](HAZARD-FLAGS-PLAN.md) (the unified `RoomFlags` proposal).

## Two kinds of hazard

1. **Actor hazards** — placed as `ID_*` actors in a room: pitfalls/trap-holes
   (`ID_PITFALL`), mines (`ID_MINES`), rolling barrels (`ID_ROLLING_BARREL`), lasers
   (`ID_LASER`/`ID_CAMERA_LASER`), cameras (`ID_CAMERA`), shooters (`ID_SHOOTER`), gas
   cloud (`ID_GAS`). **These are already fully editable** via the editor's actor panel
   (add/remove/move, shared-block fork). Only *visual affordances* are missing (see F5).
2. **Room-ID hazards** — behaviour keyed on the room *number* in engine code, with no
   per-room data the editor can edit. **This is the real gap.** Current state:

| Hazard | Mechanism | Data-driven? | Editor today |
|---|---|---|---|
| **Dark** (needs flashlight) | `DarkRooms` 0FFh-list (Banks456.asm:111), read by `SetRoomPal` | ✅ list (shipped) | badge only — no edit |
| **Gas** (needs gas mask) | `GasRooms` list + fixed count `ld b,9` (logic/damagegas.asm:11,53) | ✅ list, fixed length | badge only — no edit |
| **Electric floor** | `ChkElectricFloor` hardcoded `cp 16/37/40/110/116`, each with its own tile pair (logic/damageelectric.asm) | ❌ hardcoded + tile-coupled | badge only |
| **Water** (room 70) | hardcoded in guardalert.asm | ❌ hardcoded | not flagged |
| **Laser beams** (rooms 47/72/111) | room-id in drawlaserbeams.asm / damagelaser.asm | ❌ hardcoded | badge only |

Badges come from the hand-kept `_SPECIAL` table in `server.py` (mirrors SPECIAL-ROOMS.md),
not from the actual hazard data — so today they can drift and can't be edited.

---

## Features to implement (priority order)

### F1 — Dark-room toggle  ✅ DONE
"☾ dark" checkbox in the room info panel adds/removes the room from `DarkRooms`.
- `GET /api/room/<id>/hazards`, `POST /api/room/<id>/hazard {kind,on}`; list edit via
  `_read_hazard_list`/`_write_hazard_list` (rewrites the labelled `db` line, sorted,
  `0FFh`-terminated, via `_save_lines`). Badge now read LIVE from the list.

### F2 — Gas-room toggle  ✅ DONE
Same UI ("☣ gas" checkbox). Engine: `ChkGasRooms` made `0FFh`-terminated (dropped the
fixed `ld b,9`), `GasRooms` seeded with the current 9 rooms + `0FFh` (behaviour-neutral,
build-verified 0 errors / 128 KB). Shares F1's endpoint/codec (`HAZARD_LISTS`).

### F3 — Electric-floor editor
`ChkElectricFloor` hardcodes 5 rooms **and the electrified tile-id pair per room** (e.g.
6061h, 4546h, 4041h), so it can't collapse to a boolean.
- **Engine:** replace the `cp` chain with a small `(room, tileLo, tileHi)` table the
  routine scans (terminator-ended). Behaviour-neutral seed = the current 5 rooms.
- **Editor:** "⚡ electric floor" toggle **+ a tile-pair picker** (which floor tiles are
  live) — reuse the tile-atlas picker from the tile editor.
- **Codec:** read/write the new table.
- **Effort:** medium (table design + 2-field UI).

### F4 — Water & laser-beam rooms
Both are single-purpose room-id checks (water 70; laser beams 47/72/111).
- **Engine:** convert each to a 0FFh-terminated list (like gas), seeded behaviour-neutral.
- **Editor:** "💧 water" / "▦ laser beams" toggles (laser beams may also want the beam
  count/spacing if those are room-coupled — confirm in laserbeams.asm first).
- **Effort:** medium; water is trivial, laser beams need a check of what else is room-keyed.

### F5 — Actor-hazard visual affordances (polish, no engine work)
Actor hazards are already editable; add overlays so placement is legible (the pitfall
hole overlay already exists — `.pitfallhole`):
- **Laser** actors: draw the beam line/extent on the room render.
- **Rolling barrels**: mark the left/right limit rooms (56/200) and roll direction.
- **Mines**: small trigger-radius ring; **cameras**: field-of-view cone.
- **Effort:** low each, incremental; pure front-end (like the pitfall overlay).

### F6 — Unified `RoomFlags` byte (supersedes F1–F4 if taken)
Instead of N parallel lists, one per-room flag byte (DARK/GAS/… bits) — see
[HAZARD-FLAGS-PLAN.md](HAZARD-FLAGS-PLAN.md). Cleaner long-term and a single "Hazards"
checkbox group in the editor, but a bigger engine change (RAM cache, banking). Decision:
ship F1–F2 as lists now; reconsider F6 before doing F3/F4 so we don't build the table
twice.

---

## Suggested order
1. ~~**F1 (dark)**~~ ✅ done.
2. ~~**F2 (gas)**~~ ✅ done — two working hazard toggles, badges live from data.
3. **Decide F6 vs continue lists** — if going unified, do `RoomFlags` before F3/F4.
4. **F3 (electric)**, **F4 (water/laser)** — the tile/room-coupled ones.
5. **F5** overlays — polish alongside any of the above.

## Cross-cutting
- Each engine change must stay **byte-size-neutral or fit the bank pad** and be
  **build-verified** (the `DarkRooms` swap is the template: same-size `cp`→list scan, no
  segment shift). Seed every new list/table to the current hardcoded rooms so the change
  is behaviour-neutral until edited.
- Once a hazard is data-driven, drive its **editor badge from the data**, not from
  `_SPECIAL`, and drop that entry from the hand-kept table.
- Test each with the in-editor **warp** (⤓) — e.g. warp into a new gas room to confirm
  damage, a new dark room to confirm the flashlight gate.
