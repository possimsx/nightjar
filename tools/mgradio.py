"""Radio-call codec for Metal Gear MSX / NIGHTJAR.

Models the whole radio-call system from plain data tables, validated by a
byte-fidelity selftest (the repo convention). Reads/edits:

  * data/radiocalls.asm  - idxRoomRadio (room -> call), the RadioRoom_* person
                           chains, and the NoRadio sentinel.
  * Banks0123.asm        - RadioFreqs (person -> frequency byte).
  * constants/Enums.asm  - RADIO_* / FREQ_* values.
  * data/texts.asm       - idxTexts (Text ID -> label); decoded via mgtext.

A radio call is a chain of "persons", each 2 bytes:
    byte0 = flags: person id in bits 7-4, plus mode bits and END (bit0)
    byte1 = Text ID (-> idxTexts -> text)
Mode: bit3 (RADIO_AUTOREPLY) = replies at once + auto-tunes the radio;
      bit2 (RADIO_WAITCALL)  = waits until the player calls (no auto-tune).
The chain ends at the first person whose flags have END (bit0) set.

Editing is SURGICAL: only the touched RadioRoom block / idxRoomRadio entry /
RadioFreqs byte is rewritten, preserving the rest of the file (idempotent).

CLI:  python tools/mgradio.py selftest
      python tools/mgradio.py dump [room]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgtext

import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

RADIO_F = "data/radiocalls.asm"
BANKS_F = "Banks0123.asm"
ENUMS_F = "constants/Enums.asm"

# person id (high nibble, 1-based) -> display name. Mirrors RadioFreqs order.
PERSONS = {
    1: "Big Boss (bldg 1)", 2: "Schneider", 3: "Diane",
    4: "Schneider (bldg 2)", 5: "Diane (bldg 2)", 6: "Jeniffer",
    7: "Big Boss (bldg 2)",
}
RADIO_END = 1
RADIO_WAITCALL = 4
RADIO_AUTOREPLY = 8
NO_RADIO = "NoRadio"


def _read(path):
    """World-aware read via mgmap (D3): RADIO_F follows the active world;
    everything else (RadioFreqs in Banks0123, texts) is shared."""
    import mgmap
    return mgmap.read_text(path)


def _write(path, text):
    import mgmap
    mgmap.write_text(path, text)


def load_enums():
    """{NAME: value} for every `NAME: equ <n>` in Enums.asm (hex 'NNh'/'#NN' or dec)."""
    out = {}
    for m in re.finditer(r'^(\w+):\s*equ\s+([^\s;]+)', _read(ENUMS_F), re.M):
        out[m.group(1)] = _num(m.group(2))
    return out


def _num(tok):
    tok = tok.strip()
    if tok.endswith(("h", "H")):
        return int(tok[:-1], 16)
    if tok.startswith("#"):
        return int(tok[1:], 16)
    return int(tok, 16) if re.fullmatch(r'[0-9A-Fa-f]+', tok) and re.search(r'[A-Fa-f]', tok) else int(tok)


def eval_expr(expr, enums):
    """Evaluate an OR-expression of RADIO_*/numeric tokens -> byte value."""
    val = 0
    for tok in expr.split("|"):
        tok = tok.strip()
        if not tok:
            continue
        val |= enums[tok] if tok in enums else _num(tok)
    return val & 0xFF


def parse_blocks(src, enums):
    """Linear scan of radiocalls.asm up to idxRoomRadio: {label: [byte, ...]}
    in file order. Each db line is one byte (flags or text id)."""
    blocks = {}
    cur = None
    for ln in src.splitlines():
        code = ln.split(";", 1)[0].rstrip()
        if re.match(r'^idxRoomRadio:', code):
            break
        m = re.match(r'^(\w+):\s*db\s+(.*)$', code)
        if m:
            cur = m.group(1)
            blocks[cur] = [eval_expr(m.group(2), enums)]
            continue
        m2 = re.match(r'^\s+db\s+(.*)$', code)
        if m2 and cur is not None:
            blocks[cur].append(eval_expr(m2.group(1), enums))
    return blocks


def parse_idx(src):
    """idxRoomRadio -> list of target labels (room index = position)."""
    m = re.search(r'^idxRoomRadio:(.*)', src, re.S | re.M)
    body = m.group(1)
    out = []
    for ln in body.splitlines():
        code = ln.split(";", 1)[0]
        mm = re.search(r'\bdw\s+(\w+)', code)
        if mm:
            out.append(mm.group(1))
        elif re.match(r'^\w+:', code.strip()) and out:
            break  # next section
    return out


_FREQS = _FREQS_MT = None


def _on_project_switch():
    global _FREQS, _FREQS_MT, _TEXTS, _DICT, _IDXTEXT, _TEXTS_MTIME
    _FREQS = _FREQS_MT = None
    _TEXTS = _DICT = _IDXTEXT = _TEXTS_MTIME = None


mgproj.on_switch(_on_project_switch)


def parse_freqs(enums=None):
    """RadioFreqs (Banks0123.asm) -> [{freq, name}] for every character (person 1..N,
    N<=15). The db-line comment IS the character name (single source of truth);
    falls back to PERSONS for the stock 7 if a comment is blank. mtime-cached."""
    global _FREQS, _FREQS_MT
    mt = os.path.getmtime(mgproj.path(BANKS_F))
    if _FREQS is not None and mt == _FREQS_MT:
        return _FREQS
    if enums is None:
        enums = load_enums()
    src = _read(BANKS_F)
    m = re.search(r'^RadioFreqs:(.*?)(?=\n\S)', src, re.S | re.M)
    out = []
    for ln in m.group(1).splitlines():
        code, _, comment = ln.partition(";")
        mm = re.search(r'\bdb\s+([^\s;]+)', code)
        if mm:
            name = re.sub(r'\s+', " ", comment).strip() or PERSONS.get(len(out) + 1, "Person %d" % (len(out) + 1))
            out.append({"freq": eval_expr(mm.group(1), enums), "name": name})
    _FREQS, _FREQS_MT = out, mt
    return out


def person_name(pid):
    fr = parse_freqs()
    return fr[pid - 1]["name"] if 1 <= pid <= len(fr) else "?"


# mode = the non-person, non-END flag bits (preserved exactly for round-trip).
#   8 (RADIO_AUTOREPLY) = replies at once AND auto-tunes the radio
#   4 (RADIO_WAITCALL)  = waits until the player calls (no auto-tune)
#   0                   = plain auto-reply (no auto-tune)
MODE_BITS = 0x0E
MODE_NAME = {RADIO_AUTOREPLY: "auto", RADIO_WAITCALL: "wait", 0: "reply"}
MODE_VAL = {"auto": RADIO_AUTOREPLY, "wait": RADIO_WAITCALL, "reply": 0}


def decode_persons(byts):
    """[flags,textid,...] -> list of {person, mode, end, text_id}. NoRadio -> []."""
    if not byts or byts[0] == 0:
        return []
    out = []
    for i in range(0, len(byts) - 1, 2):
        f, tid = byts[i], byts[i + 1]
        mbits = f & MODE_BITS
        out.append({
            "person": (f >> 4) & 0xF,
            "person_name": person_name((f >> 4) & 0xF),
            "mode": MODE_NAME.get(mbits, "raw"),
            "mode_bits": mbits,
            "end": bool(f & RADIO_END),
            "text_id": tid,
            "flags": f,
        })
        if f & RADIO_END:
            break
    return out


def encode_persons(persons):
    """list of {person, mode|mode_bits, text_id} -> [flags,textid,...]; END last."""
    out = []
    n = len(persons)
    for i, p in enumerate(persons):
        mbits = p["mode_bits"] if "mode_bits" in p else MODE_VAL.get(p.get("mode", "reply"), 0)
        f = ((int(p["person"]) & 0xF) << 4) | (mbits & MODE_BITS)
        if i == n - 1:
            f |= RADIO_END
        out += [f & 0xFF, int(p["text_id"]) & 0xFF]
    return out


# ---- text preview (Text ID -> string) ---------------------------------------
_TEXTS = _DICT = _IDXTEXT = None
_TEXTS_MTIME = None


def _text_ctx():
    """Texts/dictionary/index, re-read whenever data/texts.asm changes on disk so
    a live editing session sees patched dialogue immediately."""
    global _TEXTS, _DICT, _IDXTEXT, _TEXTS_MTIME
    mt = os.path.getmtime(mgtext._texts())
    if _TEXTS is None or mt != _TEXTS_MTIME:
        _TEXTS = mgtext.load_texts()
        _DICT = mgtext.load_dictionary(_TEXTS)
        m = re.search(r'^idxTexts:(.*?)(?=\n\S)', _TEXTS, re.S | re.M)
        _IDXTEXT = re.findall(r'\bdw\s+(\w+)', m.group(1))
        _TEXTS_MTIME = mt
    return _TEXTS, _DICT, _IDXTEXT


def text_label(tid):
    # Text IDs are 1-based: the engine does idxTexts[TextId-1] (GetText: dec a).
    _, _, idx = _text_ctx()
    return idx[tid - 1] if 1 <= tid <= len(idx) else None


def text_preview(tid):
    """Decoded text for a Text ID, or None."""
    texts, dic, _ = _text_ctx()
    lbl = text_label(tid)
    if not lbl:
        return None
    raw = mgtext.parse_block(texts, lbl)
    if not raw:
        return None
    _, s = mgtext.decode(raw, dic)
    return s


# ---- model ------------------------------------------------------------------
def model():
    enums = load_enums()
    src = _read(RADIO_F)
    blocks = parse_blocks(src, enums)
    idx = parse_idx(src)
    freqs = parse_freqs(enums)
    persons = [{"id": i + 1, "name": f["name"], "freq": f["freq"]} for i, f in enumerate(freqs)]
    rooms = []
    for room, lbl in enumerate(idx):
        ps = decode_persons(blocks.get(lbl, [0]))
        for p in ps:
            p["freq"] = freqs[p["person"] - 1]["freq"] if 1 <= p["person"] <= len(freqs) else None
            p["text"] = text_preview(p["text_id"])
        rooms.append({"room": room, "label": lbl, "persons": ps})
    return {"persons": persons, "rooms": rooms,
            "labels": sorted(b for b in blocks if b != NO_RADIO)}


def room_radio(room):
    mus = room_music(room) or {}
    extra = {k: mus.get(k) for k in ("music", "incoming", "isolated")}
    for r in model()["rooms"]:
        if r["room"] == room:
            return {**r, **extra}
    return {"room": room, "label": NO_RADIO, "persons": [], **extra}


# ---- selftest ---------------------------------------------------------------
def selftest():
    enums = load_enums()
    src = _read(RADIO_F)
    blocks = parse_blocks(src, enums)
    idx = parse_idx(src)
    freqs = parse_freqs(enums)
    errs = []
    if len(idx) != 251:
        errs.append("idxRoomRadio has %d entries (expected 251)" % len(idx))
    for room, lbl in enumerate(idx):
        if lbl not in blocks and lbl != NO_RADIO:
            errs.append("room %d -> undefined label %s" % (room, lbl))
    # every RadioRoom block: pairs, person ids 1-7, END terminates exactly once
    for lbl, byts in blocks.items():
        if lbl == NO_RADIO:
            if byts != [0]:
                errs.append("%s should be [0], got %s" % (lbl, byts))
            continue
        if len(byts) % 2:
            errs.append("%s has odd byte count %d" % (lbl, len(byts)))
            continue
        ps = decode_persons(byts)
        # re-encode the model and confirm it reproduces the original bytes
        if encode_persons([{**p} for p in ps]) != byts:
            errs.append("%s round-trip mismatch: %s -> %s" % (lbl, byts, encode_persons(ps)))
        for p in ps:
            if not 1 <= p["person"] <= len(freqs):
                errs.append("%s person id %d has no RadioFreqs entry" % (lbl, p["person"]))
        if byts[-2] & RADIO_END == 0:
            errs.append("%s last person missing END" % lbl)
    if not 1 <= len(freqs) <= 15:
        errs.append("RadioFreqs has %d entries (expected 1..15)" % len(freqs))
    if errs:
        print("SELFTEST FAIL:")
        for e in errs[:30]:
            print("  -", e)
        return False
    print("SELFTEST PASS: %d rooms, %d call blocks, 7 persons; round-trip byte-exact"
          % (len(idx), sum(1 for b in blocks if b != NO_RADIO)))
    return True


# ---- surgical edits ---------------------------------------------------------
ED_BEGIN = "; === EDITOR RADIO BLOCKS (managed by tools/mgradio.py) ==="
ED_END = "; === END EDITOR RADIO BLOCKS ==="
ED_LABEL = "RadioRoomEd_%03d"


def _emit_block(label, persons):
    """ASM text for one call block: 'LABEL: db flags' + 'db text' per person, with
    a decoded-text comment. persons must be non-empty."""
    byts = encode_persons(persons)
    lines = []
    for i, p in enumerate(persons):
        f, tid = byts[2 * i], byts[2 * i + 1]
        head = ("%-16sdb " % (label + ":")) if i == 0 else "\t\t    db "
        prev = (text_preview(tid) or "").replace("\n", " ").replace("\f", " ")[:60]
        lines.append("%s%02Xh\t\t    ; %s, %s%s" % (
            head, f, person_name((f >> 4) & 0xF), MODE_NAME.get(f & MODE_BITS, "raw"),
            ", END" if f & RADIO_END else ""))
        lines.append("\t\t    db %d\t\t\t    ; %s" % (tid, prev))
    return "\n".join(lines)


def _parse_edited_region(src):
    """{label: [bytes]} for blocks currently in the managed region."""
    m = re.search(re.escape(ED_BEGIN) + r"(.*?)" + re.escape(ED_END), src, re.S)
    if not m:
        return {}
    enums = load_enums()
    return parse_blocks(m.group(1) + "\nidxRoomRadio:", enums)


def _write_region(src, blocks):
    """Insert/replace the managed region (just before NoRadio:) with `blocks`
    ({label: persons-model}). Empty -> region with only the markers."""
    body = [ED_BEGIN]
    for lbl, persons in blocks.items():
        if persons:
            body.append(_emit_block(lbl, persons))
            body.append("")
    body.append(ED_END)
    region = "\n".join(body)
    if ED_BEGIN in src:
        return re.sub(re.escape(ED_BEGIN) + r".*?" + re.escape(ED_END), region, src, flags=re.S)
    return re.sub(r'(?m)^(NoRadio:)', region + "\n\n\\1", src, count=1)


def _write_idx(src, labels):
    """Regenerate the idxRoomRadio dw table (it is the last section of the file)."""
    rows = ["idxRoomRadio:\t    dw %s" % labels[0]] + ["\t\t    dw %s" % l for l in labels[1:]]
    return re.sub(r'(?ms)^idxRoomRadio:.*\Z', "\n".join(rows) + "\n", src)


def set_room_call(room, persons):
    """Set room's radio call. persons = [{person, mode, text_id}, ...] (empty =
    silence the room). Edited blocks live in the managed region; original/shared
    blocks are never touched. Idempotent."""
    src = _read(RADIO_F)
    idx = parse_idx(src)
    if not 0 <= room < len(idx):
        raise ValueError("room %d out of range 0..%d" % (room, len(idx) - 1))
    edited = {lbl: decode_persons(b) for lbl, b in _parse_edited_region(src).items()}
    if persons:
        for p in persons:
            if not 1 <= int(p["person"]) <= len(parse_freqs()):
                raise ValueError("person id must be 1..%d (a defined character)" % len(parse_freqs()))
        lbl = ED_LABEL % room
        edited[lbl] = persons
        idx[room] = lbl
    else:
        idx[room] = NO_RADIO
        edited.pop(ED_LABEL % room, None)
    src = _write_region(src, edited)
    src = _write_idx(src, idx)
    _write(RADIO_F, src)
    return room_radio(room)


# ---- area music & room flags (RoomsMusic byte, data/musicradioconfig.asm) ----
# Each room has one RoomsMusic byte (a SEPARATE table from idxRoomRadio):
#   bits 7-4 = music id   (SetAreaMusic7): 0 Theme of Tara, 1 Sneaking mission,
#              2 TX55 Metal Gear, 3 Escape beyond Big Boss, 4+ red-alert sfx.
#              (The file header's "4 = Escape" mislabels it - the code maps
#               Escape to nibble 3; the data only uses 0/1/2/4.)
#   bit 3    = incoming-call HUD sign (ChkRadioCalls `and 8`). Decoupled from the
#              actual call in idxRoomRadio - if they disagree you get a phantom
#              sign with no dialogue (or a silent call with no sign).
#   bits 2-0 = IsolatedRoom (ChkIsolatedRoom `and 7`): drives TWO independent
#              engine checks - shots don't trigger the alarm only when the field
#              == 1 (checkweaponalert), and binoculars are blocked when it is != 0
#              (menuequipment). Real data only ever uses 0 or 1, so the editor
#              treats it as one "isolated room" flag (1=on).
# Edits are SURGICAL: only the one changed byte is rewritten. Values are printed
# in the file's own convention (<10 decimal, else 2-digit hex `NNh`), which
# reproduces every stock token byte-for-byte -> idempotent. Rooms 16-31 appear
# twice under IF(JAPANESE)/ELSE; JAPANESE equ 0, so only the ELSE (English)
# branch is indexed and edited.
MUSIC_F = "data/musicradioconfig.asm"
CALL_BIT = 8

# music nibble -> label (ground truth = SetAreaMusic7, not the file header)
MUSIC_NAMES = [
    (0, "Theme of Tara"),
    (1, "Sneaking mission"),
    (2, "TX55 Metal Gear"),
    (3, "Escape beyond Big Boss"),
    (4, "Red alert (sfx surprise)"),
]


def _music_cells():
    """(lines, cells) for the RoomsMusic table. cells = [{room, line, part, val}]
    walked in room order, skipping the IF(JAPANESE) branch (English build)."""
    lines = _read(MUSIC_F).split("\n")
    cells, room = [], 0
    started = skip = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not started:
            if s.startswith("RoomsMusic:"):
                started = True
            else:
                continue
        elif re.match(r'^\w+:', s):                 # next label -> table ended
            break
        if re.match(r'(?i)^\s*IF\b', ln):
            skip = True; continue
        if re.match(r'(?i)^\s*(ELSE|ENDIF)\b', ln):
            skip = False; continue
        code = ln.split(";", 1)[0]
        m = re.search(r'\bdb\b(.*)$', code)
        if not m:
            continue
        for pidx, raw in enumerate(m.group(1).split(",")):
            if raw.strip() == "":
                continue
            if not skip:
                cells.append({"room": room, "line": i, "part": pidx, "val": _num(raw.strip())})
            room += 1 if not skip else 0
    return lines, cells


def _fmt_byte(val):
    """Format a byte in the RoomsMusic file convention: values <10 in decimal,
    else 2-digit uppercase hex `NNh` (with a leading 0 if it starts A-F). This
    reproduces every stock token exactly, so unchanged bytes stay byte-identical."""
    if val < 10:
        return str(val)
    s = format(val, "02X")
    return ("0" + s if s[0] in "ABCDEF" else s) + "h"


def _decode_music(val):
    return {"raw": val, "music": (val >> 4) & 0xF, "incoming": bool(val & CALL_BIT),
            "isolated": bool(val & 7), "iso_raw": val & 7}


def room_music(room):
    """Decoded RoomsMusic byte for a room -> {room, raw, music, incoming,
    isolated, iso_raw} (None if the room is past the table)."""
    v = next((c["val"] for c in _music_cells()[1] if c["room"] == room), None)
    if v is None:
        return None
    return {"room": room, **_decode_music(v)}


def music_map():
    """{room: decoded} for every room in RoomsMusic (for the map overview)."""
    return {c["room"]: _decode_music(c["val"]) for c in _music_cells()[1]}


def incoming_call(room):
    """True if the room's RoomsMusic byte has the incoming-call sign bit set."""
    m = room_music(room)
    return bool(m and m["incoming"])


