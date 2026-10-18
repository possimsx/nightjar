"""Codec / progression-gate proof + codec for Metal Gear MSX / NIGHTJAR.

Phase 1 of docs/CODEC-GATE-PLAN.md: prove a *data-table + interpreter* model
reproduces the hardcoded codec/progression gates EXACTLY, before any engine
change. Three gate families:

  * text->flag   : reading a radio text sets a story flag.
                   Banks0123.asm:8380-8391 (TextBoxExit).
  * spawn/open   : an item won't spawn / a door won't open until a flag is set.
                   addroomitems.asm:60-65 (rocket), opendoor.asm ChkCompassDoor
                   (room 87) / ChkDesertDoorBuild2 (room 73).
  * antenna zone : idxMapZones nibble >=5 => radio needs the antenna, for both
                   incoming calls (Banks0123.asm:1772) and outgoing replies
                   (Banks0123.asm:11117). Table: data/musicradioconfig.asm.

For text->flag and spawn/open, NO ROM data table exists yet (the logic is inline
Z80), so the "table" here is the frozen extraction (GATE_TEXTS / GATE_SPAWNS) and
`selftest` proves it against an INDEPENDENT literal transcription of the inline
ASM (`_orig_*`). For the antenna family the table already exists as data, so it
is parsed LIVE, decoded with the exact GetNibbleRoom nibble order, and proven to
round-trip byte-for-byte (the codec guarantee for future editing).

CLI:  python tools/mgcodecgate.py selftest   prove extraction + antenna round-trip
      python tools/mgcodecgate.py dump         show gates + antenna zones
      python tools/mgcodecgate.py emit-zones    print idxMapZones from parsed nibbles
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

ZONES_F = "data/musicradioconfig.asm"
ITEMGATE_F = "logic/addroomitems.asm"      # holds the live GateItems table
TEXTGATE_F = "Banks0123.asm"               # holds the live GateTexts table
DOORGATE_F = "logic/doors/opendoor.asm"    # holds the live GateDoors table

# constants\Enums.asm
ROCKET_LAUNCHER = 4

# The story flags these gates key on (RAM bytes; 0 = locked, nonzero = unlocked).
FLAGS = ("JeniRocketF", "JeniOpenDoorF", "SchneiderCaptured", "DoorBuild2LockedF")

# The original named story flags. OpenBigBossDoor is door-only. SwitchOffMSXF /
# MadnarMoved are the late-game event flags, exposed so a text can OPT-IN to
# arming them (stock arms them by entering a room; see madnarbigbossevent.asm).
KNOWN_FLAGS = ("SwitchOffMSXF", "MadnarMoved",
               "JeniRocketF", "JeniOpenDoorF", "SchneiderCaptured",
               "DoorBuild2LockedF", "OpenBigBossDoor")

# General-purpose flag pool: `GateFlags` is a 9-byte array in the saved
# GameDataArea block (Variables.asm), so a gate can point at GateFlags+0..8 to
# arm/open/spawn anything, independent of the original story flags. Any radio
# call -> any object. Bump POOL_SIZE if the array is grown.
POOL_LABEL = "GateFlags"
POOL_SIZE = 9


def _pool_flags():
    return ["%s+%d" % (POOL_LABEL, n) for n in range(POOL_SIZE)]


def _all_flags():
    return list(KNOWN_FLAGS) + _pool_flags()

# item id -> ASM symbol, so a rewrite keeps the readable name where one exists.
_ITEM_SYM_REV = {ROCKET_LAUNCHER: "ROCKET_LAUNCHER"}

ANTENNA_ZONE = 5   # idxMapZones nibble >= this needs AntennaTaken

# ---- stock default display names (overridable per project, see LABELS_F) -----
# idxMapZones nibble meanings (data/musicradioconfig.asm header). The value also
# selects area MUSIC (SetAreaMusic), so it is NOT a plain antenna boolean.
DEFAULT_ZONE_NAMES = {
    0x0: "B1 1st floor / desert", 0x1: "B1 2nd floor", 0x2: "B1 3rd floor",
    0x3: "B1 roof", 0x4: "B1 basement", 0x5: "B2 1st floor", 0x6: "B2 2nd floor",
    0x7: "B2 roof", 0x8: "B2 basement", 0x9: "B2 desert",
    0xA: "B3 1st floor / B2 water channel",
}
# Stock descriptions for the original named story flags.
DEFAULT_FLAG_LABELS = {
    "SwitchOffMSXF": "Big Boss: \"switch off your MSX\" (fake-out) armed",
    "MadnarMoved": "Madnar moved to Building 2 (\"it's too late\" state)",
    "JeniRocketF": "Jennifer: arranges the rocket launcher",
    "JeniOpenDoorF": "Jennifer: opens the compass door",
    "SchneiderCaptured": "Schneider captured",
    "DoorBuild2LockedF": "Building-2 entrance opened by the guards",
    "OpenBigBossDoor": "Metal Gear / Big Boss escape door",
}


def _default_flag_label(flag):
    if flag in DEFAULT_FLAG_LABELS:
        return DEFAULT_FLAG_LABELS[flag]
    m = re.match(r'%s\+(\d+)$' % POOL_LABEL, flag)
    if m:
        return "Flag %s (general pool)" % m.group(1)
    return flag


def load_project_labels():
    """{'flags': {flag: name}, 'zones': {zone_str: name}} overrides, or empty.
    Cosmetic, editor-only names — stored per project (mgproj.state_file)."""
    try:
        with open(mgproj.state_file("labels"), encoding="utf-8") as f:
            d = json.load(f)
        return {"flags": dict(d.get("flags", {})), "zones": dict(d.get("zones", {}))}
    except (OSError, ValueError):
        return {"flags": {}, "zones": {}}


def _save_project_labels(data):
    lf = mgproj.state_file("labels")
    os.makedirs(os.path.dirname(lf), exist_ok=True)
    with open(lf, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def flag_label(flag):
    """Display name for a flag: project override, else stock default, else the id."""
    return load_project_labels()["flags"].get(flag) or _default_flag_label(flag)


def zone_name(value):
    """Display name for a building/area zone value (idxMapZones). Read-only stock
    label used for the room panel's zone readout — zones can't be renamed."""
    return DEFAULT_ZONE_NAMES.get(value, "zone %d" % value)


def set_flag_label(flag, label):
    """Set (or, with an empty label, clear -> revert to default) a flag's name."""
    data = load_project_labels()
    label = (label or "").strip()
    if label and label != _default_flag_label(flag):
        data["flags"][flag] = label
    else:
        data["flags"].pop(flag, None)
    _save_project_labels(data)
    return flag_label(flag)


