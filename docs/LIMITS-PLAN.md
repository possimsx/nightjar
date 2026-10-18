# Plan: extending world-data limits (128KB) and relocating tables (512KB)

**Status: Phase A SHIPPED; Phases C1 (items+actors), C2 (full per-room
connections + A5), C3 (radio calls), C4 (doors) and C5 (room layouts) SHIPPED
(2026-07-05, see below); C6 (texts) optional/deferred. Phase D COMPLETE:
D0-D2 (world banking + gateways + genworld) and D3+D4 (editor multi-world +
per-world path index/checkpoints) SHIPPED 2026-07-06.** Companion to [ROM-512KB-PLAN.md](ROM-512KB-PLAN.md) (mapper facts,
adaptive sizing, ext tilesets) and [SPECIAL-ROOMS.md](SPECIAL-ROOMS.md) (engine-locked
room ranges). Goal: give the NIGHTJAR world room to grow — more patrol routes, actors,
items, doors, texts — first inside 128KB, then by moving whole tables into ext segments.

## Verified facts this plan stands on (2026-07-05)

- **JP tables are NOT dead weight.** `data/textsjp.asm` / `radiocallsjp.asm` /
  `weaponnamesjp.asm` / `itemnamesjp.asm` are behind `IF (JAPANESE)` (=0) and cost 0
  bytes. No free space there.
- **Bank-group headroom (current New-Plot build, EXTGFX off):**
  | group | segs | world tables inside | free |
  |---|---|---|---|
  | Banks0123 | 0–3 | fixed engine code | **70 B** |
  | Banks456 | 4–6 | connections, actors-in-rooms, **paths**, items-in-rooms, respawn, palettes | **52 B** |
  | Banks789 | 7–9 | roomtileset nibbles, stock tile gfx | **26 B** |
  | BanksABC | A–C | sprites, texts, RoomFlags | **699 B** |
  | BanksDEF | D–F | room layouts, metatiles, doors, radio calls | **89 B** |
- **Approx table sizes (data bytes):** rooms ~8.9K, metatiles ~9.3K, doors ~3.0K,
  texts ~5.8K, actors-in-rooms ~1.7K, paths ~1.4K, connections ~0.6K, radio ~0.6K,
  items-in-rooms ~0.4K, roomtileset ~0.46K, respawninfo ~0.56K.
- **Path reads are bracketed:** exactly 3 read sites — `GetPathPoints`,
  `GetSentinelLookDirs` (init) and `UpdateActorPath` (per step) — and **each starts with
  its own `call SetBanks_4_5_6`**. The actor stores a raw pointer (`ACTOR.PointerL/H`)
  into the paths bank and re-reads points incrementally. So paths are relocatable by
  retargeting those 3 calls, but note `WalkSpeeds` etc. are read in the same window.
- **Connections have ONE read site** (`GetNextRoomNum3`, Banks0123 ~:919), inside a
  hardcoded remap chain (rooms 126–207 doorless, 208–227 via −82 offset, elevators −13):
  the table is 156×4, not 251×4.
- **Tools are location-agnostic.** mgmap/mgpath/mgradio/... parse `data/*.asm` files by
  label; moving an `include` from Banks456.asm to a new bank file changes nothing for
  the codecs or the editor. Only `mgrender`-style *address*-based readers would care
  (none of the world tables are read by address).
- **Two proven relocation patterns exist:** `ExtDivert`+`LoadExtDispatch` (map ext seg
  into a window, dispatch inside it — hook lives in cart-header padding) and
  `CacheRoomFlags` (copy a per-room byte to RAM at `InitRoom2` under a `SetBanks`
  bracket — check code then reads RAM, bank-free).

## What we will NOT fight (format limits, same at any ROM size)

251 rooms / 1-byte room ids **per world — see Phase D for >255 rooms via world
banking** · 4 exits per room · 16 tileset ids (nibble) · ≤256 tiles per tileset
· 16 metatile-set ids (nibble) · 16 live actors + 22 enemy sprite layers (RAM)
· radio person = nibble (15) · 8KB mapper granularity · 512KB hard max.
These are design constraints, not targets.

