#!/usr/bin/env python3
"""
mgtext.py - Metal Gear (MSX) text codec for the NIGHTJAR rework.

Engine text format (see DecodeText in Banks0123.asm):
  * first byte of a text = TextBoxType (window/prompt), NOT a glyph
  * 0x00          = space
  * 0x30-0x39     = '0'-'9'   (literal ASCII)
  * 0x41-0x5A     = 'A'-'Z'   (literal ASCII)
  * punctuation   = font glyph bytes (see GLYPH below)
  * 0xA1-0xFC     = dictionary token (index = byte-0xA1 into idxDictionary)
  * 0xFD          = next page (wait for key, then continue)
  * 0xFE          = new line
  * 0xFF          = end of text
The font has no lowercase; input is upper-cased automatically.

Authoring markers in --text: use \n for newline, \f for next page.

Usage:
  python tools/mgtext.py selftest
  python tools/mgtext.py decode <Label|all>
  python tools/mgtext.py encode --type 0x13 --label txtFoo "LINE ONE\nLINE TWO"
"""
import sys, re, os, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)


def _data(*parts):
    """data/ dir of the ACTIVE project, resolved at call time."""
    return mgproj.path(os.path.join("data", *parts))


def _texts():
    return _data("texts.asm")

# HUD name tables: slug -> (file, index-label). These entries are plain glyph
# runs terminated by 0FFh (no leading TextBoxType byte, no dictionary tokens),
# so they use a simpler codec than texts.asm (see enc_entry / patch_name_label).
NAMEFILES = {
    "items":   ("itemnames.asm",   "idxItemName"),
    "weapons": ("weaponnames.asm", "idxWeaponName"),
}

# byte -> printable glyph (decode side)
GLYPH = {0x00: ' ', 0x3D: '!', 0x3E: '!!', 0x40: '-', 0x5B: '?',
         0x5C: '.', 0x5F: ',', 0x97: "'"}
# text -> byte (encode side); longer keys handled first in encode()
ENC = {'!!': 0x3E, '!': 0x3D, '-': 0x40, '?': 0x5B, '.': 0x5C,
       ',': 0x5F, "'": 0x97, ' ': 0x00}


def b2c(b):
    if b in GLYPH:
        return GLYPH[b]
    if 0x30 <= b <= 0x39 or 0x41 <= b <= 0x5A:
        return chr(b)
    return '?'  # unknown glyph


def parse_db(operand):
    """A `db` operand list -> list of int bytes (expands "strings" and hex/dec)."""
    out = []
    i = 0
    s = operand
    while i < len(s):
        c = s[i]
        if c == '"':
            j = s.index('"', i + 1)
            out += [ord(ch) for ch in s[i + 1:j]]
            i = j + 1
        elif c == "'":                       # single-quoted char literal, e.g. ':'
            j = s.index("'", i + 1)
            out += [ord(ch) for ch in s[i + 1:j]]
            i = j + 1
        elif c in ', \t':
            i += 1
        else:
            m = re.match(r'(#([0-9A-Fa-f]+)|0x([0-9A-Fa-f]+)|([0-9A-Fa-f]+)[hH]|(\d+))', s[i:])
            if not m:
                i += 1
                continue
            g = m.group(2) or m.group(3) or m.group(4)
            out.append(int(g, 16) if g else int(m.group(5)))
            i += m.end()
    return out


def load_texts():
    return open(_texts(), encoding='latin-1').read()


def parse_block(src, label):
    """Raw byte list for a label whose definition may span continuation `db` lines."""
    out = []
    collecting = False
    for ln in src.splitlines():
        code = ln.split(';', 1)[0].rstrip()
        if not code.strip():
            if collecting:
                break
            continue
        m = re.match(r'^(\w+):\s*db\s+(.*)$', code)
        if m and m.group(1) == label:
            out += parse_db(m.group(2))
            collecting = True
            continue
        if collecting:
            m2 = re.match(r'^\s+db\s+(.*)$', code)
            if m2:
                out += parse_db(m2.group(1))
            else:
                break
    return out