def labels_model():
    """All editable display names (flags + zones) for the label editor."""
    over = load_project_labels()
    flags = [{"flag": f, "label": flag_label(f), "default": _default_flag_label(f),
              "custom": f in over["flags"], "pool": f.startswith(POOL_LABEL + "+")}
             for f in _all_flags()]
    # Zones are no longer renameable: idxMapZones is read-only building/area
    # identity (a room's zone can't be reassigned in the editor), so a cosmetic
    # zone name has no purpose. Only flags are editable here.
    return {"flags": flags}


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


# ---- the extracted gate tables (docs/CODEC-GATE-PLAN.md §2) ------------------
# Table A: reading text N sets flag. GATE_TEXTS[text_id] = flag name.
GATE_TEXTS = {
    117: "JeniRocketF",
    118: "JeniOpenDoorF",
    138: "SchneiderCaptured",
}

# Table B: spawn/open gates. Each: kind ('item'|'door'), key (item ID or room
# ID), the flag required to unlock, and whether opening consumes the flag.
GATE_SPAWNS = [
    {"kind": "item", "key": ROCKET_LAUNCHER, "flag": "JeniRocketF",      "oneshot": 0},
    {"kind": "door", "key": 87,              "flag": "JeniOpenDoorF",    "oneshot": 1},
    {"kind": "door", "key": 73,              "flag": "DoorBuild2LockedF", "oneshot": 1},
]


# ---- the generic interpreters (what would ship) -----------------------------
def text_sets_flag(text_id):
    """Table A interpreter: flag name a dismissed text sets, or None."""
    return GATE_TEXTS.get(text_id)


def _item_gate(item_id):
    for g in GATE_SPAWNS:
        if g["kind"] == "item" and g["key"] == item_id:
            return g
    return None


def _door_gate(room):
    for g in GATE_SPAWNS:
        if g["kind"] == "door" and g["key"] == room:
            return g
    return None


def item_allowed(item_id, flags):
    """Table B interpreter (item): may this item be placed given flag state
    `flags` ({name: 0/1})? Ungated items are always allowed."""
    g = _item_gate(item_id)
    return True if g is None else bool(flags.get(g["flag"], 0))


_ITEMSYM = {"ROCKET_LAUNCHER": ROCKET_LAUNCHER}   # item-id symbols used in GateItems


def parse_item_gates(src=None):
    """Read the LIVE GateItems table from addroomitems.asm -> [(item_id, flag)].
    Format: `db <item>` then `dw <flag>` per entry, 0FFh-terminated."""
    if src is None:
        src = _read(ITEMGATE_F)
    m = re.search(r'(?ms)^GateItems:(.*?)\bdb\s+0FFh', src)
    if not m:
        raise ValueError("GateItems table not found in %s" % ITEMGATE_F)
    toks = []
    for ln in m.group(1).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\b(db|dw)\s+(.*)$', code)
        if dm:
            toks.append(dm.group(2).strip())
    out = []
    for i in range(0, len(toks) - 1, 2):
        item = _ITEMSYM.get(toks[i], None)
        out.append((item if item is not None else _num(toks[i]), toks[i + 1]))
    return out


