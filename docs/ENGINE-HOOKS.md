# Engine hooks & stock parity

Goal: keep the **engine** (the original Manuel Pazos disassembly) assembling
**byte-identical** whenever our additions are switched off, so we can always fall
back to the stock ROM and reason about what we changed.

## Two independent axes

1. **Engine code** — `Banks*.asm`, `logic/`, `constants/`. Additions here are
   gated by feature flags; with all flags `0` the assembled engine is identical
   to stock. This is what the hook convention below protects.
2. **Game content** — `data/`, `gfx/`. The NIGHTJAR rework (palettes, text,
   sprites, logo, names, radio data) lives here and is *intentionally* changed.
   To get stock content, `git checkout data/ gfx/` — there is no flag for it.

A truly byte-identical *original Metal Gear* ROM therefore needs **both**: all
feature flags off **and** stock content.

## The hook convention

- **All feature flags live in [`features.asm`](../features.asm)** (included near
  the top of `MetalGear.asm`, before the banks). One `equ` per feature, default
  `0`. (`JAPANESE` is a stock flag and stays in `MetalGear.asm`.)
- **New engine code lives in its own file** — a `hooks/<feature>.asm` body and/or
  a `Banks<feature>.asm` bank — never inline in a stock file.
- **Stock files contain only a thin shim**:

  ```
      IF (FLAG)
          include "hooks/feature.asm"   ; or: call FeatureRoutine
      ELSE
          <the exact original bytes>     ; padding / the stock call / nothing
      ENDIF
  ```

  The `ELSE` branch must reproduce the original bytes so `FLAG=0` is byte-neutral.

## Why a shim stays inline (the sjasm limit)

sjasm 0.39 **appends output sequentially**; `org` only sets the label address, it
cannot seek back and write bytes at an earlier ROM offset. So a hook that must sit
at a fixed stock address (e.g. code in the cartridge-header gap, or swapping one
`call`) needs its 3-line `IF/ELSE` shim *at that point* in the stock file. Only
the code **body** moves to `hooks/`. You cannot remove the shim entirely.

## Worked example — EXTGFX (extended tilesets)

| Piece | Where | Off (`EXTGFX 0`) |
|---|---|---|
| Flag | `features.asm` | `EXTGFX equ 0` |
| Divert body | `hooks/extgfx.asm` (`ExtDivert`) | not included |
| Header-gap shim | `Banks0123.asm` (~l.21) | `ELSE` = stock `dw 0` padding |
| Call-site shim | `Banks0123.asm` (LoadRoomTiles) | `ELSE` = `call SetBanks_7_8_9` |
| Tileset bank | `BanksExtGfx.asm` | not included |
| ROM sizing | `tools/build.py` (external) | stays 128KB |

Verified: `EXTGFX 0` → md5 `e8c260a29aa082e5330827364aa86ba8` (unchanged);
`EXTGFX 1` → 256KB, builds green, runs in openMSX.

## Adding the next engine feature

1. Add `NEWFEAT equ 0` to `features.asm`.
2. Put the code in `hooks/newfeat.asm` (and/or a `Banks*.asm` for bulk data).
3. Add the minimal `IF (NEWFEAT) … ELSE <stock> ENDIF` shim(s) at the touch
   point(s) in the stock file.
4. Confirm `NEWFEAT 0` still builds to the same md5; confirm `NEWFEAT 1` works.
5. If the editor toggles it, point its flag read/write at `features.asm`
   (see `get_extgfx`/`set_extgfx` in `tools/editor/server.py`).