def incoming_map():
    """{room: bool} of the incoming-call sign bit for every room in RoomsMusic."""
    return {r: d["incoming"] for r, d in music_map().items()}


def _write_music_byte(room, newval):
    """Surgically rewrite one room's RoomsMusic byte (only if it changed)."""
    lines, cells = _music_cells()
    cell = next((c for c in cells if c["room"] == room), None)
    if cell is None:
        top = cells[-1]["room"] if cells else -1
        raise ValueError("room %d not in RoomsMusic (0..%d)" % (room, top))
    if newval == cell["val"]:
        return
    ln = lines[cell["line"]]
    code, sep, comment = ln.partition(";")
    m = re.search(r'\bdb\b', code)
    head, operand = code[:m.end()], code[m.end():]
    parts = operand.split(",")
    raw = parts[cell["part"]]
    lead = raw[:len(raw) - len(raw.lstrip())]
    trail = raw[len(raw.rstrip()):]
    parts[cell["part"]] = lead + _fmt_byte(newval) + trail
    lines[cell["line"]] = head + ",".join(parts) + (sep + comment if sep else "")
    _write(MUSIC_F, "\n".join(lines))


def set_room_music(room, music=None, incoming=None, isolated=None):
    """Set any of a room's RoomsMusic fields (leave a field None to keep it).
    music = 0..15 nibble; incoming/isolated = bool. Rebuilds the byte from its
    parts, preserving the low-bits value untouched when `isolated` is None.
    Surgical + idempotent. Returns the decoded room_music(room)."""
    cur = room_music(room)
    if cur is None:
        raise ValueError("room %d not in RoomsMusic" % room)
    nib = cur["music"] if music is None else (int(music) & 0xF)
    call = cur["incoming"] if incoming is None else bool(incoming)
    low = cur["iso_raw"] if isolated is None else (1 if isolated else 0)
    newval = (nib << 4) | (CALL_BIT if call else 0) | (low & 7)
    _write_music_byte(room, newval)
    return room_music(room)