# One-shot flag doors, keyed by door LOGIC TYPE (the JumpIndex dispatch index),
# not room. Room 87's compass door is type 13; the Big Boss door is type 14.
GATE_DOORS = [
    {"type": 13, "flag": "JeniOpenDoorF",   "note": "compass door (room 87)"},
    {"type": 14, "flag": "OpenBigBossDoor", "note": "Big Boss / escape-ladder door"},
]


def parse_door_gates(src=None):
    """Read the LIVE GateDoors table from opendoor.asm -> [(door_type, flag)].
    Format: `db <type>` then `dw <flag>` per entry, 0FFh-terminated."""
    if src is None:
        src = _read(DOORGATE_F)
    m = re.search(r'(?ms)^GateDoors:(.*?)\bdb\s+0FFh', src)
    if not m:
        raise ValueError("GateDoors table not found in %s" % DOORGATE_F)
    toks = []
    for ln in m.group(1).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\b(db|dw)\s+(.*)$', code)
        if dm:
            toks.append(dm.group(2).strip())
    return [(_num(toks[i]), toks[i + 1]) for i in range(0, len(toks) - 1, 2)]


def parse_text_gates(src=None):
    """Read the LIVE GateTexts table from Banks0123.asm -> [(text_id, flag)].
    Format: `db <text_id>` then `dw <flag>` per entry, 0FFh-terminated."""
    if src is None:
        src = _read(TEXTGATE_F)
    m = re.search(r'(?ms)^GateTexts:(.*?)\bdb\s+0FFh', src)
    if not m:
        raise ValueError("GateTexts table not found in %s" % TEXTGATE_F)
    toks = []
    for ln in m.group(1).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\b(db|dw)\s+(.*)$', code)
        if dm:
            toks.append(dm.group(2).strip())
    return [(_num(toks[i]), toks[i + 1]) for i in range(0, len(toks) - 1, 2)]


# ---- gate table writers (editor writes; docs/CODEC-GATE-PLAN.md Phase 3) -----
def _valid_flag(flag):
    """Only let a gate point at a named story flag or a pool flag GateFlags+N
    (keeps the ASM safe — the writers can never inject arbitrary text)."""
    flag = str(flag).strip().replace(" ", "")
    if flag in KNOWN_FLAGS:
        return flag
    m = re.match(r'^%s\+(\d+)$' % POOL_LABEL, flag)
    if m and 0 <= int(m.group(1)) < POOL_SIZE:
        return flag
    raise ValueError("unknown flag %r (allowed: %s, %s+0..%d)"
                     % (flag, ", ".join(KNOWN_FLAGS), POOL_LABEL, POOL_SIZE - 1))


def _emit_gate_block(label, rows):
    """rows = [(key_text, flag, comment_or_None)]. Byte-for-byte the `db key /
    dw flag` shape the interpreters read, 0FFh-terminated. The flag's display
    name is emitted as a comment so an editor rewrite stays self-documenting
    (comments are ignored on parse, so this doesn't affect the round-trip)."""
    out = ["%s:" % label]
    for key, flag, cm in rows:
        line = "\t\t    db\t    %s" % key
        if cm:
            line += "\t\t    ; %s" % cm
        out.append(line)
        dwl = "\t\t    dw\t    %s" % _valid_flag(flag)
        lbl = flag_label(flag)
        if lbl and lbl != flag:
            dwl += "\t\t    ; %s" % lbl
        out.append(dwl)
    out.append("\t\t    db\t    0FFh")
    return "\n".join(out)


def _replace_gate_block(path, label, new_text):
    """Swap just the `LABEL: ... db 0FFh` region of `path` (surgical, idempotent)."""
    src = _read(path)
    pat = re.compile(r'(?ms)^%s:.*?\bdb\s+0FFh[^\n]*' % re.escape(label))
    if not pat.search(src):
        raise ValueError("%s table not found in %s" % (label, path))
    new = pat.sub(lambda _m: new_text, src, count=1)
    if new != src:
        _write(path, new)


def set_text_gates(entries):
    """Editor write: entries = [{"text": id, "flag": name}, ...]. Rewrite GateTexts."""
    rows = [(str(int(e["text"]) & 0xFF), e["flag"], None) for e in entries]
    _replace_gate_block(TEXTGATE_F, "GateTexts", _emit_gate_block("GateTexts", rows))


def set_item_gates(entries):
    """Editor write: entries = [{"item": id, "flag": name}, ...]. Rewrite GateItems."""
    rows = []
    for e in entries:
        iid = int(e["item"]) & 0xFF
        rows.append((_ITEM_SYM_REV.get(iid, str(iid)), e["flag"], None))
    _replace_gate_block(ITEMGATE_F, "GateItems", _emit_gate_block("GateItems", rows))


