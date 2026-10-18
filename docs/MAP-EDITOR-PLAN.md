# NIGHTJAR Map Editor — Implementation Plan

A local web-app map editor for the NIGHTJAR rework. The Python toolchain we
already built (`mgmap` codec, `mgrender` graphics, `mgmove` movement model,
`mggfx`) becomes the **backend engine**; a browser front-end (HTML5 canvas)
provides the global map, per-room editor, tileset assignment, and palette
editing.

Goal: design the entire world visually, validate it the same way the engine
will interpret it, and write it back to the `data/*.asm` sources byte-safely —
no hand-editing of hex.

---

## 1. Architecture

```
  Browser (HTML5 canvas + JS)              Python (FastAPI)
  ┌───────────────────────────┐  HTTP/WS  ┌────────────────────────────┐
  │ Global map grid + linking  │◀────────▶│ /api  (thin controllers)    │
  │ Per-room tile painter      │   JSON   │   wraps existing modules:    │
  │ Tileset / metatile picker  │          │   • mgmap   (load/save .asm) │
  │ Palette editor             │          │   • mgrender(PNG tiles/rooms)│
  │ Door/item/actor overlays   │          │   • mgmove  (escape/openings)│
  │ Collision + escape overlay │          │   • mggfx   (tile/palette gfx)│
  │ Live build + openMSX launch│          │   build + emulator launchers │
  └───────────────────────────┘          └────────────────────────────┘
                                                      │
                                          reads/writes data/*.asm, MetalGear.rom
```

- **Single source of truth stays the `.asm` files.** The editor's working state
  is `tools/map.json` (already produced by `mgmap export`). Load = decode asm →
  json; Save = encode json → asm with the **byte-exact round-trip** we validated.
- **Backend is thin.** Endpoints call into the existing functions; no game logic
  is reimplemented in JS. The browser renders pixels the backend produces, so
  what you see is exactly what `mgrender` (and therefore the ROM) produces.
- **Why web:** canvas is the best surface for tile-grid painting and node-graph
  linking; PIL renders drop straight into `<img>`/canvas; runs with `uvicorn`
  and a browser, no packaging.

### Tech
- Backend: **Python stdlib `http.server`** (zero new deps — FastAPI/uvicorn were
  not installed and aren't needed for a single-user local tool), Pillow (already a
  dep of `mgrender`). Can swap to FastAPI later if async/validation grows.
- Front-end: **vanilla JS + HTML5 canvas** (no build step) to start; can graduate
  to a framework later. Tile/room images served as PNG data or cached files.
- State: editor edits `map.json` in memory; explicit **Save** writes asm,
  **Build** assembles the ROM, **Run** launches openMSX.

### Status
- **Step 1 DONE** — `tools/editor/server.py` + `tools/editor/static/index.html`.
  Read-only viewer: room list, real-pixel render with collision/atlas/scale
  toggles, connection D-pad navigation, engine openings, and a live validation
  bar (reachable 235/235, new escapes 0, one-way edges 7). Run:
  `python tools/editor/server.py --open`.
- **Step 2 DONE** — per-room metatile painter. "✎ edit room" opens a canvas
  editor: pencil / rectangle / bucket-fill / eyedropper, undo (Ctrl+Z), revert,
  and a metatile-palette picker (with optional collision tint). Live preview is
  **client-side composited** from a server-rendered metatile sheet (zero
  round-trips while painting). **Save** writes back via a **surgical block
  replace** of only the edited `RoomNNN` block (POST `/api/room/{id}/grid`), so
  diffs stay minimal and the ROM is unaffected; save re-runs validation and warns
  inline if the edit opens an off-map leak. Save is idempotent (no-op = no diff).

  **Important codec note:** `mgmap.write_model()` rewrites *every* block and
  re-emits `fmt_db` formatting, churning the whole file — do NOT use it for
  per-room saves. `selftest` is **data-level** (round-trips values), not
  byte-level; the assembler ignores `db` whitespace, so reformatting never
  changes ROM bytes, but it does create huge git diffs. The editor therefore
  edits one block at a time.
