# Plan: data-driven hazard rooms (`RoomFlags`)

**Status: SHIPPED (unified, 128 KB).** A per-room `RoomFlags` byte now drives all four
hazards; the old per-hazard lists/`cp` chains are gone. Build-verified 0 errors / 128 KB,
codec selftest passes, behaviour-neutral seed.

## Shipped design (unified `RoomFlags` + `RoomFlags2`)
- **Tables:** `RoomFlags` and `RoomFlags2` (251 bytes each, 1 byte/room) in **seg 12**
  (BanksABC), read by one `CacheRoomFlags` routine into two RAM bytes.
  - `RoomFlags` bits (full): `0 dark · 1 gas · 2 electric · 3 water · 4 deep water ·
    5 moving lasers (Banks0123 DrawMovingLasers) · 6 laser-beam room (drawlaserbeams.asm) ·
    7 short camera lasers (lasershot.asm/damagelaser.asm)`.
  - `RoomFlags2` bits: `0 capture trap (common.asm) · 1–7 spare`.
  Seeded from the original rooms (behaviour-neutral). **Laser** (bit 6) replaced the
  `cp 24/25/72` chain in `DrawLaserBeams` (seeded 24/25/72). **Short camera lasers** (bit 7)
  replaced the two `cp 111` checks in `InitLaserShot`/`ChkLaserShot` (seeded 111). **Moving
  lasers** (bit 5) replaced `cp 72` in `DrawMovingLasers` (seeded 72). Room 72 carries both
  bit 5 and bit 6.
- **`RoomFlags` filled up → `RoomFlags2` added.** Bit 5 originally held the capture trap;
  when moving lasers needed a home and `RoomFlags` was out of bits, capture moved to
  `RoomFlags2` bit 0 (freeing bit 5). `CacheRoomFlags` now caches **both** tables (two
  extra `ld/ADD_HL_A/ld` blocks) into `CurRoomFlags` / `CurRoomFlags2` (the latter reuses
  the verified-unused `UnusedVar2` RAM slot — renamed, not inserted, per the Variables.asm
  alignment rule). Both bytes are always-mapped RAM, so every reader stays bank-free.
  openMSX-verified (`tools/lasertest.tcl`): room 72 → `CurRoomFlags`=0x60 (moving+laser),
  24 → 0x40, 111 → 0x80, 8 → `CurRoomFlags2`=0x01 (capture), all others clear.
  `RoomFlags2` bits 1–7 are the new headroom for future per-room properties.
- **Cache:** `InitRoom2` (the load point both `InitRoom` and game-start `InitGame5` reach)
  does `SetBanks_A_B_C → CacheRoomFlags → SetBanks1_2_3`, copying `RoomFlags[Room]` into the
  1-byte RAM `CurRoomFlags` (Variables.asm). Every check is then `bit N,(CurRoomFlags)`,
  bank-free.
- **Checks rewired:** dark (`SetRoomPal` bit0), gas (`ChkGasRooms` bit1), electric
  (`ChkElectricFloor` bit2 + `ElectricTiles[gfx]`), water (`ChkWater` bit3 + `WaterTiles[gfx]`
  base, tiles normalized so the classifier is unchanged), deep-water shadow (`ChkDeepShadow`
  bit4). Deleted `DarkRooms`, `GasRooms`, `RoomsWater`.
