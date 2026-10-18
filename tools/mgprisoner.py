"""Prisoner-dialogue codec for Metal Gear MSX / NIGHTJAR.

Models which Text ID each rescued prisoner speaks. The data lives in
`logic/actors/prisoner.asm`:

  * RoomsPrisoner  - the prisoner roster: room id per prisoner. Position = the
                     RescuedArray index. Read-only here (placing a prisoner is an
                     actor edit); we use it only to enumerate the prisoners.
  * PrisonerTexts  - `db <room>, <Text ID>` rows: the 19 data-table prisoners
                     (incl. room 129). Each prisoner's rescue line is editable by
                     repointing the Text ID, surgically (only that operand moves).
  * Hardcoded specials - Ellen (167), Dr. Madnar (182) and the Coward Duck room
                     (193) print their lines from `ld` immediates in code, not the
                     table. We locate those operands by stable code anchors (a
                     nearby `cp`/label, never the value itself) so they round-trip.

Text previews and Text-ID allocation reuse the shared text codec (mgtext) via
mgradio's helpers (idxTexts is the single text table for the whole game).

CLI:  python tools/mgprisoner.py selftest
      python tools/mgprisoner.py dump
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgradio  # text_label / text_preview / alloc_text (idxTexts is shared)

import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

PRIS_F = "logic/actors/prisoner.asm"

# Prisoner text box type (in-game message window). Matches every existing
# long prisoner line (decoded box byte = 0x11); used when allocating new ones.
PRISONER_BOX = 0x11

text_label = mgradio.text_label
text_preview = mgradio.text_preview


def _read():
    return open(mgproj.path(PRIS_F), encoding="latin-1").read()


def _write(text):
    open(mgproj.path(PRIS_F), "w", encoding="latin-1").write(text)


# ---- generic db-table parsing ----------------------------------------------
def _table_bytes(src, label):
    """All integer operands of `label:` and its continuation `db` lines, in order.
    Numbers may be decimal or NNh hex."""
    out = []
    collecting = False
    for ln in src.splitlines():
        code = ln.split(";", 1)[0].rstrip()
        m = re.match(r'^%s:\s*db\s+(.*)$' % re.escape(label), code)
        if m:
            out += _nums(m.group(1)); collecting = True; continue
        if collecting:
            m2 = re.match(r'^\s+db\s+(.*)$', code)
            if m2:
                out += _nums(m2.group(1))
            else:
                break
    return out


def _nums(operand):
    return [_num(t) for t in re.findall(r'[0-9A-Fa-f]+[hH]|\d+', operand)]


def _num(tok):
    return int(tok[:-1], 16) if tok[-1] in "hH" else int(tok)


def _table_span(lines, label):
    """(start, end) line indices of `label:` + its continuation `db` lines, so a
    row search stays inside the table (room ids also appear in other db tables)."""
    start = next((i for i, l in enumerate(lines)
                  if re.match(r'^%s:\s*db\b' % re.escape(label), l)), None)
    if start is None:
        raise ValueError("table %s not found" % label)
    end = start + 1
    while end < len(lines) and re.match(r'^\s+db\s', lines[end].split(";", 1)[0]):
        end += 1
    return start, end


def parse_roster(src):
    """RoomsPrisoner -> [room, ...] (index = RescuedArray index)."""
    return _table_bytes(src, "RoomsPrisoner")


def parse_texts_table(src):
    """PrisonerTexts -> [(room, text_id), ...] in file order."""
    flat = _table_bytes(src, "PrisonerTexts")
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


# ---- hardcoded special prisoners --------------------------------------------
# Each entry: name + slots. A slot is one editable Text ID located by a stable
# code anchor (find `find`, then the Nth matching `ld <reg>, <imm>` at/after it),
# never by the current value -> idempotent re-editing. `radix` preserves how the
# operand is written (hex for Ellen's 81h, decimal for the rest).
SPECIALS = {
    167: {"name": "Ellen (Dr. Pettrovich's daughter)", "slots": [
        {"key": "ellen", "label": "Ellen's rescue line",
         "find": r'\bcp\s+167\b', "reg": "b", "nth": 0, "back": True, "radix": "hex"},
    ]},
    182: {"name": "Dr. Madnar", "slots": [
        {"key": "madnar", "label": "Madnar line (before Ellen is saved)",
         "note": "+1 is shown once Ellen is rescued (the Metal Gear briefing).",
         "find": r'^MadnarLogic:', "reg": "a", "nth": 0, "back": False, "radix": "dec"},
    ]},
    193: {"name": "Coward Duck room prisoner", "slots": [
        {"key": "rescued", "label": "Generic rescue line",
         "find": r'^ChkRescJenBro:', "reg": "a", "nth": 0, "back": False, "radix": "dec"},
        {"key": "brother", "label": "Jennifer's brother line",
         "find": r'^ChkRescJenBro:', "reg": "a", "nth": 1, "back": False, "radix": "dec"},
    ]},
    189: {"name": "Fake Madnar", "editable": False,
          "note": "Handled in logic/actors/fakemadnar.asm, not the prisoner tables."},
}


def _locate_slot(lines, slot):
    """(line_index, current_value) for a special slot, or (None, None)."""
    anchor = next((i for i, l in enumerate(lines) if re.search(slot["find"], l)), None)
    if anchor is None:
        return None, None
    pat = re.compile(r'\bld\s+%s,\s*([0-9A-Fa-f]+[hH]|\d+)\b' % slot["reg"])
    rng = range(anchor, -1, -1) if slot["back"] else range(anchor, len(lines))
    hits = [i for i in rng if pat.search(lines[i].split(";", 1)[0])]
    if len(hits) <= slot["nth"]:
        return None, None
    li = hits[slot["nth"]]
    return li, _num(pat.search(lines[li].split(";", 1)[0]).group(1))


def _slot_view(lines, slot):
    li, val = _locate_slot(lines, slot)
    out = {"key": slot["key"], "label": slot["label"],
           "text_id": val, "text": text_preview(val) if val else None,
           "editable": li is not None, "radix": slot.get("radix", "dec")}
    if slot.get("note"):
        out["note"] = slot["note"]
    return out


# ---- model ------------------------------------------------------------------
def model():
    """Every prisoner (from RoomsPrisoner) with its editable dialogue slot(s)."""
    src = _read()
    roster = parse_roster(src)
    table = dict(parse_texts_table(src))
    lines = src.split("\n")
    out = []
    for i, room in enumerate(roster):
        if room in SPECIALS:
            sp = SPECIALS[room]
            slots = [_slot_view(lines, s) for s in sp.get("slots", [])]
            out.append({"room": room, "rescue_index": i, "kind": "special",
                        "name": sp["name"], "note": sp.get("note", ""),
                        "editable": sp.get("editable", True), "slots": slots})
        else:
            tid = table.get(room)
            out.append({"room": room, "rescue_index": i, "kind": "table",
                        "name": None, "note": "", "editable": True,
                        "slots": [{"key": "text", "label": "rescue dialogue",
                                   "text_id": tid, "text": text_preview(tid) if tid else None,
                                   "editable": True, "radix": "dec"}]})
    return {"prisoners": out}


def prisoner(room):
    for p in model()["prisoners"]:
        if p["room"] == room:
            return p
    return None


# ---- surgical edits ---------------------------------------------------------
def _fmt(value, radix):
    value &= 0xFF
    return ("%02Xh" % value) if radix == "hex" else str(value)


def _comment(text_id, prefix="TEXT: "):
    """A fresh '; TEXT: ...' comment from the decoded line, so the ASM stays
    self-documenting after an edit (newline/next-page shown as *)."""
    s = (text_preview(text_id) or "").replace("\n", "*").replace("\f", "*")
    return "; %s%s" % (prefix, s[:70])


def _set_table_text(room, text_id):
    """Repoint a PrisonerTexts row's Text ID (the 2nd operand), keeping the room
    operand and the line's comment untouched."""
    lines = _read().split("\n")
    start, end = _table_span(lines, "PrisonerTexts")
    pat = re.compile(r'(\bdb\s+%d\s*,\s*)(\d+)' % room)
    for i in range(start, end):
        if pat.search(lines[i].split(";", 1)[0]):
            code = lines[i].split(";", 1)[0].rstrip()
            code = pat.sub(lambda m: m.group(1) + str(text_id & 0xFF), code, count=1)
            lines[i] = "%-32s%s" % (code, _comment(text_id, prefix="I'm saved! "))
            _write("\n".join(lines))
            return
    raise ValueError("room %d not found in PrisonerTexts" % room)