- **Step 3 DONE** — global map view + connection editing + resizable sidebar.
  Header toggle switches between **room view** and **🗺 map view**: a directional
  BFS auto-layout (follow N/S/W/E from room 121) places every reachable room as a
  live thumbnail on a pannable grid, with connection edges drawn **green
  (reciprocal) / orange dashed (one-way)**, rooms with new off-map leaks ringed
  red, and unreachable rooms dimmed. Click a thumbnail to select; "▦ open" jumps
  to its room view/editor. The info panel gained an **editable connection editor**
  (N/S/W/E destination fields + reciprocal toggle + wall ✕) usable in both views;
  saving re-validates live and warns on leaks. The right **properties sidebar is
  now drag-resizable** (splitter, 240–760px, persisted in localStorage; default
  widened to 340px).

  **Connection save is line-surgical, NOT `fmt_db`.** The original
  `roomsconnections.asm` is one `RoomConnections` block with decimal values,
  irregular hand-alignment, and `; <room>` row comments — impossible to reproduce
  byte-exactly. `set_connection` (POST `/api/room/{id}/conn`) therefore splices
  the new value into just the affected room's line (preserving prefix, separators,
  radix, column width, comment), giving a 1–2 line diff. A prior `fmt_db` pass had
  reformatted the whole block (decimal→hex, comments stripped); restored to HEAD +
  re-applied the two real severs (0.E, 4.W) → clean 2-line diff. Idempotent, build
  0 errors / 131072.
- **Step 4 DONE** — per-room **gfx tileset (0-7)** + **metatile set (1-6)**
  dropdowns (POST `/api/room/{id}/tileset`), surgical nibble edits preserving the
  table's pad nibble. Guards: flags layout metatiles exceeding the chosen set's
  count (would render garbage) and warns on non-stock gfx/meta pairings; live
  re-render. Map view also gained component-based 2D shelf-packing (uses screen
  width), drag-to-reposition rooms (persisted; "⟲ layout" reset), and correct
  handling of **elevator/exit-table transitions** (dest ≥ 156): these no longer lay
  out as spatial neighbours and render as dotted-purple toggleable links.
- **Renderer fix:** `mggfx.parse_block` stopped at the first blank line, so the
  Roof tileset (and any gfx block with internal blanks) decoded only part of its
  tiles (Roof: 42 of 108) → roof rooms rendered mostly black. Fixed to span blanks
  and stop at the next label; Roof now full. Renderer-only (no ROM impact).
- **Step 5 DONE** — palette editor. The info panel shows the room's effective
  16-colour palette (DefaultPalette overlaid by its `RoomPaletteN` block); click a
  swatch → R/G/B sliders (0–7, MSX2 V9938). GET `/api/room/{id}/palette`, POST sets
  one entry: updates the triple in place if already overridden, else inserts a new
  `(idx,(R<<4)|B,G)` triple before the `0FFh` terminator (build-safe, label-
  referenced). Overridden swatches marked; **palettes are shared** (e.g. room 0's
  RoomPalette0 is used by 45 rooms) so the editor surfaces the shared-room count as
  a warning. Live re-render of the room (or its map thumbnail) on each change.
- **Step 6 DONE** — doors / items / actors panel (`/api/room/{id}/objects`).
  **Item**: dropdown of the 47 `idxRoomItems` names (0=none, 1-based), sets
  `idxRoomItemsIdx[room-122]` (rooms 122-217). **Doors**: each existing door's
  destination/Y/X editable (surgical token splice in `DoorsRoomNNN`; door
  add/remove deferred — needs the idxDoors regen path). **Actors**: read-only list
  (id + position; shared blocks + symbolic ids make editing a later task). Added
  `_save_lines` so writes preserve a file's original EOF-newline state (doors.asm
  has none — avoids a spurious diff). All edits surgical & idempotent.
- **Map-view usability:** zoom control (60–250%, crisper source ≥160%) and a live
  room **preview in the sidebar** (updates as palette sliders move) so palette
  editing is usable without leaving the map.