- **Tile-coupled hazards** have a per-**tileset** side table (indexed by `CurrentTileSet`):
  `ElectricTiles[gfx]` = the live-floor tile pair (gfx0 6061h, gfx1 4041h, gfx2 4546h);
  `WaterTiles[gfx]` = the base of the 8 water tiles (gfx0 6Fh). So new tilesets can define
  electric/water tiles. Both bank-free (RAM `CurrentTileSet` + table in the check's segment).
- **Editor:** room info-panel checkboxes ☾dark ☣gas ⚡electric 💧water flip the bit in
  `RoomFlags[room]` (surgical `_set_packed_byte`); badges read live from the table; no per-
  hazard limit — any/all rooms can carry any flag.

Still needs openMSX confirmation (the seed is behaviour-neutral, but it's a real engine
change). Original analysis kept below for reference.

---

**Earlier status (superseded):** v1 read-side SHIPPED for DARK; GAS already data-driven; the
unified `RoomFlags`-byte design was then a future option — now done.

## v1 implemented (dark rooms → data list)

The packed `RoomFlags`-byte + RAM cache turned out heavier than the tight 128 KB ROM
allows safely (every base segment is near-full; growing `SetRoomPal` shifts the resident
`#6000` boundary). So v1 uses the **same proven shape as `GasRooms`** — a `0FFh`-
terminated list — which swaps in at **exactly the same byte size**, so no segment moves:
- `data` → `DarkRooms: db 123,124,125,220,221,0FFh` at the end of **Banks456** (segs
  4/5/6, mapped when `SetRoomPal` runs; consumes the bank's FF pad, zero relocation).
- `SetRoomPal` → the `cp 220/221/126/123` chain replaced by a list scan of `DarkRooms`
  (net 0 bytes in seg 0: the top `ld hl,IdsRoomPal` moves down to `SetRoomPal1`).
- **Gas** unchanged — it's already the `GasRooms` list; "more gas rooms" = edit that list.

Build-verified: assembles clean, ROM stays 128 KB, byte-diff vs baseline = **57 bytes,
all inside `SetRoomPal` + the `DarkRooms` data** (no relocation). Behaviour-neutral: the
dark set {123,124,125,220,221} is identical to the old hardcoded ranges. **Still needs
openMSX confirmation** (enter a dark room without/with the flashlight). Next: editor UI to
edit the `DarkRooms`/`GasRooms` lists.

The unified single-byte `RoomFlags` design below stays on file for if/when we want one
property table with spare flag bits (would need freed segment space or the 256 KB tier).

---

**Original proposal (unified RoomFlags byte) — kept for reference:**
**Goal:** replace the engine's hardcoded `cp <room-id>` hazard checks with a per-room
**property byte**, so the map can have *any* number of dark/gas rooms (and future
hazards) without patching ASM. Editable as checkboxes in the map editor.

---

## 1. Current state (why this is worth doing)

| Hazard | Where | Mechanism | Data-driven now? |
|---|---|---|---|
| **Gas** | `logic/damagegas.asm` `ChkGasRooms` | scans `GasRooms` list (`ld b,9`): 29,94,96,97,98,100,101,112,114 | ✅ a fixed-count list |
| **Dark** | `Banks0123.asm` `SetRoomPal` | `cp 220/221` + `cp 126`(nc)/`cp 123`(c) → rooms 123,124,125,220,221 | ❌ hardcoded |
| **Electric** | `logic/damageelectric.asm` `ChkElectricFloor` | `cp 16/37/40/110/116`, **each with its own floor-tile pair** (`bc`) | ❌ hardcoded + tile-coupled |

Gas already works by data; dark is pure `cp`; electric is the awkward one (needs the
per-room electrified-tile ids, so it does **not** collapse to a boolean — **out of
scope** for v1, see §8).

## 2. Design — one `RoomFlags` byte per room

A new table, 251 bytes (rooms 0–250), one byte each:

```
bit 0  DARK   ; needs flashlight, else black palette (SetRoomPal)
bit 1  GAS    ; needs gas mask, else gas damage   (ChkGasRooms)
bit 2..7      ; reserved (electric, water, barrels, …)
```

Constants in `constants/` (e.g. `RF_DARK equ 1`, `RF_GAS equ 2`).

**Seed values** = exactly today's behaviour, so the change is behaviour-neutral until
the designer edits a flag:
- DARK: 123,124,125,220,221
- GAS: 29,94,96,97,98,100,101,112,114

## 3. Data placement & bank addressing  *(the main risk — settled below)*

**Memory map (Konami 8KB mapper, from `SetBanks` Banks0123.asm:408,658):**
| Window | Mapping | Notes |
|---|---|---|
| #4000–5FFF | **segment 0 — FIXED, always mapped** | boot, mapper, `SetRoomPal`, `SetBanks` live here |
| #6000–7FFF | switchable (default seg1; `SetBanks_4_5_6`→seg4) | |
| #8000–9FFF | switchable (default seg2 → seg5) | |
| #A000–BFFF | switchable (default seg3 → seg6) | |
| #C000–FFFF | RAM | |

**The two read sites run with different segments paged in:**
- `SetRoomPal` is in the fixed segment 0; it `call SetBanks_4_5_6` to map **segs 4/5/6**
  into #6000–BFFF and read `IdsRoomPal`/`RoomPaletteN` (which live in **Banks456**).
- `ChkGasRooms`/`GasRooms` are in **`logic/common.asm`, included near the end of
  Banks0123 → a switchable segment (≈seg 3)**, read in the **default** bank state.

So a table at #6000–BFFF can't be seen directly by both (different segments mapped).

**Space reality (`rom_budget`, current 128 KB build):** segments 0,1,2 are **full**
(0 free trailing), seg 3 has **~81 bytes**. So a 251-byte table won't drop into the
resident region as-is.

**Chosen approach — cache the current room's flag byte at room load.** The flags only
change on a room transition, so read one byte then and stash it in RAM; both hot sites
read that always-mapped byte. Costs **1 byte of RAM**, no table copy.
- Master `RoomFlags`, **packed 2 bits/room (DARK,GAS) = 63 bytes**, in **seg 3** (81 B
  free, where `ChkGasRooms` lives); deleting the old `GasRooms` table reclaims 9 B.
- `SetRoomPal` runs on every room entry (Banks0123.asm:11537, after `RenderRoom`) — the
  cache point. At room load the **default banks are mapped (seg 3 present)**, so a small
  step reads `RoomFlags[room]` directly (no `SetBanks`) into a 1-byte `CurRoomFlags`.
- `SetRoomPal` DARK check → `ld a,(CurRoomFlags) / bit RF_DARK,a`.
- `ChkGasRooms` (per-frame) → `ld a,(CurRoomFlags) / bit RF_GAS,a` — replaces the list
  scan entirely; one always-mapped RAM read, zero banking.
- Zero-init `CurRoomFlags` at boot; room load always precedes the first per-frame gas
  check, so the cache is valid before it's read.

Budget note: segs 4/5/6 (with `IdsRoomPal`) are full (seg6 only 52 B), so the master
can't ride along there; seg 3's 63-B packed table keeps the ROM at 128 KB. *Alternative:*
master in a far/reserved 512 KB segment + a `SetBanks`/restore in the cache step (frees
placement, bumps ROM to the 256 KB tier).

## 4. ASM patches

**`SetRoomPal`** — replace the five `cp`/`jr` dark checks (~20 bytes) with (~12 bytes,
net smaller, so no bank overflow):
```
    ld   hl, RoomFlags
    ld   a, (Room)
    call ADD_HL_A            ; preserve B = Room for SetRoomPal1
    bit  RF_DARK, (hl)
    jr   nz, ChkFlashLight
    jr   ChkGogglesPal
```
(`cp 251` ending-room guard stays. Keep B=Room intact — `ADD_HL_A` uses A only.)

**`ChkGasRooms`** — replace the list scan + the `GasRooms` db with:
```
    ld   a, (Room)
    ld   hl, RoomFlags
    call ADD_HL_A
    bit  RF_GAS, (hl)
    jr   nz, ChkGasMask
    ret
```
Delete the `GasRooms:` table (9 bytes freed).

## 5. Codec (`tools/mgmap.py`)

- Add `ROOMFLAGS_F` + parse `RoomFlags` into `model["room_flags"]` (251 bytes) in
  `load_model`, and write it back in `export`/regen. Extend the **selftest** so the
  round-trip stays byte-identical (this is the project's core guarantee).

## 6. Editor (`tools/editor/`)

- `server.py`: `GET /api/room/<id>/objects` (or a new `/flags`) returns the room's flag
  bits; `POST /api/room/<id>/flags {dark,gas}` does a **surgical single-byte edit** of
  `RoomFlags` (same pattern as `_set_packed_byte`).
- `index.html`: in the info panel, a **Hazards** row with `☾ Dark` / `☣ Gas`
  checkboxes. On save, refresh the room render (dark flag changes the palette path).
- The existing **special-room badges** then become partly *live* (driven by the flag
  for dark/gas instead of the hardcoded list).

## 7. Test plan (emulator — required)

1. Build with seeded flags → diff nothing-changed behaviour: dark rooms 123/220 still
   black without flashlight; gas room 94 still damages without mask.
2. Editor: set DARK on a fresh room + GAS on another, rebuild, verify both in openMSX.
3. Clear a flag on an old hazard room, verify it's now safe.
4. `mgmap selftest` passes; ROM size within budget.

## 8. Out of scope for v1

- **Electric** floors (16/37/40/110/116): need a companion `(room → tile-pair)` table,
  not a boolean — separate task. Could become `bit 2 ELECTRIC` + an `ElectricTiles`
  lookup later.
- Water (70), rolling-barrels (56/200), mines, lasers — each has bespoke logic; fold in
  per-bit only if a clear data shape exists.

## 9. Open questions

1. Segment for `RoomFlags` that is paged in for **both** `SetRoomPal` and `ChkGasRooms`
   (§3) — decides whether any bank-switch wrapper is needed.
2. Keep `RoomFlags` as a standalone `data/roomflags.asm`, or append near `IdsRoomPal`?
   (Standalone is cleaner for the codec; placement is bank-driven.)
3. Do we want the editor badges to read the *flag* (live) or stay doc-mirrored? (Once
   flags exist, prefer live for dark/gas; keep the static `_SPECIAL` table for the
   non-flag specials.)
