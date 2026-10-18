#!/usr/bin/env python3
"""
Gently cool the room / radio / weapon-menu palettes toward NIGHTJAR's cold theme.

For each colour `db idx, (R<<4)|B, G`, warm colours (R > B) are nudged one step
bluer (R-1, B+1); already-cool/neutral colours are left alone; G is untouched.
Mild + reversible. RUN ONCE (re-running compounds — `git checkout data/palettes.asm`
to reset). Sprite-set (enemy) palettes are deliberately skipped.

Run:  python tools/cool_palettes.py   (then rebuild the ROM)
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAL = os.path.join(ROOT, "data", "palettes.asm")
TARGET = re.compile(r'^(RoomPalette\d+|RadioPalette|PalMenuWeapon)\b')


def cool(r, b):
    return (r - 1, min(7, b + 1)) if r > b else (r, b)


def tok(b):
    if b < 10:
        return str(b)
    s = "%X" % b
    return ("0" + s if s[0] not in "0123456789" else s) + "h"


def fmt_color(idx, r, g, b):
    return "db\t%3s, %3s, %3s" % (tok(idx), tok((r << 4) | b), tok(g))


def main():
    lines = open(PAL, encoding='latin-1').read().splitlines()
    active = False
    changed = 0
    out = []
    for ln in lines:
        m = re.match(r'^(\w+):', ln)
        if m:
            active = bool(TARGET.match(ln))
        code = ln.split(';', 1)[0]
        mm = re.search(r'\bdb\s+(.*)$', code)
        if active and mm:
            vals = []
            for t in mm.group(1).split(','):
                t = t.strip()
                if not t:
                    continue
                vals.append(int(t[:-1], 16) if t.endswith(('h', 'H')) else int(t))
            if len(vals) == 3 and vals[0] != 0xFF:
                idx, b1, g = vals
                r, b = b1 >> 4, b1 & 0xF
                nr, nb = cool(r, b)
                if (nr, nb) != (r, b):
                    changed += 1
                indent = ln[:len(ln) - len(ln.lstrip())]
                label = ''
                lm = re.match(r'^(\w+:\s*)db', ln)
                if lm:
                    label = lm.group(1)
                    indent = ''
                out.append(indent + label + fmt_color(idx, nr, g, nb))
                continue
        out.append(ln)
    open(PAL, 'w', encoding='latin-1').write("\n".join(out) + "\n")
    print("cooled %d palette colours (rooms/radio/weapon-menu)" % changed)


if __name__ == "__main__":
    main()