def set_door_gates(entries):
    """Editor write: entries = [{"type": t, "flag": name}, ...]. Rewrite GateDoors."""
    rows = [(str(int(e["type"]) & 0xFF), e["flag"], None) for e in entries]
    _replace_gate_block(DOORGATE_F, "GateDoors", _emit_gate_block("GateDoors", rows))


def gates_model():
    """Everything the editor needs to render + edit the three flag-gate tables."""
    return {
        "texts": [{"text": t, "flag": f} for t, f in parse_text_gates()],
        "items": [{"item": i, "flag": f} for i, f in parse_item_gates()],
        "doors": [{"type": t, "flag": f, "note": next(
            (g["note"] for g in GATE_DOORS if g["type"] == t), "")}
            for t, f in parse_door_gates()],
        "flags": _all_flags(),
        "pool_flags": _pool_flags(),
        "flag_labels": {f: flag_label(f) for f in _all_flags()},
        "door_flags": ["JeniOpenDoorF", "OpenBigBossDoor"] + _pool_flags(),
    }


def door_allowed(room, flags):
    """Table B interpreter (door): may this room's gated door open? Ungated
    rooms return True (this system doesn't lock them)."""
    g = _door_gate(room)
    return True if g is None else bool(flags.get(g["flag"], 0))


def antenna_required(room, zones):
    """Table C interpreter: does `room` need the antenna for radio? `zones` is
    the decoded per-room nibble list."""
    return zone_of(room, zones) >= ANTENNA_ZONE


# ---- independent literal transcription of the inline ASM --------------------
# Each mirrors the source branch-for-branch, INDEPENDENTLY of the tables above,
# so the equivalence test is meaningful (a misread won't cancel out).
def _orig_text_flag(text_id):
    # Banks0123.asm:8380-8391 — cp 117 / cp 118 / cp 138 chain.
    if text_id == 117:
        return "JeniRocketF"
    if text_id == 118:
        return "JeniOpenDoorF"
    if text_id == 138:
        return "SchneiderCaptured"
    return None


def _orig_item_allowed(item_id, jeni_rocket):
    # addroomitems.asm:60-65 — cp ROCKET_LAUNCHER; jr nz,ok; ld a,(JeniRocketF);
    # and a; ret z (drop item while flag clear).
    if item_id == ROCKET_LAUNCHER and jeni_rocket == 0:
        return False
    return True


def _orig_door_allowed(room, jeni_open, build2_locked):
    # opendoor.asm ChkCompassDoor (room 87 needs JeniOpenDoorF) and
    # ChkDesertDoorBuild2 (room 73 needs DoorBuild2LockedF).
    if room == 87:
        return jeni_open != 0
    if room == 73:
        return build2_locked != 0
    return True


def _orig_antenna(zone):
    # ChkRadioCalls3 / ChkRadioReply — cp 5; jr c (below 5 = no antenna needed).
    return zone >= 5


# ---- idxMapZones: nibble table parse / decode / emit ------------------------
_ZONES_RE = re.compile(r'(?ms)^idxMapZones:[ \t]*(.*?)(?=^\S|\Z)')


def parse_zone_bytes(src=None):
    """Raw bytes of the idxMapZones `db` block, in order."""
    if src is None:
        src = _read(ZONES_F)
    m = _ZONES_RE.search(src)
    if not m:
        raise ValueError("idxMapZones table not found in %s" % ZONES_F)
    out = []
    for ln in m.group(0).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\bdb\s+(.*)$', code)
        if not dm:
            continue
        for t in dm.group(1).split(","):
            t = t.strip()
            if t:
                out.append(_num(t) & 0xFF)
    return out


def decode_zones(byts):
    """Byte list -> per-room nibble list, using GetNibbleRoom's order:
    even room = high nibble, odd room = low nibble (byte index = room//2)."""
    zones = []
    for b in byts:
        zones.append((b >> 4) & 0xF)   # even room
        zones.append(b & 0xF)          # odd room
    return zones


def encode_zones(zones):
    """Per-room nibble list -> bytes (inverse of decode_zones). Pads an odd
    tail room's partner nibble with 0, matching how the table is authored."""
    byts = []
    for i in range(0, len(zones), 2):
        hi = zones[i] & 0xF
        lo = zones[i + 1] & 0xF if i + 1 < len(zones) else 0
        byts.append((hi << 4) | lo)
    return byts


def zone_of(room, zones):
    """Zone nibble for `room` (0 if out of range, matching a zero-padded table)."""
    return zones[room] if 0 <= room < len(zones) else 0


def load_zones():
    return decode_zones(parse_zone_bytes())