def load_dictionary(src):
    order = []
    m = re.search(r'idxDictionary:(.*?)(?=\n\S)', src, re.S)
    for mm in re.finditer(r'dw\s+(\w+)', m.group(1)):
        order.append(mm.group(1))
    toks = []
    for idx, lbl in enumerate(order):
        raw = parse_block(src, lbl)
        if raw and raw[-1] == 0xFF:
            raw = raw[:-1]
        toks.append((0xA1 + idx, ''.join(b2c(b) for b in raw)))
    return toks


def decode(raw, toks):
    d = {t: p for t, p in toks}
    box = raw[0]
    out = []
    for b in raw[1:]:
        if b == 0xFF:
            break
        elif b == 0xFE:
            out.append('\n')
        elif b == 0xFD:
            out.append('\f')
        elif b >= 0xA1:
            out.append(d.get(b, '{tok%02X}' % b))
        else:
            out.append(b2c(b))
    return box, ''.join(out)


def encode(text, box, toks, use_dict=True):
    text = text.upper()
    dic = sorted(toks, key=lambda t: -len(t[1])) if use_dict else []
    out = [box]
    i = 0
    n = len(text)

    def isword(ch):
        return ch.isalnum()

    while i < n:
        ch = text[i]
        if ch == '\n':
            out.append(0xFE); i += 1; continue
        if ch == '\f':
            out.append(0xFD); i += 1; continue
        matched = False
        if use_dict:
            for tb, tp in dic:
                if not tp:
                    continue
                if text.startswith(tp, i):
                    lok = (i == 0) or (not isword(text[i - 1])) or (not isword(tp[0]))
                    end = i + len(tp)
                    rok = (end >= n) or (not isword(text[end])) or (not isword(tp[-1]))
                    if lok and rok:
                        out.append(tb); i = end; matched = True; break
        if matched:
            continue
        if text.startswith('!!', i):
            out.append(ENC['!!']); i += 2; continue
        if ch in ENC:
            out.append(ENC[ch]); i += 1; continue
        if '0' <= ch <= '9' or 'A' <= ch <= 'Z':
            out.append(ord(ch)); i += 1; continue
        out.append(0x00); i += 1  # unknown -> space
    out.append(0xFF)
    return out


def fmt_db(raw, label=None, perline=14):
    def tok(b):
        return ('0%Xh' % b) if b >= 0xA0 else (('%Xh' % b) if b >= 0x0A else str(b))
    body = [tok(b) for b in raw]
    lines = []
    for k in range(0, len(body), perline):
        lines.append('\t\t    db\t' + ', '.join(body[k:k + perline]))
    if label:
        lines[0] = ('%-20s' % (label + ':')) + 'db\t' + ', '.join(body[:perline])
    return '\n'.join(lines)


def _tok(b):
    return ('0%Xh' % b) if b >= 0xA0 else (('%Xh' % b) if b >= 0x0A else str(b))


def enc_entry(text):
    """Encode a dictionary entry: literal glyph bytes + 0xFF, no box, no tokens."""
    return encode(text, 0, [], use_dict=False)[1:]


def build_dict_section(entries):
    out = ["idxDictionary:"]
    for name, _ in entries:
        out.append("\t\t    dw " + name)
    out += ["", ";" + "-" * 76, "; Dictionary entries (NIGHTJAR)", ";" + "-" * 76]
    for name, pt in entries:
        out.append("%-16sdb\t%s" % (name + ":", ", ".join(_tok(b) for b in enc_entry(pt))))
    return "\n".join(out) + "\n"