def set_incoming_call(room, on):
    """Set/clear the room's incoming-call sign bit (RoomsMusic bit3). Returns
    {room, incoming}."""
    return {"room": room, "incoming": set_room_music(room, incoming=on)["incoming"]}


# ---- state-conditional radio-reply overrides (RadioOverrides, Banks0123) -----
# The engine's ChkReplyBigBoss interpreter walks this table when the player dials
# a caller: if the entry's frequency matches AND its condition flag (a RAM byte)
# is nonzero, the caller's reply text is swapped for the entry's text. First
# match wins (order = priority). Reworked from two hardcoded Big Boss branches
# (the "switch off your MSX" fake-out and the "you've been bugged" warning) so any
# caller can be given a flag-gated alternate line. Editable data, surgical edits.
OVERRIDES_F = "Banks0123.asm"

# Curated RAM flag bytes offered as conditions (nonzero = condition met). Each is
# a real Variables.asm label; the comment is the display name.
# Named story/event flags (RAM bytes) offered as reply conditions, plus the
# general-purpose GateFlags pool (0..8) so a call can be gated on ANY flag you
# arm from the gates editor -- e.g. "read text A -> set GateFlags+0" then
# "Big Boss + GateFlags+0 -> text B", entirely data-driven.
RADIO_CONDITIONS = [
    ("SwitchOffMSXF", "\"Switch off your MSX\" event is active"),
    ("TransmiTaken", "carrying the enemy bug (transmitter)"),
    ("SchneiderCaptured", "Schneider has been captured"),
    ("MadnarMoved", "Madnar moved to Building 2 (\"it's too late\")"),
] + [("GateFlags+%d" % n, "General flag %d (radio/gate pool)" % n) for n in range(9)]
_COND_NAMES = dict(RADIO_CONDITIONS)