# ---- surgical single-nibble edit of idxMapZones (editor write) --------------
def _zone_token_spans(block):
    """Absolute (start, end) span of every numeric `db` operand token in the
    idxMapZones block, in room-byte order. Comments are ignored."""
    spans = []
    for lm in re.finditer(r'(?m)^.*$', block):
        code = lm.group(0).split(";", 1)[0]
        dbm = re.search(r'\bdb\b', code)
        if not dbm:
            continue
        base = lm.start() + dbm.end()
        for tm in re.finditer(r'[0-9A-Fa-f]+[hH]|\d+', code[dbm.end():]):
            spans.append((base + tm.start(), base + tm.end()))
    return spans


def _set_zone_text(block, room, zone):
    """Pure text transform: return `block` with `room`'s nibble set to `zone`,
    touching ONLY that one byte token (minimal diff). No-op (returns block
    unchanged) when the nibble already holds `zone`, so writes are idempotent."""
    room, zone = int(room), int(zone) & 0xF
    spans = _zone_token_spans(block)
    bi = room // 2
    if bi >= len(spans):
        raise ValueError("room %d is beyond idxMapZones (%d rooms)"
                         % (room, len(spans) * 2))
    s, e = spans[bi]
    cur = _num(block[s:e])
    new = ((zone << 4) | (cur & 0x0F)) if room % 2 == 0 else ((cur & 0xF0) | zone)
    if new == cur:
        return block
    return block[:s] + "0%02Xh" % new + block[e:]




# ---- per-room antenna requirement (idxAntennaRooms), decoupled from music ----
_ANTENNA_RE = re.compile(r'(?ms)^idxAntennaRooms:[ \t]*(.*?)(?=^\S|\Z)')


def parse_antenna_bytes(src=None):
    """Raw bytes of the idxAntennaRooms `db` block (nibble per room; nonzero =
    needs the antenna). Same packing as idxMapZones."""
    if src is None:
        src = _read(ZONES_F)
    m = _ANTENNA_RE.search(src)
    if not m:
        raise ValueError("idxAntennaRooms table not found in %s" % ZONES_F)
    out = []
    for ln in m.group(0).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\bdb\s+(.*)$', code)
        if not dm:
            continue
        for t in dm.group(1).split(","):
            t = t.strip()
            if t:
                out.append(_num(t) & 0xFF)
    return out


def load_antenna():
    """Per-room needs-antenna flags (0/1), decoded like the zone nibbles."""
    return [1 if n else 0 for n in decode_zones(parse_antenna_bytes())]


def room_needs_antenna(room):
    a = load_antenna()
    return bool(a[room]) if 0 <= room < len(a) else False


def set_antenna_room(room, on):
    """Editor write: set whether `room` needs the antenna (surgical single-nibble
    edit of idxAntennaRooms). Independent of the music zone. Rebuild after."""
    src = _read(ZONES_F)
    m = _ANTENNA_RE.search(src)
    if not m:
        raise ValueError("idxAntennaRooms table not found in %s" % ZONES_F)
    new_block = _set_zone_text(m.group(0), room, 1 if on else 0)
    if new_block != m.group(0):
        _write(ZONES_F, src[:m.start()] + new_block + src[m.end():])
    return zone_model(room)


# ---- per-room "carrying the bug trips the alarm" flag (idxBugAlarmRooms) -----
# Stock: while the enemy bug is in your equipment (TransmiTaken), moving in a room
# forces alert mode UNLESS the room's music zone is the B1 basement (4) or the
# desert/B3 zones (>=8) -- SetAreaMusic's `cp 4 / cp 8`. That building-derived
# rule is reworked into an explicit per-room flag so ANY room can be made
# bug-sensitive independent of building. Seeded byte-exact from the zone rule;
# same nibble packing/edit path as idxAntennaRooms.
_BUGALARM_RE = re.compile(r'(?ms)^idxBugAlarmRooms:[ \t]*(.*?)(?=^\S|\Z)')


def stock_bug_alarm(zone):
    """Frozen stock rule: does carrying the bug trip the alarm in a room of this
    music zone? True everywhere except B1 basement (4) and desert/B3 (>=8)."""
    return zone != 4 and zone < 8


def _orig_bug_alarm(zone):
    """Independent literal transcription of SetAreaMusic2 (Banks0123.asm:1618-1625):
    `cp 4 / jr z skip` then `cp 8 / jr nc skip` (skip = alert NOT armed)."""
    if zone == 4:
        return False
    if zone >= 8:
        return False
    return True


def bug_alarm_seed():
    """Per-room 0/1 seed derived from the live idxMapZones (byte-exact to stock)."""
    return [1 if stock_bug_alarm(z) else 0 for z in load_zones()]


