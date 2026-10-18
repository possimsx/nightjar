#!/usr/bin/env python3
"""
mgmap.py - Metal Gear (MSX) MAP codec for the NIGHTJAR rework.

The world is pure data (no engine changes needed to reshape it). This tool
decodes the three core map layers into one editable JSON and encodes the JSON
back to the .asm sources, with a byte-exact round-trip (`selftest`).

Layers handled (see docs/05-WORLD-AND-PROGRESSION.md):

  layouts      data/rooms.asm          RoomNNN = 6 rows x 8 cols of metatile
                                        bytes (an 8x6 screen). Order + count
                                        come from the idxRooms pointer table.
  connections  data/roomsconnections.asm  RoomConnections = 4 bytes/room:
                                        North, South, West, East (255 = wall).
  tilesets     data/roomtileset.asm    RoomGfxSetIds = packed nibbles, one per
                                        room: even room -> high nibble,
                                        odd room -> low nibble. Value = tileset
                                        id (0 Building .. 7 Ending).

Usage:
  python tools/mgmap.py info
  python tools/mgmap.py show <room>            ASCII layout + conns + tileset
  python tools/mgmap.py export [-o tools/map.json]
  python tools/mgmap.py import [--file tools/map.json] [--dry]
  python tools/mgmap.py selftest               parse -> repack == original
"""
import sys, re, os, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
import mgproj                     # active-project resolver (docs/PROJECTS-PLAN.md)

ROOMS_F = "data/rooms.asm"
CONNS_F = "data/roomsconnections.asm"
TILES_F = "data/roomtileset.asm"
DOORS_F = "data/doors.asm"
ITEMS_F = "data/itemsinrooms.asm"
ACTORS_F = "data/actorsinrooms.asm"
CHKPT_F = "data/checkpoints.asm"      # SaveStatRooms (code stays in logic/)

ROOM_W, ROOM_H = 8, 6                 # 8 cols x 6 rows of metatiles
TILESET_NAMES = ["Building", "Basem/Desert", "Roof", "Elevator/Ladder",
                 "Lorry/Isolated", "HindD", "MetalGear", "Ending"]

# Engine indexing quirks (Banks0123.asm / logic/addroomitems.asm).
# Since Phase A (docs/LIMITS-PLAN.md) the item/actor bounds are SYMBOLIC in the
# ASM (ITEMROOM_END / N_ACTORROOMS equ, derived from the table length), so the
# live range is whatever the table currently covers — grow the table, the
# engine bound follows. Stock lengths: items 96 slots (rooms 122..217), actors
# 222 slots (rooms 0..221). MAX_ROOM caps growth (room id byte, 251 rooms).
#  items : idxRoomItemsIdx[room-ITEM_ROOM_BASE]; base fixed at 122 (lowering it
#          would reindex every slot — possible, but a separate change)
#  doors : idxDoors slot = room (room<225); room 225..239 have NO doors;
#          room>=240 -> slot = room-15. So slots map to rooms 0..224, 240..250.
#  actors: idxActorsRooms slot = room, one dw per room from 0.
ITEM_ROOM_BASE = 122
MAX_ROOM = 250                                                   # room ids 0..250
DOOR_SLOT_ROOMS = list(range(0, 225)) + list(range(240, 251))   # 236 entries


# ---------------------------------------------------------------------------
# low-level asm value <-> token helpers (same dialect as tools/mggfx.py)
# ---------------------------------------------------------------------------
def _vals(s):
    out = []
    for t in s.split(','):
        t = t.strip()
        if not t:
            continue
        if t.endswith(('h', 'H')):
            out.append(int(t[:-1], 16))
        elif t.startswith('#'):
            out.append(int(t[1:], 16))
        elif t.startswith('0x'):
            out.append(int(t, 16))
        else:
            out.append(int(t))
    return out


def _tok(b):
    if b < 10:
        return str(b)
    s = "%X" % b                       # sjasm hex literals must start with a digit
    if s[0] not in "0123456789":
        s = "0" + s
    return s + "h"


# ---------------------------------------------------------------------------
# multi-world context (docs/LIMITS-PLAN.md Phase D3)
#
# World 0 is the canonical data/ set. World N >= 1 is a parallel per-room
# dataset in data/worldN/ (created by tools/mgworld.py), with every label the
# world file set defines suffixed _wN so all worlds assemble side by side.
# set_world(N) redirects every read/write of a PER-WORLD file to the world's
# copy, stripping the suffix on read and re-applying it on write - so every
# codec/editor above this layer keeps working on stock label names, unaware
# of worlds. Files NOT in WORLD_FILES (tilesets, palettes, metatiles, texts,
# route blocks, RoomFlags, ...) are engine-SHARED across worlds and are never
# redirected: an edit there affects every world, exactly like the ROM.
# ---------------------------------------------------------------------------
GATE_F = "data/gateways.asm"
PATHIDX_F = "data/pathindex.asm"
# NOTE: the stock 156-slot roomsconnections.asm is NOT here - worlds >0 exist
# only in WORLDBANK builds, which navigate via RoomConnsFull; the stock table
# is world 0's flag-off fallback and stays shared (read-only for world N).
WORLD_FILES = {"rooms.asm", "roomconnsfull.asm",
               "doors.asm", "itemsinrooms.asm", "actorsinrooms.asm",
               "radiocalls.asm", "gateways.asm", "pathindex.asm",
               "checkpoints.asm"}
_WORLD = 0
_LABEL_RE = re.compile(r'^(\w+):', re.M)


def current_world():
    return _WORLD


def world_count():
    """Number of assembled worlds (the WORLDS equ in features.asm; 1 if absent)."""
    try:
        txt = open(mgproj.path("features.asm"), encoding="latin-1").read()
        m = re.search(r'^WORLDS\s+equ\s+(\d+)', txt, re.M)
        return int(m.group(1)) if m else 1
    except OSError:
        return 1


def set_world(n):
    """Make world `n` the active dataset for all reads/writes of per-world
    files. Invalidate the model cache (same source paths, different content)."""
    global _WORLD, _MODEL_CACHE
    n = int(n)
    if n < 0 or n >= max(1, world_count()):
        raise ValueError("world %d out of range (have 0..%d)" % (n, world_count() - 1))
    if n != _WORLD:
        _WORLD = n
        _MODEL_CACHE = None
    return _WORLD


def _on_project_switch():
    """Project switch: same relative paths, different source tree — drop the
    model cache and fall back to world 0 (world counts differ per project)."""
    global _MODEL_CACHE, _WORLD
    _MODEL_CACHE = None
    _WORLD = 0


mgproj.on_switch(_on_project_switch)


def world_file(path):
    """The on-disk file the active world reads `path` from: data/worldN/<name>
    for per-world files when world N>0 is active, else `path` unchanged."""
    if _WORLD > 0:
        d, name = os.path.split(path.replace("\\", "/"))
        if d == "data" and name in WORLD_FILES:
            return "data/world%d/%s" % (_WORLD, name)
    return path


def _world_suffix_re():
    return re.compile(r'_w%d\b' % _WORLD)


def _world_defined_labels(extra_text=""):
    """Base names of every label the active world's file set defines (suffix
    stripped), plus any labels defined in `extra_text` (covers labels a write
    is about to mint). This is the set genworld suffixes - references to
    labels OUTSIDE it (Metatiles*, Paths_*, enums, engine symbols) stay
    unsuffixed and resolve to the SHARED definitions."""
    names = set(_LABEL_RE.findall(extra_text))
    strip = _world_suffix_re()
    for f in sorted(WORLD_FILES):
        real = mgproj.path(world_file("data/" + f))
        if os.path.exists(real):
            names |= set(_LABEL_RE.findall(
                strip.sub('', open(real, encoding='latin-1').read())))
    return names


