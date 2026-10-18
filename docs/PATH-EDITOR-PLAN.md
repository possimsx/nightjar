# Enemy movement-route (path) editor — plan

Goal: make enemy **patrol routes** editable in the map editor, the same way
radio calls / prisoner dialogue / actors already are — a byte-fidelity codec
(`tools/mgpath.py`) + server API + a waypoint-drag UI on the room canvas.

Everything below is reverse-engineered from `data/paths.asm`,
`Banks0123.asm` (`GetPathPoints`/`UpdateActorPath`), `logic/actors/guard.asm`
and `logic/actors/camera.asm`.

---

## 1. Data model (what lives in `data/paths.asm`)

Three layers, all in one file:

**a. Waypoint lists — `Path_<room>_<n>`**
A count byte + that many **(Y, X)** point pairs (Y first — same Y-low byte
order the actor/item codecs already use in `mgsprite`):
```asm
Path_000_02:  db 8          ; 8 waypoints
              db 50h, 38h   ; point 0: Y=50h, X=38h
              db 74h, 38h
              ...
```
The actor walks point→point and **loops** back to point 0 after the last
(`UpdateActorPath`, Banks0123.asm:7058). A repeated point ≈ a pause/turn beat.
Count = number of points (verified: `db 8` → 8 rows).

**b. Per-room path lists — `Paths_<room>`**
`dw` pointers to the individual paths used in that room:
```asm
Paths_000:  dw Path_000_01
            dw Path_000_02
            dw Path_000_03
```
Paths can be **shared** across rooms/actors (e.g. `Paths_080` reuses
`Path_053_01` three times; `Paths_082` borrows `Path_008_01`). The codec must
key blocks by label and write shared ones once — same discipline as
`mgmap` actor blocks and `mgradio` call blocks.

**c. Room index — `idxRoomPaths`**
One `dw` per room → that room's `Paths_<room>`. **179 entries** (rooms 0..178).
Totals today: 53 `Paths_*` blocks, 114 `Path_*` waypoint lists.

---

## 2. The binding rule (the critical gotcha)

An actor is **not** told which path to use — the engine derives it positionally
at spawn:

* `idxRoomPaths[Room]` → the room's `Paths_*` list.
* Index into that list = the actor's ordinal among **path-following actors**.
  For guards this is the running sum of `CountEnemyType` over
  `ID_GUARD_SLOW + ID_CAMERA + ID_SENTINEL + ID_GUARD_MEDIUM + ID_GUARD_FAST`
  as actors are loaded (`InitGuardPath`, Banks0123.asm:6854-6893). Cameras and
  sentinels use their own `IDX_SAME_ID` ordinal into the *same* list
  (camera.asm:65, Banks0123.asm:7194).

Consequences the editor MUST respect:

1. **Path #k belongs to the k-th path-follower in the room's actor list.**
   Reordering or inserting/deleting a guard in `actorsinrooms.asm` silently
   re-pairs paths. The existing actor editor can already do this — so this plan
   also adds a **cross-check** (§6) so an actor edit that breaks path alignment
   is flagged.
2. A room needs **at least as many paths as it has path-following actors**, or
   a late actor indexes past the end. The engine clamps to the last point via
   `SetLastPathPoint` (carry) but the pairing is then wrong.
3. Only `ID_GUARD_SLOW/MEDIUM/FAST`, `ID_CAMERA`, `ID_SENTINEL` (and the lorry/
   elevator guard variants that fall through to `ChkWaitPathPoint`) consume a
   path. Mines, prisoners, bosses, etc. do not. The codec keeps a
   `PATH_FOLLOWERS` id-set (sourced from `Enums.asm`) to know which actor rows
   count.

Sentinels are special: their "path" bytes are **look-directions**, not XY
(`GetSentinelLookDirs`). The codec parses them but the UI should render/edit
them as a direction list, not a walk route (Phase 2).

---

## 3. `tools/mgpath.py` — the codec

Mirror `mgradio.py`/`mgprisoner.py` conventions exactly: latin-1 I/O, mtime
cache, `selftest` with **byte-exact round-trip**, surgical managed-region edits.