### Rejected: 16-bit room ids (evidence, 2026-07-05)
~150 code sites read `Room`/`PreviousRoom`/`NextRoom` across 30 files; almost
all use the "room in A" calling convention (8-bit `cp` chains + `GetRoomPointer`
/`GetPointerDE2A` dw-table indexing). Widening means: every cp chain becomes a
6-10 byte 16-bit compare (seg 0 has 0 bytes free), every VALUE format changes
(connection exits, door dests, checkpoint pairs, respawn, elevators, demo
recordings), the 255-wall sentinel changes everywhere at once (missed site =
silent corruption, not build error), and the whole tool stack assumes byte ids.
Whole-engine-rewrite cost for a limit that world banking lifts for ~1% of it.

## Phase D — PLANNED: >255 rooms via WORLD BANKING (byte ids + world index)

Rooms stay 0..250 per world; a **`CurWorldSeg` RAM byte** (init `WORLD_SEG`)
picks which parallel copy of the per-room dataset is live. The C1-C4 funnel
makes this cheap: the five `ld a,WORLD_SEG / call MapSeg60` hook sites become
`ld a,(CurWorldSeg) / call MapSeg60`, and layouts+conns+items+actors+doors+
radio all switch worlds atomically. ~17KB ≈ 2-3 segments per world → 256KB
fits ~4 extra worlds (~1250 rooms), 512KB far more. Fits the act structure.

- **Gateways**: door dest bytes 252-254 = sentinels into a gateway table
  (target world, room, entry pos); door-entry hook switches CurWorldSeg + runs
  normal room init. Nothing else in the engine knows worlds exist.
- **Saves**: append CurWorld to `GameDataAreas` (one new terminated-table entry).
- **Constraints**: hardcoded special rooms (121 parachute, 240-250 elevators,
  251 ending) recur in EVERY world — design around them or keep data-driving
  them (hazards+conns done, hide-guard planned). Patrol paths stay in Banks456;
  per-world = the room→routes index only, route blocks shared. Editor grows a
  world switcher + per-world file sets (reuse the blank-template machinery).
- **Order**: D0 = C5 (SHIPPED — see Phase C5) → **D1 SHIPPED 2026-07-05**:
  `CurWorldSeg` RAM byte (Variables.asm end), boot-initialized to `WORLD_SEG`;
  ALL seven `ld a,WORLD_SEG` hook sites + CacheRoomLayout's LSEG pair now read
  `(CurWorldSeg)`(+1/+2). Behaviour-neutral with one world (flag-off md5
  unchanged; flag-on A/B logs identical incl. map checksums). Switching worlds
  is now literally `ld a,<seg> / ld (CurWorldSeg),a` + a room re-init.
**D2 SHIPPED 2026-07-06 — gateways + world 1 + genworld. >255 rooms is live.**
- **World directory (D2a)**: every world's data segment starts with a 32-byte
  pointer directory (`WDIR_*` equates; layout seg 1 likewise `LDIR_*`); ALL
  engine table loads (items/actors/doors/radio/conns/layouts — 12 sites) read
  through it, so worlds lay out content freely. World 0's directory is plain
  `dw` lines in BanksWorld.asm; behaviour-neutral (A/B verified).
- **Gateway resolver (D2b)**: a door whose DESTINATION byte is >= 252 is a
  gateway. The resolver body lives IN each world's segment at the fixed
  offset **WGATE = #6020** (hooks/worldgate.asm, dot-local labels scoped by a
  per-world global; Banks0123 had no room — its tail is FULL, the ~30-byte
  inline-swap hook in SetDoorDestination is all it pays). GatewayTable is an
  authoring file (`data/gateways.asm`, copied per world): db srcRoom,
  sentinel(252-254), destWorldIdx, destRoom; miss = stay put. CurWorldSeg is
  in `GameDataAreas`, so saves/continue keep the world.
- **genworld** (`tools/mgworld.py gen N [--force]`): clones the world-0 data
  files into `data/worldN/` with locally-defined labels suffixed `_wN`
  (external refs — Metatiles*, enums — untouched), emits `BanksWorldN.asm`
  (directory + resolver + includes + pads), wires MetalGear.asm
  (`IF (WORLDS-N)`) and bumps `WORLDS` in features.asm. 3 segments/world.
- **VERIFIED (tools/gwtest.tcl)**: world-1 clone with a marker layout byte in
  room 5 + return gateway; in-emu: poke a door's dest to 252 → enter →
  CurWorldSeg 16→19, map checksum changes to world-1's content, DoorsList
  rebuilt from world-1 data; poke+enter again → back to 16 with world-0
  checksum. Flag-off md5 unchanged; flag-on wbtest regression identical
  (world 1 inert without gateways). Script notes: DoorsList RAM = C3D0
  (16-byte records, +15 = dest), CurWorldSeg = F131.