def _freq_to_person(enums=None):
    """{frequency value -> person id} from RadioFreqs (for naming overrides)."""
    return {d["freq"]: i + 1 for i, d in enumerate(parse_freqs(enums))}


def _override_block(src):
    m = re.search(r'(?ms)^(RadioOverrides:)(.*?)(\n\s*db\s+0FFh)', src)
    if not m:
        raise ValueError("RadioOverrides table not found in %s" % OVERRIDES_F)
    return m


def parse_overrides():
    """Read RadioOverrides -> [{person, freq, flag, text, caller, cond}]. Each
    entry is `db <freq>, dw <flag>, db <text>` (freq may be a FREQ_* symbol)."""
    src = _read(OVERRIDES_F)
    enums = load_enums()
    f2p = _freq_to_person(enums)
    toks = []
    for ln in _override_block(src).group(2).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\b(db|dw)\s+(.*)$', code)
        if dm:
            toks.append((dm.group(1), dm.group(2).strip()))
    out = []
    for i in range(0, len(toks) - 2, 3):
        freq = enums.get(toks[i][1], None)
        if freq is None:
            freq = _num(toks[i][1])
        flag = toks[i + 1][1]
        text = int(toks[i + 2][1]) if toks[i + 2][1].isdigit() else _num(toks[i + 2][1])
        pid = f2p.get(freq)
        out.append({"person": pid, "freq": freq, "flag": flag, "text": text,
                    "caller": person_name(pid) if pid else "freq %02Xh" % freq,
                    "cond": _COND_NAMES.get(flag, flag)})
    return out


