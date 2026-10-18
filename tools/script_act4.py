#!/usr/bin/env python3
"""
NIGHTJAR — Act IV radio + NPC script (The Drowned Quarter: blackout maze, PYRE,
scorpions, the channel, and "Roth" the Double's ambush).
See tools/script_act1.py for format notes. Run, then re-run regen_dict.py + rebuild.
"""
import mgtext

ACT4 = [
    # txtPitfalls (ID 113) — ORACLE: mind the pitfalls (radio, room 123)
    ("txtPitfalls", 0x03,
     "THIS IS ORACLE...\nMIND YOUR STEP IN\nTHERE. THE FLOOR\nISN'T ALL THERE.\n...BYE"),

    # txtImFireTrop (ID 108) — PYRE boss taunt (in-room, room 95). Box 4 = 2x17.
    ("txtImFireTrop", 0x04,
     "I'M PYRE...\nBURN, INTRUDER!"),

    # txtGasArea (ID 106) — RELAY: gassy area (radio, room 99)
    ("txtGasArea", 0x03,
     "THIS IS RELAY...\nTHERE'S A GASSY AREA\nIN THERE. MASK UP.\n...OVER"),

    # txtUseAntidote (ID 130) — ORACLE: antivenom for the stingers (radio, room 102)
    ("txtUseAntidote", 0x03,
     "THIS IS ORACLE...\nTHOSE STINGERS CARRY\nVENOM. KEEP\nANTIVENOM ON YOU.\n...BYE"),

    # txtTrap (ID 109) — "Roth" the Double springs the ambush (in-room, room 189). Box 1 = 3x19.
    ("txtTrap", 0x01,
     "AN AGENT! THIS WAY,\nQUICKLY... TO THE\nCORE ACCESS...\fIT'S A TRAP, FOOL!"),

    # txtOxygenLoc (ID 135) — SAINT: rebreather behind the wall (radio, room 115)
    ("txtOxygenLoc", 0x03,
     "THIS IS SAINT...\nA REBREATHER IS\nBEHIND THAT WALL.\nTHE CHANNEL FLOODS\nAHEAD. ...OVER"),

    # txtRunFast (ID 146) — SAINT: just run, stims will do (radio, room 116)
    ("txtRunFast", 0x03,
     "THIS IS SAINT...\nJUST RUN. YOU'LL\nMAKE IT WITH ENOUGH\nSTIMS. ...OVER"),

    # txtJammingAtk (ID 99) — WARDEN: jamming cleared (radio, room 178)
    ("txtJammingAtk", 0x03,
     "THIS IS WARDEN...\nWE HAD A JAMMING\nATTACK. IT'S CLEARED\nNOW. ...OUT"),

    # txtWaterChan (ID 123) — the channel route to Building 3 (sign/SAINT). Box 1 = 3x19.
    ("txtWaterChan", 0x01,
     "THE WATER CHANNEL\nRUNS TO BUILDING 3.\nGET THE REBREATHER."),
]


def main():
    total = 0
    for label, box, text in ACT4:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-16s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAct IV: %d texts, %d bytes." % (len(ACT4), total))


if __name__ == '__main__':
    main()
