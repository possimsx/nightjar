#!/usr/bin/env python3
"""
mggfx.py - Metal Gear (MSX) graphics codec for the NIGHTJAR rework.

Decodes the compressed tile graphics in gfx/*.asm into PNGs you can actually see
(and, later, edit + re-encode). Formats (from Decode{1,2,3}bppTile in Banks0123.asm):

  1bpp : 8 bytes/tile, 1 byte = 1 row of 8 px. MSB = leftmost. bit set -> color C,
         clear -> color 0.
  2bpp : 16 bytes/tile, each row = [plane0, plane1]; pixel index(0-3) =
         (plane1_bit<<1)|plane0_bit  ->  colortab[index].
  3bpp : 24 bytes/tile, each row = [plane0, plane1, plane2]; index(0-7) ->
         colortab[index].

colortab = the 8-entry BufferColor the engine loads before decoding (maps the raw
index to a VRAM colour 0-15). Pixels are rendered with the MSX2 default palette
unless --palette gives explicit colours.

Usage:
  python tools/mggfx.py list
  python tools/mggfx.py decode <asset> [-o out.png] [--cols N] [--scale N]
  python tools/mggfx.py decode-raw --file gfx/x.asm --label lbl --bpp 3 \
        --tiles 70 --colors 0,2,3,4,5,9,10,14 --cols 10 -o out.png
"""
import sys, re, os, argparse
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

# MSX2 / TMS9918 default 16-colour palette (RGB). Index 0 shown as black here.
MSX_PAL = [
    (0, 0, 0), (0, 0, 0), (62, 184, 73), (116, 208, 125),
    (89, 85, 224), (128, 118, 241), (185, 94, 81), (101, 219, 239),
    (219, 101, 89), (255, 137, 125), (204, 195, 94), (222, 208, 135),
    (58, 162, 65), (183, 102, 181), (204, 204, 204), (255, 255, 255),
]

# Known assets: name -> dict(file,label,bpp,tiles,colors,cols[, maps])
# colors is the 8-entry BufferColor; for 1bpp it's the single pen colour.
# maps (optional): list of (mapfile, maplabel, width) tile-arrangement tables
#   (1-based tile index into the decoded list, 0 = blank) used to assemble the
#   graphic as it appears on screen.
ASSETS = {
    "konami1":  dict(file="gfx/konamilogo.asm", label="gfxKonamiLogo",  bpp=1, tiles=13, colors=[7], cols=13),
    "konami2":  dict(file="gfx/konamilogo.asm", label="gfxKonamiLogo2", bpp=1, tiles=13, colors=[7], cols=13),
    "mglogo":   dict(file="gfx/metalgearlogo.asm", label="gfxMetalGearLogo", bpp=3, tiles=0x46,
                     colors=[0, 2, 3, 4, 5, 9, 10, 14], cols=10,
                     maps=[("logic/mainmenu.asm", "MetalTilesDat", 13),
                           ("logic/mainmenu.asm", "GearTilesDat", 9)]),
}


def parse_block(path, label):
    """Collect the byte list for a `label: db ...` block (+ continuation db lines).
    Spans blank lines inside the block (some gfx blocks, e.g. GfxRoof, have blank
    separators yet belong to one label) and stops only at the NEXT label or a
    non-db code line."""
    out = []
    collecting = False
    for ln in open(mgproj.path(path), encoding='latin-1').read().splitlines():
        code = ln.split(';', 1)[0].rstrip()
        if not code.strip():
            continue                                   # span blanks, don't terminate
        m = re.match(r'^(\w+):\s*db\s+(.*)$', code)
        if m:
            if m.group(1) == label:
                out += _vals(m.group(2)); collecting = True
            elif collecting:
                break                                  # a different label ends the block
            continue
        if collecting:
            m2 = re.match(r'^\s+db\s+(.*)$', code)
            if m2:
                out += _vals(m2.group(1))
            else:
                break                                  # any non-db code line ends the block
    return out


def _vals(s):
    out = []
    for t in s.split(','):
        t = t.strip()
        if not t:
            continue
        if t.endswith(('h', 'H')):
            out.append(int(t[:-1], 16))
        elif t.startswith('#'):
            out.append(int(t[1:], 16))
        elif t.startswith('0x'):
            out.append(int(t, 16))
        else:
            out.append(int(t))
    return out


def _bit(byte, col):
    return (byte >> (7 - col)) & 1


def pack_tiles(tiles, bpp, colors):
    """Inverse of decode_tiles: list of 8x8 VRAM-colour tiles -> packed bytes."""
    # invert colortab: VRAM colour -> packed index (lowest index wins on dupes)
    inv = {}
    for i, c in enumerate(colors):
        inv.setdefault(c & 15, i)
    out = bytearray()
    for tile in tiles:
        for row in range(8):
            planes = [0] * bpp
            for col in range(8):
                c = tile[row][col] & 15
                if bpp == 1:
                    idx = 1 if c == (colors[0] & 15) else 0
                else:
                    idx = inv.get(c, 0)
                for p in range(bpp):
                    if (idx >> p) & 1:
                        planes[p] |= (1 << (7 - col))
            out += bytes(planes)   # plane0 (low) .. planeN (high)
    return bytes(out)


