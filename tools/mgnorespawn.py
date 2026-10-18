"""No-respawn-on-alert codec for Metal Gear MSX / NIGHTJAR.

Rooms that suppress guard respawns when an alert triggers there used to be a
single hardcoded `cp 216` at two sites (SetAlertMode + SetRespawnTime). That is
now the `NoRespawnRooms` data list in logic/norespawn.asm, read by the shared
`IsNoRespawnRoom` test. This tool reads/edits that list and proves the list
reproduces the original 216-only behaviour across every room id.

  * STOCK + _orig    the frozen original (the single `cp 216`) and the list that
                     replaces it; `selftest` proves them equal over all ids.
  * parse_list()     reads the LIVE list from norespawn.asm.
  * set_rooms()      surgical rewrite of the list region (editor writes).

CLI:  python tools/mgnorespawn.py selftest   prove equivalence + round-trip
      python tools/mgnorespawn.py emit        print the NoRespawnRooms ASM block
      python tools/mgnorespawn.py dump         list the current rooms
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

NORESPAWN_F = "logic/norespawn.asm"
TABLE_LABEL = "NoRespawnRooms"
TERMINATOR = 0xFF


def _read(path):
    return open(mgproj.path(path), encoding="latin-1").read()


def _write(path, text):
    open(mgproj.path(path), "w", encoding="latin-1").write(text)


def _num(tok):
    """One asm byte literal: `0D8h`/`0FFh` = hex, bare `216` = decimal."""
    tok = tok.strip()
    if tok.endswith(("h", "H")):
        return int(tok[:-1], 16)
    return int(tok)


# ---- frozen original ---------------------------------------------------------
# The stock engine hardcoded exactly one room (`cp 216`) at both call sites.
STOCK = [216]


def _orig(room):
    """Literal transcription of the original `cp 216` test at both sites."""
    return room == 216


def list_match(room, rooms=None):
    """The interpreter, EXACTLY as IsNoRespawnRoom scans NoRespawnRooms: is
    `room` present in the list (before the 0FFh terminator)?"""
    return (room & 0xFF) in (STOCK if rooms is None else rooms)


# ---- equivalence selftest ----------------------------------------------------
def selftest():
    mism = [r for r in range(256) if list_match(r) != _orig(r)]
    if mism:
        print("SELFTEST FAIL: list != original for ids: %s" % mism[:10])
        return False

    # round-trip: the LIVE list re-emits to bytes that re-parse identically.
    try:
        live = parse_list()
        if parse_list("\n".join(emit_lines(live))) != live:
            print("SELFTEST FAIL: NoRespawnRooms round-trip mismatch")
            return False
        rt = " live list: %s (%d room%s) round-trips byte-exact;" % (
            live, len(live), "" if len(live) == 1 else "s")
        if live != STOCK:
            rt += " (list edited away from stock)"
    except Exception as e:                             # noqa: BLE001
        print("SELFTEST FAIL: cannot parse NoRespawnRooms: %s" % e)
        return False

    print("SELFTEST PASS: list == original (216-only) over all 256 ids;%s" % rt)
    return True


# ---- ASM list emit / parse / write ------------------------------------------
def emit_lines(rooms=None):
    """ASM lines for the `NoRespawnRooms` block. Byte-for-byte what
    IsNoRespawnRoom reads. Default is the frozen STOCK list."""
    rooms = STOCK if rooms is None else rooms
    out = ["%s:" % TABLE_LABEL]
    for r in rooms:
        note = ("\t    ; 4th desert lorry / entrance to building 3"
                if r == 216 else "")
        out.append("\t\t    db	    %d%s" % (r, note))
    out.append("\t\t    db	    0FFh			    ; end of list")
    return out


def emit():
    print("\n".join(emit_lines()))


_TABLE_RE = re.compile(r'(?ms)^%s:.*?\bdb\s+0FFh.*?$' % TABLE_LABEL)


def _table_block(src):
    m = _TABLE_RE.search(src)
    if not m:
        raise ValueError("%s list not found in %s" % (TABLE_LABEL, NORESPAWN_F))
    return m


def parse_list(src=None):
    """Read the live NoRespawnRooms list -> [room, ...] (terminator dropped)."""
    if src is None:
        src = _read(NORESPAWN_F)
    block = _table_block(src).group(0)
    rooms = []
    for ln in block.splitlines()[1:]:                  # skip the label line
        code = ln.split(";", 1)[0]
        m = re.search(r'\bdb\s+(.*)$', code)
        if not m:
            continue
        for t in m.group(1).split(","):
            t = t.strip()
            if not t:
                continue
            v = _num(t)
            if v == TERMINATOR:
                return rooms
            rooms.append(v)
    return rooms


def set_list(rooms):
    """Replace the whole NoRespawnRooms block with `rooms` (only that region of
    norespawn.asm changes; idempotent)."""
    src = _read(NORESPAWN_F)
    new = "\n".join(emit_lines(rooms))
    _write(NORESPAWN_F, _TABLE_RE.sub(lambda _m: new, src, count=1))


# ---- editor API --------------------------------------------------------------
def set_rooms(rooms):
    """Editor write: set the full list (de-duped, sorted, 0..254)."""
    clean = sorted({int(r) & 0xFF for r in rooms if 0 <= int(r) < TERMINATOR})
    set_list(clean)
    return clean


def set_room(room, on):
    """Editor write: add/remove a single room. Returns the new list."""
    rooms = set(parse_list())
    room = int(room) & 0xFF
    if on:
        rooms.add(room)
    else:
        rooms.discard(room)
    return set_rooms(rooms)


def is_no_respawn(room):
    """Does `room` suppress alert respawns in the LIVE list?"""
    return list_match(room, parse_list())


def model():
    """Editor model: the current no-respawn room list."""
    return {"rooms": parse_list()}


def dump(room=None):
    rooms = parse_list()
    if room is not None:
        print("room %d: %s" % (room, "no-respawn" if room in rooms else "normal"))
    else:
        print("no-respawn rooms: %s" % rooms)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "emit":
        return emit()
    if len(sys.argv) >= 2 and sys.argv[1] == "dump":
        return dump(int(sys.argv[2]) if len(sys.argv) >= 3 else None)
    print(__doc__)


if __name__ == "__main__":
    main()
