#!/usr/bin/env python3
"""
NIGHTJAR — Act III radio + NPC script (The Yards desert -> Building 2).
See tools/script_act1.py for format notes. Run, then re-run regen_dict.py + rebuild.
"""
import mgtext

ACT3 = [
    # txtTankMines (ID 92) — ORACLE: GOLIATH weakness (radio, room 67)
    ("txtTankMines", 0x03,
     "THIS IS ORACLE...\nGOLIATH IS A CRAWLER.\nARMOR SHRUGS OFF\nBULLETS. USE MINES.\n...BYE"),

    # txtDesetGuards (ID 35) — desert security challenge (in-room, room 69 area)
    ("txtDesetGuards", 0x01,
     "HALT! STATE YOUR\nUNIT. ...DON'T MAKE\nTROUBLE."),

    # txtUseUniform (ID 93) — WARDEN: checkpoint, wear a uniform (radio, room 69)
    ("txtUseUniform", 0x13,
     "THIS IS WARDEN...\nCHECKPOINT AHEAD.\nWEAR A CONCORD\nUNIFORM AND WALK\nTHROUGH.\f...KESTREL, OUT."),

    # txtUniformLoc (ID 94) — RELAY: uniform location (radio, room 69)
    ("txtUniformLoc", 0x13,
     "THIS IS RELAY...\nA CONCORD UNIFORM IS\nIN THE BASEMENT OF\nBUILDING ONE.\n...OVER"),

    # txtDianeNewFreq (ID 95) — ORACLE: new band (radio, room 69)
    ("txtDianeNewFreq", 0x13,
     "THIS IS ORACLE...\nI'M MOVING TO BAND\n12091. STAY SHARP\nIN THERE.\n...BYE"),

    # txtArnorlds (ID 114) — ORACLE: the Arbiters can't be killed (radio, room 83)
    ("txtArnorlds", 0x03,
     "THIS IS ORACLE...\nTHE ARBITERS CAN'T\nBE KILLED. DON'T TRY.\nSLIP PAST. LEAVE!\n...BYE"),

    # txtRocketLaunch (ID 117) — SAINT introduces himself + rocket launcher (radio, room 86)
    ("txtRocketLaunch", 0x13,
     "THIS IS SAINT...\nJOON PARK. I LEFT\nYOU A ROCKET\nLAUNCHER.\fMY SISTER IRIS IS A\nHOSTAGE HERE. GET\nHER OUT. ...OVER"),

    # txtOpeningDoor (ID 118) — SAINT opens the vault (radio, room 87)
    ("txtOpeningDoor", 0x03,
     "THIS IS SAINT...\nOPENING THE VAULT\nNOW. GO. ...OVER"),

    # txtCompassLoc (ID 122) — RELAY: compass on floor 2 (radio, room 82/202)
    ("txtCompassLoc", 0x03,
     "THIS IS RELAY...\nTHE COMPASS IS ON\nFLOOR 2. GET IT FOR\nTHE DARK LEVELS.\n...OVER"),

    # txtFlashLoc (ID 112) — RELAY: the lamp on floor 1 (radio, room 93/123)
    ("txtFlashLoc", 0x03,
     "THIS IS RELAY...\nTHE LAMP IS ON\nFLOOR 1. GRAB IT OR\nGO BLIND.\n...OVER"),
]


def main():
    total = 0
    for label, box, text in ACT3:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-18s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAct III: %d texts, %d bytes." % (len(ACT3), total))


if __name__ == '__main__':
    main()