def read_text(path):
    """World-aware whole-file read (latin-1): redirects per-world files to the
    active world's copy and strips the _wN label suffix, so callers always see
    stock label names."""
    real = world_file(path)
    txt = open(mgproj.path(real), encoding='latin-1').read()
    if real != path:
        txt = _world_suffix_re().sub('', txt)
    return txt


def write_text(path, txt, preserve_eof=False):
    """World-aware whole-file write: re-applies the _wN suffix to every label
    the world's file set defines (definitions AND references) and writes to
    the active world's copy. With preserve_eof, keep the target file's
    trailing-newline state (doors.asm has none)."""
    real = world_file(path)
    if real != path:
        defined = _world_defined_labels(txt)
        if defined:
            pat = re.compile(r'\b(' + '|'.join(
                sorted(map(re.escape, defined), key=len, reverse=True)) + r')\b')
            txt = pat.sub(lambda m: m.group(1) + "_w%d" % _WORLD, txt)
    full = mgproj.path(real)
    if preserve_eof:
        try:
            had_nl = open(full, "rb").read().endswith(b"\n")
        except OSError:
            had_nl = True
        if not had_nl:
            txt = txt.rstrip("\n")
        elif not txt.endswith("\n"):
            txt += "\n"
    open(full, 'w', encoding='latin-1').write(txt)


def _read(path):
    return read_text(path).splitlines()


def _write(path, lines):
    write_text(path, '\n'.join(lines) + '\n')


def _code(ln):
    """Strip a trailing ; comment, keep the code part."""
    return ln.split(';', 1)[0]


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def parse_label_order(lines, idx_label):
    """Read a `idx_label: dw RoomXXX / dw RoomYYY ...` pointer table -> ordered
    list of referenced labels. Spans blank lines and comment-only lines inside
    the table (idxDoors has a 'rooms 225-239 skipped' gap); stops at the first
    real code line that is not a `dw` continuation (the next label/divider)."""
    order, collecting = [], False
    for ln in lines:
        code = _code(ln)
        s = code.strip()
        if not collecting:
            m = re.match(r'^%s:\s*dw\s+(\w+)' % re.escape(idx_label), code)
            if m:
                order.append(m.group(1)); collecting = True
            continue
        if s == '':                       # blank or comment-only gap: skip
            continue
        m2 = re.match(r'^\s+dw\s+(\w+)', code)
        if m2:
            order.append(m2.group(1)); continue
        break                             # first non-dw code line ends the table
    return order


def find_block(lines, label):
    """Return (start, end) line indices of `label:` + its indented db
    continuation lines (end exclusive). Stops at a blank line or new label.

    A *bare* label (e.g. `RoomUndefined:` with no `db` on its line and no
    db continuation) is a zero-byte placeholder: returns (start, start+1) with
    no value lines."""
    start = None
    bare = False
    for i, ln in enumerate(lines):
        c = _code(ln)
        if re.match(r'^%s:\s*db' % re.escape(label), c):
            start = i
            break
        if re.match(r'^%s:\s*$' % re.escape(label), c):
            start = i; bare = True
            break
    if start is None:
        raise KeyError("label not found: %s" % label)
    if bare:
        return start, start + 1
    end = start + 1
    while end < len(lines):
        c = _code(lines[end])
        if not c.strip():
            break
        if not re.match(r'^\s+db\s', c):
            break
        end += 1
    return start, end


def block_vals(lines, start, end):
    out = []
    # first line: strip "label: db" if present (bare placeholder labels have no db)
    first = _code(lines[start])
    m = re.match(r'^\w+:\s*db\s+(.*)$', first)
    if m:
        out += _vals(m.group(1))
    for i in range(start + 1, end):
        out += _vals(re.sub(r'^\s+db\s+', '', _code(lines[i])))
    return out


def parse_rooms(lines):
    """Slot-indexed list of (label, layout) using the idxRooms pointer table.
    Room id == slot index in idxRooms. Placeholder slots (RoomUndefined / any
    zero-byte label) get layout = None."""
    order = parse_label_order(lines, "idxRooms")
    rooms = []
    for lab in order:
        s, e = find_block(lines, lab)
        vals = block_vals(lines, s, e)
        if not vals:                          # bare placeholder (RoomUndefined)
            rooms.append((lab, None)); continue
        if len(vals) != ROOM_W * ROOM_H:
            raise ValueError("%s has %d metatiles (expected %d)"
                             % (lab, len(vals), ROOM_W * ROOM_H))
        rooms.append((lab, vals))
    return rooms


def parse_flat(lines, label):
    s, e = find_block(lines, label)
    return block_vals(lines, s, e)


def parse_connections(lines):
    flat = parse_flat(lines, "RoomConnections")
    if len(flat) % 4:
        raise ValueError("RoomConnections not a multiple of 4 (%d)" % len(flat))
    return [flat[i:i + 4] for i in range(0, len(flat), 4)]


def parse_tilesets(lines, nrooms):
    """Unpack RoomGfxSetIds nibbles -> (per-room tileset ids, trailing pad
    nibbles, packed_len). The table is 2*packed_len nibbles; any nibble past
    room nrooms-1 is unused padding that must be preserved byte-for-byte."""
    packed = parse_flat(lines, "RoomGfxSetIds")
    ids = []
    for b in packed:
        ids.append((b >> 4) & 0xF)     # even room = high nibble
        ids.append(b & 0xF)            # odd room  = low nibble
    return ids[:nrooms], ids[nrooms:], len(packed)


# ---------------------------------------------------------------------------
# encoding (value-level; preserves file structure, rewrites only db blocks)
# ---------------------------------------------------------------------------
def fmt_db(label, data, perline=8, indent="\t\t    "):
    """Render a db block. First line carries the label, rest are continuations."""
    lines = []
    for k in range(0, len(data), perline):
        toks = ',\t'.join(_tok(b) for b in data[k:k + perline])
        if k == 0:
            lines.append(("%-20sdb\t" % (label + ':')) + toks)
        else:
            lines.append(indent + "db\t" + toks)
    return lines


def replace_block(lines, label, new_lines):
    s, e = find_block(lines, label)
    lines[s:e] = new_lines
    return lines


def replace_label_block(lines, label, new_lines):
    """Like replace_block but spans mixed db/dw continuations (actor blocks)."""
    s, e, _ = block_tokens(lines, label)
    lines[s:e] = new_lines
    return lines


def pack_tilesets(ids, pad, packed_len):
    """Inverse of parse_tilesets. Appends the preserved trailing pad nibbles so
    the packed bytes are byte-identical to the source."""
    nibs = list(ids) + list(pad)
    while len(nibs) < packed_len * 2:
        nibs.append(0)
    out = []
    for i in range(0, packed_len * 2, 2):
        out.append(((nibs[i] & 0xF) << 4) | (nibs[i + 1] & 0xF))
    return out[:packed_len]


# ---------------------------------------------------------------------------
# doors / items / actors  (per-room gating + content layers)
# ---------------------------------------------------------------------------
def _toks(s):
    """Split an operand list into raw, stripped token strings (preserves
    symbolic constants like ID_GUARD_MEDIUM)."""
    return [t.strip() for t in s.split(',') if t.strip()]


def label_room(label):
    """Room id encoded in a per-room data label (DoorsRoom_063 -> 63,
    Door_166 -> 166). Shared sentinels (NoDoorsRoom) -> None."""
    m = re.search(r'(\d+)$', label)
    return int(m.group(1)) if m else None