def _set_special_slot(room, key, text_id):
    sp = SPECIALS[room]
    slot = next((s for s in sp.get("slots", []) if s["key"] == key), None)
    if slot is None:
        raise ValueError("prisoner %d has no slot %r" % (room, key))
    lines = _read().split("\n")
    li, _cur = _locate_slot(lines, slot)
    if li is None:
        raise ValueError("could not locate slot %r for prisoner %d" % (key, room))
    pat = re.compile(r'(\bld\s+%s,\s*)([0-9A-Fa-f]+[hH]|\d+)\b' % slot["reg"])
    # replace the operand and refresh the comment so the ASM stays documented
    code = lines[li].split(";", 1)[0].rstrip()
    code = pat.sub(lambda m: m.group(1) + _fmt(text_id, slot.get("radix", "dec")), code, count=1)
    lines[li] = "%-44s%s" % (code, _comment(text_id))
    _write("\n".join(lines))


def set_text_id(room, text_id, slot="text"):
    """Point a prisoner's rescue line at Text ID `text_id`. `slot` selects which
    line for the hardcoded specials (167/182/193); table prisoners use 'text'."""
    text_id = int(text_id)
    if not 1 <= text_id <= len(mgradio._text_ctx()[2]):
        raise ValueError("Text ID %d out of range" % text_id)
    if room in SPECIALS:
        if not SPECIALS[room].get("editable", True):
            raise ValueError("prisoner %d (%s) is not editable here" % (room, SPECIALS[room]["name"]))
        _set_special_slot(room, slot, text_id)
    else:
        _set_table_text(room, text_id)
    return prisoner(room)