def _tok(b):
    if b < 10:
        return str(b)
    s = "%X" % b                 # hex must start with a digit for sjasm
    if s[0] not in "0123456789":
        s = "0" + s
    return s + "h"


def write_block(path, label, data, perline=16):
    """Replace label's `db` block in an .asm file with new bytes."""
    full = mgproj.path(path)
    lines = open(full, encoding='latin-1').read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r'^%s:\s*db' % re.escape(label), ln):
            start = i
            break
    if start is None:
        raise KeyError("label not found: %s" % label)
    end = start + 1
    while end < len(lines) and re.match(r'^\s+db\s', lines[end].split(';', 1)[0]):
        end += 1
    body = [_tok(b) for b in data]
    new = []
    for k in range(0, len(body), perline):
        chunk = ', '.join(body[k:k + perline])
        new.append((("%-20s" % (label + ':')) + 'db\t' + chunk) if k == 0
                   else ('\t\t    db\t' + chunk))
    lines[start:end] = new
    open(full, 'w', encoding='latin-1').write('\n'.join(lines) + '\n')


def decode_tiles(data, bpp, ntiles, colors):
    """Return list of tiles; each tile is 8 rows x 8 cols of VRAM colour (0-15)."""
    tiles = []
    per = {1: 8, 2: 16, 3: 24}[bpp]
    for t in range(ntiles):
        base = t * per
        if base + per > len(data):
            break
        tile = []
        for row in range(8):
            px = []
            if bpp == 1:
                b0 = data[base + row]
                for col in range(8):
                    px.append(colors[0] if _bit(b0, col) else 0)
            elif bpp == 2:
                b0 = data[base + row * 2]
                b1 = data[base + row * 2 + 1]
                for col in range(8):
                    idx = (_bit(b1, col) << 1) | _bit(b0, col)
                    px.append(colors[idx])
            else:  # 3bpp
                b0 = data[base + row * 3]
                b1 = data[base + row * 3 + 1]
                b2 = data[base + row * 3 + 2]
                for col in range(8):
                    idx = (_bit(b2, col) << 2) | (_bit(b1, col) << 1) | _bit(b0, col)
                    px.append(colors[idx])
            tile.append(px)
        tiles.append(tile)
    return tiles