def emit_bugalarm_table():
    """The `idxBugAlarmRooms:` db block (nibble-packed seed) to paste into
    data/musicradioconfig.asm. One nibble/room; 1 = bug trips the alarm here."""
    byts = encode_zones(bug_alarm_seed())
    out = ["idxBugAlarmRooms:"]
    for i in range(0, len(byts), 8):
        out.append("\t\t    db " + ", ".join("0%02Xh" % b for b in byts[i:i + 8]))
    return "\n".join(out)


def ensure_bugalarm_table():
    """Insert the seeded idxBugAlarmRooms table into musicradioconfig.asm right
    after idxAntennaRooms, if it isn't there yet. Idempotent; returns True if it
    wrote the file. The seed reproduces stock behaviour byte-for-byte."""
    src = _read(ZONES_F)
    if "idxBugAlarmRooms:" in src:
        return False
    m = _ANTENNA_RE.search(src)
    if not m:
        raise ValueError("idxAntennaRooms table not found in %s" % ZONES_F)
    block = ("\n;-----------------------------------------------------------"
             "-----------------\n"
             "; Per-room \"carrying the bug trips the alarm\" flag (one NIBBLE per\n"
             "; room, GetNibbleRoom packing). 1 = the enemy bug (TransmiTaken)\n"
             "; forces alert here. Seeded = stock zone rule (zone != 4 and < 8);\n"
             "; edit per-room in the map editor. Decoupled from idxMapZones.\n"
             ";-----------------------------------------------------------"
             "-----------------\n" + emit_bugalarm_table() + "\n")
    end = m.end()
    _write(ZONES_F, src[:end] + block + src[end:])
    return True


def parse_bugalarm_bytes(src=None):
    """Raw bytes of the idxBugAlarmRooms `db` block (nibble/room; nonzero = bug
    trips the alarm here). Same packing as idxMapZones/idxAntennaRooms."""
    if src is None:
        src = _read(ZONES_F)
    m = _BUGALARM_RE.search(src)
    if not m:
        raise ValueError("idxBugAlarmRooms table not found in %s" % ZONES_F)
    out = []
    for ln in m.group(0).splitlines():
        code = ln.split(";", 1)[0]
        dm = re.search(r'\bdb\s+(.*)$', code)
        if not dm:
            continue
        for t in dm.group(1).split(","):
            t = t.strip()
            if t:
                out.append(_num(t) & 0xFF)
    return out


def load_bug_alarm():
    """Per-room bug-alarm flags (0/1), decoded like the zone nibbles."""
    return [1 if n else 0 for n in decode_zones(parse_bugalarm_bytes())]


def bug_alarm_available():
    """True if idxBugAlarmRooms is present (base-only engine feature; a stale
    project copy won't have it yet)."""
    try:
        parse_bugalarm_bytes()
        return True
    except ValueError:
        return False


def room_bug_alarm(room):
    room = int(room)
    try:
        a = load_bug_alarm()
    except ValueError:
        # table absent (stale project) -> fall back to the stock zone-derived value
        return stock_bug_alarm(zone_of(room, load_zones()))
    return bool(a[room]) if 0 <= room < len(a) else False


def set_bug_alarm_room(room, on):
    """Editor write: set whether carrying the bug trips the alarm in `room`
    (surgical single-nibble edit of idxBugAlarmRooms). Rebuild after."""
    src = _read(ZONES_F)
    m = _BUGALARM_RE.search(src)
    if not m:
        raise ValueError("idxBugAlarmRooms table not found in %s" % ZONES_F)
    new_block = _set_zone_text(m.group(0), room, 1 if on else 0)
    if new_block != m.group(0):
        _write(ZONES_F, src[:m.start()] + new_block + src[m.end():])
    return zone_model(room)


def zone_model(room):
    """Editor model for one room: its music zone (idxMapZones, now a read-only
    building label) plus its independent per-room flags -- antenna requirement
    (idxAntennaRooms) and 'bug trips the alarm here' (idxBugAlarmRooms)."""
    zones = load_zones()
    room = int(room)
    z = zone_of(room, zones)
    return {
        "room": room, "zone": z, "zone_name": zone_name(z), "n_rooms": len(zones),
        "antenna": room_needs_antenna(room),        # real per-room flag (decoupled)
        "zone_antenna_default": z >= ANTENNA_ZONE,   # what the music zone would imply
        "bug_alarm": room_bug_alarm(room),           # per-room flag (decoupled)
        "bug_alarm_default": stock_bug_alarm(z),     # what the music zone would imply
        "bug_alarm_available": bug_alarm_available(),  # False on a stale project copy
        "zones": [{"value": v, "name": zone_name(v)}
                  for v in sorted(DEFAULT_ZONE_NAMES)],
    }