def alloc_text(text):
    """Allocate a fresh Text ID (its own dialogue) for a prisoner line, using the
    in-game message box. Reuses the shared text allocator."""
    return mgradio.alloc_text(text or "RESCUED!", box=PRISONER_BOX)


def text_used_by(tid):
    """Prisoner rooms whose rescue line (any slot) references Text ID `tid`. Used by
    the shared allocated-text manager so a prisoner-used id can't be deleted."""
    tid = int(tid)
    return sorted({p["room"] for p in model()["prisoners"]
                   for s in p["slots"] if s["text_id"] == tid})


# ---- selftest ---------------------------------------------------------------
def selftest():
    src = _read()
    roster = parse_roster(src)
    table = parse_texts_table(src)
    lines = src.split("\n")
    errs = []
    if len(roster) != 23:
        errs.append("RoomsPrisoner has %d entries (expected 23)" % len(roster))
    table_rooms = [r for r, _ in table]
    if len(table) != 19:
        errs.append("PrisonerTexts has %d rows (expected 19)" % len(table))
    # the 4 specials are exactly the roster rooms missing from the table
    missing = [r for r in roster if r not in table_rooms]
    if sorted(missing) != sorted(SPECIALS):
        errs.append("specials %s != roster-minus-table %s" % (sorted(SPECIALS), sorted(missing)))
    for r in table_rooms:
        if r in SPECIALS:
            errs.append("room %d is both a table row and a special" % r)
        if r not in roster:
            errs.append("PrisonerTexts room %d not in RoomsPrisoner" % r)
    # table edit is idempotent: re-writing the current Text ID changes nothing
    tstart, tend = _table_span(lines, "PrisonerTexts")
    for room, tid in table:
        pat = re.compile(r'(\bdb\s+%d\s*,\s*)(\d+)' % room)
        hit = next((lines[i] for i in range(tstart, tend)
                    if pat.search(lines[i].split(";", 1)[0])), None)
        if hit is None or pat.sub(lambda m: m.group(1) + str(tid), hit, count=1) != hit:
            errs.append("PrisonerTexts row %d not idempotent" % room)
    # every special slot must be locatable and its rewrite idempotent
    for room, sp in SPECIALS.items():
        for slot in sp.get("slots", []):
            li, val = _locate_slot(lines, slot)
            if li is None:
                errs.append("special %d slot %s not locatable" % (room, slot["key"]))
                continue
            pat = re.compile(r'(\bld\s+%s,\s*)([0-9A-Fa-f]+[hH]|\d+)\b' % slot["reg"])
            code = lines[li].split(";", 1)[0]
            if pat.sub(lambda m: m.group(1) + _fmt(val, slot.get("radix", "dec")), code, count=1) != code:
                errs.append("special %d slot %s not idempotent" % (room, slot["key"]))
    if errs:
        print("SELFTEST FAIL:")
        for e in errs[:30]:
            print("  -", e)
        return False
    print("SELFTEST PASS: %d prisoners (%d table + %d special), slots locatable, "
          "edits idempotent" % (len(roster), len(table), len(SPECIALS)))
    return True


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "dump":
        for p in model()["prisoners"]:
            tag = p["name"] or ("table" if p["kind"] == "table" else "")
            print("room %3d  %-32s %s" % (p["room"], tag, "(locked)" if not p["editable"] else ""))
            for s in p["slots"]:
                print("    [%-8s] text#%-3s  %s" % (
                    s["key"], s["text_id"], (s["text"] or "").split("\n")[0][:60]))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