def render_map(tiles, mapvals, width, scale, palette):
    """Arrange tiles per a 1-based tilemap (0 = blank) into width x rows cells."""
    rows = (len(mapvals) + width - 1) // width
    W, H = width * 8, rows * 8
    img = Image.new("RGB", (W, H), (40, 40, 40))
    px = img.load()
    for i, v in enumerate(mapvals):
        if v == 0:
            continue
        if v - 1 >= len(tiles):
            continue
        tile = tiles[v - 1]
        ox, oy = (i % width) * 8, (i // width) * 8
        for y in range(8):
            for x in range(8):
                px[ox + x, oy + y] = palette[tile[y][x] & 15]
    return img.resize((W * scale, H * scale), Image.NEAREST)


def render(tiles, cols, scale, palette, grid=True):
    rows = (len(tiles) + cols - 1) // cols
    W, H = cols * 8, rows * 8
    img = Image.new("RGB", (W, H), (40, 40, 40))
    px = img.load()
    for i, tile in enumerate(tiles):
        ox, oy = (i % cols) * 8, (i // cols) * 8
        for y in range(8):
            for x in range(8):
                px[ox + x, oy + y] = palette[tile[y][x] & 15]
    img = img.resize((W * scale, H * scale), Image.NEAREST)
    if grid and scale >= 4:
        g = img.load()
        for gy in range(0, H * scale, 8 * scale):
            for gx in range(W * scale):
                g[gx, gy] = (60, 60, 60)
        for gx in range(0, W * scale, 8 * scale):
            for gy in range(H * scale):
                g[gx, gy] = (60, 60, 60)
    return img


def nearest_color(rgb, palette):
    best, bi = 1 << 30, 0
    for i, p in enumerate(palette):
        d = (rgb[0] - p[0]) ** 2 + (rgb[1] - p[1]) ** 2 + (rgb[2] - p[2]) ** 2
        if d < best:
            best, bi = d, i
    return bi


def read_png_tiles(path, cols, ntiles, scale, palette):
    img = Image.open(path).convert("RGB")
    px = img.load()
    rows = (ntiles + cols - 1) // cols
    tiles = []
    half = max(scale // 2, 0)
    for t in range(ntiles):
        tx, ty = (t % cols) * 8, (t // cols) * 8
        tile = []
        for row in range(8):
            line = []
            for col in range(8):
                sx = (tx + col) * scale + half
                sy = (ty + row) * scale + half
                line.append(nearest_color(px[sx, sy], palette))
            tile.append(line)
        tiles.append(tile)
    return tiles


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'selftest':
        ok = bad = 0
        for name, v in ASSETS.items():
            data = parse_block(v['file'], v['label'])
            tiles = decode_tiles(data, v['bpp'], v['tiles'], v['colors'])
            repacked = pack_tiles(tiles, v['bpp'], v['colors'])
            n = min(len(data), len(repacked))
            if bytes(data[:n]) == repacked[:n] and len(repacked) == v['tiles'] * {1: 8, 2: 16, 3: 24}[v['bpp']]:
                ok += 1
                print("  OK   %-10s decode->pack identical (%d bytes)" % (name, n))
            else:
                bad += 1
                print("  FAIL %s" % name)
        print("round-trip: %d ok, %d fail" % (ok, bad))
        return
    if cmd == 'export':
        ap = argparse.ArgumentParser()
        ap.add_argument('asset')
        ap.add_argument('--scale', type=int, default=8)
        ap.add_argument('--cols', type=int, default=None)
        ap.add_argument('-o', default=None)
        a = ap.parse_args(sys.argv[2:])
        v = ASSETS[a.asset]
        cols = a.cols or v['cols']
        data = parse_block(v['file'], v['label'])
        tiles = decode_tiles(data, v['bpp'], v['tiles'], v['colors'])
        out = a.o or os.path.join(HERE, a.asset + "_edit.png")
        render(tiles, cols, a.scale, MSX_PAL, grid=False).save(out)
        print("wrote editable sheet %s  (%d tiles, %d cols, scale %d)" %
              (out, len(tiles), cols, a.scale))
        return
    if cmd == 'encode':
        ap = argparse.ArgumentParser()
        ap.add_argument('asset')
        ap.add_argument('--png', required=True)
        ap.add_argument('--scale', type=int, default=8)
        ap.add_argument('--cols', type=int, default=None)
        ap.add_argument('--dry', action='store_true')
        a = ap.parse_args(sys.argv[2:])
        v = ASSETS[a.asset]
        cols = a.cols or v['cols']
        tiles = read_png_tiles(a.png, cols, v['tiles'], a.scale, MSX_PAL)
        data = pack_tiles(tiles, v['bpp'], v['colors'])
        if a.dry:
            print("would write %d bytes to %s:%s" % (len(data), v['file'], v['label']))
        else:
            write_block(v['file'], v['label'], data)
            print("encoded %s -> %s:%s  (%d bytes)" % (a.png, v['file'], v['label'], len(data)))
        return
    if cmd == 'list':
        print("Known assets:")
        for k, v in ASSETS.items():
            print("  %-10s %s %s  bpp=%d tiles=%d%s" %
                  (k, v['file'], v['label'], v['bpp'], v['tiles'],
                   "  (assembled)" if v.get('maps') else ""))
        return
    if cmd == 'decode':
        ap = argparse.ArgumentParser()
        ap.add_argument('asset')
        ap.add_argument('-o', default=None)
        ap.add_argument('--cols', type=int, default=None)
        ap.add_argument('--scale', type=int, default=6)
        ap.add_argument('--sheet', action='store_true', help="raw tile sheet, ignore maps")
        a = ap.parse_args(sys.argv[2:])
        v = ASSETS[a.asset]
        data = parse_block(v['file'], v['label'])
        tiles = decode_tiles(data, v['bpp'], v['tiles'], v['colors'])
        out = a.o or os.path.join(HERE, a.asset + ".png")
        if v.get('maps') and not a.sheet:
            # assemble each map block, stack vertically
            imgs = [render_map(tiles, parse_block(mf, ml), w, a.scale, MSX_PAL)
                    for (mf, ml, w) in v['maps']]
            W = max(i.width for i in imgs)
            H = sum(i.height for i in imgs) + 4 * (len(imgs) - 1)
            combo = Image.new("RGB", (W, H), (40, 40, 40))
            y = 0
            for im in imgs:
                combo.paste(im, (0, y)); y += im.height + 4
            combo.save(out)
        else:
            render(tiles, a.cols or v['cols'], a.scale, MSX_PAL).save(out)
        print("wrote %s  (%d tiles, %d bytes, bpp=%d)" % (out, len(tiles), len(data), v['bpp']))
        return
    if cmd == 'decode-raw':
        ap = argparse.ArgumentParser()
        ap.add_argument('--file', required=True)
        ap.add_argument('--label', required=True)
        ap.add_argument('--bpp', type=int, required=True)
        ap.add_argument('--tiles', type=int, required=True)
        ap.add_argument('--colors', default="0,1,2,3,4,5,6,7")
        ap.add_argument('--cols', type=int, default=16)
        ap.add_argument('--scale', type=int, default=6)
        ap.add_argument('-o', default=None)
        a = ap.parse_args(sys.argv[2:])
        colors = [int(x) for x in a.colors.split(',')]
        data = parse_block(a.file, a.label)
        tiles = decode_tiles(data, a.bpp, a.tiles, colors)
        out = a.o or os.path.join(HERE, a.label + ".png")
        render(tiles, a.cols, a.scale, MSX_PAL).save(out)
        print("wrote %s  (%d tiles, %d bytes)" % (out, len(tiles), len(data)))
        return
    print(__doc__)


if __name__ == '__main__':
    main()
