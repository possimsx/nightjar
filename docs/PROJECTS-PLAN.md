# Multi-project support — plan

> **STATUS (2026-07-10): ALL PHASES SHIPPED.** `tools/mgproj.py` (resolver +
> registry), every codec/tool refactored to `mgproj.path()`, editor project
> switcher + New-project modal + base write-guard (403), and
> `tools/mgnewgame.py` (blank template). Verified: selftests + stock build
> byte-identical on base; blank project assembles 128KB/0 errors and
> emulator-boots to room 121 (Konami intro → title → play, screenshot-checked);
> duplicate-project edits leave the base untouched (git-clean). Notes below on
> what shifted from the original plan are marked ⟲.
>
> Post-ship refinements (user feedback): the blank template now clears EVERY
> room except 121 — including 204 and the ladder/elevator bands, whose engine
> behaviours stay in code and are inert until routed to (re-verified: build
> green + emulator boot to 121). Editor: room-render `<img>` URLs carry a
> per-load `GEN` cache-bust token (map thumbs went stale on project switch —
> the browser's memory cache ignores no-store), and manual map positions are
> stored per project (`mapPos:<slug>`, legacy `mapPos` read as base's).

Source: `docs/Missing or funny things.txt`. Today the editor and codecs write straight
into the repo's ASM source, so there is exactly one map, and editing it erodes the
original Metal Gear base. Goal:

1. **Projects** — several independent games, each with its own map + source, switchable
   from the editor.
2. **Protected base** — the original Metal Gear source stays pristine and read-only.
3. **New project (blank)** — a generated template with map/actors cleared, engine +
   artwork + intro kept, room 121 (start/insertion, `logic/checkpoints.asm:134`) intact,
   so a brand-new plot can be built from an empty fortress.

## Re-check delta (2026-07-10, before build)

Changes landed since the plan was written (`c28a055`) that affect it:

* **Worlds layer** (LIMITS D1–D4): `mgmap` now has `_WORLD`/`set_world()`/`world_file()`
  (`mgmap.py:91-205`) redirecting per-world files to `data/worldN/` and stripping `_wN`
  suffixes. Orthogonal to projects and composes for free: `world_file()` returns a
  *relative* path that is then joined with ROOT — pointing the join at the project dir
  gives per-project worlds. On project switch, reset `_WORLD = 0` (world counts differ
  per project via each project's `features.asm`; WORLDBANK is currently off in base).
* **New modules to refactor**: `mgcodecgate.py` (own `_read/_write` + `LABELS_F =
  tools/editor/labels.json` — an existing per-project cosmetic store at a fixed path;
  move to per-project state), `mgworld.py` (own `_read/_write`, genworld), `mgrespawn.py`
  (uses mgmap IO), `mgtext.py` (`DATA = tools/../data` constant), `genextgfx.py`.
* **git-based features**: server "restore stock" + palette-reset endpoints and
  `mgrender.py:363` run `git show HEAD:<path>` with `cwd=ROOT` — need `cwd=repo_root()`
  plus a `git_prefix()` for files inside `projects/<slug>/`.
* **`tools/map.json` semantics**: bcaa2d0 made opening the editor no longer rewrite it;
  ~12 mutating endpoints still export it. Becomes per-project state.
* **One-off authoring scripts** (`build_nightjar_text.py`, `recolor_kestrel.py`,
  `cool_palettes.py`, `script_act*.py`) stay repo-anchored — out of scope.
* Root source verified still stock Metal Gear (no NIGHTJAR content in
  data/gfx/logic/constants; WORLDBANK reverted to 0 by f8558e8), so
  "repo root = protected base" stands.
* Per-project editor state consolidates in `<project>/.editor/` (map.json, labels.json,
  reach cache); the base keeps its legacy paths (`tools/map.json`,
  `tools/editor/labels.json`, `tools/editor/.reach_cache.json`) via `mgproj.state_file()`.

## Current state (from exploration)

* Every tool computes its own `ROOT` from `__file__` and joins hardcoded repo-relative
  strings — ~13 modules (`mgmap.py:30-39`, `build.py:30-33`, `editor/server.py:34-36`,
  `mgsprite.py:32-41`, `mgrender.py` inline literals, `mgradio.py`, `mgprisoner.py`,
  `mgpath.py`, `mghideguard.py`, `mgpal.py`, `mggfx.py`, `mgtext.py`, `cool_palettes.py`).
  Only `mgrender` reuses `mgmap.ROOT`. `mgmove` is path-free. No config mechanism exists
  (only `MG_SJASM` / `MG_OPENMSX` / `MG_EMUDIR` env vars).
* Read/write funnels: `mgmap._read/_write` (`mgmap.py:84-89`), `server._save_lines`
  (`server.py:51-57`) — both `os.path.join(ROOT, rel)`.
* Caches to invalidate on switch: `mgmap._MODEL_CACHE` (mtime-keyed, `mgmap.py:447-470`),
  `server._REACH_CACHE` + `tools/editor/.reach_cache.json`, `mgsprite` lru_caches (has a
  clear helper), `mgrender` lru_caches.
* Buildable source set = root `*.asm` (MetalGear/Banks*/Variables/features) +
  `constants/ data/ gfx/ logic/ sound/ hooks/` ≈ 230 files / ~2 MB. `room_images/`
  (~3 MB PNGs) is reference-only for mgrender — shared, never copied.
* `build.py` runs sjasm with `cwd=ROOT` and relative `SRC`/`ROM`, so it retargets for
  free once ROOT is project-aware; the `.rom` lands inside the project dir.
* Editor also persists `tools/map.json` (`mgmap.export_json`, ~10 call sites in server)
  — must become per-project.

## Design decisions

* **Repo root = the protected "Metal Gear (base)" project.** It is already git-guarded;
  the editor additionally refuses all mutating endpoints while base is active (HTTP 403
  with "duplicate to edit" hint). No second copy of the base is kept.
* **Projects live in `projects/<slug>/`**, each a full buildable copy of the source set
  plus `project.json` (`{name, description, created, template, protected:false}`).
  Projects are **git-tracked** (they are the user's game source); build artifacts inside
  them (`*.rom`, `*.lst`, `*.sym`, `.cache/`) are gitignored.
* **Active project** is a runtime property: `projects/active.json` (gitignored) for the
  editor, `MG_PROJECT=<slug|path>` env var / `--project` arg for CLI tools. Default =
  repo root (base), so all existing workflows keep working unchanged.
* **Blank template keeps room 121 byte-for-byte** (grid, tileset, palette) and keeps all
  engine code including intro/title (`logic/mainmenu.asm`) and hardcoded special-room
  behaviours (parachute 204, elevators 240–250, ladders ≥224, bosses — see
  `docs/SPECIAL-ROOMS.md`). Those are inert until a map routes into them; the generator
  documents this in the project's README.

## Phase 1 — central path resolver (`tools/mgproj.py`)

No behaviour change; pure refactor.

* New module: `repo_root()` (asset/tool anchor, never changes), `root()` (active project
  dir, defaults to repo root, honours `MG_PROJECT`), `set_root(path)`, `path(rel)`,
  and `on_switch(callback)` cache-invalidation registry.
* Replace every `os.path.join(ROOT, …)` / module `ROOT` use with `mgproj.path(rel)` /
  `mgproj.root()` **at call time** (module-level constants can't follow runtime
  switches). Keep repo-anchored things on `repo_root()`: `room_images/`, `tools/editor`
  static files, sjasm path.
* Register cache clears: `mgmap` model cache, `mgsprite.clear_caches()`, `mgrender`
  lru_caches, server reach cache. (mgmap's mtime keying alone is not reliable across a
  whole-directory swap.)
* `mgrender.py:359` (`git show HEAD:data/rooms.asm` diff feature): prefix the git path
  with the project's repo-relative dir when a project is active.
* Move per-project state into the project: `map.json` export → `<project>/map.json`
  (base keeps `tools/map.json`), reach cache → `<project>/.cache/reach_cache.json`.

**Gate:** `mgmap selftest`, `mgsprite` selftest, full editor smoke on the base project,
`python tools/build.py` — all byte/behaviour-identical to today.

## Phase 2 — project registry, server API, editor UI

* `tools/mgproj.py` grows registry helpers: `list_projects()` (base + scan
  `projects/*/project.json`), `create_project(name, template, source)` (copy the source
  set with `shutil`, write `project.json`), `activate(slug)`.
* Server endpoints: `GET /api/projects`, `POST /api/projects` (`{name, template:
  "duplicate"|"blank", source?}`), `POST /api/project/activate`, `DELETE
  /api/projects/<slug>` (with confirm). Activation calls `mgproj.set_root` → all caches
  drop; response tells the UI to reload.
* Protection: one guard in the POST dispatcher — if active project is protected, every
  mutating endpoint returns 403; UI shows a read-only banner with a "Duplicate…" button.
* UI (`tools/editor/index.html`): header dropdown with current project, entries for each
  project, "New project…" modal — name + template radio (**Copy of Metal Gear** /
  **Blank — new plot**). Build/run buttons already follow the active root via Phase 1.
* `.gitignore`: `projects/active.json`, `projects/*/*.rom|*.lst|*.sym`, `projects/*/.cache/`.

**Gate:** duplicate base → edit rooms/actors in the copy → base files untouched (git
status clean); build both projects to separate ROMs; restart server resumes active
project; base refuses edits.

⟲ Shipped deltas vs the text below: `mgtext`/`mgrespawn`/`mgpal` expose
call-time path helpers (`_texts()`, `_data()`, `_respawn()`, `_pal()`) instead
of constants — `mgradio` follows via `mgtext._texts()`; the editor's selftest
subprocess passes `MG_PROJECT=<active root>`; `restore stock`/palette-reset and
`mgrender` git baselines read the BASE history (`cwd=repo_root()`), writing to
the active project; radio/path/hideguard/respawn/gate/gateway clearing uses
each codec's own setter (`set_room_call`, `set_room_paths`, `set_table`,
`set_entry`, `set_*_gates`, `set_antenna_room`, `write_gateways`).

## Phase 3 — blank-project generator (`tools/mgnewgame.py`)

Applies the "cleared" transform to a fresh copy **through the existing codecs** (never
raw text surgery), then `mgmap` regen so all indexes stay consistent:

1. Copy base → `projects/<slug>/`.
2. **Rooms 0–120** (all open-grid except 121): metatile grid → plain empty floor with
   border walls (Building tileset tiles); tileset id → Building; connections → sealed
   (self-loop = wall, the engine's `208.W=208` idiom). Room **121 untouched**, but its
   connections also sealed so the start screen is self-contained until the user wires it.
3. **Doors**: every slot emptied. **Items** (door rooms 122–217): all emptied.
   **Actors**: zero in every room (regen rebuilds `idxActorsRooms`). **Paths**:
   `idxRoomPaths` emptied via mgpath codec.
4. **Checkpoints**: reduce `logic/checkpoints.asm` to the single start entry
   (`SaveStatRooms: 121,121 / 121,0`).
5. **Radio**: clear per-room triggers (`idxRoomRadio`) via mgradio, keep frequency table
   and text tables intact. **Prisoner texts**: leave defaults (no prisoners are placed).
   **Hide-guards**: empty room list (no actors exist to cull anyway).
6. Keep untouched: all engine/logic code, intro/menu, texts.asm, gfx (tilesets, sprites,
   items, player), palettes, sound.
7. Generator writes `projects/<slug>/README.md` noting the locked room-number bands
   (items 122–217, ladders ≥224, elevators 240–250, parachute 204) from
   `docs/SPECIAL-ROOMS.md`.

Validator note: `/api/validate` route-coverage and `mgmap graph` reachability will
trivially pass or report "everything sealed" on a blank map — verify they degrade
gracefully (no crash on empty tables) rather than assuming Metal Gear counts.

**Gate:** generated project → sjasm 0 errors; `mgmap selftest` + `graph` clean on it;
openMSX boot → Konami intro → title → new game → player lands in room 121, empty
neighbouring rooms render as sealed floors; editor opens it and can add a room, door,
actor, path.

## Phase 4 — polish

* `--project` on the CLIs people actually run standalone (`mgmap.py`, `build.py`,
  `mgradio.py`, `mgpath.py`); the rest inherit via `MG_PROJECT`.
* Docs: update `docs/MAP-EDITOR-PLAN.md` cross-refs; short section in README.
* Migration note: current NIGHTJAR work continues by creating `projects/nightjar` as a
  duplicate of base and applying `docs/NEWGAME-MAP.md` there; repo root stops being
  edited directly.

## Verification (end-to-end)

1. Phase 1 regression: selftests + byte-identical round-trips on base.
2. Create "test-dup" (duplicate) and "test-blank" (blank); build both; confirm base
   `git status` stays clean throughout.
3. Emulator: base ROM plays as before; blank ROM boots to intro and room 121.
4. Editor: switch between all three projects repeatedly — renders, sprites, paths, and
   validate all reflect the active project (cache invalidation proof).