- **Step 7 DONE** — metatile editor + tile-atlas browser. In room-edit mode, "🧩
  tiles" opens a modal for the brush metatile: a 4×4 cell editor composited
  client-side from a **tile atlas** (16×16 grid, tile id = row·16+col, with a
  collision tint). Click an atlas tile to pick a brush, click a cell to paint,
  save writes the 16 tile bytes to the `MetatilesN` block (surgical run-splice,
  `metatile M` = its M-th `db` line). **Metatiles are shared** (e.g. Metatiles1 =
  71 rooms) so the modal warns before editing. GET/POST `/api/room/{id}/metatile/
  {m}`, GET `/api/room/{id}/tileatlas.png`. Saving refreshes the room painter/
  render live.
- **Edit fidelity:** dropped the value `rjust` column-padding from the splice
  helpers — it left stray leading spaces on shrink-then-grow, breaking byte round-
  trips. Now every surgical edit (conn/tileset/palette/item/door/metatile) is
  fully idempotent; verified shrink-then-grow returns the file byte-identical.
- **Step 8 DONE** — "🔧 build / checks" modal. **Build** (POST `/api/build`) runs
  sjasm, reports error count + ROM size + output tail. **Run** (POST `/api/run`)
  launches openMSX with the built ROM (detached). **Validation dashboard** (GET
  `/api/dashboard`) aggregates: codec selftest (byte round-trip), reachability
  (235/235), walk-off escapes, one-way/transition edges, metatile-in-range,
  item-in-range, ROM size, and sjasm/openMSX availability — each a green/red row.
  Tool paths via `MG_SJASM` / `MG_OPENMSX` env (default to the known install
  locations).
- **Step 9 DONE** — polish. **ROM-budget tracker** in the dashboard: per-16KB-bank
  used/free bars (free = trailing fill run) + total; shows the stock ROM has only
  **196 B free across 8 banks** (≈full), with a prompt to extend to 512KB (Konami
  mapper) for new art. **Live openMSX read-back**: Run launches openMSX with a
  generated control script that writes the player state (room/X/Y/dir/prev) to
  `EMU_STATE` every 0.3s; a "live" header toggle polls GET `/api/emu/state` and
  shows `▶ room R (x,y)` in a pill (click → jump to that room) and **highlights the
  player's current room on the map** in real time. (File-based, reusing the proven
  start.tcl mechanism; `MG_EMUDIR` overrides the space-free state dir.)

## Refinements (post-Step-9)
- **Neighbour previews while painting** — the room editor now frames the canvas
  with the N/S/W/E connected rooms (faint, 0.6 opacity, same scale) so you can
  line up openings/walls with the adjacent rooms a player passes between.
- **Brush ghost preview** — hovering a cell shows a translucent preview of the
  brush metatile (not just the crosshair).
- **Door open-method ("which card")** — each door's objects row now has an
  "opens" dropdown. A door's id (1-based) indexes `IdDoorsLogic`; the low 5 bits
  select the method (1=elevator/none, **2-9 = Card 1-8**, 10=punch, 11=lorry/bomb,
  12=desert/uniform, 13=compass, 14=BigBoss, 15=prison wall, 16=basement wall);
  the high bits (default open/closed) are preserved on edit. POST
  `/api/room/{id}/doorlogic`.

## Authoring refinements (post-Step-9, batch 2)
- **Drag-to-connect** — map view "🔗 connect" toggle: drag from one room to another
  to link them (direction inferred from grid positions, reciprocal), re-validates.
