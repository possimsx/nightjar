#!/usr/bin/env python3
"""
mgpal.py - preview MSX2 palettes from data/palettes.asm as swatch PNGs.

Palette entry format (V9938 "RB0G"):
  data/palettes.asm : db colorIndex, (R<<4)|B, G   ... 0FFh   (per-room/sprite overrides)
  DefaultPalette    : db (R<<4)|B, G                          (16 base colours, in Banks0123.asm)
  Each channel is 0-7.

Usage:
  python tools/mgpal.py render [namefilter]   -> tools/palettes.png
"""
import sys, re, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)


def _pal():
    return mgproj.path(os.path.join("data", "palettes.asm"))

# MSX2 default 16-colour palette as (R,G,B) in 0-7, for slots a palette doesn't set.
MSX_DEF = [
    (0, 0, 0), (0, 0, 0), (1, 6, 1), (3, 7, 3), (1, 1, 7), (2, 3, 7), (5, 1, 1), (2, 6, 7),
    (7, 1, 1), (7, 3, 3), (6, 6, 1), (6, 6, 4), (1, 4, 1), (6, 2, 5), (5, 5, 5), (7, 7, 7),
]


def c8(v3):
    return round(v3 * 255 / 7)


def parse_palettes(path):
    pals = {}
    cur = None
    for ln in open(path, encoding='latin-1').read().splitlines():
        code = ln.split(';', 1)[0]
        m = re.match(r'^(\w+):\s*(.*)$', code)
        body = code
        if m:
            cur = m.group(1)
            pals[cur] = []
            body = m.group(2)
        if cur is None:
            continue
        m2 = re.search(r'\bdb\s+(.*)$', body)
        if not m2:
            continue
        vals = []
        for t in m2.group(1).split(','):
            t = t.strip()
            if not t:
                continue
            if t.endswith(('h', 'H')):
                vals.append(int(t[:-1], 16))
            elif t.startswith('#'):
                vals.append(int(t[1:], 16))
            else:
                vals.append(int(t))
        i = 0
        while i < len(vals):
            if vals[i] == 0xFF:
                cur = cur  # keep; block ends but we stop adding
                cur_done = True
                break
            if i + 2 < len(vals):
                idx, b1, g = vals[i], vals[i + 1], vals[i + 2]
                # b1 = (R<<4)|B ; g = G
                pals[cur].append((idx, b1 >> 4, g, b1 & 0xF))
                i += 3
            else:
                break
    return {k: v for k, v in pals.items() if v}


def parse_default_palette():
    """The 16-colour base palette in Banks0123.asm: `db (R<<4)|B, G` x16."""
    src = open(mgproj.path("Banks0123.asm"), encoding='latin-1').read()
    m = re.search(r'DefaultPalette:(.*?)(?=\n;---|\nSetPalette:)', src, re.S)
    nums = []
    for ln in m.group(1).splitlines():
        code = ln.split(';', 1)[0]
        mm = re.search(r'\bdb\s+(.*)$', code)
        if not mm:
            continue
        for t in mm.group(1).split(','):
            t = t.strip()
            if not t:
                continue
            nums.append(int(t[:-1], 16) if t.endswith(('h', 'H')) else int(t))
    entries = []
    for c in range(16):
        if 2 * c + 1 < len(nums):
            b1, g = nums[2 * c], nums[2 * c + 1]
            entries.append((c, b1 >> 4, g, b1 & 0xF))
    return entries


def render(pals, namefilter=None):
    items = [(k, v) for k, v in pals.items()
             if (not namefilter or namefilter.lower() in k.lower())]
    sw, rowh, labelw = 26, 30, 150
    W = labelw + 16 * sw
    H = rowh * len(items)
    img = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(img)
    for r, (name, entries) in enumerate(items):
        y = r * rowh
        d.text((4, y + 9), name, fill=(220, 220, 220))
        colors = dict()
        for (idx, rr, gg, bb) in entries:
            colors[idx] = (rr, gg, bb)
        for slot in range(16):
            x = labelw + slot * sw
            rgb3 = colors.get(slot, MSX_DEF[slot])
            col = (c8(rgb3[0]), c8(rgb3[1]), c8(rgb3[2]))
            d.rectangle([x, y + 2, x + sw - 2, y + rowh - 4], fill=col,
                        outline=(60, 60, 60))
            if slot in colors:
                d.rectangle([x, y + 2, x + sw - 2, y + 5], fill=(255, 255, 0))
    return img


def main():
    namefilter = sys.argv[2] if len(sys.argv) > 2 else None
    pals = {"DefaultPalette": parse_default_palette()}
    pals.update(parse_palettes(_pal()))
    img = render(pals, namefilter)
    out = os.path.join(HERE, "palettes.png")
    img.save(out)
    print("wrote %s  (%d palettes; yellow tick = slot the palette defines)" %
          (out, len([k for k in pals if not namefilter or namefilter.lower() in k.lower()])))


if __name__ == '__main__':
    main()
