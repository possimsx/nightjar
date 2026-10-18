#!/usr/bin/env python3
"""
NIGHTJAR — Act II radio + NPC script (capture, prison, freeing GRAVE).
See tools/script_act1.py for format notes. Run, then re-run regen_dict.py + rebuild.
"""
import mgtext

ACT2 = [
    # txtFindGear (ID 60) — WARDEN: recover your kit (radio, room 54/58)
    ("txtFindGear", 0x13,
     "THIS IS WARDEN...\nTHEY STRIPPED YOU.\nYOUR KIT IS HIDDEN\nIN A ROOM NEARBY.\fPUNCH THE HOLLOW\nWALLS TO FIND IT.\n...OUT"),

    # txtGearTaken (ID 62) — KESTREL recovers the Kit Bag (shown on pickup)
    ("txtGearTaken", 0x01,
     "I RECOVERED MY KIT.\nWEAPONS AND GEAR\nRESTORED."),

    # txtBombWall (ID 64) — RELAY: punch/bomb hollow walls (radio, room 58)
    ("txtBombWall", 0x13,
     "THIS IS RELAY...\nPUNCH THE WALLS THAT\nSOUND HOLLOW, AND\nBOMB THE REST.\n...OVER"),

    # txtShootGunn (ID 61) — BREAKER boss taunt (in-room, room 57)
    ("txtShootGunn", 0x01,
     "I'M BREAKER...\nNOTHING GETS PAST\nME. NOT EVEN YOU."),

    # txtChkWall (ID 58) — WARDEN: find GRAVE's cell, check the wall (radio, room 165)
    ("txtChkWall", 0x13,
     "THIS IS WARDEN...\nINFILTRATION HOLDING.\nFIND GRAVE'S CELL.\fCHECK THE WALLS TO\nBREAK HIM OUT.\n...OUT"),

    # txtGrayFox (ID 59) — GRAVE (Cole Marsh) in his cell (in-room, room 164)
    ("txtGrayFox", 0x11,
     "KESTREL...\nKNEW THEY'D SEND\nYOU.\fAZRAEL IS REAL,\nAND THIS OP IS\nROTTEN.\fDON'T TRUST THE\nVOICE IN YOUR EAR.\nCHECK THE WALL."),
]


def main():
    total = 0
    for label, box, text in ACT2:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-18s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAct II: %d texts, %d bytes." % (len(ACT2), total))


if __name__ == '__main__':
    main()
