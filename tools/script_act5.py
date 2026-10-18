#!/usr/bin/env python3
"""
NIGHTJAR — Act V finale (The Spire: stand-down trap, the real Roth, RELAY captured,
MAGPIE, Crane's confession, the escape, and the ending).
See tools/script_act1.py for format notes. Run, then re-run regen_dict.py + rebuild.
"""
import mgtext

ACT5 = [
    # txtRightLorry (133) — WARDEN: into the right skiff (radio, room 104)
    ("txtRightLorry", 0x03,
     "THIS IS WARDEN...\nCREEP INTO THE SKIFF\nON THE RIGHT. IT\nCARRIES YOU IN.\n...OUT"),

    # txtGoLeftDoor (132) — WARDEN: take the left door (misleading, radio, room 108)
    ("txtGoLeftDoor", 0x03,
     "THIS IS WARDEN...\nTAKE THE LEFT DOOR.\nTRUST ME. ...OUT"),

    # txtDestroyWall (134) — SAINT: don't, blast the wall (radio, room 108)
    ("txtDestroyWall", 0x03,
     "THIS IS SAINT...\nDON'T! BLAST THE\nWALL INSTEAD. THE\nLEFT DOOR IS A\nFURNACE. ...OVER"),

    # txtSwitchOffMSX (136) — WARDEN: THE STAND-DOWN TRAP (radio, room 111)
    ("txtSwitchOffMSX", 0x13,
     "THIS IS WARDEN...\nKESTREL, THE OP IS\nBURNED. TRIGGER YOUR\nSELF-WIPE AND GO\nDARK.\fTHAT IS A DIRECT\nORDER. ...OUT"),

    # txtCardLoc (137) — SAINT: the real route / core card (radio, room 111)
    ("txtCardLoc", 0x13,
     "THIS IS SAINT...\nDON'T YOU DARE.\nTHE CORE CARD IS IN\nBUILDING 3 EAST,\fBACK THROUGH THE\nWATER CHANNEL. KEEP\nMOVING. ...OVER"),

    # txtSecrPassage (126) — RELAY: secret passage (radio, room 182)
    ("txtSecrPassage", 0x03,
     "THIS IS RELAY...\nA SECRET PASSAGE\nRUNS FROM THE SW\nBASEMENT TO\nBUILDING ONE. ...OVER"),

    # txtImMadnar (125) — the REAL Dr. Roth: AZRAEL's weakness + the trigger twist (room 182)
    ("txtImMadnar", 0x11,
     "DR. ROTH...\nYOU FOUND ME.\fAZRAEL HAS THREE\nCORES. BREACHING\nCHARGES, ALL THREE,\fOR IT'S POINTLESS.\fAND CRANE FIRES THE\nUPLINK WHEN THE\nALARM PEAKS.\fYOUR BREAK-IN IS\nHIS TRIGGER. BEAT\nHIS CLOCK."),

    # txtBossRevealed (138) — RELAY names the traitor and is cut off (radio, room 192)
    ("txtBossRevealed", 0x13,
     "THIS IS RELAY...\nI HAVE IT! THE\nARCHITECT OF AZRAEL\nIS-- IT'S-- NO--!!\f...SIGNAL LOST."),

    # txtCowardDuck (139) — MAGPIE taunt behind hostages (in-room, room 193)
    ("txtCowardDuck", 0x01,
     "I'M MAGPIE...\nSHOOT ME AND YOU\nHIT THE HOSTAGES!"),

    # txtDuckCard8 (142) — SAINT: MAGPIE has the master card; spare the hostages (radio, room 193)
    ("txtDuckCard8", 0x13,
     "THIS IS SAINT...\nMAGPIE HAS THE\nMASTER CARD. HE\nHIDES BEHIND\nHOSTAGES.\fMY SISTER IS THERE.\nDON'T HIT THEM.\n...OVER"),

    # txtUseHandGun (141) — ORACLE: handgun only (radio, room 193)
    ("txtUseHandGun", 0x13,
     "THIS IS ORACLE...\nA HANDGUN DROPS\nMAGPIE WITHOUT\nSPRAYING THE ROOM.\n...BYE"),

    # txtBigBossIdBad (144) — the reveal: Crane is the architect (radio)
    ("txtBigBossIdBad", 0x11,
     "CRANE IS THE\nARCHITECT OF\nAZRAEL.\fHE RUNS THE\nCONCORD. END HIM,\nKESTREL."),

    # txtUpToYou (149) — ORACLE: it's up to you (radio, room 119)
    ("txtUpToYou", 0x13,
     "THIS IS ORACLE...\nI CAN'T TELL YOU HOW\nTO BEAT CRANE.\nONLY YOU CAN.\f...JUST COME BACK,\nKESTREL."),

    # txtUseCigarette (148) — SAINT: pulse stim extends the timer (radio, room 119)
    ("txtUseCigarette", 0x13,
     "THIS IS SAINT...\nA PULSE STIM STEADIES\nYOUR HANDS AND BUYS\nTIME ON THE CLOCK.\fLIVE, KESTREL.\n...OVER"),

    # txtBigBossConf (147) — Crane's confession, the final boss (room 119)
    ("txtBigBossConf", 0x11,
     "YOU FINALLY CAME.\fYEAH... I'M WARDEN.\fI BUILT NIGHTJAR.\nI BUILT AZRAEL.\fYOU WERE MY KEY,\nKESTREL.\fA FALSE FLAG.\nI USED YOU... AND\nYOU SERVED.\fNOW DIE WITH THE\nREACH."),

    # txtEmergency (150) — self-destruct, escape (room-wide event)
    ("txtEmergency", 0x01,
     "EMERGENCY!!\fSELF-DESTRUCT ON.\fESCAPE THE REACH!!"),

    # txtN313End (155) — the ending (ORACLE sign-off)
    ("txtN313End", 0x13,
     "THIS IS ORACLE...\nNIGHTJAR IS GONE,\nKESTREL.\fOFFICIALLY, YOU\nNEVER EXISTED.\f...UNOFFICIALLY,\nTHANK YOU."),

    # txtClimbLeftLadder (140) — a freed ally: use the left ladder to escape (room 145+)
    ("txtClimbLeftLadder", 0x11,
     "RESCUED!\fCLIMB THE LEFT\nLADDER WHEN YOU\nESCAPE."),

    # txtImElen (129) — a hostage, Iris (SAINT's sister) (in-room, room 167)
    ("txtImElen", 0x11,
     "I'M IRIS...\nJOON'S SISTER.\fGET ME OUT,\nPLEASE."),

    # txtComeIn (127) / txtHelpMe (128) — tiny voice cues (box 0 = 1x7)
    ("txtComeIn", 0x00, "GET IN!"),
    ("txtHelpMe", 0x00, "HELP ME"),
]


def main():
    total = 0
    for label, box, text in ACT5:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-18s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAct V: %d texts, %d bytes." % (len(ACT5), total))


if __name__ == '__main__':
    main()