def block_tokens(lines, label):
    """Return (start, end, rows) where rows = list of (mnemonic, [tokens]) for
    the label line + its indented db/dw continuation lines. Bare label -> []."""
    start = None
    rows = []
    for i, ln in enumerate(lines):
        c = _code(ln)
        m = re.match(r'^%s:\s*(db|dw)\s+(.*)$' % re.escape(label), c)
        if m:
            start = i; rows.append((m.group(1), _toks(m.group(2)))); break
        if re.match(r'^%s:\s*$' % re.escape(label), c):
            start = i; break
    if start is None:
        raise KeyError("label not found: %s" % label)
    j = start + 1
    while j < len(lines):
        c = _code(lines[j])
        if not c.strip():
            break
        m = re.match(r'^\s+(db|dw)\s+(.*)$', c)
        if not m:
            break
        rows.append((m.group(1), _toks(m.group(2)))); j += 1
    return start, j, rows


# ---- doors ----------------------------------------------------------------
def parse_doors(lines):
    """Returns (order, rooms, noterm).
      order  : ordered idxDoors label list (for round-trip)
      rooms  : {room_id: [[id,render,y,x,dest], ...]} keyed by label-encoded room
      noterm : set of rooms whose source block has NO 0FFh of its own (the last
               block, DoorsRoom250, borrows NoDoorsRoom's terminator) -- must be
               re-emitted without a terminator to stay byte-identical."""
    order = parse_label_order(lines, "idxDoors")
    rooms = {}
    noterm = set()
    seen = set()
    for lab in order:
        if lab in seen:
            continue
        seen.add(lab)
        rid = label_room(lab)
        if rid is None:                       # NoDoorsRoom sentinel
            continue
        _, _, rows = block_tokens(lines, lab)
        flat = []
        for _mn, toks in rows:
            flat += _vals(','.join(toks))
        # split into 5-byte entries until the 0FF terminator
        entries = []
        k = 0
        while k < len(flat) and flat[k] != 0xFF:
            entries.append(flat[k:k + 5]); k += 5
        rooms[rid] = entries
        if not (k < len(flat) and flat[k] == 0xFF):
            noterm.add(rid)
    return order, rooms, noterm


def door_block_lines(label, entries, term=True):
    out = []
    if not entries:
        out.append("%-20sdb\t0FFh" % (label + ':'))
        return out
    for n, e in enumerate(entries):
        toks = ',\t'.join(_tok(b) for b in e)
        out.append((("%-20sdb\t" % (label + ':')) if n == 0 else "\t\t    db\t") + toks)
    if term:
        out.append("\t\t    db\t0FFh")
    return out


def parse_iddoorslogic(lines):
    return parse_flat(lines, "IdDoorsLogic")


# ---- items (per-room item-set index) --------------------------------------
def parse_item_idx(lines):
    return parse_flat(lines, "idxRoomItemsIdx")


def _is_item_term(tok):
    """True if `tok` is the 0FFh item-set terminator (symbolic ids -> False)."""
    try:
        return _vals(tok)[0] == 0xFF
    except (ValueError, IndexError):
        return False


def parse_item_sets(lines):
    """Returns (order, blocks) for the editable item-set content.
      order  : ordered idxRoomItems label list (labels may REPEAT — shared sets)
      blocks : {label: [[id_token, pos_mnemonic, [pos_tokens]], ...]}
    Each item = an id (db, 1 symbolic/numeric token) + a position that is EITHER
    `dw word` (Y=low byte, X=high byte) OR two position bytes `db Y, X` (which
    the stock data also spells as `db Y` + `db X` on two lines). Blocks are
    0FFh-terminated. dw and db,db are byte-identical, so writers normalise to
    dw; the parse keeps the original mnemonic for read-only fidelity."""
    order = parse_label_order(lines, "idxRoomItems")
    blocks = {}
    for lab in order:
        if lab in blocks:
            continue
        _, _, rows = block_tokens(lines, lab)
        flat = [(mn, t) for mn, toks in rows for t in toks]
        entries, i = [], 0
        while i < len(flat):
            mn, tok = flat[i]
            if _is_item_term(tok):                        # 0FFh ends the set
                break
            idtok = tok; i += 1
            if i < len(flat) and flat[i][0] == "dw":      # id + dw pos
                entries.append([idtok, "dw", [flat[i][1]]]); i += 1
            elif i + 1 < len(flat):                       # id + db Y + db X
                entries.append([idtok, "db", [flat[i][1], flat[i + 1][1]]]); i += 2
            else:                                         # malformed tail — stop
                break
        blocks[lab] = entries
    return order, blocks


def item_entry_yx(entry):
    """(y, x) pixel coords of one parsed item entry (position byte order y=low)."""
    _idtok, mn, toks = entry
    if mn == "dw":
        w = _vals(toks[0])[0]
        return w & 0xFF, (w >> 8) & 0xFF
    return _vals(toks[0])[0] & 0xFF, _vals(toks[1])[0] & 0xFF


def item_block_lines(label, entries):
    """Render an item-set block: `db ID / dw pos` per item, then `db 0FFh`.
    Positions are normalised to the `dw` form (byte-identical to db Y,X)."""
    out = []
    for n, ent in enumerate(entries):
        y, x = item_entry_yx(ent)
        pre = ("%-20sdb\t" % (label + ':')) if n == 0 else "\t\t    db\t"
        out.append(pre + ent[0])
        out.append("\t\t    dw\t%s" % _tok(((x & 0xFF) << 8) | (y & 0xFF)))
    out.append("\t\t    db\t0FFh")
    return out


# ---- gateways (docs/LIMITS-PLAN.md D2/D3) ----------------------------------
def parse_gateways(lines=None):
    """GatewayTable = [srcRoom, sentinel(252-254), destWorld, destRoom]
    entries, 0FFh-terminated. A door in srcRoom whose DESTINATION byte is the
    sentinel hops to (destWorld, destRoom); each world owns its table."""
    flat = parse_flat(lines if lines is not None else _read(GATE_F), "GatewayTable")
    out, k = [], 0
    while k + 3 < len(flat) and flat[k] != 0xFF:
        out.append(flat[k:k + 4]); k += 4
    return out


def write_gateways(entries):
    """Rewrite the active world's GatewayTable block (file header comment is
    preserved; per-entry comments are not - the table is the editor's)."""
    lines = _read(GATE_F)
    rows = []
    for n, e in enumerate(entries):
        pre = ("%-20sdb\t    " % "GatewayTable:") if n == 0 else "\t\t    db\t    "
        rows.append(pre + ", ".join(str(int(v) & 0xFF) for v in e))
    pre = ("%-20sdb\t    " % "GatewayTable:") if not entries else "\t\t    db\t    "
    rows.append(pre + "0FFh")
    replace_block(lines, "GatewayTable", rows)
    _write(GATE_F, lines)
    return parse_gateways()


# ---- checkpoints ----------------------------------------------------------
def parse_checkpoints(lines):
    """SaveStatRooms = [room, prevRoom] pairs, 0FFh-terminated (Phase A: any
    count; the engine scans to the terminator). When the player moves
    prevRoom->room and the pair matches, progress is saved."""
    flat = parse_flat(lines, "SaveStatRooms")
    if flat and flat[-1] == 0xFF:
        flat = flat[:-1]
    return [flat[i:i + 2] for i in range(0, len(flat), 2)]