# Late-game events (madnarbigbossevent.asm, Banks789) that are armed by entering
# ONE room. Stock hardcoded the room numbers; reworked into editable `db` bytes so
# the designer picks the trigger room. Returns None if the byte isn't in the
# active project (base-only feature; stale project copy).
EVENTS_F = "logic/madnarbigbossevent.asm"


def _event_room(label):
    m = re.search(r'(?m)^%s:\s*db\s+(\d+)' % label, _read(EVENTS_F))
    return int(m.group(1)) if m else None


def _set_event_room(label, room):
    src = _read(EVENTS_F)
    new = re.sub(r'(?m)^(%s:\s*db\s+)\d+' % label,
                 lambda mm: mm.group(1) + str(int(room) & 0xFF), src, count=1)
    if new == src and (label + ":") not in src:
        raise ValueError("%s byte not found in %s" % (label, EVENTS_F))
    if new != src:
        _write(EVENTS_F, new)
    return _event_room(label)


def switchoff_room():
    """Room that arms the Big Boss 'switch off your MSX' event (SwitchOffMSXF)."""
    return _event_room("SwitchOffMsxRoom")


def set_switchoff_room(room):
    return _set_event_room("SwitchOffMsxRoom", room)


def madnar_room():
    """Room that fires the 'Madnar has been moved / it's too late' event."""
    return _event_room("MadnarMovedRoom")


