#!/usr/bin/env python3
"""
NIGHTJAR — auxiliary/system texts (intro briefing, tutorial, your-reply, boss
threat, prisoner-rescue intel, and a missed radio call). These weren't part of the
Act I-V scripts. See tools/script_act1.py for format notes.
Run, then re-run regen_dict.py + rebuild.  (txtStaff dev credits left intact.)
"""
import mgtext

AUX = [
    # txtOpIntrude (ID 2) — the INTRO briefing cutscene (first dialogue seen)
    ("txtOpIntrude", 0x13,
     "THIS IS WARDEN...\nOPERATION NIGHTJAR.\fINFILTRATE THE\nCONCORD FORTRESS\nHALCYON REACH AND\nDESTROY THE WEAPON\nAZRAEL.\fFIRST, FIND OUR\nMISSING AGENT GRAVE,\nAND CONFIRM AZRAEL.\fCONTACT ON THE BAND\nOF 12085 FROM NOW.\n...OUT"),

    # txtYourReply — Kestrel's outgoing call header
    ("txtYourReply", 0x03, "THIS IS KESTREL...\nYOUR REPLY, PLEASE."),

    # txtFinalThread — a defeated boss's threat
    ("txtFinalThread", 0x03,
     "LISTEN, KESTREL...\nI'LL NEVER DIE.\fI'LL GET YOU\nONE DAY.\fSEE YOU AGAIN..."),

    # txtTutorial — WARDEN explains the F-keys
    ("txtTutorial", 0x03,
     "THIS IS WARDEN...\nLET ME EXPLAIN THE\nF-KEYS.\fF-1 PAUSE.\nF-2 SELECT WEAPONS.\nF-3 SELECT EQUIPMENT.\nF-4 TRANSCEIVER BAND.\fREMEMBER THESE.\n...OUT"),

    # txtChkBugged — WARDEN: check for bug
    ("txtChkBugged", 0x13,
     "THIS IS WARDEN...\nCHECK YOUR EQUIPMENT.\nMAKE SURE THE ENEMY\nHASN'T BUGGED YOU.\n...OUT"),

    # txtTheyHaveSil — ORACLE: silencer (radio room 150)
    ("txtTheyHaveSil", 0x03,
     "THIS IS ORACLE...\nI SUSPECT THEY HAVE\nA SILENCER.\n...BYE"),

    # --- prisoner-rescue intel ("RESCUED!" reward messages) ---
    ("txtDianeFreq", 0x11,
     "RESCUED!\fORACLE WILL SUPPORT\nYOU ON WAVEBAND\n12033."),
    ("txtFoxHoundInf", 0x11,
     "RESCUED!\fAN AGENT GOT IN\nDAYS AGO, THEN WAS\fCAPTURED BY\nTHE ENEMY."),
    ("txtFoxHundInfo", 0x11,
     "RESCUED!\fTHE AGENT GRAVE\nMUST BE IN\fTHE SECRET CELL."),
    ("txtMadnarLocation", 0x11,
     "RESCUED!\fDR. ROTH IS IN\nA SOLITARY CELL\fIN THE COURTYARD."),
    ("txtDrMovedB2", 0x11,
     "RESCUED!\fDR. ROTH WAS MOVED\nTO BUILDING 2.\fIT'S 10KM NORTH\nOF HERE."),
    ("txtDrUndergCell", 0x11,
     "RESCUED!\fDR. ROTH IS IN\nTHE BASEMENT."),
    ("txtJennifer", 0x11,
     "RESCUED!\fCONTACT SAINT OF\nTHE RESISTANCE ON\fWAVEBAND 12048.\fHE WON'T ANSWER\nUNLESS YOU ARE\nTHE REAL AGENT."),

    # txtSaveEllen — Dr. Roth, coerced (hostage)
    ("txtSaveEllen", 0x11,
     "I'M DR. ROTH.\fTHEY TOOK MY\nFAMILY AS HOSTAGE.\fSAVE THEM, OR I\nWON'T HELP YOU\nVS AZRAEL."),

    # txtTooLate — the "Roth moved" event
    ("txtTooLate", 0x04, "...DR. ROTH.\nIT'S TOO LATE."),
]


def main():
    total = 0
    for label, box, text in AUX:
        nb, dec = mgtext.patch_label(label, text, box=box)
        total += nb
        print("%-18s %3d B | %s" % (label, nb, dec.replace('\n', ' / ').replace('\f', ' <P> ')))
    print("\nAux: %d texts, %d bytes." % (len(AUX), total))


if __name__ == '__main__':
    main()
