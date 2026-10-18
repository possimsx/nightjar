#!/usr/bin/env python3
"""
Recolour the player sprite (Snake -> KESTREL) in data/playersprite.asm.

Player sprites are layered MSX2 sprites; each sprite entry is `db Y, X, pattern, color`
(4 values). The colour byte's bit6 (#40) is the composite/OR bit. Snake's body uses
base 7 (cyan) + overlays 4Ah/4Ch that OR to white highlights.

KESTREL = navy body + cyan highlights (cold operative):
  7  -> 4   (base: cyan  -> navy blue)
  4Ah-> 47h (overlay: OR gives cyan highlight on navy)
  4Ch-> 47h
Only the colour column of 4-value sprite lines is touched (positions/patterns/empty
80h sprites and the parachute canopy / damage-flash colours are left alone).

Run:  python tools/recolor_kestrel.py   (then rebuild the ROM)
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "data", "playersprite.asm")
REMAP = {0x07: 0x04, 0x4A: 0x47, 0x4C: 0x47}


def tok(b):
    if b < 10:
        return str(b)
    s = "%X" % b
    return ("0" + s if s[0] not in "0123456789" else s) + "h"


def val(t):
    t = t.strip()
    if t.endswith(('h', 'H')):
        return int(t[:-1], 16)
    if t.startswith('#'):
        return int(t[1:], 16)
    return int(t)


def main():
    out = []
    changed = 0
    for ln in open(F, encoding='latin-1').read().splitlines():
        m = re.match(r'^(\s*)db(\s+)(.*?)(\s*)(;.*)?$', ln)
        if m:
            parts = [p for p in m.group(3).split(',')]
            nums = [p.strip() for p in parts if p.strip() != '']
            if len(nums) == 4:
                try:
                    v = [val(x) for x in nums]
                except ValueError:
                    v = None
                if v is not None:
                    # entry = Y, X, pattern, color ; skip empty sprites (80h,0,0,0)
                    if not (v[0] == 0x80 and v[1] == 0 and v[2] == 0):
                        if v[3] in REMAP:
                            v[3] = REMAP[v[3]]
                            changed += 1
                        body = ",\t".join(tok(x) for x in v)
                        comment = (" " + m.group(5)) if m.group(5) else ""
                        out.append("%sdb\t%s%s" % (m.group(1), body, comment))
                        continue
        out.append(ln)
    open(F, 'w', encoding='latin-1').write("\n".join(out) + "\n")
    print("recoloured %d sprite colour bytes (Snake -> Kestrel: navy+cyan)" % changed)


if __name__ == "__main__":
    main()