def set_madnar_room(room):
    return _set_event_room("MadnarMovedRoom", room)


def overrides_model():
    """Everything the editor needs to render/edit the conditional-reply table.
    `available` is False when the RadioOverrides table isn't in the active
    project's Banks0123.asm (base-only engine feature; stale project copy)."""
    try:
        ov, available = parse_overrides(), True
    except ValueError:
        ov, available = [], False
    return {"overrides": ov, "available": available,
            "conditions": [{"flag": f, "name": n} for f, n in RADIO_CONDITIONS],
            "switchoff_room": switchoff_room(),
            "madnar_room": madnar_room(),
            "persons": model()["persons"]}


def set_overrides(entries):
    """Editor write: replace the whole RadioOverrides table. entries =
    [{person, flag, text}, ...]; the caller's frequency is taken from the person's
    RadioFreqs row. Surgical (only the table body is rewritten), idempotent."""
    src = _read(OVERRIDES_F)
    m = _override_block(src)
    freqs = parse_freqs()
    valid_flags = {f for f, _ in RADIO_CONDITIONS}
    lines = []
    for e in entries:
        pid = int(e["person"])
        if not 1 <= pid <= len(freqs):
            raise ValueError("unknown caller person id %d" % pid)
        flag = str(e["flag"]).strip()
        if flag not in valid_flags:
            raise ValueError("unknown condition flag %r" % flag)
        tid = int(e["text"]) & 0xFF
        fv = freqs[pid - 1]["freq"]
        lines.append("\t\t    db\t    0%02Xh\t\t    ; %s" % (fv, freqs[pid - 1]["name"]))
        lines.append("\t\t    dw\t    %s" % flag)
        lines.append("\t\t    db\t    %d\t\t\t    ; %s" % (tid, _COND_NAMES.get(flag, flag)))
    body = "\n" + "\n".join(lines) + ("\n" if lines else "")
    new = src[:m.start(2)] + body + src[m.end(2):]
    if new != src:
        _write(OVERRIDES_F, new)
    return overrides_model()


