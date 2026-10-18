# 07 — Text Encoding & the `mgtext.py` Tool

All in-game text (radio calls, item descriptions, the ending) is stored in a **compressed,
tokenised format**. This document is the validated spec plus the Python tool that lets you
author NIGHTJAR dialogue in plain English and compile it into the ROM.

Reverse-engineered from `DecodeText` / `DrawChar` in `Banks0123.asm` and verified by
round-tripping **all 91 existing strings** (`python tools/mgtext.py selftest`).

---

## 1. Format spec

Each text (a `txt*` label in `data/texts.asm`, indexed by `idxTexts`) is a byte stream:

| Byte | Meaning |
|------|---------|
| **byte 0** | `TextBoxType` — window size + prompt icon. **Not a glyph.** |
| `0x00` | space |
| `0x30`–`0x39` | digits `0`–`9` (literal ASCII) |
| `0x41`–`0x5A` | letters `A`–`Z` (literal ASCII) |
| punctuation | font-glyph bytes — see table below |
| `0xA1`–`0xFC` | **dictionary token** (index = byte − `0xA1` into `idxDictionary`) |
| `0xFD` | next page (wait for key, then continue) |
| `0xFE` | new line |
| `0xFF` | end of text |

The font has **no lowercase**. Glyph tile in VRAM = byte + `0x10` (`DrawChar`).

### Validated glyph (punctuation) map

| Byte | Glyph | | Byte | Glyph |
|------|-------|-|------|-------|
| `0x00` | (space) | | `0x5B` | `?` |
| `0x3D` | `!` | | `0x5C` | `.` |
| `0x3E` | `!!` | | `0x5F` | `,` |
| `0x40` | `-` | | `0x97` | `'` |

`...` (ellipsis) is its own dictionary token (`dicPoints` = three `.`), so it compresses to a
single byte `0xA2`.

> In the **source** `.asm`, authors sometimes type the ASCII char whose code *is* the glyph
> byte (e.g. `"REMOTE@CONTROL"` because `@`=`0x40`=`-`, or `"MR",#5C,"SCHNEIDER"` for the
> `.`). The tool handles both quoted chars and `#`/`h` hex.

### `TextBoxType` (byte 0)

Low nibble = window size, high nibble bit = show prompt icon (`Variables.asm`):

| Low nibble | Window |
|-----------|--------|
| 0 | 1×7 |
| 1 | 3×19 |
| 2 | 5×16 |
| 3 | 5×23 |
| 4 | 2×17 |

So `0x13` = prompt icon + 5×23 window (the standard radio box); `0x03` = same window, no
prompt; `0x01` = 3×19 no prompt (used for in-world signs/voices).

---

## 2. The dictionary

`idxDictionary` (end of `data/texts.asm`) holds **92 entries** (tokens `0xA1`–`0xFC`).
Tokens `0xFD`/`0xFE`/`0xFF` are control codes, so **92 is the hard maximum — the table is
full.** A new game must **replace** entries, not add them.

Each entry is a word/phrase (e.g. `dicBigBoss` = `"BIG BOSS"`, `dicOver` = `"OVER"`,
`dicThisIs` = `"THIS IS"`). Many are generic and reusable for NIGHTJAR (`THE`, `YOU`, `AND`,
`WITH`, `TO`, `ON`, `DOOR`, `WALL`, `ROOM`, `FLOOR`, `BASEMENT`, `ACCESS`, `CARD`, `OVER`,
`HELLO`, `BYE`, `THIS IS`, `…`). Others are Metal-Gear-specific (`METAL GEAR`, `BIG BOSS`,
`GREY FOX`, `OUTER HEAVEN`, `MR.SCHNEIDER`, `DR.PETTROVICH`) and are prime candidates to
**repurpose** into NIGHTJAR terms (`AZRAEL`, `WARDEN`, `GRAVE`, `HALCYON REACH`, `RELAY`,
`DR.ROTH`) when you do the full script — keeping the count ≤ 92.