# ---- actors / enemies -----------------------------------------------------
def parse_actors(lines):
    """Returns (slot_labels, blocks). idxActorsRooms is room-indexed (slot i =
    room i, rooms 0..221), and actor blocks are SHARED across rooms (e.g.
    ActorPrisoner, ActorLaserRooms, ActorsRoom59_62), so we key blocks by label
    and keep the per-slot label list.
      slot_labels : list, slot i -> label (incl. 'NoActorsInRoom' sentinel)
      blocks      : {label: [[id_token, pos_mnemonic, [pos_tokens]], ...]}
    Each actor = an id row (db, 1 symbolic token) + a position row that is
    EITHER `dw word` OR `db Y,X` (both 2 bytes; original form preserved)."""
    slot_labels = parse_label_order(lines, "idxActorsRooms")
    blocks = {}
    for lab in slot_labels:
        if lab == "NoActorsInRoom" or lab in blocks:
            continue
        _, _, rows = block_tokens(lines, lab)
        if not rows:
            blocks[lab] = []; continue
        count = _vals(rows[0][1][0])[0]
        body = rows[1:]
        entries = []
        for i in range(count):
            idtok = body[2 * i][1][0]
            pos_mn, pos_tok = body[2 * i + 1]
            entries.append([idtok, pos_mn, pos_tok])
        blocks[lab] = entries
    return slot_labels, blocks


def actors_by_room(slot_labels, blocks):
    """Resolve slot_labels + blocks -> {room: entries} (read-only view)."""
    out = {}
    for r, lab in enumerate(slot_labels):
        if lab != "NoActorsInRoom" and blocks.get(lab):
            out[r] = blocks[lab]
    return out


def actor_block_lines(label, entries):
    out = ["%-20sdb\t%s" % (label + ':', _tok(len(entries)))]
    for idtok, pos_mn, pos_tok in entries:
        out.append("\t\t    db\t%s" % idtok)
        out.append("\t\t    %s\t%s" % (pos_mn, ',\t'.join(pos_tok)))
    return out


# ---- table regeneration (add/remove per-room doors & actors) --------------
def room_label_map(order):
    """room id -> existing data label, from a parsed idx order list."""
    out = {}
    for lab in order:
        r = label_room(lab)
        if r is not None:
            out[r] = lab
    return out


def gen_index_lines(label, slot_rooms, has_data, room_label, sentinel):
    """Rebuild a `label: dw ...` pointer table: one entry per slot, pointing to
    the room's data label (if it has data) else the shared sentinel."""
    out = []
    for i, r in enumerate(slot_rooms):
        tgt = room_label[r] if (has_data(r) and r in room_label) else sentinel
        pre = ("%-20sdw\t" % (label + ':')) if i == 0 else "\t\t    dw\t"
        out.append(pre + tgt)
    return out


def find_line(lines, pat):
    for i, ln in enumerate(lines):
        if re.match(pat, ln):
            return i
    raise KeyError("no line matching %s" % pat)


def replace_region(lines, start_pat, end_pat, new_lines):
    """Replace lines[start..end) where start matches start_pat and end is the
    first subsequent line matching end_pat (or EOF if end_pat is None)."""
    s = find_line(lines, start_pat)
    if end_pat is None:
        e = len(lines)
    else:
        e = s + 1
        while e < len(lines) and not re.match(end_pat, lines[e]):
            e += 1
    lines[s:e] = new_lines
    return lines


# ---------------------------------------------------------------------------
# model load / save
# ---------------------------------------------------------------------------
FULLCONNS_F = "data/roomconnsfull.asm"   # 251x4 full table (WORLDBANK / plan C2)
_MODEL_FILES = (ROOMS_F, CONNS_F, TILES_F, DOORS_F, ITEMS_F, ACTORS_F, CHKPT_F,
                FULLCONNS_F)
_MODEL_CACHE = None
_MODEL_MTIMES = None


def _model_mtimes():
    out = [_WORLD]                       # world switch always invalidates
    for f in _MODEL_FILES:
        try:
            out.append(os.path.getmtime(mgproj.path(world_file(f))))
        except OSError:
            out.append(None)
    return tuple(out)


def load_model():
    """Parse all map source files into one model. Cached by the source files'
    mtimes so the editor's many per-request callers (objects/paths/hideguards/…)
    reparse only when a file actually changes. The result is treated read-only by
    callers, so the cached object is shared."""
    global _MODEL_CACHE, _MODEL_MTIMES
    mt = _model_mtimes()
    if _MODEL_CACHE is not None and mt == _MODEL_MTIMES:
        return _MODEL_CACHE
    rl = _read(ROOMS_F)
    cl = _read(CONNS_F)
    tl = _read(TILES_F)
    dl = _read(DOORS_F)
    il = _read(ITEMS_F)
    al = _read(ACTORS_F)
    kl = _read(CHKPT_F)
    rooms = parse_rooms(rl)
    conns = parse_connections(cl)
    tids, tpad, packed_len = parse_tilesets(tl, len(rooms))
    door_order, doors, door_noterm = parse_doors(dl)
    actor_slots, actor_blocks = parse_actors(al)
    _MODEL_CACHE = {
        "labels": [lab for lab, _ in rooms],
        "layouts": [v for _, v in rooms],
        "connections": conns,
        "tilesets": tids,
        "_tileset_pad": tpad,
        "_packed_tileset_len": packed_len,
        "door_order": door_order,
        "doors": doors,
        "door_noterm": door_noterm,
        "iddoorslogic": parse_iddoorslogic(dl),
        "item_idx": parse_item_idx(il),
        "actor_slots": actor_slots,
        "actor_blocks": actor_blocks,
        "checkpoints": parse_checkpoints(kl),
        # full per-room connections (rooms 0..250) when data/roomconnsfull.asm
        # exists (WORLDBANK C2); None otherwise. When present it is CANONICAL
        # for navigation — the stock 156-slot table stays for flag-off builds.
        "connections_full": (
            [row for row in _parse_full_conns()]
            if os.path.exists(mgproj.path(FULLCONNS_F)) else None),
    }
    _MODEL_MTIMES = mt
    return _MODEL_CACHE


def _parse_full_conns():
    flat = parse_flat(_read(FULLCONNS_F), "RoomConnsFull")
    if len(flat) != (MAX_ROOM + 1) * 4:
        raise ValueError("RoomConnsFull has %d bytes (expected %d)"
                         % (len(flat), (MAX_ROOM + 1) * 4))
    return [flat[i:i + 4] for i in range(0, len(flat), 4)]


def gen_full_conns(force=False):
    """Seed data/roomconnsfull.asm (251 rows x db N,S,W,E) from the stock table
    through the GetNextRoomNum remap — behaviour-neutral expansion. Rooms with
    no walk-off exits (126-207, 228-240) get 255,255,255,255 (the routine's
    stock C=FFh default). Returns the path; refuses to overwrite unless force."""
    path = mgproj.path(FULLCONNS_F)
    if os.path.exists(path) and not force:
        return FULLCONNS_F
    model = load_model()
    out = [";----------------------------------------------------------------------------",
           ";",
           "; Full per-room connections (rooms 0..%d): db North, South, West, East" % MAX_ROOM,
           "; (255 = no exit). Seeded from RoomConnections through the stock",
           "; GetNextRoomNum slot remap (docs/LIMITS-PLAN.md C2) - behaviour-neutral.",
           "; Assembled into BanksWorld.asm (WORLDBANK); cached to CurRoomConns at",
           "; room load. This file is CANONICAL for navigation when it exists.",
           ";",
           ";----------------------------------------------------------------------------"]
    for r in range(MAX_ROOM + 1):
        slot = eff_conn_slot(r)
        row = model["connections"][slot] if slot is not None else [255] * 4
        pre = ("%-20sdb\t" % "RoomConnsFull:") if r == 0 else "\t\t    db\t"
        out.append(pre + ", ".join(_tok(b) for b in row) + "\t; room %d" % r)
    _write(FULLCONNS_F, out)
    return FULLCONNS_F