- **Copy / clear / load + stamps** — painter: copy/paste/fill-all/load-from-room,
  and a **stamp palette** of canonical Building structures (incl. a full "Room
  frame" with correct 2×2 corners) for fast, joint-correct authoring.
- **Checkpoints editor** — "💾 saves" modal edits all 31 `SaveStatRooms` pairs
  (surgical, comment-preserving).
- **Door add / remove** — mint a door (fresh DoorID 157–160, appended to
  `IdDoorsLogic`; mints a `DoorsRoomNNN` block + wires the `idxDoors` slot if the
  room had none) or delete one (drops the block + resets the slot when the last
  door goes). POST `/api/room/{id}/dooradd|doorremove`.
- **Actor placement** — add/move/retype/remove enemies & objects (65 `ID_*`
  types). Editing a **shared** block (e.g. `ActorPrisoner`, 17 rooms) auto-**forks**
  a room-private `ActorsRoomNNN` so others are unaffected; positions are `db Y,X`
  (the `dw` word is bytes `[Y,X]`). Door & actor positions show as numbered badges
  on the room render. POST `/api/room/{id}/actoradd|actorremove|actorset`.

All verified against the codec **selftest** (data round-trip) + build; door/actor
structural edits keep `idxDoors`/`idxActorsRooms`/`IdDoorsLogic` consistent.

## Tile pixel editor
From the metatile editor, "✎ edit pixels" opens an **8×8 tile painter**: click a tile
in the atlas → pick a brush, paint with the tileset's 8-colour sub-palette
(ColorsTileset through the room palette), save writes the 3bpp gfx back to the
`Gfx*` block (surgical byte-splice, blank-spanning for GfxRoof). Tiles are shared
per tileset, so it warns "affects every room using this tileset"; flip/crate/
powswitch tiles are read-only. GET/POST `/api/room/{id}/tile/{t}`. This is
"repaint existing tiles"; *adding* tiles beyond a tileset's count is the 512KB
Phase B (new gfx segment + tileset count/collision). Verified: decode matches the
renderer, no-op byte-stable, build 0 errors.

## All 9 steps complete
The editor covers the full authoring loop — global map (link/grid + drag layout),
per-room metatile painter, tileset/metatile-set assignment, palette, doors/items/
actors, metatile + tile-atlas editing, build/run, a validation dashboard, ROM
budget, and live in-engine read-back — all with surgical idempotent saves (clean
git diffs) and engine-accurate validation.

---

## 2. Global map view (room link / grid)

The world is 251 rooms connected N/S/W/E (255 = wall). Two complementary views:

- **Grid placement canvas** — drag rooms onto an infinite 2D grid. Each room is a
  thumbnail (live `mgrender` mini-render). Placing room B directly north of A and
  drawing a link sets `A.N=B` and `B.S=A`. This is the primary "draw the map"
  surface.
- **Graph/adjacency view** — the `mgmove graph` output as an interactive node
  graph for rooms that don't lay out cleanly on a grid (elevators, warps).

Critical behaviors (learned the hard way — see memory `map-codec-tool.md`):
- **Reciprocity helper:** linking A→N→B offers to auto-set B→S→A; flags one-way
  links explicitly (they exist in stock and are valid, but should be intentional).
- **Live connection validation** via `mgmap conncheck` — highlight dangling links
  (A points to B but B doesn't point back), and links into unreachable rooms.
- **Escape/leak overlay** via `mgmove validate` — the killer feature. Mark any
  room edge where the player can walk **off into an unmapped room** (the "black
  screen" bug). A room is only safe to ship when every walkable edge tile either
  (a) has a real destination, or (b) is blocked by collision. Show per-edge
  red/green.
- **Reachability** — flood-fill from the start room; grey out rooms the player can
  never reach (`mgmove` already computes this: "235/235 reachable").
- **Entry-coordinate awareness:** the engine preserves the perpendicular coord on
  room exit (N→Y184, S→Y18, W→X242, E→X12; other axis kept). The editor should
  warn when a door/opening on one side has no matching opening at the partner's
  entry band — that's how you strand the player even with a valid link.

---

## 3. Per-room editor

A room = 8×6 **metatiles**; each metatile = 4×4 **tiles**; full room = 32×24 tiles
= 256×192 px. Two zoom levels of editing:

- **Metatile paint mode (primary):** an 8×6 grid; paint cells by picking from the
  room's metatile-set palette (Metatiles1..6). This is exactly the `RoomNNN` byte
  layout. Click-drag paint, rectangle fill, flood fill, eyedropper, copy/paste a
  rectangle, copy whole room.
- **Tile-level inspect:** expand a metatile to its 4×4 tiles to understand/choose
  the right metatile (and, in the metatile editor below, to author new ones).
- **Overlays (toggle):**
  - **Collision** — per-tileset 32-byte bitmap (MSB-first; tile T solid iff bit
    `7-(T&7)` of `CollTiles[T>>3]`). Renders the real solidity the engine sees.
  - **Edge/threshold bands** — draw the exit thresholds (X<12 W, X≥244 E, Y<16 N,
    Y≥186 S) and the entry points, so you can see whether an opening lines up.
  - **Doors / items / actors** — icons at their positions (see §5).
  - **Escape** — the off-map leak check for this specific room.
- **Palette assist (the vocabulary we derived):** a "stamp" library of canonical
  Building pieces so corners are never wrong again — e.g. the 2×2 corners
  (top-left `08`/`09` over `17`/`1F`; top-right `09`/`0B` over `1F`/`0E`), wall
  bodies (`19h` left, `14h` right), top wall (`0A`/`09`/`08`/`0B`), bottom wall
  (`0D` + `0C`/`0F` corners), floor `07`, shadow `1F`, opening `0B3h`, water set.
  These are tileset-specific stamps so each style gets its correct joints.
- **Live preview:** every edit re-renders the room PNG from the backend (the real
  pipeline), shown beside the editable grid. Optional side-by-side with the
  stock `room_images/MGEAR1_NNNN.png` reference.

---

## 4. Tilesets per room (assignable)

- Each room has a **gfx tileset id** (0..7: Building, Basem/Desert, Roof,
  Elevator, Lorry, HindD, MetalGear, Ending) stored as packed nibbles in
  `RoomGfxSetIds`, and a **metatile set** (Metatiles1..6) in `MetaTileSetIDs`.
- Editor: per-room dropdowns for **gfx tileset** and **metatile set**, with the
  known-good stock pairings preselected (Building gfx0+meta1, Basem gfx1+meta2,
  Roof gfx2+meta3, Elev gfx3+meta4, Lorry gfx4+meta5, HindD gfx5+meta6,
  MetalGear gfx6+meta1).
- **Guardrails:**
  - Metatile sets differ in size (Metatiles1=217, Metatiles2=123…). Changing a
    room's set must validate that every metatile id used still exists in the new
    set, or the room renders garbage / the engine indexes out of range. Show a
    "N metatiles out of range" warning with the offending cells highlighted.
  - Warn on non-stock gfx/meta pairings (allowed, but usually a mistake).
  - Re-render on change so style swaps are immediate and visible.
- **Multi-style guidance baked in:** dry rooms → Building; flooded/water → Basement
  or Building-water; rooftop → Roof. (Basement floor reads as water/sand, so it's
  not a generic dry floor.)

---

## 5. Doors, items, actors, checkpoints (the rest of the map data)

`mgmap` already round-trips all of these — the editor should expose them so a
room is fully authored in one place. **Mind the engine indexing quirks:**

- **Doors** — `idxDoors`/`DoorsRoomNNN`. Place door tiles on the grid; editor
  writes the door block. Respect the slot mapping (rooms 0..224, then 240..250).
- **Items** — `idxRoomItemsIdx` is indexed by **room−122** (valid rooms 122..217).
  This bit us before ("Gas Mask room 16" was actually 138). The editor must show
  the real room and handle the −122 offset internally; refuse item placement in
  rooms outside 122..217.
- **Actors/enemies** — `idxActorsRooms`/`ActorsRoomNNN`, rooms 0..221. Place
  enemies/NPCs with position + type; preserve each position's mnemonic/tokens
  (the `dw 40B0h` vs `db Y,X` lesson — encoding must match per-slot or the ROM
  diff fails).
- **Checkpoints** — `SaveStatRooms`, 31 `[room, prevRoom]` pairs. Edit as a list;
  validate rooms exist.

---

## 6. Palette editor

- Rendering uses `DefaultPalette` + per-room `RoomPalette`, with the tile color
  table `ColorsTileset = [1,3,5,8,9,Ch,Eh,Fh]` (3bpp tiles → palette indices).
- Editor: a **16-color palette grid** per room (MSX2 9-bit RGB, 0..7 per channel).
  Click a slot → RGB picker (3 bits each). Live re-render so you see the room
  recolor immediately.
- **Per-room palette assignment:** pick which palette a room uses; clone/derive a
  palette from another room; preview the same room under different palettes.
- Show the color table mapping so it's clear which palette slots a given tile
  actually draws with.

---

## 7. Things you might be missing — recommended additions

1. **Metatile editor** — author/edit the 4×4 tile composition of a metatile (and
   ideally add new metatiles within a set's capacity). Without this you're limited
   to the metatiles the stock game already defines.
2. **Tile/atlas browser** — visual grid of every tile in a tileset with its id and
   collision flag, so picking tiles isn't guesswork (this is where "21 is a roof,
   not a wall" mistakes come from).
3. **Build + run integration** — one button to assemble
   (`sjasm MetalGear.asm MetalGear.rom`, assert 0 errors / 131072 bytes) and one to
   launch openMSX at a chosen room (we can warp via RAM writes to `0xC130`). Tighter
   than the current `start.tcl` loop.
4. **Validation dashboard** — a single panel aggregating: conncheck, escape/leak
   lint, reachability, metatile-range check, item-room-range check, and the
   byte-exact `selftest`. Green/red status before you ship. This is the safety net
   that has repeatedly caught real bugs.
5. **Undo/redo + autosave** of `map.json`; **diff view** vs git-stock so you can
   see exactly what changed before writing asm.
6. **512KB ROM budget tracker** — show ROM size and free space per bank (Konami
   mapper, 32×16KB). Relevant when you start adding new tile art beyond 128KB.
7. **Side-by-side stock reference** — load `room_images/MGEAR1_NNNN.png` next to
   the live render to copy the original art style.
8. **Path/critical-route annotation** — overlay the intended critical path and
   gating from `docs/NEWGAME-MAP.md` onto the global grid, so design intent and
   actual connectivity are checked against each other.
9. **In-editor openMSX state read-back** (stretch) — read player room/X/Y live to
   confirm an edit behaves in-engine without a full manual playthrough.

---

## 8. API surface (sketch)

```
GET  /api/map                      -> map.json (decoded from asm)
POST /api/map/save                 -> encode json -> data/*.asm (byte-safe)
GET  /api/room/{id}                -> room {layout, gfx, meta, palette, doors,
                                            items, actors}
PUT  /api/room/{id}                -> update any of the above
GET  /api/room/{id}/render.png     ?collision=&overlay=   (mgrender)
GET  /api/room/{id}/openings       (mgmove)   exit ranges + reachable exits
POST /api/connect                  {a, dir, b, reciprocal}  + revalidate
GET  /api/tileset/{id}/atlas.png   tile grid + collision flags
GET  /api/metaset/{id}             metatile definitions (4x4 each)
GET  /api/validate                 conncheck + escapes + reachable + selftest
POST /api/build                    assemble ROM, return size + errors
POST /api/run                      launch openMSX (optional warp room)
```

---

## 9. Build order (incremental, each step usable on its own)

1. **Backend skeleton** — FastAPI app; `/api/map`, `/api/room/{id}/render.png`,
   `/api/validate` wrapping existing modules. Prove the renders + validation come
   through in a browser. *(Read-only viewer — immediately useful.)*
2. **Per-room metatile painter** — editable 8×6 grid, palette stamps, live
   re-render, save back to `map.json` and asm. *(Replaces hand-editing rooms.asm.)*
3. **Global grid + linking** — drag/place rooms, draw N/S/W/E links, reciprocity,
   conncheck + escape + reachability overlays.
4. **Tileset/metatile assignment** with range guardrails.
5. **Palette editor.**
6. **Doors / items / actors / checkpoints** panels (with the indexing quirks).
7. **Metatile editor + tile atlas browser.**
8. **Build/run integration + validation dashboard + diff view.**
9. **Polish:** undo/redo, autosave, ROM-budget tracker, stock-reference overlay,
   live openMSX read-back.

Step 1 alone gives a visual map browser; each subsequent step removes another
class of hand-editing. The byte-exact `mgmap` round-trip and the `mgmove` escape
lint are the foundations that make all of this safe.