> ⚠️ One original entry has a typo: `dicDestroy` = `"DESTOROY"`. The encoder won't match your
> `"DESTROY"` to it (good — you'll get correct literal text), but it means `DESTROY` costs
> more bytes until you fix/replace that entry.

### Regenerating the dictionary for NIGHTJAR

`tools/regen_dict.py` rebuilds the whole dictionary **frequency-optimally over the current
corpus**, force-including the NIGHTJAR proper nouns/gear (`WARDEN`, `AZRAEL`, `HALCYON`,
`KESTREL`, `CONCORD`, `GRAVE`, `HOWLER`, …). It:

1. decodes every text with the old dictionary,
2. installs the new 92-entry dictionary,
3. **re-encodes every text** so still-MG placeholder lines keep rendering correctly.

Because it optimises the *real* text, the result always fits the bank.

> **Timing matters.** A hand-curated all-NIGHTJAR dictionary *overflows* bank A/B/C today,
> because ~85% of the script is still original MG text — dropping the MG tokens (`BIG BOSS`,
> `METAL GEAR`, …) makes those placeholders grow by ~1 KB. The frequency-optimal mode avoids
> that. **Re-run `regen_dict.py` after each Act is converted to NIGHTJAR** — the dictionary
> will drift toward NIGHTJAR words automatically as they come to dominate the corpus. Always
> rebuild afterward and watch for `ASSERT $=#C000`.

---

## 3. The tool — `tools/mgtext.py`

Pure-Python (3.x), no dependencies. It reads `data/texts.asm` for the live dictionary, so it
always matches the current build.

```sh
# sanity check: decode samples + round-trip all strings
python tools/mgtext.py selftest

# read existing text(s)
python tools/mgtext.py decode txtMission
python tools/mgtext.py decode all

# encode a line to db statements (preview; \n = newline, \f = next page)
python tools/mgtext.py encode --type 0x13 --label txtFoo "LINE ONE\nLINE TWO\f...OVER"

# rewrite a label's block in data/texts.asm IN PLACE (the authoring workflow)
python tools/mgtext.py patch txtMission --type 0x13 "THIS IS WARDEN.\n...KESTREL, OUT."
```

* `encode`/`patch` **upper-case** input automatically and greedily apply dictionary tokens
  (boundary-aware, so `ON` won't be matched inside `CONTROL`).
* `--nodict` disables compression (larger, all-literal output) for debugging.
* `patch` preserves the existing `TextBoxType` unless you pass `--type`.
* After `patch`, **rebuild** (`sjasm MetalGear.asm MetalGear.rom`) and watch for
  `ASSERT $=#C000` — that means the texts overflowed bank A/B/C (compress more, or trim).

### Proven pipeline

`author English → mgtext.py patch → sjasm → 131072 bytes / 0 errors → glyphs in ROM`.

**The full NIGHTJAR story script is already shipped this way** (all 5 acts, ~59 texts). The
act dialogue lives in `tools/script_act1.py` … `script_act5.py`; rebuild the entire text
layer deterministically with:

```sh
python tools/build_nightjar_text.py     # checkout texts.asm -> apply act1-5 -> regen dict
sjasm MetalGear.asm MetalGear.rom
```

After the final regen the all-NIGHTJAR payload (4806 B) is *smaller* than the original MG
text — the NIGHTJAR-tuned dictionary more than pays for itself once the corpus is converted.

---

## 4. Authoring the NIGHTJAR script

1. Take a line from the [beat sheet](NEWGAME-BEATSHEET.md) (it lists caller + the exact line
   per room).
2. Pick the `TextBoxType` (almost always `0x13` for radio).
3. Break it into lines (`\n`) that fit the window width (23 chars for the 5×23 box) and pages
   (`\f`) for long calls.
4. `python tools/mgtext.py patch <txtLabel> --type 0x13 "..."`.
5. Point the room's `RadioRoom_xxx` entry (in `data/radiocalls.asm`) at the right text ID if
   you're adding new texts (see [03-STORY-INDEX.md](03-STORY-INDEX.md) for the room→text
   wiring).
6. Rebuild and test in an emulator.

> **Tip:** decode the original line first (`decode <label>`) to see its box type and length
> budget, then write the NIGHTJAR replacement to a similar size to stay within the bank.
