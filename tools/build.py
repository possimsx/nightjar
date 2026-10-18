#!/usr/bin/env python3
"""Adaptive ROM build for NIGHTJAR / Metal Gear MSX.

Assembles MetalGear.asm with sjasm, then pads the output to the SMALLEST
Konami-mapper-legal ROM size that still holds every byte of real content:

    content <= 128KB  ->  128KB   (stock; no padding, byte-identical)
    content <= 256KB  ->  256KB
    content <= 512KB  ->  512KB   (hard MAX)

Why power-of-2 sizes only: the Konami4 mapper masks the 8-bit segment number
written to #6000/#8000/#A000 down to the ROM size. That mask is only coherent
on a power-of-2 ROM, so a 140KB ROM must round up to 256KB, not stay at 140KB.
We never reserve space we don't use, so the build stays at 128KB until new
high-segment data (e.g. extended graphics) actually pushes past it -- which is
also the only point at which an emulator's "Konami ROM > 256KB" heuristic
warning can appear.

Usage:
    python tools/build.py            # build + adaptive pad, print report
    python tools/build.py --max 256  # cap the MAX at 256KB instead of 512KB

Importable:  from tools.build import pad_rom, build
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

SJASM = os.environ.get("MG_SJASM", "C:/DevMSX/sjasm039j/sjasm.exe")
SRC = "MetalGear.asm"
ROM = "MetalGear.rom"

KB = 1024
SEGMENT = 8 * KB                      # Konami mapper bank size
STEPS = (128 * KB, 256 * KB, 512 * KB)  # legal adaptive ROM sizes
PAD_BYTE = 0xFF                       # matches the ds (#C000-$),#ff bank fill


def target_size(content_len, max_size=512 * KB):
    """Smallest legal ROM size (128/256/512KB) that holds content_len bytes,
    never exceeding max_size. Raises if content does not fit."""
    for step in STEPS:
        if step > max_size:
            break
        if content_len <= step:
            return step
    raise ValueError(
        "content is %d bytes (%.1fKB) but the ROM MAX is %d bytes (%dKB) -- "
        "too much data to fit the Konami mapper budget"
        % (content_len, content_len / KB, max_size, max_size // KB))


def pad_rom(path, max_size=512 * KB):
    """Pad the ROM at `path` with PAD_BYTE up to the adaptive target size.
    Returns (raw_size, padded_size, segments_used). A no-op when already at
    target (e.g. stock 128KB stays byte-identical)."""
    with open(path, "rb") as f:
        data = f.read()
    tgt = target_size(len(data), max_size)
    if len(data) < tgt:
        with open(path, "ab") as f:
            f.write(bytes([PAD_BYTE]) * (tgt - len(data)))
    segs_used = (len(data) + SEGMENT - 1) // SEGMENT
    return len(data), tgt, segs_used


def build(max_size=512 * KB):
    """Run sjasm then adaptively pad. Returns a report dict (also used by the
    editor). 'ok' is False on missing sjasm, assembly errors, or overflow."""
    if not os.path.exists(SJASM):
        return {"ok": False, "error": "sjasm not found at %s (set MG_SJASM)" % SJASM}
    p = subprocess.run([SJASM, SRC, ROM], cwd=mgproj.root(),
                       capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"Errors?:\s*(\d+)", out)
    errors = int(m.group(1)) if m else (0 if p.returncode == 0 else 1)
    romp = mgproj.path(ROM)
    if errors or not os.path.exists(romp):
        return {"ok": False, "errors": errors, "size": 0,
                "output": "\n".join(out.splitlines()[-25:])}
    try:
        raw, size, segs = pad_rom(romp, max_size)
    except ValueError as e:
        return {"ok": False, "errors": 0, "size": os.path.getsize(romp),
                "output": str(e)}
    return {"ok": True, "errors": 0, "size": size, "raw_size": raw,
            "segments_used": segs, "padded": size - raw,
            "output": "\n".join(out.splitlines()[-25:])}


def main(argv):
    max_size = 512 * KB
    if "--max" in argv:
        max_size = int(argv[argv.index("--max") + 1]) * KB
    r = build(max_size)
    if not r["ok"]:
        print("BUILD FAILED:", r.get("error") or "%d error(s)" % r.get("errors", 1))
        if r.get("output"):
            print(r["output"])
        return 1
    print("Assembled %s -> %s" % (SRC, ROM))
    print("  content      : %d bytes (%.1fKB, %d x 8KB segments)"
          % (r["raw_size"], r["raw_size"] / KB, r["segments_used"]))
    print("  ROM size     : %d bytes (%dKB)" % (r["size"], r["size"] // KB))
    if r["padded"]:
        print("  padded       : +%d bytes of 0x%02X" % (r["padded"], PAD_BYTE))
    else:
        print("  padded       : none (content fills the tier exactly)")
    if r["size"] > 256 * KB:
        print("  note         : >256KB -- emulators may warn (heuristic); "
              "Konami4 supports it, verified to run.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
