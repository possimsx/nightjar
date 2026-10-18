"""Hide-guard codec for Metal Gear MSX / NIGHTJAR.

Entry-dependent guard culling ("don't spawn the player onto a guard") lives in
logic/actors/hideguards.asm as the `HideGuardRules` data table (read by the
generic ApplyHideGuardRules interpreter). This tool reads/edits that table and
proves the extraction reproduces the original 9 routines exactly.

See docs/HIDE-GUARD-PLAN.md.
  * RULES + _orig       — the frozen original extraction and a literal
                          transcription of the 9 routines; `selftest` proves
                          them equal exhaustively (the extraction guarantee).
  * parse_table()       — reads the LIVE table from hideguards.asm.
  * model()             — decodes it and joins each rule to the room's actors.
  * set_room_rules()    — surgical rewrite of the table region (editor writes).

CLI:  python tools/mghideguard.py selftest     prove extraction + round-trip
      python tools/mghideguard.py emit          print the HideGuardRules ASM block
      python tools/mghideguard.py dump [room]    show rules joined to the actor list
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

HIDEGUARD_F = "logic/actors/hideguards.asm"


def _read(path):
    return open(mgproj.path(path), encoding="latin-1").read()


def _write(path, text):
    open(mgproj.path(path), "w", encoding="latin-1").write(text)


def _num(tok):
    """One asm byte literal: `0B0h`/`0FFh` = hex, bare `1`/`137` = decimal."""
    tok = tok.strip()
    if tok.endswith(("h", "H")):
        return int(tok[:-1], 16)
    return int(tok)

# ---- condition / flag enums (mirror constants/Enums.asm to be added) --------
COND_DIR, COND_PREV, COND_ELSE = 0, 1, 2       # what a rule tests
AXIS_Y, AXIS_X = 0, 1                           # axis identifier
OP_EQ, OP_NEQ = 0, 1                            # op identifier
# the packed FLAGS byte (3rd byte of a table entry) the ASM interpreter reads:
FLAG_AXIS_X = 0x01                              # bit 0 set => X axis (else Y)
FLAG_OP_NEQ = 0x02                              # bit 1 set => != (else ==)
COND_NAME = {COND_DIR: "dir", COND_PREV: "prev", COND_ELSE: "else"}
COND_TOKEN = {"COND_DIR": COND_DIR, "COND_PREV": COND_PREV, "COND_ELSE": COND_ELSE}
COND_ASM = {COND_DIR: "COND_DIR ", COND_PREV: "COND_PREV", COND_ELSE: "COND_ELSE"}
# NextRoomDirect: 1=Up(from S), 2=Down(from N), 3=Left(from E), 4=Right(from W)
DIR_FROM = {1: "S", 2: "N", 3: "E", 4: "W"}


# ---- the extracted rules (docs/HIDE-GUARD-PLAN.md §2) -----------------------
# room -> ordered [(cond, val, axis, op, coord)]; first matching cond wins,
# then cull the actor iff (actor.axis <op> coord). No match -> no cull.
RULES = {
    1:  [(COND_DIR, 1, AXIS_Y, OP_EQ, 0xB0), (COND_ELSE, 0, AXIS_Y, OP_EQ, 0x18)],
    13: [(COND_PREV, 137, AXIS_X, OP_EQ, 0x88)],
    15: [(COND_DIR, 4, AXIS_X, OP_EQ, 0x10)],
    17: [(COND_DIR, 1, AXIS_Y, OP_NEQ, 0x30), (COND_ELSE, 0, AXIS_Y, OP_EQ, 0x30)],
    18: [(COND_DIR, 1, AXIS_Y, OP_NEQ, 0x13), (COND_ELSE, 0, AXIS_Y, OP_EQ, 0x13)],
    19: [(COND_PREV, 141, AXIS_Y, OP_EQ, 0x78), (COND_DIR, 1, AXIS_Y, OP_EQ, 0xA8)],
    22: [(COND_PREV, 20, AXIS_X, OP_EQ, 0x20), (COND_ELSE, 0, AXIS_X, OP_EQ, 0xF0)],
    35: [(COND_PREV, 156, AXIS_Y, OP_EQ, 0x28), (COND_PREV, 33, AXIS_X, OP_EQ, 0x18)],
    39: [(COND_PREV, 242, AXIS_Y, OP_EQ, 0x48), (COND_ELSE, 0, AXIS_Y, OP_EQ, 0xB0)],
}


def _encode_rules(rules):
    """One room's rules -> the flat 4-byte-per-entry form the ASM table holds:
    [(cond, val, flags, coord), ...]. This is the single source the emitter AND
    the byte-level interpreter both use, so what we prove is what ships."""
    out = []
    for cond, val, axis, op, coord in rules:
        flags = (FLAG_AXIS_X if axis == AXIS_X else 0) | (FLAG_OP_NEQ if op == OP_NEQ else 0)
        out.append((cond, val & 0xFF, flags, coord & 0xFF))
    return out


def _cull_from_bytes(entries, D, E, X, Y):
    """Interpret encoded [(cond,val,flags,coord)] EXACTLY as the ASM will:
    first matching cond selects (flags,coord); cull per the flags byte."""
    for cond, val, flags, coord in entries:
        if (cond == COND_DIR and val == D) or (cond == COND_PREV and val == E) \
                or cond == COND_ELSE:
            v = X if flags & FLAG_AXIS_X else Y
            return (v != coord) if flags & FLAG_OP_NEQ else (v == coord)
    return False


def table_cull(room, D, E, X, Y):
    """The generic interpreter, through the shipped byte encoding: does the table
    cull an actor at (X,Y) entering `room` with direction D / previous-room E?"""
    return _cull_from_bytes(_encode_rules(RULES.get(room, [])), D, E, X, Y)


# ---- literal transcription of the original 9 routines (hideguards.asm) ------
# Each mirrors the ASM branch-for-branch, INDEPENDENTLY of RULES above, so the
# equivalence test is meaningful (a misread here or there won't cancel out).
def _orig(room, D, E, X, Y):
    if room == 1:                                   # c=B0h if from S else 18h; cull Y==c
        c = 0xB0 if D == 1 else 0x18
        return Y == c
    if room == 13:                                  # only if came from room 137
        return X == 0x88 if E == 137 else False
    if room == 15:                                  # only if entered from left (D==4)
        return X == 0x10 if D == 4 else False
    if room == 17:                                  # from S -> cull Y!=30h, else Y==30h
        return (Y != 0x30) if D == 1 else (Y == 0x30)
    if room == 18:                                  # from S -> cull Y!=13h, else Y==13h
        return (Y != 0x13) if D == 1 else (Y == 0x13)
    if room == 19:                                  # E==141 -> Y==78h; elif from S -> Y==A8h
        if E == 141:
            return Y == 0x78
        return Y == 0xA8 if D == 1 else False
    if room == 22:                                  # E==20 -> X==20h; else X==F0h
        return X == 0x20 if E == 20 else X == 0xF0
    if room == 35:                                  # E==156 -> Y==28h; elif E==33 -> X==18h
        if E == 156:
            return Y == 0x28
        return X == 0x18 if E == 33 else False
    if room == 39:                                  # E==242 -> Y==48h; else Y==B0h
        return Y == 0x48 if E == 242 else Y == 0xB0
    return False


# ---- equivalence selftest ---------------------------------------------------
# meaningful coord probes: every constant the routines compare against + a few
# non-matching values, so both axes and both ops are exercised at and off target.
_COORDS = sorted({0x00, 0x10, 0x13, 0x18, 0x20, 0x28, 0x30, 0x48, 0x78,
                  0x88, 0xA8, 0xB0, 0xF0, 0x99, 0xFF})


def selftest():
    mism = []
    checks = 0
    for room in RULES:
        for D in range(1, 5):                       # entry directions 1..4
            for E in range(0, 256):                 # every possible previous room
                for X in _COORDS:
                    for Y in _COORDS:
                        checks += 1
                        if table_cull(room, D, E, X, Y) != _orig(room, D, E, X, Y):
                            mism.append((room, D, E, X, Y))
    if mism:
        print("SELFTEST FAIL: table != original in %d case(s), e.g.:" % len(mism))
        for room, D, E, X, Y in mism[:10]:
            print("  room %d D=%d E=%d X=%02Xh Y=%02Xh  orig=%s table=%s"
                  % (room, D, E, X, Y, _orig(room, D, E, X, Y),
                     table_cull(room, D, E, X, Y)))
        return False

    # 2) codec round-trip: the LIVE table in hideguards.asm re-emits to bytes that
    #    re-parse identically (holds after edits too, unlike the frozen proof).
    try:
        live = parse_table()
        if parse_table("\n".join(emit_lines(live))) != live:
            print("SELFTEST FAIL: HideGuardRules round-trip mismatch")
            return False
        rt = " live table: %d rooms round-trip byte-exact;" % len(live)
        if {r: _encode_rules(RULES[r]) for r in RULES} != live:
            rt += " (table has been edited away from stock)"
    except Exception as e:                             # noqa: BLE001
        print("SELFTEST FAIL: cannot parse HideGuardRules: %s" % e)
        return False

    print("SELFTEST PASS: table == original over %d (room,dir,prev,X,Y) cases; "
          "%d rooms, %d rules;%s" % (checks, len(RULES),
                                     sum(len(v) for v in RULES.values()), rt))
    return True


# ---- ASM table emit / parse / write -----------------------------------------
TABLE_LABEL = "HideGuardRules"


def emit_lines(data=None):
    """ASM lines for the `HideGuardRules` block. `data` = {room: [(cond,val,flags,
    coord), ...]} in ENCODED form (as parse_table / _encode_rules return); default
    is the frozen RULES. Byte-for-byte what ApplyHideGuardRules reads."""
    if data is None:
        data = {r: _encode_rules(RULES[r]) for r in RULES}
    out = ["%s:\t; room, nEntries; then per entry: cond, val, flags, coord" % TABLE_LABEL,
           "\t\t; flags bit0: 1=X axis (else Y);  bit1: 2 = \"!=\" op (else \"==\")"]
    for room in sorted(data):
        enc = data[room]
        out.append("\t\t    db %3d, %d" % (room, len(enc)))
        for cond, val, flags, coord in enc:
            out.append("\t\t      db %s, %3d, %d, 0%02Xh\t; %s%s -> cull %s %s 0%02Xh"
                       % (COND_ASM[cond], val, flags, coord, COND_ASM[cond].strip(),
                          _condhint(cond, val), "X" if flags & FLAG_AXIS_X else "Y",
                          "!=" if flags & FLAG_OP_NEQ else "==", coord))
    out.append("\t\t    db 0FFh\t\t\t; end of table")
    return out


def emit():
    print("\n".join(emit_lines()))


def _condhint(cond, val):
    if cond == COND_DIR:
        return " (from %s)" % DIR_FROM.get(val, "?")
    if cond == COND_PREV:
        return " (from room %d)" % val
    return ""


_TABLE_RE = re.compile(r'(?ms)^%s:.*?\bdb\s+0FFh.*?$' % TABLE_LABEL)


def _table_block(src):
    m = _TABLE_RE.search(src)
    if not m:
        raise ValueError("HideGuardRules table not found in %s" % HIDEGUARD_F)
    return m


def parse_table(src=None):
    """Read the live HideGuardRules table -> ordered {room: [(cond,val,flags,
    coord), ...]} (encoded form). Structural walk of the flattened db stream:
    [room, n, 4*n entry bytes] repeated, 0FFh terminates."""
    if src is None:
        src = _read(HIDEGUARD_F)
    block = _table_block(src).group(0)
    toks = []
    for ln in block.splitlines()[1:]:                  # skip the label line
        code = ln.split(";", 1)[0]
        m = re.search(r'\bdb\s+(.*)$', code)
        if not m:
            continue
        for t in m.group(1).split(","):
            t = t.strip()
            if t:
                toks.append(COND_TOKEN[t] if t in COND_TOKEN else _num(t))
    out, i = {}, 0
    while i < len(toks):
        room = toks[i]
        if room == 0xFF:
            break
        n = toks[i + 1]
        i += 2
        rules = []
        for _ in range(n):
            rules.append(tuple(toks[i:i + 4]))
            i += 4
        out[room] = rules
    return out


def set_table(data):
    """Replace the whole HideGuardRules block with `data` ({room: encoded rules});
    only that region of hideguards.asm changes (idempotent)."""
    src = _read(HIDEGUARD_F)
    new = "\n".join(emit_lines(data))
    _write(HIDEGUARD_F, _TABLE_RE.sub(lambda _m: new, src, count=1))


def _pack_flags(axis, op):
    """axis: 'X'/'Y' (or AXIS_*), op: '=='/'!=' (or OP_*)  ->  flags byte."""
    ax = FLAG_AXIS_X if str(axis).upper() in ("X", "1") else 0
    nq = FLAG_OP_NEQ if str(op) in ("!=", "ne", "1") else 0
    return ax | nq


def _encode_rule(r):
    """A UI/model rule dict -> (cond, val, flags, coord). Accepts either a raw
    `flags` byte or `axis`+`op`."""
    cond = r["cond"] if isinstance(r["cond"], int) else COND_TOKEN[r["cond"]]
    val = int(r.get("val", 0)) & 0xFF
    if "flags" in r:
        flags = int(r["flags"]) & 0x03
    else:
        flags = _pack_flags(r.get("axis", "Y"), r.get("op", "=="))
    return (cond, val, flags, int(r["coord"]) & 0xFF)


def set_room_rules(room, rules):
    """Editor write: set `room`'s cull rules (list of dicts; [] deletes the room's
    block). Re-parses the live table, replaces just this room, rewrites the region.
    Returns the reloaded model for the room."""
    data = parse_table()
    room = int(room)
    if rules:
        data[room] = [_encode_rule(r) for r in rules]
    else:
        data.pop(room, None)
    set_table(data)
    return room_model(room)


# ---- dump (rules joined to the room's actors) -------------------------------
def _actor_coords(room):
    """[(idx, id, X, Y)] path-following guards of `room`, via mgmap."""
    try:
        import mgmap as M
        m = M.load_model()
        by = M.actors_by_room(m["actor_slots"], m["actor_blocks"])
    except Exception:
        return []
    ents = by.get(room, [])
    out = []
    for i, (idtok, pos_mn, pos_tok) in enumerate(ents):
        if pos_mn == "dw":
            w = int(pos_tok[0].rstrip("hH"), 16)
            x, y = (w >> 8) & 0xFF, w & 0xFF
        else:
            y = int(pos_tok[0].rstrip("hH"), 16)
            x = int(pos_tok[1].rstrip("hH"), 16)
        out.append((i, idtok, x, y))
    return out


def _target_actors(room, axis, op, coord):
    """Which actor index(es) a rule's (axis,op,coord) resolves to."""
    hits = []
    for i, idtok, x, y in _actor_coords(room):
        v = x if axis == AXIS_X else y
        if (v == coord) if op == OP_EQ else (v != coord):
            hits.append(i)
    return hits


