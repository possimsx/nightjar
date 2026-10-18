# 08 — Graphics: formats & the `mggfx.py` tool

How the tile graphics are stored, and the tool that decodes them to PNG so they can be
re-skinned. Reverse-engineered from `Decode{1,2,3}bppTile` in `Banks0123.asm` and verified
by decoding the Konami + Metal Gear logos to recognisable images.

---

## 1. Where graphics live

| Kind | Where | Editable how |
|------|-------|--------------|
| **Palettes** | `data/palettes.asm` (+ `DefaultPalette` in `Banks0123.asm`) | **Plain data.** Preview with `tools/mgpal.py`. Format below. |
| **Font** | `gfx/font.asm` | 1bpp, 8 bytes per 8×8 glyph, 1 byte = 1 row (MSB = leftmost). Directly editable bit patterns. |
| **Tile graphics** (buildings, logos, sprites, portraits, items…) | `gfx/*.asm` | **Compressed 1/2/3bpp** — use `tools/mggfx.py` to decode/preview. |

Each room/area uses a **tileset** (`data/roomtileset.asm`) whose tiles are decoded into VRAM
at load time; per-pixel colours come from the active **palette**.

### Palette format (V9938 "RB0G") — get this right or colours scramble

Each colour is **2 bytes**: `byte1 = (R<<4) | B`, `byte2 = G`. Every channel is **0–7**
(MSX2 9-bit colour). Note the order is **R, B, then G** — *not* R,G,B.

* **`DefaultPalette`** (in `Banks0123.asm`): 16 base colours, `db (R<<4)|B, G` ×16, no index.
  Set once at boot. Rooms only override a few slots, so the base greens here drive the whole
  game's look.
* **`data/palettes.asm`** (room/sprite/menu overrides): `db colorIndex, (R<<4)|B, G` … `0FFh`.
  Room palettes typically set only slots 1, 3, 5, 9 (+ sometimes `0Ch`); slots they don't set
  keep the `DefaultPalette` value.

Preview any of them:

```sh
python tools/mgpal.py render            # all palettes -> tools/palettes.png
python tools/mgpal.py render RoomPalette # filter by name
```

(Swatch grid: 16 slots per row; a yellow tick marks the slots that palette actually defines.)

**Quick re-skin lever:** changing the green base colours (slots 2, 3, 12) in `DefaultPalette`
cold-shifts the entire game. NIGHTJAR already does this — greens → teal/cyan
(`db 15h,5` / `db 37h,7` / `db 4,3`), leaving reds (alerts), blue (water), salmon (skin) and
greys (steel) intact.

## 2. Compression formats

VRAM is MSX2 **SCREEN 5** (16 colours, 4 bits/pixel). Tiles are 8×8. The on-disk packed
formats (decoded by the engine at load):

* **1bpp** — 8 bytes/tile; 1 byte = 1 row of 8 px; bit (MSB-first) set → pen colour `C`,
  clear → colour 0. Used for the font, the Konami logo, simple icons. The pen colour is a
  parameter (`C` in the load call).
* **2bpp** — 16 bytes/tile; each row = `[plane0, plane1]`; pixel index `(plane1_bit<<1)|plane0_bit`
  (0–3) → `colortab[index]`.
* **3bpp** — 24 bytes/tile; each row = `[plane0, plane1, plane2]`; index 0–7 → `colortab[index]`.

`colortab` is the 8-entry **`BufferColor`** table the engine loads *before* decoding (e.g. the
Metal Gear logo loads `MGLogoColors: db 0,2,3,4,5,9,10,14`). It maps the packed index to a
VRAM colour 0–15; the palette then maps that to RGB.

Bit/plane order (important for any encoder): **byte0 = lowest plane, last byte = highest
plane; within a byte the MSB is the leftmost pixel.**

## 3. `tools/mggfx.py`

Decodes a labelled gfx block to PNG (scaled, with a tile grid), optionally **assembling**
tiles into their on-screen layout via a tilemap table.

```sh
python tools/mggfx.py list                      # known assets
python tools/mggfx.py decode mglogo             # assembled "METAL GEAR" -> tools/mglogo.png
python tools/mggfx.py decode mglogo --sheet     # raw 70-tile sheet instead
python tools/mggfx.py decode konami1 --scale 8

# any block, ad hoc:
python tools/mggfx.py decode-raw --file gfx/items.asm --label gfxItems \
       --bpp 2 --tiles 32 --colors 0,14,7,1 --cols 8 -o items.png
```

* Output uses the **MSX2 default 16-colour palette** for preview (shapes are faithful; exact
  hues depend on the game's runtime palette — pass real palette colours later if needed).
* **Assets registry** (`ASSETS` dict in the tool) records each known graphic's
  `file/label/bpp/tiles/colors/cols` and optional `maps` (tilemap tables → assembled view).
  Add new graphics there as you identify their load parameters (bpp + tile count + the
  `BufferColor`/pen colour from the `Load*bppTile` call site in `Banks0123.asm`).

### Finding a graphic's parameters

For any `gfx*` label, find its `Load1bppTiles` / `Load2bppTile` / `Load3bppTiles` call in the
code: `B` = tile count, `C` = pen colour (1bpp), and the nearby `BufferColor`/`ColorsTileset`
load = the `colortab` (2/3bpp). That's everything `mggfx.py` needs.

## 4. Editing graphics (the encoder)

`mggfx.py` also **re-encodes** an edited PNG back into packed `db` bytes and writes it into the
`.asm`. The edit loop:

```sh
python tools/mggfx.py export mglogo --scale 8 -o tools/mglogo_edit.png   # clean sheet, no grid
#  ... edit tools/mglogo_edit.png in any pixel editor, at 8x scale ...
python tools/mggfx.py encode mglogo --png tools/mglogo_edit.png --scale 8   # writes gfx/metalgearlogo.asm
python tools/mggfx.py encode mglogo --png ... --dry                         # preview byte count only
sjasm MetalGear.asm MetalGear.rom
```

* `export` writes the **sheet** layout (tile *i* at grid position *i*) at the chosen scale,
  **no grid lines** — that's the canvas the encoder reads back. (`decode` with a tilemap is for
  *viewing* the assembled image; encode always uses sheet order.)
* **Paint only with the asset's real palette colours** (the ones you see in the decode).
  `encode` matches each pixel to the nearest MSX colour, then back to a packed index via the
  `colortab`. For **1bpp** there are only two colours — the **pen** (`colors[0]`) and
  background (0); any other colour collapses to background.
* **Lossless & safe:** `python tools/mggfx.py selftest` confirms decode→pack reproduces the
  original bytes for every registered asset; a full export→encode→rebuild leaves the ROM
  **byte-identical** (CRC unchanged). So an unedited round-trip never corrupts anything.

> Previews/edit sheets are written to `tools/*.png` (git-ignored).
>
> **`db` formatting gotcha (handled by the tool):** sjasm hex literals must start with a
> digit — `0Fh`/`0FFh`, never `Fh`/`FFh`. The encoder formats bytes accordingly.