def build_doc(model):
    """Build the mgmap export doc (dict) from a model WITHOUT touching disk. Used
    by read paths (e.g. the editor's map load) so merely opening/browsing never
    rewrites tools/map.json — only actual edits, via export_json, do."""
    rooms = []
    for rid, lab in enumerate(model["labels"]):       # rid == idxRooms slot
        layout = model["layouts"][rid]
        rec = {"id": rid, "label": lab, "tileset": model["tilesets"][rid],
               "placeholder": layout is None,
               "grid": None if layout is None else
                       [layout[r * ROOM_W:(r + 1) * ROOM_W] for r in range(ROOM_H)]}
        if rid < len(model["connections"]):
            n, s, w, e = model["connections"][rid]
            rec["conn"] = {"N": n, "S": s, "W": w, "E": e}
        if model.get("connections_full") is not None and rid < len(model["connections_full"]):
            n, s, w, e = model["connections_full"][rid]
            rec["conn_full"] = {"N": n, "S": s, "W": w, "E": e}
        islot = rid - ITEM_ROOM_BASE          # items indexed by room-122
        if 0 <= islot < len(model["item_idx"]):
            rec["item"] = model["item_idx"][islot]
        if rid in model["doors"]:
            rec["doors"] = model["doors"][rid]
        # _actors is a READ-ONLY resolved view; authoritative actor data lives in
        # top-level actor_slots + actor_blocks (blocks are shared across rooms).
        if rid < len(model["actor_slots"]):
            lab = model["actor_slots"][rid]
            if lab != "NoActorsInRoom" and model["actor_blocks"].get(lab):
                rec["_actors"] = {"label": lab, "list": model["actor_blocks"][lab]}
        rooms.append(rec)
    doc = {"_format": "mgmap/1", "room_w": ROOM_W, "room_h": ROOM_H,
           "tileset_names": TILESET_NAMES,
           "_packed_tileset_len": model["_packed_tileset_len"],
           "_tileset_pad": model["_tileset_pad"],
           "connections_count": len(model["connections"]),
           "connections_full_count": (len(model["connections_full"])
                                      if model.get("connections_full") is not None else 0),
           "item_idx_count": len(model["item_idx"]),
           "door_order": model["door_order"],
           "door_noterm": sorted(model.get("door_noterm", [])),
           "iddoorslogic": model["iddoorslogic"],
           "actor_slots": model["actor_slots"],
           "actor_blocks": model["actor_blocks"],
           "checkpoints": model["checkpoints"],
           "rooms": rooms}
    return doc


def export_json(model, path):
    """Build the doc AND persist it to `path` (tools/map.json). Call this only
    after an edit that changed the .asm sources."""
    doc = build_doc(model)
    full = mgproj.path(path)
    d = os.path.dirname(full)
    if d:
        os.makedirs(d, exist_ok=True)
    open(full, 'w', encoding='utf-8').write(json.dumps(doc, indent=1))
    return doc


def model_from_json(doc):
    rooms = sorted(doc["rooms"], key=lambda r: r["id"])
    labels = [r["label"] for r in rooms]
    layouts = [None if r.get("grid") is None
               else [b for row in r["grid"] for b in row] for r in rooms]
    tilesets = [r["tileset"] for r in rooms]
    nconn = doc["connections_count"]
    conns = [[255, 255, 255, 255] for _ in range(nconn)]
    for r in rooms:
        if "conn" in r and r["id"] < nconn:
            c = r["conn"]
            conns[r["id"]] = [c["N"], c["S"], c["W"], c["E"]]
    item_idx = [0] * doc.get("item_idx_count", 0)
    doors = {}
    for r in rooms:
        islot = r["id"] - ITEM_ROOM_BASE
        if "item" in r and 0 <= islot < len(item_idx):
            item_idx[islot] = r["item"]
        if "doors" in r:
            doors[r["id"]] = r["doors"]
    nfull = doc.get("connections_full_count", 0)
    conns_full = None
    if nfull:
        conns_full = [[255, 255, 255, 255] for _ in range(nfull)]
        for r in rooms:
            if "conn_full" in r and r["id"] < nfull:
                c = r["conn_full"]
                conns_full[r["id"]] = [c["N"], c["S"], c["W"], c["E"]]
    return {"labels": labels, "layouts": layouts, "connections": conns,
            "connections_full": conns_full,
            "tilesets": tilesets, "_tileset_pad": doc.get("_tileset_pad", []),
            "_packed_tileset_len": doc["_packed_tileset_len"],
            "door_order": doc.get("door_order", []), "doors": doors,
            "door_noterm": set(doc.get("door_noterm", [])),
            "iddoorslogic": doc.get("iddoorslogic", []), "item_idx": item_idx,
            "actor_slots": doc.get("actor_slots", []),
            "actor_blocks": doc.get("actor_blocks", {}),
            "checkpoints": doc.get("checkpoints", [])}


def write_doors(dl, model, regen):
    """Rewrite door blocks in place. If regen: also mint+append blocks for rooms
    that gained doors and rebuild the idxDoors pointer table (room order)."""
    doors = model["doors"]
    noterm = set(model.get("door_noterm", []))
    rl_map = room_label_map(model["door_order"])
    for lab in model["door_order"]:                    # existing blocks, in place
        rid = label_room(lab)
        if rid is None:
            continue
        replace_label_block(dl, lab,
                            door_block_lines(lab, doors.get(rid, []), term=rid not in noterm))
    if regen:
        new = [r for r in sorted(doors) if doors[r] and r not in rl_map]
        for r in [r for r in new if r not in DOOR_SLOT_ROOMS]:
            print("  WARN: room %d has no idxDoors slot (rooms 225-239) - doors dropped" % r)
        new = [r for r in new if r in DOOR_SLOT_ROOMS]
        ins = []
        for r in new:
            lab = "DoorsRoomNew%d" % r
            rl_map[r] = lab
            ins += door_block_lines(lab, doors[r]) + [""]
        if ins:
            at = find_line(dl, r'^NoDoorsRoom:')
            dl[at:at] = ins
        has = lambda r: r in doors and bool(doors[r])
        idx = gen_index_lines("idxDoors", DOOR_SLOT_ROOMS, has, rl_map, "NoDoorsRoom")
        replace_region(dl, r'^idxDoors:', r'^;---', idx + [""])
    replace_block(dl, "IdDoorsLogic", fmt_db("IdDoorsLogic", model["iddoorslogic"], perline=16))
    return dl


def write_actors(al, model, regen):
    """Rewrite actor blocks in place (by label, shared blocks written once).
    If regen: append any newly-referenced labels and rebuild idxActorsRooms
    positionally from actor_slots (slot i = room i)."""
    slots = model["actor_slots"]
    blocks = model["actor_blocks"]
    new_labels = []
    for lab, entries in blocks.items():
        try:
            replace_label_block(al, lab, actor_block_lines(lab, entries))
        except KeyError:
            new_labels.append(lab)            # minted label not yet in file
    if regen:
        ins = []
        for lab in new_labels:
            ins += actor_block_lines(lab, blocks[lab]) + [""]
        if ins:
            at = find_line(al, r'^NoActorsInRoom:')
            al[at:at] = ins
        idx = []
        for i, lab in enumerate(slots):
            pre = ("%-20sdw\t" % ("idxActorsRooms:")) if i == 0 else "\t\t    dw\t"
            idx.append(pre + lab)
        # NOTE: idxActorsRooms must stay the LAST section of the file — the
        # N_ACTORROOMS engine bound in Banks456.asm is ($-idxActorsRooms)/2
        replace_region(al, r'^idxActorsRooms:', None, idx)
    elif new_labels:
        print("  WARN: new actor labels %s need --regen to be linked" % new_labels)
    return al