**D4 SHIPPED 2026-07-06 — per-world path index + checkpoint lists.**
- **Path index (D4a)**: `idxRoomPaths` split out of paths.asm into
  **`data/pathindex.asm`** (tail move, flag-off byte-identical) and assembled
  PER WORLD (WDIR_PATHS = #6012); the Path_*/Paths_* route blocks stay in
  Banks456, SHARED by every world (a world's index entries point into the one
  pool). The two index readers (GetPathPoints / GetSentinelLookDirs) call
  **`GetRoomPathList`** (hooks/worldbank.asm, seg 6) under the flag: map
  CurWorldSeg at #6000, read the entry, restore the caller's segment from the
  BankIn60 shadow, return HL. UpdateActorPath (the per-frame hot path) is
  untouched — it reads via the stored ACTOR.PointerL/H.
- **Checkpoints (D4b)**: `data/checkpoints.asm` assembled PER WORLD
  (WDIR_CHKPT = #6014). ChkSaveGameStatus under the flag wraps the scanner:
  callers use SetBankInA0_6 (seg 6 at #A000 ONLY), so the previous #6000
  segment is restored from BankIn60 on BOTH exits; the match result rides in
  the CARRY flag across the restore (push af/pop af would destroy it — B
  carries the saved segment instead, scratch at both call sites). Saving
  itself (StoreGameStat/GameDataAreas) is unchanged.
- hooks/worldbank.asm now ASSERTs `$ >= #A000` at file TOP too (the D4 data
  evictions shift the seg-6 code block; TRAP #5 guard).
- **VERIFIED (tools/d4test.tcl)**: flag-off md5 unchanged; flag-on wbtest A/B
  logs identical; gwtest world hop intact; with TEMP world-1 edits (room 1 →
  Paths_002, extra pair [1,5]) the in-emu run shows guard path pointers
  0x9593/0x9598 (w0) vs 0x95AE/0x95B5 (w1) and the [1,5] save firing ONLY in
  world 1 (GameProgressBuffer = CA00 flips 121→1/prev 5), both reverting on
  the return gateway. mgpath reads the index from pathindex.asm now.

**D3 SHIPPED 2026-07-06 — editor multi-world (switcher, per-world file sets,
gateway editing).**
- **World IO layer (mgmap)**: `set_world(N)` + `world_file()/read_text()/
  write_text()` redirect every per-world file (WORLD_FILES: rooms, conns-full,
  doors, items, actors, radio, gateways, pathindex, checkpoints) to
  `data/worldN/`, stripping the `_wN` label suffix on read and re-applying it
  on write (defined-label set computed across the world's file set, so
  external refs — Metatiles*, Paths_*, enums — stay shared). Every codec and
  the whole editor work on stock label names, unaware of worlds; mgrender/
  mgsprite already read through mgmap, mgpath/mgradio now delegate their IO.
  Model cache keys on the active world. The stock 156-slot connections table
  is NOT per-world (flag-off fallback, world 0 only — set_connection skips
  the stock dual-write for worlds >0).
- **Server**: GET /api/worlds, POST /api/world (switch; clears mgsprite lru
  caches), POST /api/world/new (mgworld.gen clone of world 0), gateway CRUD
  (GET /api/gateways, POST /api/gateway/add|set|remove via mgmap
  parse_gateways/write_gateways), per-world map/restore (first-commit revert
  of the ACTIVE world's file set, shared files skipped for worlds >0),
  per-world walk-off-escape baseline (git HEAD of the world's rooms file),
  and warp pinning the emulator to the editor's world (optional `W<seg>`
  token pokes CurWorldSeg=F131 before the recipe fires).
- **UI**: 🌐 world dropdown + "+ world" button in the header (visible when
  WORLDBANK is on, follows the dashboard toggle); a "gateways" section in the
  room objects panel (add/edit/remove entries, free-sentinel picker, doors
  with dest 252-254 badge "⇒ gw"); everything else — grids, conns, doors,
  items, actors, radio, checkpoints modal, paths editor, validation pills —
  operates on the active world transparently.
- Engine-SHARED layers (tileset nibbles, palettes, metatiles, texts, RoomFlags
  hazards, respawn, hide-guard rules, prisoner texts) are per-ROM, not
  per-world: editing them in any world changes all worlds, same as the engine.
- **Verified**: world-1 model loads with stock names (marker byte visible),
  renders 256×192 via the world files, item/conn/checkpoint edits land ONLY
  in data/world1/ with suffixed labels (world 0 untouched), gateway add/set/
  remove round-trips, restore reverts the world-1 edits, mgmap selftest
  passes against BOTH worlds' file sets, flag-on/off builds byte-identical to
  the pre-D3 D4 ROMs.

---

## Phase A — SHIPPED 2026-07-05 (pay-as-you-go: bounds follow table length)

Implemented as **symbolic engine bounds + on-demand table growth**, so stock
content pays 0 bytes and each new out-of-range placement costs only its own
table bytes. Verified: stock rebuild differs from pre-Phase-A by **316 bytes,
all the A4 checkpoint change** (A1/A2 symbol swaps are byte-identical); growth
exercise (item→room 220, actor→room 222, route→room 180, checkpoint add/remove
incl. pair 0) builds clean with the engine `cp` operands following the grown
tables automatically; all codec selftests byte-exact.

**VERIFIED IN openMSX (2026-07-05, `tools/cptest.tcl`):** scripted run boots the
game, walks the dock ladder 121→0→121 with breakpoints on the scanner entry and
on `StoreGameStat` (signature-guarded so only real seg-6 hits count). With a
test pair `[0,121]` appended as **pair #32** — unreachable by the old `ld b,31`
loop — the 121→0 transition fired `SAVE room=0 prev=121` (terminator scan reads
past 31 ✓), the return 0→121 fired `SAVE room=121 prev=0` via stock pair
`[121,0]` (stock behaviour intact ✓), a non-pair transition scanned without
saving (no false positive ✓), and every scan terminated cleanly at the `0FFh`
(no runaway ✓). Test pair removed afterwards; stock = 31 pairs. The script is
reusable — it also documents the boot dance (space/return mash 13.5s–38s clears
title+intro radio call; `pcm` 0xc180 = 0 means player control is live) and the
bp addresses (scanner entry `0xBDF8`, loop `0xBE08`, `StoreGameStat` `0xBE20`,
CPU = `0xA000 + romoff - 0xC000` for seg 6).

- **A4 checkpoints**: `ChkSaveGameStatus` scans to a **0FFh terminator** (same
  15 code bytes, +1 data byte) — any pair count. `SaveStatRooms` moved to
  **`data/checkpoints.asm`** (own include after logic/checkpoints.asm in
  Banks456) so map-restore reverts checkpoint DATA without reverting the
  scanner CODE. Editor saves-modal gained **+ add / ✕ delete**
  (`/api/checkpoint/add|remove`); deleting pair 0 pulls pair 1 onto the label
  line.
- **A1 items**: `cp 218/cp 122/sub 122` → **`ITEMROOM_END/ITEMROOM_BASE`**.
- **A2 actors**: `cp 222` → **`N_ACTORROOMS`**.
- **Key layout decision:** the equs live in **Banks456.asm right after each
  include** (`N_ACTORROOMS equ ($-idxActorsRooms)/2` — table must stay last in
  its file; `ITEMROOM_END equ ITEMROOM_BASE + (idxRoomItems-idxRoomItemsIdx)`),
  NOT in the data files — sjasm 0.39 forbids forward refs in equ, and the
  editor's "restore original map" rewrites data files to their first-commit
  state (would have deleted in-file equs → broken build). Data files stay
  byte-pristine.
- **A3 paths**: no engine bound exists; `mgpath` now derives the room count
  from `idxRoomPaths` (stock 179, `MAX_ROOMS` 251) and `set_room_paths` grows
  the index on demand (filler repeats the last pointer, stock's own style).
- **Codec/server**: `mgmap.grow_actor_index` / `grow_item_index` (+`MAX_ROOM`),
  terminator-aware checkpoint parse/encode; `set_item`/`_set_actors` grow on
  demand; `restore_map` skips files with no git history yet.
- **When Banks456 headroom (~50 B) runs out the build still fails loudly**
  (`ds` negative / ASSERT) — demonstrated live with a 100+-byte growth. Bigger
  worlds need Phase C eviction, exactly as planned.

### Original Phase A design (for reference)

Each item is a tiny operand/loop edit plus a table growth. Costs land in Banks456/DEF,
so sequence them against the bytes the new-plot content actually frees (a mostly-blank
NIGHTJAR world is far smaller than the stock data it replaces — rooms.asm layouts are
shared blocks, blank rooms dedupe to almost nothing).

| # | change | edit | data cost | unlocks |
|---|---|---|---|---|
| A1 | items in any room | `cp 122`/`cp 218` bounds in addroomitems | +~155 B (`idxRoomItemsIdx` 1 B/room) | items outside 122–217 |
| A2 | actors in rooms 222–250 | `cp 222` → 251 | +58 B (29 dw) + lists | guards in high rooms |
| A3 | paths in rooms 179–250 | `idxRoomPaths` length (data-only; verify no cp) | +144 B (72 dw) | patrols everywhere |
| A4 | checkpoints beyond 31 | fixed-31 loop → `0FFh`-terminated list (DarkRooms pattern) | ±0 | any checkpoint count |
| A5 | full 251×4 connections | delete the `GetNextRoomNum` remap chain, index directly | +~380 B table, −~20 B code | doors rooms get real exits; codec/editor simplify; frees hardcoded ranges in SPECIAL-ROOMS |
| A6 | doors in rooms 225–239 | rework `idxDoors` slot gap | +~30 dw | only if the new map needs it — else keep as design constraint |

Order: A4 (free) → A1/A2/A3 (as content needs them) → A5 (best done together with C2
below, which pays for it) → A6 (only on demand).

Each step: edit ASM + extend the matching codec (`mgmap`/`mgpath`) + `selftest` +
build 0 errors + one openMSX smoke test of the touched mechanic.

## Phase B — 128KB: keep paths where they are, fund them by eviction

**Decision: do NOT relocate paths.** Their per-step reader (`UpdateActorPath`) runs
every frame per actor; leave it byte-identical. Instead grow the paths budget by moving
its *neighbors* out of Banks456 in Phase C — items+actors+connections+respawn eviction
frees ~3.3KB in 456, a ~2.5× growth budget for routes with zero risk to the hot loop.

## Phase C1 — SHIPPED 2026-07-05: world bank holds items+actors

Flag-gated **`WORLDBANK`** (features.asm, default 0 = byte-identical build; md5
verified). When 1: `BanksWorld.asm` (org #6000, segment `WORLD_SEG equ
16+EXTGFX*3`) holds data/actorsinrooms.asm + data/itemsinrooms.asm + the Phase A
bound equs; ROM auto-grows to 256KB; **Banks456 gains ~2.1KB** (seg 6 pad 52 →
2138 bytes) for paths/routes. Editor: "World-data bank" checkbox in the Build
dashboard (`/api/worldbank`), same pattern as EXTGFX.

Mechanism: **`MapSeg60`** (hooks/worldbank.asm, 9 bytes, lives in Banks456 seg
5/6 so it survives its own swap) maps a segment into #6000-#7FFF ONLY, with the
`BankIn60` shadow updated under DI (ISR/SetSoundEntry restore from shadows, so
this is interrupt-safe). Readers:
- `SetupEnemyRoom` (Banks0123 seg 0): two `IF (WORLDBANK)` injections right
  after its stock `call SetBanks_4_5_6` (entry + per-iteration re-map); exits
  still `jp SetBanks1_2_3`, AddEnemy's internal bank churn is untouched.
- `AddRoomItems`: wrapped (`AddRoomItems` shim → `AddRoomItems_` stock body).

**Three traps found the hard way (cost a hung intro + garbage items):**
1. **openMSX auto-detects the mapper WRONG on >128KB images** — always pass
   `-romtype konami` (run_openmsx now does). Symptom: BankIn shadows garbage,
   PC spinning in unmapped data at boot.
2. **AddRoomItems' callers are NOT under `SetBanks_4_5_6`** — they use
   `SetBankInA0_6` (seg 6 at #A000 only, seg 1 still at #6000). The shim must
   save/restore the previous `BankIn60` value, never assume seg 4. A hardcoded
   restore corrupted the mapping to (4,2,6) and hung the intro.
3. **The `_`-suffixed helpers (`ADD_DE_A__`, `GetPointerDE2A_`, `ADD_HL_A_`)
   are trampolines that end `jr SetBanks_1_2_X`** — they re-map 1_2_X after
   every call (that's how the stock seg-6 body kept itself+its data reachable).
   They silently unmap the world segment mid-body; under WORLDBANK the body
   must call the plain variants (`IF` blocks at 3 sites in addroomitems.asm).

**Phase A correction found during C1:** stock `idxRoomItemsIdx` is **97** bytes
(rooms 122..218) with `cp 218` making slot 96 (a leftover 2Dh ration for room
218) DEAD. Phase A's length-derived `ITEMROOM_END` assembles as **219**, which
silently un-deadened it — fixed by zeroing slot 96 (`db 2Dh` → `db 0`), so the
bound is 219 with an empty slot = stock behaviour. Flag-off diff vs pre-Phase-A
baseline is now 317 bytes (316 checkpoint rework + this byte).

**Verified**: flag off md5-identical; flag on: world seg holds the tables
byte-for-byte (2108 used / 6084 free), `cp N_ACTORROOMS`/`ITEMROOM_END` resolve
across banks, and an openMSX A/B harness (`tools/wbtest.tcl`: boot → spatial
warp into room 5 → door warp into item room 126, dumping EnemyList ids +
ItemsInTheRoom RAM at fixed emu-times) produces **byte-identical logs** on both
ROMs — guard spawns from world data, ration (30,1,80,80) loads in 126, enemy
list clears. Warp recipes for scripts: spatial = `Room(0xc130)=src,
NextRoomDirect(0xc133)=dir, 0xc151=1`; door = `DoorOpenArray(0xc450+id-1)=0,
IdDoorEnter(0xc4fc)=id, 0xc133=0, 0xc151=1`. True RAM addrs: EnemyList D000
(16×80h, byte0=ID), ItemsInTheRoom C5D0, BankIn60 F0F1.

## Phase C2 — SHIPPED 2026-07-05: full per-room connections (delivers A5)

With WORLDBANK on, **every room 0..250 owns its 4 exits** — `RoomConnsFull`
(251×4, `data/roomconnsfull.asm`, in BanksWorld) replaces the stock 156-slot
table AND the whole `GetNextRoomNum` remap chain. **Door rooms can now have
real walk-off exits** (the editor's room panel edits any room's connections
when the full table is active; slot-borrow hints disappear).

- **Engine**: `CacheRoomConns` (hooks/worldbank.asm) copies `RoomConnsFull
  [Room]` → 4-byte RAM `CurRoomConns` from the same SetRoomPal bracket as
  `CacheRoomFlags` — SetRoomPal runs on every room change INCLUDING binocular
  room flips, always before any `GetNextRoomNum` use, so the cache is never
  stale. `GetNextRoomNum` under the flag is 6 instructions reading RAM (keeps
  the `jp SetBanks1_2_3` side-effect); the stock chain assembles in the ELSE.
  `CurRoomConns` was APPENDED to Variables.asm (after `CurRoomFlags`) so no
  RAM address shifts — the editor/tcl hardcoded addresses stay valid.
- **Seed**: `python tools/mgmap.py genfullconns` expands the stock table
  through the remap (rooms 126-207/228-240 → FF rows = the stock C=FFh
  default); behaviour-neutral, graph-identical (235/235 reachable, 0 escapes,
  0 one-way — same as stock). `set_worldbank(True)` auto-seeds if missing.
- **Codec/editor**: `connections_full` in the model (parse/write/JSON/
  selftest); `mgmap.eff_conns` is the single accessor — full row when active,
  stock slot-remap otherwise — and build_graph/asymmetric_edges/validation/
  warp all go through it. `set_connection` **dual-writes**: full row always
  (canonical) + the stock slot when representable, so flag-off 128KB builds
  keep matching the authored world; door-room-only exits exist just in the
  full table (documented divergence, same idea as EXTGFX-only tilesets).
- **Verified**: flag-off md5 unchanged; A/B emu run (121→5 poked-cache warp,
  then 5→1→5 walk-offs driven by the ENGINE-filled cache, then door→126)
  byte-identical logs; codec selftest incl. full-conns round-trip.

## Phase C3 — SHIPPED 2026-07-05: radio calls in the world bank

`data/radiocalls.asm` (idxRoomRadio + RadioRoom_* chains, ~0.9KB incl. the
pointer table) moved from BanksDEF to BanksWorld under the flag (JAPANESE
variant handled the same way). Single reader `UpdateRadio` (Banks0123, runs on
every room load): its `call SetBanks_D_E_F` becomes `SetBanks_4_5_6` +
`MapSeg60(WORLD_SEG)` under the flag (4_5_6 first so MapSeg60 in seg 5/6 is
reachable); `RadioFreqs` stays in fixed seg 0 and mgradio's editing of it is
untouched. mgradio codec is file-based → zero changes. Verified: flag-off
md5 unchanged; A/B emu logs identical including live per-room radio RAM
(`NumRadioPersons` C87F / `RadioPersonsDat` C880: room 5 = 1 caller freq 133,
room 1 = 2 callers, room 126 = none). BanksDEF regains the radio bytes when
the flag is on.

## Phase C4 — SHIPPED 2026-07-05: per-room door data in the world bank

`data/doors.asm` (DoorOpenEnterDat + DoorsRoom_* + idxDoors + IdDoorsLogic,
~2.9KB) moved to BanksWorld under the flag. The two 16-byte tile-pair tables
(`DoorClosedTiles`/`DoorOpenTiles`) were **split out to `data/doortiles.asm`**
and stay in BanksDEF — the draw/erase paths read them under stock mappings and
never touch the world segment. mgmap's door codec/regen is unaffected (it only
parses the moved tables, same file).

Readers (both copy to RAM, so gameplay reads DoorsList/DoorOpenArray only):
- `AddDoorsData` (room load + binocular rooms): swap `SetBanks_D_E_F` →
  `SetBanks_4_5_6`+`MapSeg60(WORLD)`. **TRAP #4 of this project: the injected
  `ld a,WORLD_SEG` clobbered A, which held the door-slot index consumed by
  `GetPointerDE2A` — stock `SetBanks_*` preserves A (push af/pop af), a naked
  `ld a` does not.** Symptom: every room reported room 16's two doors and the
  door-warp collapsed. Fixed with push af/pop af around the swap; audited the
  C1/C3 hooks for the same hazard (safe — A is dead at those points).
- `SetDefaultDoorLock` (game init, seeds DoorOpenArray): same swap, A unused.

Verified: flag-off md5 unchanged (file split is byte-neutral — doortiles
include sits directly before the doors include); flag-on A/B emu logs
identical incl. per-room `DoorsInRoom` counts (121:0, 5:5, 1:0, 126:1) and the
door-warp entry into 126. World seg now 6699/8192 used; BanksDEF regains
~3.7KB when the flag is on.

## Phase C5 — SHIPPED 2026-07-05: room layouts in the world bank (= D0)

`data/rooms.asm` (idxRooms + RoomNNN layouts + MetaTileSetIDs + idxMetatileSet,
~8.9KB) moved to **two dedicated layout segments** (`WORLD_LSEG1/2 = WORLD_SEG
+1/+2`) assembled as ONE contiguous `#6000-#9FFF` region so idxRooms pointers
stay plain 16-bit. Reader design: **cache-to-RAM at render** — `CacheRoomLayout`
(hooks/worldbank.asm) maps BOTH windows (`MapSeg60`+new `MapSeg80`), copies the
current room's 48-byte layout to `CurRoomLayout` and resolves the metatile-set
pointer into `CurRoomMetaPtr` (both APPENDED to Variables.asm — RAM map end
F0FF→F132, stack at F0F0 grows down, no address shifts). `RenderRoom` calls it
at entry (before its stock `SetBanks_D_E_F`), then reads layout from RAM while
metatile DEFINITIONS stay in BanksDEF exactly as stock — this dissolves the
interleaved layout/metatile #6000-window conflict. Binoculars re-render goes
through the same path, so the cache is per-render fresh.

**TRAP #5 — the big one (cost three debug rounds): BanksDEF mixes DATA and
CODE, and the code's SEGMENT placement is part of the ABI.** `UpdateSprites`/
`saveload`/`ending`/`drawlaserbeams` are called through `SetBankInA0_F`, which
maps seg F at #A000 ONLY (the callers run in segs 1/2 and must stay mapped).
Evicting ~12.7KB of data shifted `UpdateSprites` out of segment F; its callers
then executed unrelated seg-2 bytes — which happened to write Room/PlayerX
through IX (left = ItemsInTheRoom from DrawRoomItems) and fall into SetShotSpr
with NumSprites=126, trampling C5D4+/C87F+ RAM only on door-room loads. Fix:
an `IF (WORLDBANK) ds (#0A000-$) / ASSERT` **pins the DEF code block to
segment F**; the pad IS the reclaimed headroom (grow metatiles above it, the
pad shrinks, code stays pinned, ASSERT fails loudly if it ever can't). Also
fixed en route: `idxMetatileSet` lives INSIDE rooms.asm (moved with it), so
the cache resolves the metatile-set pointer rather than the raw nibble.
Audited the same hazard for Banks456's evictions: its code block (hooks +
addroomitems + checkpoints scanner) stays in seg 6 (hooks file `ASSERT >=
#A000` guards it).

**Payoff measured (flag on)**: BanksDEF free = **12,571 bytes ≈ 3,140
metatiles** (seg E 6,150 + seg F 6,421); layout window has 7,488 bytes spare;
first world segment unchanged (6,699/8,192). Verified: flag-off md5 unchanged;
A/B emu logs byte-identical incl. **RoomTileBuffer checksums per room** (the
render is provably identical), shot-struct RAM clean, and the full
items/actors/doors/radio/conns battery. `tools/wbtest.tcl` now also dumps the
map checksum + shots array.

## Phase C — 256/512KB: the "world bank" (relocate load-time tables)

New generated bank file `BanksWorld.asm` (segments 13h+, after ext-gfx's 10h–12h; flag
`WORLDBANK equ 1` next to `EXTGFX`, same editor toggle pattern). Only tables read at
**room-load / mode-enter time** move; per-frame data stays put. Hook style: tiny
trampoline at the read site (through `SetBanks`-correct mapping — see the ROM-512KB
KEY GOTCHA about `BankIn` shadows), dispatcher + data inside the world segment, restore
banks after. Hook-byte scarcity in seg 0 (70 B free) is the known tight spot — keep
resident additions to `ld a,SEG / call MapWorld`-sized stubs; the ExtDivert cart-header
gap is spent.

Relocations, in risk order (each is its own commit + selftest + openMSX check):

| # | table | from | read sites / when | frees | risk |
|---|---|---|---|---|---|
| C1 | items-in-rooms + actors-in-rooms | 456 | **SHIPPED — see above** | ~2.1K in 456 ✓ | done |
| C2 | connections (full 251×4, = A5) | 456 | **SHIPPED — see above** | ~0.6K in 456 ✓ | done |
| C3 | radio calls | DEF | **SHIPPED — see above** | ~0.9K in DEF ✓ | done |
| C4 | doors | DEF | **SHIPPED — see above** | ~2.9K in DEF ✓ | done |
| C5 | room layouts + idxRooms | DEF | **SHIPPED — see above** | ~12.5K in DEF total ✓ | done |
| C6 | texts | ABC | DecodeText (in-game pickups, radio, menus — many entry points) | ~5.8K in ABC | HIGH — do last, or skip until text volume demands it |

After C1–C5: **Banks456** ≈ 3.3K free → paths/respawn growth (Phase B payoff);
**BanksDEF** ≈ 12K free → metatiles can roughly double (more/bigger metatile sets for
new art); **BanksABC** keeps its 0.7K (+5.8K if C6) → more actor sprite data for
mgsprite-authored enemies. Each world table gets its own 8KB segment ceiling — enough
for all 251 rooms fully populated (largest mover, layouts, is 8.9K shared-block data
that dedupes; if a fully-authored world ever exceeds 8K, split across two world
segments the way ext gfx already does with `SegBaseExt`).

ROM tier lands at 256KB with EXTGFX+WORLDBANK (segs 10h–~18h); 512KB stays reserved for
future consumers (byte-wide tileset ids, sprite/music banks) exactly as ROM-512KB-PLAN
decided — the adaptive sizer picks the tier automatically either way.

## Editor / tooling work per phase

- Codecs: extend counts/ranges (A1–A3, A5) — they already parse by label, so C-moves
  need **zero** codec changes; add `selftest` coverage for the new ranges.
- Editor: lift the UI guards tied to old ranges (item-room 122–217 gating, path-room
  cap); dashboard budget tracker already shows per-segment free — add a "world bank"
  row when WORLDBANK is on.
- `tools/genworldbank.py` (mirror of `genextgfx.py`): emits `BanksWorld.asm` from the
  same `data/*.asm` includes so the source of truth stays the data files.

## Verification gates (every step)

1. `python tools/build.py` — 0 errors, expected tier, byte-diff limited to the touched
   region when the step claims neutrality.
2. Codec selftests (mgmap/mgpath/mgradio/mgprisoner) — byte-exact round-trip.
3. openMSX: enter a room exercising the moved table (spawn actors, take item, open
   door, trigger radio, cross a connection both ways, patrol a route).
4. `/api/validate` sweep clean (route coverage, metatile/item OOB).