def alloc_text(text, box=0x13):
    """Allocate a NEW Text ID with its own dialogue: append `dw txtNewNNN` to
    idxTexts and define the encoded text just before the dictionary. Existing ids
    are untouched (new id = current count + 1, 1-based). box 0x13 = radio. Returns
    {text_id, label, text}. Encodes against the existing dictionary (no regen)."""
    src = open(mgtext._texts(), encoding="latin-1").read()
    toks = mgtext.load_dictionary(src)
    raw = mgtext.encode((text or "").upper(), box, toks)
    m = re.search(r'(^idxTexts:.*?)(?=\n\S)', src, re.S | re.M)
    block = m.group(1)
    new_id = len(re.findall(r'\bdw\s+\w+', block)) + 1
    label = "txtNew%03d" % new_id
    newblock = block.rstrip() + "\n\t\t    dw %s\t\t\t    ; %d (editor-allocated)" % (label, new_id)
    src = src.replace(block, newblock, 1)
    textdef = mgtext.fmt_db(raw, label)
    src = src.replace("\nidxDictionary:", "\n" + textdef + "\n\n\nidxDictionary:", 1)
    open(mgtext._texts(), "w", encoding="latin-1").write(src)
    return {"text_id": new_id, "label": label, "text": text_preview(new_id)}


def text_used_by(tid):
    """Rooms whose radio call references Text ID `tid`."""
    return sorted({r["room"] for r in model()["rooms"]
                   for p in r["persons"] if p["text_id"] == tid})


def prisoner_text_used_by(tid):
    """Prisoner rooms referencing Text ID `tid` (lazy import to avoid a cycle:
    mgprisoner imports mgradio). [] if the prisoner codec isn't available."""
    try:
        import mgprisoner
        return mgprisoner.text_used_by(tid)
    except Exception:
        return []


def allocated_texts():
    """Every editor-allocated text (label txtNew*): id, label, decoded text, and
    the rooms (if any) that use it. For the 'Allocated text IDs' manager."""
    src = open(mgtext._texts(), encoding="latin-1").read()
    blk = re.search(r'(^idxTexts:.*?)(?=\n\S)', src, re.S | re.M).group(1)
    labels = re.findall(r'\bdw\s+(\w+)', blk)
    out = []
    for i, lab in enumerate(labels):
        if lab.startswith("txtNew"):
            tid = i + 1
            out.append({"id": tid, "label": lab, "text": text_preview(tid),
                        "rooms": text_used_by(tid), "prisoners": prisoner_text_used_by(tid)})
    return out


def _def_span(lines, label):
    """(start, end) line indices of a `label: db ...` block incl. continuation db lines."""
    for i, l in enumerate(lines):
        if re.match(r'^%s:\s*db' % re.escape(label), l):
            j = i + 1
            while j < len(lines) and re.match(r'^\s+db\s', lines[j].split(";", 1)[0]):
                j += 1
            return i, j
    return None, None


def delete_text(tid):
    """Delete/free an editor-allocated Text ID (must be unused). If it is the last
    idxTexts entry it is physically removed (table shrinks); otherwise its slot is
    repointed to txtEmpty and the definition dropped (id stays as a reusable blank,
    so positional ids of in-use texts never shift)."""
    label = text_label(tid)
    if not label or not label.startswith("txtNew"):
        raise ValueError("id %d (%s) is not editor-allocated; only txtNew* ids can be deleted"
                         % (tid, label))
    used = text_used_by(tid)
    pused = prisoner_text_used_by(tid)
    if used or pused:
        parts = []
        if used:
            parts.append("radio room(s) %s" % ", ".join(map(str, used)))
        if pused:
            parts.append("prisoner room(s) %s" % ", ".join(map(str, pused)))
        raise ValueError("text %d is used by %s - reassign or silence them first"
                         % (tid, "; ".join(parts)))
    src = open(mgtext._texts(), encoding="latin-1").read()
    total = len(re.findall(r'\bdw\s+\w+', re.search(r'(^idxTexts:.*?)(?=\n\S)', src, re.S | re.M).group(1)))
    lines = src.split("\n")
    dwi = next(i for i, l in enumerate(lines) if re.search(r'\bdw\s+%s\b' % re.escape(label), l))
    ds, de = _def_span(lines, label)
    # remove the definition first (it sits after idxTexts, so dwi stays valid)
    if ds is not None:
        del lines[ds:de]
    if tid == total:                       # last entry -> shrink the table
        del lines[dwi]
        action = "removed (table shrank)"
    else:                                  # middle -> free the slot
        lines[dwi] = re.sub(r'\bdw\s+%s\b' % re.escape(label), "dw txtEmpty", lines[dwi]) + "  ; freed"
        action = "freed (slot -> txtEmpty)"
    open(mgtext._texts(), "w", encoding="latin-1").write("\n".join(lines))
    return {"ok": True, "id": tid, "label": label, "action": action}