# ---- Phase A growth (docs/LIMITS-PLAN.md): tables sized by content ----------
def grow_actor_index(lines, upto_room):
    """Append `dw NoActorsInRoom` slots so rooms 0..upto_room all have an
    idxActorsRooms entry. The engine bound (N_ACTORROOMS equ) follows the
    table length automatically. Returns the number of slots added."""
    if upto_room > MAX_ROOM:
        raise ValueError("room %d beyond MAX_ROOM %d" % (upto_room, MAX_ROOM))
    need = upto_room + 1 - len(parse_label_order(lines, "idxActorsRooms"))
    if need <= 0:
        return 0
    s = find_line(lines, r'^idxActorsRooms:')
    i, last = s + 1, s
    while i < len(lines):
        c = _code(lines[i])
        if re.match(r'^\s+dw\s+\w+', c):
            last = i
        elif c.strip():
            break
        i += 1
    lines[last + 1:last + 1] = ["\t\t    dw\tNoActorsInRoom"] * need
    return need


def grow_item_index(lines, upto_room):
    """Extend idxRoomItemsIdx with 0 (= no item) slots so room upto_room has
    one. The engine bound (ITEMROOM_END equ) follows the table length.
    Returns the number of slots added."""
    if upto_room > MAX_ROOM:
        raise ValueError("room %d beyond MAX_ROOM %d" % (upto_room, MAX_ROOM))
    flat = parse_flat(lines, "idxRoomItemsIdx")
    need = (upto_room - ITEM_ROOM_BASE) + 1 - len(flat)
    if need <= 0:
        return 0
    replace_block(lines, "idxRoomItemsIdx",
                  fmt_db("idxRoomItemsIdx", flat + [0] * need, perline=16))
    return need


def write_model(model, dry=False, regen=False):
    rl = _read(ROOMS_F)
    cl = _read(CONNS_F)
    tl = _read(TILES_F)

    # rooms: rewrite each RoomNNN block as 6 rows x 8 bytes (skip placeholders)
    for lab, layout in zip(model["labels"], model["layouts"]):
        if layout is None:
            continue
        replace_block(rl, lab, fmt_db(lab, layout, perline=ROOM_W))
    # connections: one flat block
    flat = [b for quad in model["connections"] for b in quad]
    replace_block(cl, "RoomConnections", fmt_db("RoomConnections", flat, perline=4))
    # full per-room connections (canonical when active — see effective_conns)
    fcl = None
    if model.get("connections_full") is not None and \
            os.path.exists(mgproj.path(FULLCONNS_F)):
        fcl = _read(FULLCONNS_F)
        fflat = [b for quad in model["connections_full"] for b in quad]
        replace_block(fcl, "RoomConnsFull", fmt_db("RoomConnsFull", fflat, perline=4))
    # tilesets: packed nibbles
    packed = pack_tilesets(model["tilesets"], model["_tileset_pad"],
                           model["_packed_tileset_len"])
    replace_block(tl, "RoomGfxSetIds", fmt_db("RoomGfxSetIds", packed, perline=16))

    # doors (+ optional table regeneration)
    dl = write_doors(_read(DOORS_F), model, regen)

    # items: per-room item-set index (flat table, indexed by room-122)
    il = _read(ITEMS_F)
    replace_block(il, "idxRoomItemsIdx", fmt_db("idxRoomItemsIdx", model["item_idx"], perline=16))

    # actors / enemies (+ optional table regeneration)
    al = write_actors(_read(ACTORS_F), model, regen)

    # checkpoints: SaveStatRooms = [room, prevRoom] pairs + 0FFh terminator
    kl = _read(CHKPT_F)
    if model.get("checkpoints"):
        flat = [b for pair in model["checkpoints"] for b in pair] + [0xFF]
        replace_block(kl, "SaveStatRooms", fmt_db("SaveStatRooms", flat, perline=2))

    if dry:
        return
    _write(ROOMS_F, rl)
    _write(CONNS_F, cl)
    _write(TILES_F, tl)
    _write(DOORS_F, dl)
    _write(ITEMS_F, il)
    _write(ACTORS_F, al)
    _write(CHKPT_F, kl)
    if fcl is not None:
        _write(FULLCONNS_F, fcl)


UNDEFINED_LABEL = "RoomUndefined"


def undefine_rooms(ids, lines=None):
    """Repoint the given room ids' idxRooms slots at the shared RoomUndefined
    placeholder, turning them into 'undefined' rooms (parse_rooms -> layout
    None). The orphaned RoomNNN data blocks are LEFT INTACT on purpose: many
    layouts are shared (RoomLorry backs 18 ids, Room103 backs 3, ...), so
    deleting a block is unsafe; an unreferenced block is just harmless dead
    data. Slots already pointing at RoomUndefined are skipped.

    Edits ROOMS_F in place (or the given `lines`, without writing). Returns the
    set of ids actually changed. Room ids are idxRooms slot indices, matching
    parse_rooms / load_model ordering exactly (blank/comment-only lines inside
    the table are skipped without advancing the slot, mirroring
    parse_label_order)."""
    own = lines is None
    if own:
        lines = _read(ROOMS_F)
    want = set(ids)
    changed = set()
    slot = -1
    in_table = False
    for i, ln in enumerate(lines):
        code = _code(ln)
        if not in_table:
            if re.match(r'^%s:\s*dw\s+\w+' % re.escape("idxRooms"), code):
                in_table = True
                slot = 0
            else:
                continue
        else:
            if code.strip() == '':                    # gap line: skip, no advance
                continue
            if not re.match(r'^\s+dw\s+\w+', code):    # first non-dw ends the table
                break
            slot += 1
        m = re.match(r'^(.*\bdw\s+)(\w+)(.*)$', code)
        if m and slot in want and m.group(2) != UNDEFINED_LABEL:
            # preserve any trailing ; comment on the original line
            comment = ln[len(code):]
            lines[i] = m.group(1) + UNDEFINED_LABEL + m.group(3) + comment
            changed.add(slot)
    if own:
        _write(ROOMS_F, lines)
    return changed


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_info(_):
    m = load_model()
    print("rooms (layouts) : %d   (idxRooms order)" % len(m["labels"]))
    print("connections     : %d  (rooms 0..%d)" % (len(m["connections"]),
                                                    len(m["connections"]) - 1))
    print("tileset nibbles : %d packed bytes -> %d room ids"
          % (m["_packed_tileset_len"], len(m["tilesets"])))
    from collections import Counter
    c = Counter(m["tilesets"])
    print("tileset usage   :")
    for tid in sorted(c):
        nm = TILESET_NAMES[tid] if tid < len(TILESET_NAMES) else "?"
        print("   %2d %-16s %3d rooms" % (tid, nm, c[tid]))
    ndoors = sum(len(v) for v in m["doors"].values())
    by_room = actors_by_room(m["actor_slots"], m["actor_blocks"])
    nact = sum(len(v) for v in by_room.values())
    print("doors           : %d rooms, %d door entries (idxDoors %d slots)"
          % (len(m["doors"]), ndoors, len(m["door_order"])))
    print("iddoorslogic    : %d door-id bytes" % len(m["iddoorslogic"]))
    print("items           : %d rooms have an item-set (of %d item-idx slots, rooms 122..%d)"
          % (sum(1 for v in m["item_idx"] if v), len(m["item_idx"]),
             ITEM_ROOM_BASE + len(m["item_idx"]) - 1))
    print("actors/enemies  : %d rooms, %d total actors (%d slots, %d unique blocks%s)"
          % (len(by_room), nact, len(m["actor_slots"]), len(m["actor_blocks"]),
             ", some shared" if len(by_room) > len(m["actor_blocks"]) else ""))
    print("checkpoints     : %d [room,prevRoom] save-trigger pairs" % len(m["checkpoints"]))


