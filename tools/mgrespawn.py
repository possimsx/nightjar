#!/usr/bin/env python3
"""
mgrespawn.py - Metal Gear (MSX) alert-reinforcement table codec (NIGHTJAR).

`RespawnInfo` (data/respawninfo.asm) is a flat, room-indexed table: one 3-byte
entry per room (entry N = room N), for rooms 0..187 (the engine does `cp 188 /
ret nc`, so rooms >=188 never respawn).

  +0  enemy ID to respawn   (0 = this room produces no reinforcements)
  +1  respawn location 1
  +2  respawn location 2    (the engine alternates 1/2 by a tick bit)

Location byte 0xHL encodes a screen position (see ChkRespawnEnemy in
Banks0123.asm, and AddEnemy4 which stores E->Y): the HIGH nibble is Y and the
LOW nibble is X, each multiplied by 16.  So:
      x = (byte & 0x0F) * 16          y = (byte >> 4) * 16
      byte = ((y // 16) << 4) | (x // 16)

This is the *alert reinforcement* system (only runs while AlertMode != 0) - it
is unrelated to entry-time guard culling (see mghideguard.py / hide-guard).

Editing is surgical: only the one edited room's `db` line is rewritten.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)


def _respawn():
    """data/respawninfo.asm of the ACTIVE project, resolved at call time."""
    return mgproj.path(os.path.join("data", "respawninfo.asm"))
LABEL = "RespawnInfo"
MAX_ROOM = 188                                  # rooms 0..187 have entries

# enemy IDs actually used by the table (constants/Enums.asm)
ENEMIES = [
    (0x00, "none (no respawn)"),
    (0x0A, "alert guard"),
    (0x0B, "red-alert guard"),
    (0x16, "jetpack guard"),
]
ENEMY_NAMES = dict(ENEMIES)


def _tok(b):
    """Byte -> source token in the file's house style (0Ah, 19h, 0AFh, 0). Hex
    that starts with a letter gets a leading 0 so it can't parse as a label."""
    if b == 0:
        return "0"
    h = "%X" % b
    if h[0] in "ABCDEF":
        h = "0" + h
    return h + "h"


def _parse_db(operand):
    """`db` operand -> list of int bytes (hex `NNh`/`0xNN`, or decimal)."""
    out = []
    for tok in operand.split(","):
        s = tok.strip()
        if not s:
            continue
        m = re.match(r'(?:0x([0-9A-Fa-f]+)|([0-9A-Fa-f]+)[hH]|(\d+))$', s)
        if not m:
            continue
        if m.group(3) is not None and m.group(2) is None and m.group(1) is None:
            out.append(int(m.group(3)))
        else:
            out.append(int(m.group(1) or m.group(2), 16))
    return out


def _entry_lines(lines):
    """Ordered list of (line_index, [bytes]) for each room entry, starting at the
    `RespawnInfo:` line (room 0) through the consecutive `db` lines."""
    out = []
    started = False
    for i, ln in enumerate(lines):
        code = ln.split(';', 1)[0]
        if not started:
            m = re.match(r'^%s:\s*db\s+(.*)$' % LABEL, code)
            if m:
                out.append((i, _parse_db(m.group(1))))
                started = True
            continue
        m = re.match(r'^\s+db\s+(.*)$', code)
        if m:
            out.append((i, _parse_db(m.group(1))))
        elif code.strip():
            break                                # left the table
    return out


def loc_xy(byte):
    return {"byte": byte & 0xFF, "x": (byte & 0x0F) * 16, "y": (byte >> 4) * 16}


def xy_byte(x, y):
    """(x,y) pixels -> location byte (snapped to the 16px grid, clamped 0..15)."""
    lo = max(0, min(15, int(round(x / 16))))
    hi = max(0, min(15, int(round(y / 16))))
    return (hi << 4) | lo


def room_entry(room):
    """{room, enemy, enemy_name, loc1, loc2, in_range} for `room` (None fields if
    out of range)."""
    if room < 0 or room >= MAX_ROOM:
        return {"room": room, "in_range": False, "max_room": MAX_ROOM,
                "enemies": ENEMIES}
    lines = open(_respawn(), encoding='latin-1').read().splitlines()
    entries = _entry_lines(lines)
    e = entries[room][1] if room < len(entries) else [0, 0, 0]
    e = (e + [0, 0, 0])[:3]
    return {"room": room, "in_range": True, "max_room": MAX_ROOM,
            "enemy": e[0], "enemy_name": ENEMY_NAMES.get(e[0], "id 0x%02X" % e[0]),
            "loc1": loc_xy(e[1]), "loc2": loc_xy(e[2]),
            "enemies": ENEMIES}


def set_entry(room, enemy, loc1, loc2):
    """Surgically rewrite `room`'s 3-byte entry. Returns the new room_entry."""
    if room < 0 or room >= MAX_ROOM:
        raise ValueError("room %d has no respawn entry (0..%d only)" % (room, MAX_ROOM - 1))
    src = open(_respawn(), encoding='latin-1').read()
    had_eol = src.endswith('\n')
    lines = src.splitlines()
    entries = _entry_lines(lines)
    if room >= len(entries):
        raise ValueError("room %d beyond table (%d entries)" % (room, len(entries)))
    idx = entries[room][0]
    b = [enemy & 0xFF, loc1 & 0xFF, loc2 & 0xFF]
    body = "db\t" + ", ".join(_tok(x) for x in b)
    code, sep, comment = lines[idx].partition(';')
    if room == 0:
        prefix = "%-20s" % (LABEL + ":")
    else:
        m = re.match(r'^(\s+)', code)
        prefix = m.group(1) if m else "\t\t    "
    lines[idx] = prefix + body + ((' ;' + comment) if sep else '')
    open(_respawn(), 'w', encoding='latin-1').write('\n'.join(lines) + ('\n' if had_eol else ''))
    return room_entry(room)


def selftest():
    lines = open(_respawn(), encoding='latin-1').read().splitlines()
    entries = _entry_lines(lines)
    print("%s: %d room entries" % (LABEL, len(entries)))
    bad = [ (i, b) for i, b in entries if len(b) != 3 ]
    print("entries != 3 bytes:", len(bad))
    used = {}
    for _, b in entries:
        if b and b[0]:
            used[b[0]] = used.get(b[0], 0) + 1
    for eid, n in sorted(used.items()):
        print("  enemy 0x%02X (%s): %d rooms" % (eid, ENEMY_NAMES.get(eid, "?"), n))
    # round-trip the xy<->byte codec
    ok = all(xy_byte(loc_xy(b)["x"], loc_xy(b)["y"]) == b for b in range(256))
    print("xy<->byte round-trip 0..255:", "OK" if ok else "FAIL")
    # sample
    for r in (0, 1, 20, 50):
        print(" ", room_entry(r))


if __name__ == "__main__":
    selftest()