def regen_dictionary(entries):
    """Replace the dictionary with `entries` (list of (label, plaintext)) and re-encode
    every text against it. Safe: existing texts keep their plaintext, just re-tokenised."""
    assert len(entries) <= 92, "max 92 dictionary entries (tokens 0xA1-0xFC)"
    src = load_texts()
    old = load_dictionary(src)
    plain = {lbl: decode(parse_block(src, lbl), old)
             for lbl in re.findall(r'^(txt\w+):\s*db', src, re.M)}
    new_toks = [(0xA1 + i, pt) for i, (name, pt) in enumerate(entries)]
    lines = src.splitlines()
    didx = next(i for i, l in enumerate(lines) if l.startswith("idxDictionary:"))
    head = lines[:didx]
    new_head = []
    i = 0
    oldsz = newsz = 0
    while i < len(head):
        m = re.match(r'^(txt\w+):\s*db', head[i])
        if m:
            lbl = m.group(1)
            j = i + 1
            while j < len(head) and re.match(r'^\s+db\s', head[j].split(';', 1)[0]):
                j += 1
            if lbl == 'txtEmpty':
                new_head += head[i:j]
            else:
                box, pt = plain[lbl]
                raw = encode(pt, box, new_toks)
                oldsz += len(parse_block(src, lbl))
                newsz += len(raw)
                new_head += fmt_db(raw, lbl).splitlines()
            i = j
        else:
            new_head.append(head[i]); i += 1
    open(_texts(), 'w', encoding='latin-1').write("\n".join(new_head) + "\n" + build_dict_section(entries))
    return oldsz, newsz, len(entries)


def _count_occ(phrase, corpus):
    if phrase == '...':
        return corpus.count('...')
    pat = re.escape(phrase)
    if phrase[0].isalnum():
        pat = r'(?<![A-Z0-9])' + pat
    if phrase[-1].isalnum():
        pat = pat + r'(?![A-Z0-9])'
    return len(re.findall(pat, corpus))


def regen_auto(must_include, max_entries=92):
    """Build a frequency-optimal dictionary over the CURRENT corpus, force-including
    `must_include` phrases. Always fits (it optimises the real text). Returns stats."""
    src = load_texts()
    old = load_dictionary(src)
    plain = {lbl: decode(parse_block(src, lbl), old)[1]
             for lbl in re.findall(r'^(txt\w+):\s*db', src, re.M)}
    corpus = '\x00'.join(plain.values())
    # candidate phrases: must-includes + every multi-letter word in the corpus
    cands = list(dict.fromkeys(['...'] + list(must_include) +
                               re.findall(r'[A-Z0-9]{2,}', corpus)))

    def saving(p):
        L = len(enc_entry(p)) - 1          # glyph bytes (excl. 0xFF)
        c = _count_occ(p, corpus)
        return c * (L - 1) - (L + 3)       # bytes saved vs. literal, incl. table cost

    forced = ['...'] + [m for m in must_include]
    chosen = []
    seen = set()
    for p in forced:                       # force NIGHTJAR terms in
        if p not in seen:
            chosen.append(p); seen.add(p)
    rest = sorted((p for p in cands if p not in seen), key=saving, reverse=True)
    for p in rest:
        if len(chosen) >= max_entries:
            break
        if saving(p) > 0:
            chosen.append(p); seen.add(p)

    def lbl(p):
        if p == '...':
            return 'dicDots'
        return 'dic' + re.sub(r'[^A-Za-z0-9]', '', p.title())
    used = {}
    entries = []
    for p in chosen:
        nm = lbl(p)
        while nm in used:
            nm += 'X'
        used[nm] = 1
        entries.append((nm, p))
    return regen_dictionary(entries)


def patch_label(label, text, box=None, use_dict=True):
    """Rewrite `label`'s db block in data/texts.asm in place. Returns (nbytes, decoded)."""
    src = load_texts()
    toks = load_dictionary(src)
    lines = src.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r'^%s:\s*db' % re.escape(label), ln):
            start = i
            break
    if start is None:
        raise KeyError("label not found: %s" % label)
    orig = parse_block(src, label)
    if box is None:
        box = orig[0] if orig else 0
    end = start + 1
    while end < len(lines) and re.match(r'^\s+db\s', lines[end].split(';', 1)[0]):
        end += 1
    # \n / \f authoring markers — accept either case (the editor's textarea is
    # CSS-uppercased, so a hand-typed marker often arrives as \N / \F)
    text = (text.replace('\\n', '\n').replace('\\N', '\n')
                .replace('\\f', '\f').replace('\\F', '\f'))
    raw = encode(text, box, toks, use_dict=use_dict)
    lines[start:end] = fmt_db(raw, label).splitlines()
    open(_texts(), 'w', encoding='latin-1').write('\n'.join(lines) + '\n')
    return len(raw), decode(raw, toks)[1]