# ---- decoded model (for the editor) -----------------------------------------
def _decode_rule(room, enc):
    """(cond,val,flags,coord) -> a friendly dict joined to the room's actors."""
    cond, val, flags, coord = enc
    axis = AXIS_X if flags & FLAG_AXIS_X else AXIS_Y
    op = OP_NEQ if flags & FLAG_OP_NEQ else OP_EQ
    return {
        "cond": cond, "cond_name": COND_NAME[cond], "val": val,
        "hint": _condhint(cond, val).strip(),
        "axis": "X" if axis == AXIS_X else "Y", "op": "!=" if op == OP_NEQ else "==",
        "coord": coord, "flags": flags,
        "targets": _target_actors(room, axis, op, coord),
    }


def room_model(room):
    """Editor model for one room: its cull rules (decoded + actor-joined) and the
    room's path-following actors. `has_rules` false if the room isn't in the table."""
    room = int(room)
    table = parse_table()
    actors = [{"idx": i, "id": idt, "x": x, "y": y}
              for i, idt, x, y in _actor_coords(room)]
    rules = [_decode_rule(room, e) for e in table.get(room, [])]
    stale = [k for k, r in enumerate(rules) if not r["targets"]]
    return {"room": room, "has_rules": room in table, "rules": rules,
            "actors": actors, "stale": stale}


