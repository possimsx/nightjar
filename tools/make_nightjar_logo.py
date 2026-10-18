#!/usr/bin/env python3
"""
Generate the NIGHTJAR title logo and write it into the ROM source, reusing the
Metal Gear logo's structure (no engine code changes):

  gfxMetalGearLogo  (gfx/metalgearlogo.asm)  - 70 tiles, 3bpp, colortab[0,2,3,4,5,9,10,14]
  MetalTilesDat     (logic/mainmenu.asm)     - 13x4 tilemap, drawn at the top  -> "NIGHT"
  GearTilesDat      (logic/mainmenu.asm)     - 9x4  tilemap, drawn below       -> "JAR"

Two lines (NIGHT / JAR) mirror METAL / GEAR. Tiles are de-duplicated so the whole
logo fits in the 70-tile budget. Cold chrome gradient: gray -> cyan -> blue
(VRAM colours 14, 3, 4 — all in the colortab; with the NIGHTJAR palette 3=cyan, 4=blue).

Run:  python tools/make_nightjar_logo.py   (then rebuild the ROM)
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mggfx

FONT = "C:/Windows/Fonts/ariblk.ttf"
COLORTAB = [0, 2, 3, 4, 5, 9, 10, 14]   # gfxMetalGearLogo BufferColor

# chrome gradient, one colour per 8px TILE ROW (so solid stems dedup across columns).
# all values are in COLORTAB. Rows: gray highlight, cyan, cyan, blue.
_BANDS = [14, 3, 3, 4]
def grad(y):
    return _BANDS[(y // 8) % 4]


def fit_font(word, maxw, maxh):
    for size in range(40, 9, -1):
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(word)
        if (b[2] - b[0]) <= maxw and (b[3] - b[1]) <= maxh:
            return f, b
    return ImageFont.truetype(FONT, 10), ImageFont.truetype(FONT, 10).getbbox(word)


def render_word(word, tiles_w, maxh, tiles_h=4):
    """Return tiles_h x tiles_w grid; each cell an 8x8 list of VRAM colours."""
    W, H = tiles_w * 8, tiles_h * 8
    base = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(base)
    f, b = fit_font(word, W - 2, maxh)
    w, h = b[2] - b[0], b[3] - b[1]
    d.text(((W - w) // 2 - b[0], (H - h) // 2 - b[1]), word, fill=255, font=f)
    m = base.load()
    cells = [[None] * tiles_w for _ in range(tiles_h)]
    for ty in range(tiles_h):
        for tx in range(tiles_w):
            tile = [[0] * 8 for _ in range(8)]
            for yy in range(8):
                for xx in range(8):
                    if m[tx * 8 + xx, ty * 8 + yy] > 128:
                        tile[yy][xx] = grad(ty * 8 + yy)
            cells[ty][tx] = tile
    return cells


def build(maxh):
    night = render_word("NIGHT", 13, maxh)
    jar = render_word("JAR", 9, maxh)
    tile_list = []
    index = {}

    def tile_id(tile):
        if all(all(p == 0 for p in row) for row in tile):
            return 0
        key = tuple(tuple(r) for r in tile)
        if key not in index:
            tile_list.append(tile)
            index[key] = len(tile_list)
        return index[key]

    metal_map = [tile_id(night[ty][tx]) for ty in range(4) for tx in range(13)]
    gear_map = [tile_id(jar[ty][tx]) for ty in range(4) for tx in range(9)]
    return tile_list, metal_map, gear_map


def main():
    # auto-shrink until the logo fits the 70-tile budget
    for maxh in range(30, 9, -1):
        tile_list, metal_map, gear_map = build(maxh)
        if len(tile_list) <= 70:
            print("fit at maxh=%d -> %d unique tiles" % (maxh, len(tile_list)))
            break
    else:
        raise SystemExit("could not fit logo in 70 tiles")
    n = len(tile_list)

    # pad to exactly 70 tiles (Load3pppTile count stays 0x46)
    blank = [[0] * 8 for _ in range(8)]
    while len(tile_list) < 70:
        tile_list.append(blank)

    gfx_bytes = mggfx.pack_tiles(tile_list, 3, COLORTAB)
    assert len(gfx_bytes) == 70 * 24

    mggfx.write_block("gfx/metalgearlogo.asm", "gfxMetalGearLogo", gfx_bytes, perline=16)
    mggfx.write_block("logic/mainmenu.asm", "MetalTilesDat", metal_map, perline=13)
    mggfx.write_block("logic/mainmenu.asm", "GearTilesDat", gear_map, perline=9)
    print("wrote gfxMetalGearLogo (%d B), MetalTilesDat (%d), GearTilesDat (%d)" %
          (len(gfx_bytes), len(metal_map), len(gear_map)))


if __name__ == "__main__":
    main()