def idx_texts_map(src):
    """{label: [1-based Text IDs]} from the idxTexts dw table. Many IDs map to
    txtEmpty (unused slots); a label may appear at more than one ID."""
    m = re.search(r'^idxTexts:(.*?)(?=\n\S)', src, re.S | re.M)
    out = {}
    if m:
        for i, mm in enumerate(re.finditer(r'dw\s+(\w+)', m.group(1))):
            out.setdefault(mm.group(1), []).append(i + 1)
    return out


def list_texts():
    """Every editable string in data/texts.asm: [{label, box, text, ids}].
    Skips txtEmpty (the shared 'no text' placeholder). `ids` are idxTexts slots
    (1-based) pointing at this label, [] if it is referenced only by name."""
    src = load_texts()
    toks = load_dictionary(src)
    idmap = idx_texts_map(src)
    out = []
    for lbl in re.findall(r'^(txt\w+):\s*db', src, re.M):
        if lbl == 'txtEmpty':
            continue
        raw = parse_block(src, lbl)
        if not raw:
            continue
        box, txt = decode(raw, toks)
        out.append({"label": lbl, "box": box, "text": txt,
                    "ids": idmap.get(lbl, [])})
    return out


def _name_path(slug):
    if slug not in NAMEFILES:
        raise KeyError("unknown name table: %s" % slug)
    return _data(NAMEFILES[slug][0])


def list_names(slug):
    """HUD names from a name table (items/weapons): [{label, text, slot}].
    `slot` is the 0-based position in the idx*Name table (order the engine uses)."""
    file, idxlabel = NAMEFILES[slug]
    src = open(_data(file), encoding='latin-1').read()
    m = re.search(r'^%s:(.*?)(?=\n\S)' % idxlabel, src, re.S | re.M)
    order = re.findall(r'dw\s+(\w+)', m.group(1)) if m else []
    out = []
    for slot, lbl in enumerate(order):
        raw = parse_block(src, lbl)
        if raw and raw[-1] == 0xFF:
            raw = raw[:-1]
        out.append({"label": lbl, "text": ''.join(b2c(b) for b in raw), "slot": slot})
    return out


def _fmt_name_db(raw):
    """Format name bytes back in the source's house style: printable glyph runs
    as "quoted" strings, the space glyph (0) and 0FFh terminator as bare tokens
    (e.g. `"HAND",   0, "GUN", #ff`)."""
    parts = []
    run = ''
    for b in raw[:-1]:                                   # all but the 0FFh
        if 0x20 <= b <= 0x7E and b != ord('"'):
            run += chr(b)
        else:
            if run:
                parts.append('"%s"' % run); run = ''
            parts.append(_tok(b))
    if run:
        parts.append('"%s"' % run)
    parts.append('#ff')
    return ', '.join(parts)


def patch_name_label(slug, label, text):
    """Rewrite a HUD name's db line in itemnames/weaponnames.asm in place, keeping
    the file's quoted house style and EOF-newline state. Encodes as literal glyph
    bytes + 0FFh (no box, no dictionary). Returns (nbytes, decoded)."""
    path = _name_path(slug)
    src = open(path, encoding='latin-1').read()
    had_eol = src.endswith('\n')
    lines = src.splitlines()
    idx = None
    for i, ln in enumerate(lines):
        if re.match(r'^%s:\s*db' % re.escape(label), ln.split(';', 1)[0]):
            idx = i
            break
    if idx is None:
        raise KeyError("name label not found: %s" % label)
    raw = enc_entry(text.replace('\\n', '\n'))          # glyph bytes + 0FFh
    code, sep, comment = lines[idx].partition(';')
    # keep the original label column width + a trailing space before any comment
    m = re.match(r'^(\S+:\s*)db', code)
    head = m.group(1) if m else (label + ':\t    ')
    lines[idx] = '%sdb\t%s %s' % (head, _fmt_name_db(raw), sep + comment) if sep \
        else '%sdb\t%s ' % (head, _fmt_name_db(raw))
    open(path, 'w', encoding='latin-1').write('\n'.join(lines) + ('\n' if had_eol else ''))
    return len(raw), ''.join(b2c(b) for b in raw[:-1])