# ---- equivalence selftest ---------------------------------------------------
def selftest():
    checks = 0

    # 1) text -> flag, over every possible text id byte.
    for tid in range(0, 256):
        checks += 1
        if text_sets_flag(tid) != _orig_text_flag(tid):
            print("SELFTEST FAIL: text->flag mismatch at text %d "
                  "(table=%s orig=%s)" % (tid, text_sets_flag(tid),
                                          _orig_text_flag(tid)))
            return False

    # 2) item spawn gate, every item id x every JeniRocketF state.
    for item_id in range(0, 64):
        for jr in (0, 1):
            checks += 1
            flags = dict.fromkeys(FLAGS, 1)
            flags["JeniRocketF"] = jr
            if item_allowed(item_id, flags) != _orig_item_allowed(item_id, jr):
                print("SELFTEST FAIL: item gate mismatch item=%d JeniRocketF=%d"
                      % (item_id, jr))
                return False

    # 3) door gate, every room id x both door flags.
    for room in range(0, 256):
        for jo in (0, 1):
            for b2 in (0, 1):
                checks += 1
                flags = {"JeniOpenDoorF": jo, "DoorBuild2LockedF": b2}
                if door_allowed(room, flags) != _orig_door_allowed(room, jo, b2):
                    print("SELFTEST FAIL: door gate mismatch room=%d JeniOpen=%d "
                          "Build2=%d" % (room, jo, b2))
                    return False

    # 4) antenna zones: parse LIVE table, prove decode==interpreter over every
    #    room, and prove the nibble codec round-trips byte-for-byte.
    try:
        raw = parse_zone_bytes()
        zones = decode_zones(raw)
    except Exception as e:                              # noqa: BLE001
        print("SELFTEST FAIL: cannot parse idxMapZones: %s" % e)
        return False
    for room in range(0, len(zones)):
        checks += 1
        if antenna_required(room, zones) != _orig_antenna(zone_of(room, zones)):
            print("SELFTEST FAIL: antenna mismatch room=%d zone=%d"
                  % (room, zone_of(room, zones)))
            return False
    if encode_zones(zones) != raw:
        print("SELFTEST FAIL: idxMapZones nibble round-trip not byte-exact")
        return False

    # anchor checks — documented ground truth, catches a silent nibble-order flip.
    # room -> expected zone, counted by hand from data/musicradioconfig.asm:
    # rooms 0-15 = 0 (first db row of eight 0s); room 16 = first zone-1 nibble
    # (11h at byte 8); room 70 = first zone-5 nibble (55h at byte 35, needs antenna).
    anchors = {0: 0, 1: 0, 16: 1, 70: 5}
    for room, want in anchors.items():
        checks += 1
        if zone_of(room, zones) != want:
            print("SELFTEST FAIL: anchor room %d expected zone %d, got %d "
                  "(nibble-order bug?)" % (room, want, zone_of(room, zones)))
            return False

    # 5) surgical zone edit (editor write) — proven in-memory, no file change:
    #    setting a room's nibble changes ONLY that room, and re-setting the same
    #    value is a byte-exact no-op (idempotent).
    block = _ZONES_RE.search(_read(ZONES_F)).group(0)
    base = decode_zones(parse_zone_bytes(block))
    for room, newz in [(0, 7), (1, 3), (16, 0), (70, 0), (200, 9), (len(zones) - 1, 5)]:
        checks += 1
        nb = _set_zone_text(block, room, newz)
        got = decode_zones(parse_zone_bytes(nb))
        if got[room] != newz:
            print("SELFTEST FAIL: set_zone room %d -> %d not reflected"
                  % (room, newz))
            return False
        if any(got[r] != base[r] for r in range(len(base)) if r != room):
            print("SELFTEST FAIL: set_zone room %d disturbed another room" % room)
            return False
        if _set_zone_text(block, room, base[room]) != block:
            print("SELFTEST FAIL: set_zone(room %d, same value) not a no-op" % room)
            return False

    # 6-8) the LIVE tables (as shipped) are compared to the frozen stock model.
    #    A mismatch is INFORMATIONAL, not a failure: the equivalence proof above
    #    is frozen/independent, so once the editor legitimately edits a table the
    #    live data is expected to diverge from stock (mirrors mghideguard). What
    #    must always hold is that each table still PARSES and round-trips (9).
    edited = []
    try:
        live = parse_item_gates()
        livet = parse_text_gates()
        livd = parse_door_gates()
    except Exception as e:                              # noqa: BLE001
        print("SELFTEST FAIL: cannot parse a gate table: %s" % e)
        return False
    checks += 3
    if live != [(g["key"], g["flag"]) for g in GATE_SPAWNS if g["kind"] == "item"]:
        edited.append("GateItems")
    if livet != list(GATE_TEXTS.items()):
        edited.append("GateTexts")
    if livd != [(g["type"], g["flag"]) for g in GATE_DOORS]:
        edited.append("GateDoors")

    # 9) writer round-trip (editor writes) — emit each table from the live model
    #    and re-parse it; must reproduce the same entries (no file change).
    rt = [
        ("GateItems", parse_item_gates, [(_ITEM_SYM_REV.get(i, str(i)), f, None) for i, f in live]),
        ("GateTexts", parse_text_gates, [(str(t), f, None) for t, f in livet]),
        ("GateDoors", parse_door_gates, [(str(t), f, None) for t, f in livd]),
    ]
    for label, parser, rows in rt:
        checks += 1
        reparsed = parser(_emit_gate_block(label, rows))
        base = {"GateItems": live, "GateTexts": livet, "GateDoors": livd}[label]
        # items keep symbols, so compare on resolved ints/strings uniformly
        norm = [(_ITEMSYM.get(k, k) if isinstance(k, str) else k, fl) for k, fl in reparsed]
        if norm != base:
            print("SELFTEST FAIL: %s writer round-trip %s != %s" % (label, norm, base))
            return False

    # 10) idxAntennaRooms parses + round-trips; note if it diverges from the
    #     stock zone>=5 default (informational — the table is user-editable).
    try:
        araw = parse_antenna_bytes()
        ant = load_antenna()
    except Exception as e:                              # noqa: BLE001
        print("SELFTEST FAIL: cannot parse idxAntennaRooms: %s" % e)
        return False
    checks += 1
    if encode_zones([1 if x else 0 for x in ant]) != [b & 0x11 for b in araw]:
        # (antenna nibbles are 0/1 so bytes are 0x00/0x01/0x10/0x11)
        print("SELFTEST FAIL: idxAntennaRooms round-trip not byte-exact")
        return False
    if [r for r in range(len(zones)) if bool(ant[r]) != (zones[r] >= ANTENNA_ZONE)]:
        edited.append("idxAntennaRooms")

    # 11) bug-alarm: prove the table-derivation rule == an INDEPENDENT literal
    #     transcription of SetAreaMusic2 over every zone; and if the shipped
    #     idxBugAlarmRooms table exists, prove it decodes to the stock seed and
    #     round-trips byte-for-byte (else note it's not inserted yet).
    for zone in range(0, 16):
        checks += 1
        if stock_bug_alarm(zone) != _orig_bug_alarm(zone):
            print("SELFTEST FAIL: bug-alarm rule != orig at zone %d" % zone)
            return False
    try:
        braw = parse_bugalarm_bytes()
    except ValueError:
        braw = None
    if braw is None:
        edited.append("idxBugAlarmRooms:NOT-INSERTED")
    else:
        balarm = load_bug_alarm()
        for room in range(len(zones)):
            checks += 1
            if bool(balarm[room]) != stock_bug_alarm(zones[room]):
                edited.append("idxBugAlarmRooms")
                break
        if encode_zones([1 if x else 0 for x in balarm]) != [b & 0x11 for b in braw]:
            print("SELFTEST FAIL: idxBugAlarmRooms round-trip not byte-exact")
            return False

    need = sum(1 for z in zones if z >= ANTENNA_ZONE)
    note = (" [edited from stock: %s]" % ", ".join(edited)) if edited else ""
    print("SELFTEST PASS: gates == original over %d cases "
          "(%d texts, %d spawn gates, %d antenna rooms of %d need the antenna); "
          "idxMapZones %d bytes round-trip byte-exact; gate tables parse + "
          "round-trip.%s"
          % (checks, len(GATE_TEXTS), len(GATE_SPAWNS), need, len(zones), len(raw), note))
    return True


