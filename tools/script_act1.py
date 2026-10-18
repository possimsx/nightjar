#!/usr/bin/env python3
"""
NIGHTJAR — Act I radio script. Patches all Act-I text IDs in data/texts.asm.

Each entry: (txt_label, box_type, text).  \n = newline, \f = next page.
Box 0x13 = radio box with prompt (5x23); 0x03 = same, no prompt; 0x11 = 3x19.
Run:  python tools/script_act1.py   (then rebuild the ROM)
"""
import mgtext

# (label, box, text)
ACT1 = [
    # txtMission (ID 3) — WARDEN mission briefing (rooms 0/1/4)
    ("txtMission", 0x13,
     "THIS IS WARDEN.\nINFILTRATE HALCYON\nREACH. CONFIRM AZRAEL\nIS REAL, AND DESTROY\nIT.\f...KESTREL, OUT."),

    # txtSchneider (ID 23) — RELAY introduces herself (room 1, 30, 31, 33)
    ("txtSchneider", 0x13,
     "THIS IS RELAY...\nMARA VANCE. I LEFT\nTHE CONCORD. I HAVE\nTHE MAP OF HALCYON\nREACH.\fTUNE 12079 AND I'LL\nGUIDE YOU. ...OVER"),

    # txtTakeWeapon (ID 4) — WARDEN: take gear off the skiff, need a card (room 5/7/8)
    ("txtTakeWeapon", 0x13,
     "THIS IS WARDEN...\nTAKE THE GEAR FROM\nTHE CONCORD SKIFF.\fYOU NEED AN ACCESS\nCARD TO OPEN THE\nDOOR. ...OUT"),

    # txtResistance (ID 20) — WARDEN: find the resistance (room 28/30)
    ("txtResistance", 0x13,
     "THIS IS WARDEN...\nTHERE IS A RESISTANCE\nCELL INSIDE. CONTACT\nTHEM ON THE\nTRANSCEIVER. ...OUT"),

    # txtMachGunKidInfo (ID 80) — ORACLE: HOWLER weakness (room 20)
    ("txtMachGunKidInfo", 0x03,
     "THIS IS ORACLE...\nADA LIN. THAT DRONE,\nHOWLER, ONLY CRACKS\nTO A GUIDED MISSILE.\n...BYE"),

    # txtGasMask (ID 25) — WARDEN: put on a gas mask (room 29)
    ("txtGasMask", 0x03,
     "THIS IS WARDEN...\nTOXIC GAS AHEAD.\nPUT ON A GAS MASK.\n...OUT"),

    # txtGasMaskLoc (ID 26) — RELAY: mask location (room 29)
    ("txtGasMaskLoc", 0x13,
     "THIS IS RELAY...\nTHE GAS MASK IS IN\nTHE SOUTH OF THE\n1ST FLOOR. GET IT\nFIRST. ...OVER"),

    # txtDestroyPS (ID 38) — WARDEN: missile the power box (room 37)
    ("txtDestroyPS", 0x13,
     "THIS IS WARDEN...\nBREAK THE POWER BOX\nWITH A GUIDED\nMISSILE TO KILL THE\nLIVE FLOOR. ...OUT"),

    # txtMissilLoc (ID 39) — RELAY: missile location (room 37)
    ("txtMissilLoc", 0x03,
     "THIS IS RELAY...\nA GUIDED MISSILE IS\nIN THE SOUTHEAST\nCELLS. ...OVER"),

    # txtParacFind (ID 83) — RELAY: parachute on floor 2 (room 45/46/48/51)
    ("txtParacFind", 0x03,
     "THIS IS RELAY...\nYOU CAN FIND A\nPARACHUTE ON THE\n2ND FLOOR. ...OVER"),

    # txtHindDGrenade (ID 88) — ORACLE: SHRIKE weakness (room 50)
    ("txtHindDGrenade", 0x03,
     "THIS IS ORACLE...\nSHRIKE IS A GUNSHIP.\nHIT IT WITH A\nGRENADE LAUNCHER.\n...BYE"),

    # txtWindBarrier (ID 42) — WARDEN: rooftop wind-wall (room 53)
    ("txtWindBarrier", 0x13,
     "THIS IS WARDEN...\nA KINETIC WIND-WALL\nGUARDS THE ROOF.\nFIND THE KINETIC\nSUIT TO PASS. ...OUT"),

    # txtBombSuitLoc (ID 51) — RELAY: kinetic suit in basement (room 53)
    ("txtBombSuitLoc", 0x03,
     "THIS IS RELAY...\nTHE KINETIC SUIT IS\nIN THE BASEMENT.\n...OVER"),
]


def main():
    total = 0
    for label, box, text in ACT1:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-20s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAct I: %d texts, %d bytes total." % (len(ACT1), total))


if __name__ == '__main__':
    main()