# ---------------------------------------------------------------------------
# Positioned HUD / menu / title / ending texts.
#
# These files use a different layout than texts.asm: each label is a stream of
# `dw <screen-pos>` words followed by literal glyph runs, segments separated by
# 0FEh (new positioned line) and ended by 0FFh (terminators are sometimes inline
# with the payload, e.g. `db "START", 0, 0, 0FFh`). There is no TextBoxType byte
# and no dictionary. Editing is surgical *per db-line*: we rewrite only the glyph
# payload of one line, preserving its position word, terminator, label + comment.
# ---------------------------------------------------------------------------
POSFILES = {
    "menu-weapon":    ("menuweapontexts.asm",    "Weapon menu"),
    "menu-equipment": ("menuequipmenttexts.asm", "Equipment menu"),
    "menu-radio":     ("menuradiotexts.asm",     "Radio menu"),
    "hud":            ("hudstartendtexts.asm",   "HUD / title / ending"),
}


def enc_glyphs(text):
    """Encode plain text to literal glyph bytes only (no box, no terminator,
    no dictionary) - the payload of a positioned db line."""
    return encode(text, 0, [], use_dict=False)[1:-1]


def _fmt_bytes(bytes_list):
    """Byte list -> source house style: printable ASCII runs as "quoted"
    strings, everything else (the 0 space glyph, hi tiles) as bare tokens."""
    parts, run = [], ''
    for b in bytes_list:
        if 0x20 <= b <= 0x7E and b != ord('"'):
            run += chr(b)
        else:
            if run:
                parts.append('"%s"' % run); run = ''
            parts.append(_tok(b))
    if run:
        parts.append('"%s"' % run)
    return ', '.join(parts) if parts else '""'


def _split_db(code):
    """(prefix-incl-db-and-ws, operand) for a `db` code line, else None."""
    m = re.match(r'^(.*?\bdb\b[ \t]+)(.*)$', code)
    return (m.group(1), m.group(2).rstrip()) if m else None


def _pos_path(slug):
    if slug not in POSFILES:
        raise KeyError("unknown positioned-text table: %s" % slug)
    return _data(POSFILES[slug][0])


def list_positioned(slug):
    """Editable text lines of a positioned-text file, grouped by label:
    [{label, items:[{line, pos, text, editable}]}]. `line` is 0-based; `pos`
    is the segment's screen position word (hex str); non-clean payloads (raw
    tile graphics) are returned editable=False so they show but can't be typed."""
    path = _pos_path(slug)
    lines = open(path, encoding='latin-1').read().splitlines()
    groups, cur_label, cur_pos, gmap = [], None, None, {}
    for i, ln in enumerate(lines):
        code = ln.split(';', 1)[0]
        m = re.match(r'^(\w+):', code)
        if m:
            cur_label = m.group(1)
        mdw = re.search(r'\bdw\s+([0-9A-Fa-f]+)h?\b', code)
        if mdw:
            cur_pos = '%04X' % (int(mdw.group(1), 16) & 0xFFFF)
        sp = _split_db(code.rstrip())
        if not sp:
            continue
        raw = parse_db(sp[1])
        while raw and raw[-1] in (0xFE, 0xFF):       # strip trailing terminators
            raw.pop()
        if not raw:
            continue                                  # terminator-only line
        text = ''.join(b2c(b) for b in raw)
        editable = (enc_glyphs(text) == raw)
        if cur_label not in gmap:
            gmap[cur_label] = {"label": cur_label, "items": []}
            groups.append(gmap[cur_label])
        gmap[cur_label]["items"].append(
            {"line": i, "pos": cur_pos, "text": text, "editable": editable})
    return groups