def cmd_show(args):
    m = load_model()
    rid = args.room                                   # room id == idxRooms slot
    if rid < 0 or rid >= len(m["labels"]):
        sys.exit("no room %d (have 0..%d)" % (rid, len(m["labels"]) - 1))
    layout = m["layouts"][rid]
    tid = m["tilesets"][rid]
    print("Room %d  (%s)  tileset %d=%s" %
          (rid, m["labels"][rid], tid,
           TILESET_NAMES[tid] if tid < len(TILESET_NAMES) else "?"))
    if rid < len(m["connections"]):
        n, s, w, e = m["connections"][rid]
        f = lambda v: "  -" if v == 255 else "%3d" % v
        print("  conn  N%s  S%s  W%s  E%s" % (f(n), f(s), f(w), f(e)))
    islot = rid - ITEM_ROOM_BASE
    if 0 <= islot < len(m["item_idx"]) and m["item_idx"][islot]:
        print("  item-set idx %d (idxRoomItems[%d])" %
              (m["item_idx"][islot], m["item_idx"][islot] - 1))
    for d in m["doors"].get(rid, []):
        print("  door id=%02X render=%X -> room %d  (at y=%02X x=%02X)" %
              (d[0], d[1], d[4], d[2], d[3]))
    if rid < len(m["actor_slots"]):
        lab = m["actor_slots"][rid]
        ents = m["actor_blocks"].get(lab, []) if lab != "NoActorsInRoom" else []
        if ents:
            print("  actors (block %s%s):" %
                  (lab, ", shared" if m["actor_slots"].count(lab) > 1 else ""))
            for a in ents:
                print("    %-22s @ %s %s" % (a[0], a[1], ','.join(a[2])))
    if layout is None:
        print("  (placeholder / undefined room - no layout)")
        return
    print("  +" + "---" * ROOM_W + "+")
    for r in range(ROOM_H):
        row = layout[r * ROOM_W:(r + 1) * ROOM_W]
        print("  |" + "".join("%02X " % b for b in row) + "|")
    print("  +" + "---" * ROOM_W + "+")


def eff_conn_slot(room):
    """The RoomConnections slot a room navigates through, per GetNextRoomNum
    (Banks0123.asm:893; docs/SPECIAL-ROOMS.md §1b): 0-125 direct; 208-227 borrow
    slot room-82; 241-250 borrow room-95; 126-207 & 228-240 are door-only/undefined
    (no walk-off connections) -> None."""
    if room < 126:
        return room
    if 208 <= room < 228:
        return room - 82
    if 241 <= room <= 250:
        return room - 95
    return None


def build_graph(m):
    """Adjacency from EFFECTIVE connections + door destinations. {room: set(neighbors)}.
    Walk-off edges use each room's effective connection slot (exit-table rooms 208-227 and
    elevators 241-250 navigate through borrowed slots, NOT their id; door-only rooms have
    none) so reachability follows real engine routing (e.g. the 211→212→107 climb) and does
    NOT add the phantom edges a door-only room's unused slot would imply."""
    defined = {i for i, l in enumerate(m["layouts"]) if l is not None}
    adj = {}
    for r in defined:
        adj.setdefault(r, set())
        quad = eff_conns(m, r)
        if quad is not None:
            for v in quad:
                if v != 255:
                    adj[r].add(v)
    for r, entries in m["doors"].items():
        adj.setdefault(r, set())
        for e in entries:
            adj[r].add(e[4])          # DEST_ROOM
    return adj


def eff_conns(m, room):
    """A room's effective N/S/W/E connection values, or None for rooms without
    walk-off exits. With connections_full active (WORLDBANK C2) every room has
    its own row (all-255 row -> None, mirroring the stock door-only case);
    otherwise the stock table is read through its borrowed slot."""
    full = m.get("connections_full")
    if full is not None:
        row = full[room] if 0 <= room < len(full) else None
        return None if row is None or row == [255] * 4 else row
    s = eff_conn_slot(room)
    conns = m["connections"]
    return conns[s] if s is not None and s < len(conns) else None


def asymmetric_edges(m):
    """One-way EFFECTIVE connection edges as [room, dir, dest]: a->b where b's effective
    reverse edge doesn't point back to a. Uses each room's effective slot, and skips
    door-only rooms, so the exit-table chain reads reciprocal and door-only slots don't
    produce phantom asymmetries (the 7 'one-way edges' in stock were all phantoms)."""
    OPP_I = {"N": 1, "S": 0, "W": 3, "E": 2}
    defined = {i for i, l in enumerate(m["layouts"]) if l is not None}
    out = []
    for r in sorted(defined):
        quad = eff_conns(m, r)
        if quad is None:
            continue
        for d, v in zip("NSWE", quad):
            if v == 255:
                continue
            dq = eff_conns(m, v)
            if dq is None or dq[OPP_I[d]] != r:
                out.append([r, d, v])
    return out


def cmd_graph(args):
    m = load_model()
    adj = build_graph(m)
    start = args.start
    seen, frontier = {start}, [start]
    while frontier:
        nxt = []
        for r in frontier:
            for v in adj.get(r, ()):
                if v not in seen:
                    seen.add(v); nxt.append(v)
        frontier = nxt
    defined = {i for i, l in enumerate(m["layouts"]) if l is not None}
    reach_open = sorted(r for r in seen if r < 122 and r in defined)
    reach_door = sorted(r for r in seen if 122 <= r < 240 and r in defined)
    reach_elev = sorted(r for r in seen if r >= 240)
    unreached = sorted(defined - seen)
    print("reachable from room %d : %d rooms" % (start, len(seen & defined)))
    print("  open grid (<122)     : %d" % len(reach_open))
    print("  door rooms (122-217) : %d" % len(reach_door))
    print("  elevators (>=240)    : %d" % len(reach_elev))
    print("unreachable defined rooms (%d): %s%s" %
          (len(unreached), unreached[:40], " ..." if len(unreached) > 40 else ""))
    # one-way EFFECTIVE connection edges (a->b but b doesn't point back)
    asym = asymmetric_edges(m)
    print("one-way/asymmetric connection edges: %d (doors/teleports expected)" % len(asym))


def cmd_conncheck(args):
    """Topology validator: report one-way (asymmetric) connections and rooms
    unreachable from the start, over the open-grid connection table."""
    m = load_model()
    OPP_I = {"N": 1, "S": 0, "W": 3, "E": 2}
    asym = [(r, d, v, (eff_conns(m, v) or [255, 255, 255, 255])[OPP_I[d]])
            for r, d, v in asymmetric_edges(m)]   # + the dest's mismatching reverse, for the printout
    # reachability
    adj = build_graph(m)
    seen, frontier = {121}, [121]
    while frontier:
        nxt = []
        for x in frontier:
            for y in adj.get(x, ()):
                if y not in seen:
                    seen.add(y); nxt.append(y)
        frontier = nxt
    defined = {i for i, l in enumerate(m["layouts"]) if l is not None}
    unreached = sorted(defined - seen)
    print("asymmetric (one-way) connections: %d" % len(asym))
    for r, d, v, back in asym[:40]:
        print("   room %3d %s-> %3d  but %3d's reverse -> %3d" % (r, d, v, v, back))
    print("unreachable-from-121 defined rooms: %d %s"
          % (len(unreached), unreached[:30]))