Model shape:
```python
{
  "rooms": [ {"room": r, "label": "Paths_007",
              "paths": [ {"label": "Path_007_01", "shared": bool,
                          "points": [ {"y":..,"x":..}, ... ]}, ... ],
              "followers": [ {"idx":0,"id":"ID_GUARD_MEDIUM","y":..,"x":..}, ...] }
             for r in range(179) ],
  "labels": [...all Path_* labels...],
}
```
`followers` is joined from `mgmap.actors_by_room` (filtered to `PATH_FOLLOWERS`)
so the UI can show which actor each path drives and validate counts.

Functions:
* `parse_paths(src)` → `{Path_label: [(y,x),...]}` (count byte + pairs).
* `parse_room_lists(src)` → `{Paths_label: [Path_label,...]}`.
* `parse_idx(src)` → `[Paths_label per room]` (179).
* `model()` — join the three + actor followers.
* `set_room_paths(room, paths)` — the one write entry point:
  * New/edited waypoint lists go in a **managed region** (markers
    `; === EDITOR PATH BLOCKS (managed by tools/mgpath.py) ===`), label
    `PathEd_<room>_<n>`, so original/shared blocks are never mutated.
  * Rewrites that room's `Paths_<room>` block (or an editor `PathsEd_<room>`)
    and repoints `idxRoomPaths[room]` to it.
  * Idempotent: re-parses the managed region first, replaces only this room's
    entries (copy `mgradio._parse_edited_region` / `_write_region` / `_write_idx`).
* `selftest()` — assert `len(idx)==179`; every referenced label defined; each
  path is count byte + 2·count bytes; **re-emit == original bytes**; every
  `Paths_*` block length ≥ path-follower count of every room that points to it
  (warn, not fail — stock data may already rely on clamping).

CLI: `python tools/mgpath.py selftest | dump [room]`.

---

## 4. Server API (`tools/editor/server.py`)

Follow the radio/prisoner route pattern:
* `GET  /api/paths?room=<r>` → `mgpath.model()` slice for the room (paths +
  followers + a computed `warnings` list).
* `POST /api/paths/room` `{room, paths:[{points:[{y,x}...]}...]}` →
  `set_room_paths`, return the reloaded room.
* Overlay render: extend `actors_png` (server.py:205) or add
  `GET /api/room/<id>/paths.png?scale=2` — a transparent overlay drawing each
  path as a polyline through its (x,y) points with numbered nodes, colour-keyed
  per path index so it lines up with the actor badges `mgsprite` already draws.

Reuse `mgsprite` coordinate handling (y=low byte) so path nodes and actor
sprites share one pixel space.

---

## 5. Editor UI (`tools/editor/static/index.html`)

On the existing room canvas (already composites `render.png` + `actors.png`):
* A **"Paths"** settings toggle (peer of the sprite/footprint/badge toggles)
  overlays `paths.png`.
* A room **Paths panel**: list the room's paths, each tagged with the actor it
  drives (`#0 → ID_GUARD_MEDIUM @ (x,y)`), colour-matched to the overlay.
* Direct manipulation: click-drag a node to move it; click a segment to insert
  a node; right-click/Del to remove; "add path" / "remove path". Snap to the
  8px tile grid (points are byte coords). Save posts the whole room's path set.
* Live warnings banner from the model: *"3 path-followers but only 2 paths —
  actor #2 will reuse the last path"*, and a note when a path is `shared` so the
  user knows an edit forks a private copy (the codec does that automatically via
  the managed region).