def patch_positioned(slug, line, text):
    """Rewrite the glyph payload of one db line (0-based `line`) in a positioned-
    text file, preserving its position word, terminator bytes, label + comment.
    Returns (nbytes, decoded)."""
    path = _pos_path(slug)
    src = open(path, encoding='latin-1').read()
    had_eol = src.endswith('\n')
    lines = src.splitlines()
    ln = lines[line]
    code, sep, comment = ln.partition(';')
    sp = _split_db(code.rstrip())
    if not sp:
        raise ValueError("line %d is not a db payload line" % line)
    prefix, operand = sp
    raw = parse_db(operand)
    term = []
    while raw and raw[-1] in (0xFE, 0xFF):
        term.insert(0, raw.pop())
    payload = enc_glyphs(text.replace('\\n', '\n'))
    body = _fmt_bytes(payload)
    if term:
        body += ', ' + ', '.join(_tok(b) for b in term)
    lines[line] = prefix + body + ((' ;' + comment) if sep else '')
    open(path, 'w', encoding='latin-1').write('\n'.join(lines) + ('\n' if had_eol else ''))
    return len(payload), ''.join(b2c(b) for b in payload)


def main():
    src = load_texts()
    toks = load_dictionary(src)
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'

    if cmd == 'selftest':
        print("Dictionary: %d entries (tokens 0xA1-0x%02X)" % (len(toks), 0xA1 + len(toks) - 1))
        for lbl in ['txtSleepy', 'txtMission', 'txtSwitchOffMSX', 'txtSaveEllen',
                    'txtTheyHaveSil', 'txtEmergency']:
            raw = parse_block(src, lbl)
            if not raw:
                print("  (missing %s)" % lbl); continue
            box, txt = decode(raw, toks)
            print("\n[%s] box=0x%02X" % (lbl, box))
            print("  " + txt.replace('\n', ' / ').replace('\f', ' <NEXT> '))
        labels = re.findall(r'^(txt\w+):\s*db', src, re.M)
        ok = bad = 0
        fails = []
        for lbl in labels:
            raw = parse_block(src, lbl)
            if not raw:
                continue
            box, txt = decode(raw, toks)
            box2, txt2 = decode(encode(txt, box, toks), toks)
            if txt2 == txt:
                ok += 1
            else:
                bad += 1
                if len(fails) < 5:
                    fails.append((lbl, txt, txt2))
        print("\nround-trip decode == decode(encode(decode)): %d ok, %d differ" % (ok, bad))
        for lbl, a, b in fails:
            print("  DIFF %s:\n    A=%r\n    B=%r" % (lbl, a, b))
        return

    if cmd == 'decode':
        target = sys.argv[2]
        labels = [target] if target != 'all' else re.findall(r'^(txt\w+):\s*db', src, re.M)
        for lbl in labels:
            raw = parse_block(src, lbl)
            box, txt = decode(raw, toks)
            print("%-20s box=0x%02X | %s" % (lbl, box, txt.replace('\n', '\\n').replace('\f', '\\f')))
        return

    if cmd == 'patch':
        # patch <label> --type 0xNN "text"  -> rewrite that label's block in texts.asm
        ap = argparse.ArgumentParser()
        ap.add_argument('label')
        ap.add_argument('--type', default=None)
        ap.add_argument('--nodict', action='store_true')
        ap.add_argument('text')
        a = ap.parse_args(sys.argv[2:])
        box = None
        if a.type is not None:
            t = a.type
            box = int(t, 16) if (t.lower().startswith('0x') or t.lower().endswith('h')) else int(t, 0)
        nb, dec = patch_label(a.label, a.text, box=box, use_dict=not a.nodict)
        print("patched %s (%d bytes) -> %s" %
              (a.label, nb, dec.replace('\n', ' / ').replace('\f', ' <NEXT> ')))
        return

    if cmd == 'encode':
        ap = argparse.ArgumentParser()
        ap.add_argument('--type', default='0')
        ap.add_argument('--label', default=None)
        ap.add_argument('--nodict', action='store_true')
        ap.add_argument('text')
        a = ap.parse_args(sys.argv[2:])
        t = a.type
        box = int(t, 16) if (t.lower().startswith('0x') or t.lower().endswith('h')) else int(t, 0)
        text = a.text.replace('\\n', '\n').replace('\\f', '\f')
        raw = encode(text, box, toks, use_dict=not a.nodict)
        print(fmt_db(raw, a.label))
        print("; decodes to: " + decode(raw, toks)[1].replace('\n', ' / ').replace('\f', ' <NEXT> '))
        print("; %d bytes" % len(raw))
        return

    print(__doc__)


if __name__ == '__main__':
    main()
