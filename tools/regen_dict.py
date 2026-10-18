#!/usr/bin/env python3
"""
Regenerate data/texts.asm's dictionary, frequency-optimised over the CURRENT
corpus, with NIGHTJAR proper nouns / gear force-included as tokens.

Because it optimises the real text, the result always fits the bank; as more of
the script becomes NIGHTJAR, re-running this shifts the dictionary toward NIGHTJAR
words automatically. Max 92 entries (tokens 0xA1-0xFC).

Run:  python tools/regen_dict.py   (then rebuild the ROM)
"""
import mgtext

# Force these into the dictionary even if currently infrequent (they will recur
# heavily once the whole script is NIGHTJAR).
MUST_INCLUDE = [
    "WARDEN", "RELAY", "ORACLE", "SAINT", "KESTREL", "AZRAEL", "GRAVE",
    "HALCYON", "REACH", "CONCORD", "HOWLER", "SHRIKE", "GOLIATH", "DOZER",
    "PYRE", "MAGPIE", "ROTH", "KINETIC", "GUIDED", "REBREATHER", "BREACHING",
    "ANTIVENOM", "THIS IS",
]


def main():
    oldsz, newsz, n = mgtext.regen_auto(MUST_INCLUDE, max_entries=92)
    print("Regenerated dictionary: %d entries (forced %d NIGHTJAR terms)." % (n, len(MUST_INCLUDE)))
    print("Total text payload: %d -> %d bytes (%+d)." % (oldsz, newsz, newsz - oldsz))


if __name__ == '__main__':
    main()