def model():
    """All rooms that carry cull rules (for a global list)."""
    table = parse_table()
    return {"rooms": [room_model(r) for r in sorted(table)]}


def cull_preview(room, direction, prev):
    """Actor indices culled when entering `room` with NextRoomDirect=`direction`
    and PreviousRoom=`prev` — the exact table logic, for the UI entry-preview."""
    room, direction, prev = int(room), int(direction), int(prev)
    for enc in parse_table().get(room, []):
        cond, val, flags, coord = enc
        if (cond == COND_DIR and val == direction) or \
           (cond == COND_PREV and val == prev) or cond == COND_ELSE:
            axis = AXIS_X if flags & FLAG_AXIS_X else AXIS_Y
            op = OP_NEQ if flags & FLAG_OP_NEQ else OP_EQ
            return _target_actors(room, axis, op, coord)
    return []


def dump(room=None):
    table = parse_table()
    for r in sorted(table):
        if room is not None and r != room:
            continue
        print("room %d:" % r)
        for rl in (_decode_rule(r, e) for e in table[r]):
            whos = ("actor #%s" % ",".join(map(str, rl["targets"]))) if rl["targets"] \
                else "(no actor matches — STALE)"
            print("  when %-4s%-16s remove %s %s 0%02Xh  -> %s"
                  % (rl["cond_name"], rl["hint"], rl["axis"], rl["op"], rl["coord"], whos))


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