def cmd_export(args):
    m = load_model()
    export_json(m, args.o)
    print("exported %d rooms -> %s" % (len(m["labels"]), args.o))


def cmd_import(args):
    doc = json.loads(open(mgproj.path(args.file), encoding='utf-8').read())
    model = model_from_json(doc)
    write_model(model, dry=args.dry, regen=args.regen)
    print(("[dry] would write" if args.dry else "wrote") +
          " %d rooms / %d conns / %d tileset ids%s"
          % (len(model["labels"]), len(model["connections"]), len(model["tilesets"]),
             "  (regen: idxDoors/idxActorsRooms rebuilt)" if args.regen else ""))


def cmd_selftest(_):
    """Parse the sources, re-encode in memory, and verify every value matches."""
    m = load_model()
    # round-trip through JSON model too (catches export/import asymmetry)
    import io
    tmp = mgproj.repo_path("tools/_selftest_map.json")
    export_json(m, tmp)
    doc = json.loads(open(tmp, encoding='utf-8').read())
    m2 = model_from_json(doc)
    os.remove(tmp)

    ok = True

    def chk(name, a, b):
        nonlocal ok
        if a != b:
            ok = False
            print("  FAIL %s: differs" % name)
        else:
            print("  ok   %s" % name)

    chk("labels", m["labels"], m2["labels"])
    chk("layouts", m["layouts"], m2["layouts"])
    chk("connections", m["connections"], m2["connections"])
    chk("tilesets", m["tilesets"], m2["tilesets"])

    # verify packing inverts exactly (incl. trailing pad nibbles)
    packed = pack_tilesets(m["tilesets"], m["_tileset_pad"], m["_packed_tileset_len"])
    re_ids = []
    for b in packed:
        re_ids += [(b >> 4) & 0xF, b & 0xF]
    chk("tileset pack/unpack", m["tilesets"] + m["_tileset_pad"], re_ids)

    # verify write-back db blocks re-parse to identical values (dry, in memory)
    rl = _read(ROOMS_F)
    for lab, layout in zip(m["labels"], m["layouts"]):
        if layout is None:
            continue
        replace_block(rl, lab, fmt_db(lab, layout, perline=ROOM_W))
    chk("rooms re-parse", parse_rooms(rl), list(zip(m["labels"], m["layouts"])))

    # undefine_rooms: repoint a defined slot -> RoomUndefined, verify that slot
    # (and only that slot) parses to None afterwards, on an in-memory copy.
    ul = _read(ROOMS_F)
    victim = next(r for r, l in enumerate(m["layouts"]) if l is not None)
    changed = undefine_rooms([victim], lines=ul)
    up = parse_rooms(ul)
    chk("undefine_rooms changed set", changed, {victim})
    chk("undefine_rooms slot None", up[victim][1], None)
    chk("undefine_rooms others intact",
        [x[1] for j, x in enumerate(up) if j != victim],
        [x[1] for j, x in enumerate(parse_rooms(_read(ROOMS_F))) if j != victim])

    cl = _read(CONNS_F)
    flat = [b for quad in m["connections"] for b in quad]
    replace_block(cl, "RoomConnections", fmt_db("RoomConnections", flat, perline=4))
    chk("connections re-parse", parse_connections(cl), m["connections"])

    if m.get("connections_full") is not None:
        chk("connections_full", m["connections_full"], m2["connections_full"])
        fcl = _read(FULLCONNS_F)
        fflat = [b for quad in m["connections_full"] for b in quad]
        replace_block(fcl, "RoomConnsFull", fmt_db("RoomConnsFull", fflat, perline=4))
        reparsed = parse_flat(fcl, "RoomConnsFull")
        chk("connections_full re-parse",
            [reparsed[i:i + 4] for i in range(0, len(reparsed), 4)],
            m["connections_full"])

    dl = _read(DOORS_F)
    for lab in m["door_order"]:
        rid = label_room(lab)
        if rid is None:
            continue
        replace_label_block(dl, lab, door_block_lines(lab, m["doors"].get(rid, [])))
    replace_block(dl, "IdDoorsLogic", fmt_db("IdDoorsLogic", m["iddoorslogic"], perline=16))
    chk("doors re-parse", parse_doors(dl)[1], m["doors"])
    chk("iddoorslogic re-parse", parse_iddoorslogic(dl), m["iddoorslogic"])

    il = _read(ITEMS_F)
    replace_block(il, "idxRoomItemsIdx", fmt_db("idxRoomItemsIdx", m["item_idx"], perline=16))
    chk("item_idx re-parse", parse_item_idx(il), m["item_idx"])

    al = write_actors(_read(ACTORS_F), m, regen=False)
    chk("actors re-parse (slots)", parse_actors(al)[0], m["actor_slots"])
    chk("actors re-parse (blocks)", parse_actors(al)[1], m["actor_blocks"])

    # regeneration no-op: rebuilt tables must re-parse to the same data AND the
    # regenerated idxDoors/idxActorsRooms must list the same labels per slot.
    dlr = write_doors(_read(DOORS_F), m, regen=True)
    chk("doors regen re-parse", parse_doors(dlr)[1], m["doors"])
    orig_didx = parse_label_order(_read(DOORS_F), "idxDoors")
    chk("idxDoors regen order", parse_label_order(dlr, "idxDoors"), orig_didx)
    alr = write_actors(_read(ACTORS_F), m, regen=True)
    chk("actors regen re-parse (blocks)", parse_actors(alr)[1], m["actor_blocks"])
    orig_aidx = parse_label_order(_read(ACTORS_F), "idxActorsRooms")
    chk("idxActorsRooms regen order", parse_label_order(alr, "idxActorsRooms"), orig_aidx)

    kl = _read(CHKPT_F)
    flat = [b for pair in m["checkpoints"] for b in pair]
    replace_block(kl, "SaveStatRooms", fmt_db("SaveStatRooms", flat, perline=2))
    chk("checkpoints re-parse", parse_checkpoints(kl), m["checkpoints"])

    print("\nSELFTEST", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description="Metal Gear MSX map codec (NIGHTJAR)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info").set_defaults(fn=cmd_info)
    sp = sub.add_parser("show"); sp.add_argument("room", type=int); sp.set_defaults(fn=cmd_show)
    sp = sub.add_parser("graph"); sp.add_argument("--start", type=int, default=121); sp.set_defaults(fn=cmd_graph)
    sub.add_parser("conncheck").set_defaults(fn=cmd_conncheck)
    sp = sub.add_parser("export"); sp.add_argument("-o", default="tools/map.json"); sp.set_defaults(fn=cmd_export)
    sp = sub.add_parser("import"); sp.add_argument("--file", default="tools/map.json")
    sp.add_argument("--dry", action="store_true")
    sp.add_argument("--regen", action="store_true",
                    help="rebuild idxDoors/idxActorsRooms tables (allows adding "
                         "doors/actors to rooms that had none)")
    sp.set_defaults(fn=cmd_import)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    sp = sub.add_parser("genfullconns",
                        help="seed data/roomconnsfull.asm (251x4) from the stock table")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(fn=lambda a: print("wrote", gen_full_conns(force=a.force)))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