def _freq_idxs(lines):
    """Line indices of the RadioFreqs rows (the label line + continuation db lines)."""
    start = next(i for i, l in enumerate(lines) if l.startswith("RadioFreqs:"))
    idxs = [start]
    j = start + 1
    while j < len(lines) and re.match(r'^\s+db\s', lines[j].split(";", 1)[0]):
        idxs.append(j)
        j += 1
    return idxs


def set_freq(person_id, value):
    """Set a character's frequency byte (the db operand on its RadioFreqs line),
    preserving its name comment. Surgical."""
    lines = _read(BANKS_F).split("\n")
    idxs = _freq_idxs(lines)
    if not 1 <= person_id <= len(idxs):
        raise ValueError("character id must be 1..%d" % len(idxs))
    li = idxs[person_id - 1]
    lines[li] = re.sub(r'(\bdb\s+)[^\s;]+',
                       lambda m: m.group(1) + ("%02Xh" % (value & 0xFF)), lines[li], count=1)
    _write(BANKS_F, "\n".join(lines))
    return {"person": person_id, "freq": value & 0xFF}


def rename_character(person_id, name):
    """Set a character's display name = the RadioFreqs db-line comment (the names'
    single source of truth)."""
    lines = _read(BANKS_F).split("\n")
    idxs = _freq_idxs(lines)
    if not 1 <= person_id <= len(idxs):
        raise ValueError("character id must be 1..%d" % len(idxs))
    li = idxs[person_id - 1]
    nm = re.sub(r'[;\r\n]', " ", (name or "").strip())
    lines[li] = lines[li].split(";", 1)[0].rstrip() + ("\t\t    ; " + nm if nm else "")
    _write(BANKS_F, "\n".join(lines))
    return {"person": person_id, "name": nm}


def add_character(name, freq):
    """Append a new character (a RadioFreqs row: frequency byte + name comment).
    Returns the new person id. Max 15 (person id is a 4-bit nibble)."""
    lines = _read(BANKS_F).split("\n")
    idxs = _freq_idxs(lines)
    if len(idxs) >= 15:
        raise ValueError("max 15 characters (person id is a 4-bit nibble)")
    nm = re.sub(r'[;\r\n]', " ", (name or "").strip()) or "Person %d" % (len(idxs) + 1)
    lines.insert(idxs[-1] + 1, "\t\t    db %02Xh\t\t\t    ; %s" % (freq & 0xFF, nm))
    _write(BANKS_F, "\n".join(lines))
    return {"id": len(idxs) + 1, "name": nm, "freq": freq & 0xFF}


def persons_used_by(pid):
    """Rooms whose radio call has a caller of character `pid`."""
    return sorted({r["room"] for r in model()["rooms"]
                   for p in r["persons"] if p["person"] == pid})


def delete_character(pid):
    """Remove a character. Person ids are positional, so only the LAST RadioFreqs
    row can be removed without shifting the others, and only if it is unused."""
    lines = _read(BANKS_F).split("\n")
    idxs = _freq_idxs(lines)
    n = len(idxs)
    if not 1 <= pid <= n:
        raise ValueError("character id must be 1..%d" % n)
    if pid != n:
        raise ValueError("only the last character (#%d) can be deleted; ids are positional" % n)
    used = persons_used_by(pid)
    if used:
        raise ValueError("character %d is used by room(s) %s - reassign them first"
                         % (pid, ", ".join(map(str, used))))
    del lines[idxs[-1]]
    _write(BANKS_F, "\n".join(lines))
    return {"ok": True, "deleted": pid}


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "dump":
        m = model()
        rooms = [r for r in m["rooms"] if r["persons"]]
        if len(sys.argv) >= 3:
            rooms = [r for r in m["rooms"] if r["room"] == int(sys.argv[2])]
        for r in rooms:
            print("room %3d (%s):" % (r["room"], r["label"]))
            for p in r["persons"]:
                print("   %-20s freq %02Xh  %-4s  text#%-3d  %s"
                      % (p["person_name"], p["freq"] or 0, p["mode"], p["text_id"],
                         (p["text"] or "")[:60].replace("\n", " ")))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
