#!/usr/bin/env python3
"""
Rebuild the entire NIGHTJAR text layer from scratch, deterministically:

  1. git checkout data/texts.asm   (restore original MG text + dictionary)
  2. apply Act I..V scripts          (patch all story texts to NIGHTJAR)
  3. regen the dictionary            (frequency-optimal + NIGHTJAR terms)

Then rebuild the ROM:  sjasm MetalGear.asm MetalGear.rom

Usage:  python tools/build_nightjar_text.py
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    subprocess.run(["git", "checkout", "data/texts.asm"], cwd=ROOT, check=True)
    import script_act1, script_act2, script_act3, script_act4, script_act5, script_aux, regen_dict
    for mod in (script_act1, script_act2, script_act3, script_act4, script_act5, script_aux):
        print("== %s ==" % mod.__name__)
        mod.main()
    print("== regen_dict ==")
    regen_dict.main()
    print("\nText layer rebuilt. Now run:\n  sjasm MetalGear.asm MetalGear.rom")


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()