# ---- dump -------------------------------------------------------------------
def dump():
    print("Table A  text -> flag:")
    for tid in sorted(GATE_TEXTS):
        print("  text %3d  sets  %s" % (tid, GATE_TEXTS[tid]))
    print("\nTable B  spawn / open gates:")
    for g in GATE_SPAWNS:
        keyname = ("item %d" % g["key"]) if g["kind"] == "item" else ("room %d" % g["key"])
        print("  %-4s %-9s needs %-17s %s"
              % (g["kind"], keyname, g["flag"],
                 "(one-shot)" if g["oneshot"] else ""))
    zones = load_zones()
    need = [r for r in range(len(zones)) if zones[r] >= ANTENNA_ZONE]
    print("\nTable C  antenna zones (idxMapZones): %d rooms, %d need the antenna"
          % (len(zones), len(need)))
    print("  rooms needing antenna: %s%s"
          % (", ".join(map(str, need[:24])), " ..." if len(need) > 24 else ""))


def emit_zones():
    byts = encode_zones(load_zones())
    for i in range(0, len(byts), 8):
        print("\t\t    db " + ", ".join("0%02Xh" % b for b in byts[i:i + 8]))


def main():
    cmd = sys.argv[1] if len(sys.argv) >= 2 else ""
    if cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    if cmd == "dump":
        return dump()
    if cmd == "emit-zones":
        return emit_zones()
    print(__doc__)


if __name__ == "__main__":
    main()