Phase 2: sentinel look-direction editor (compass buttons, not a route);
snapping paths to walkable tiles using `mgrender.room_solid_grid` (reuse
`mgmove`'s solid grid) to warn when a waypoint sits inside a wall.

---

## 6. Actor↔path alignment guard

Because the actor editor can reorder path-followers, add to
`/api/validate` (and the actors panel) a check that, per room:
`#path-followers ≤ #paths` and flag when an actor insert/delete/reorder would
change which path a follower gets. Cheap: both lists come from
`mgmap`/`mgpath` models already loaded server-side.

**DONE (both halves).** *Actors panel:* the per-room "enemy routes" panel warns
while you edit that room (`nf > rts`). *Global sweep:* `server.path_alignment()`
scans every room via `mgpath.model()` and returns the misaligned ones; it feeds
`get_validation(..., include_paths=True)` → the `path_align` field of
`/api/validate` and the **build / checks** dashboard, which shows an "enemy route
coverage" row (`r5(3▸1) …`). `include_paths` is off on the per-save validation
call so map/connection saves don't re-parse `paths.asm`. Verified live: stock
data reports `path_align: []` (all aligned); a synthetic 3-followers/1-route room
is flagged.

---

## 7. Build / regen

No new build step — `data/paths.asm` is already assembled. `set_room_paths`
edits are surgical text edits like every other codec, so `tools/build.py`
picks them up with no `--regen`. Add `mgpath.selftest` to whatever runs the
other codec selftests.

---

## 8. Phasing

1. **`mgpath.py` codec + selftest** (byte-exact round-trip). Standalone, no UI.
   **DONE** — `tools/mgpath.py`, `selftest` green: 179 rooms, 114 routes
   (104 walk / 10 dir), 53 path-lists, round-trip byte-exact. Verified against
   the engine: walk routes ↔ guards (room 1), DIR routes ↔ sentinels (room 11
   — 4 sentinels pair with 4 facing-lists). Two facts corrected while building:
   **dogs do NOT follow routes** (they chase via `GetDirToPlayer`, dog.asm), and
   the lone data quirk `Path_031_02` carries 3 stray trailing bytes after its
   route — the codec preserves them as an opaque `tail` so bytes round-trip.
2. **Read-only overlay**: `/api/paths` + `paths.png` + the "Paths" toggle —
   just *see* every route. High value, low risk.
   **DONE** — server `paths_png` (walk routes = numbered colour-keyed closed
   polylines; sentinel dir routes = facing-arrow stars at the paired actor) +
   `GET /api/room/<id>/paths.png` and `/paths` (JSON) + a "Paths" Settings
   toggle compositing `.pathspr` over the room render. Verified visually on
   room 1 (3 guard routes on the floor) and room 11 (4 sentinel facings match
   the `[2,0,3]`/`[2,1]` data).
3. **Editing**: `set_room_paths` + drag UI + alignment guard.
   **DONE** — `mgpath.set_room_paths(room, routes|None)` forks a room's routes
   into a managed region (`PathEd_<room>_<n>` blocks + `PathsEd_<room>` list,
   markers `; === EDITOR PATH BLOCKS ===`) and repoints `idxRoomPaths[room]`,
   fully isolating rooms that share a `Paths_*`/`Path_*` (verified: editing room
   1 leaves room 0's shared `Paths_000` untouched); `None` reverts via the
   `; orig=` note. Parsers now scan the whole file and recognise the managed
   labels; selftest stays byte-exact. Server `POST /api/room/<id>/paths`
   (`{routes}` or `{revert:true}`). Editor "enemy routes" panel: per-route
   follower pairing + node counts, the **alignment guard** (§6: warns when
   #path-followers > #routes), and an **edit mode** drawing an SVG overlay of
   draggable waypoint nodes (drag = move, snap 8px; dbl-click = delete;
   `+node`/`✕ route`/`+ route`) with save/revert. Verified: codec write/revert +
   round-trip + build; API over HTTP; panel + drag rendered headless.
4. **Sentinels & wall-snapping** (niceties).
   **DONE** — dir-route (sentinel) editing: the panel shows a facing editor
   (↑↓←→ selects + add/remove) for each dir route; edits post as
   `{shape:"dir",dirs:[…]}`. Wall check: `room_paths` now returns the 24×32
   solid grid; waypoints landing on a solid tile are ringed red in the SVG and
   counted in a panel warning. Also: waypoint drag snaps to **4px** (half-tile —
   stock coords use it, e.g. `0x74`=116), and the read-only `.pathspr` PNG
   overlay is **suppressed while editing** so only the live SVG shows.

Biggest risk was §2 (positional binding), not the file format — the alignment
guard (§6) landed alongside editing as planned.
