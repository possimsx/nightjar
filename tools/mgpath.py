"""Enemy movement-route (path) codec for Metal Gear MSX / NIGHTJAR.

Models the patrol-route system from plain data tables, validated by a
byte-fidelity selftest (the repo convention). Reads `data/paths.asm`, which has
three layers:

  * Path_<room>_<n>  - one route: a count byte + payload. Two shapes:
        WALK  -> `count` (Y,X) point pairs  (payload = 2*count bytes)
        DIR   -> `count` look-direction bytes (payload = count bytes; used by
                 ID_SENTINEL, whose "path" is a list of facing directions).
      Shape is structural: 2*count vs count payload bytes (unambiguous for
      count>=1). A route walks point->point and LOOPS (UpdateActorPath).
  * Paths_<room>     - dw list of the Path_* used in that room (SHAREABLE: a
                       Path_* can appear in several lists / several times).
  * idxRoomPaths     - one dw per room -> that room's Paths_*. Length is
                       content-driven (stock 179; grows on demand up to 251 —
                       the engine has NO bounds check here, rooms without
                       path-followers simply never read their entry).

Coordinate order is (Y, X) with Y first, matching the actor/item codecs.

BINDING (see docs/PATH-EDITOR-PLAN.md): an actor is not told its route; the
engine assigns route #k to the k-th path-following actor in the room (guards +
cameras + sentinels), so route order is paired to actor order positionally.

Phase 1 = read model + byte-exact selftest (this file). Editing/UI land later.

CLI:  python tools/mgpath.py selftest
      python tools/mgpath.py dump [room]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PATHS_F = "data/paths.asm"
IDX_F = "data/pathindex.asm"     # idxRoomPaths (split out of paths.asm, plan D4:
                                 # PER WORLD under WORLDBANK; route blocks shared)
MAX_ROOMS = 251                                # room ids 0..250 (idxRoomPaths cap)
STOCK_N_ROOMS = 179                            # stock idxRoomPaths length

# Actor IDs the engine steps along a route from idxRoomPaths. This is the
# COMPLETE set: idxRoomPaths is read at exactly two places -- GetPathPoints
# (walk routes, Y/X points) and GetSentinelLookDirs (dir routes, facings) -- and
# tracing every init that reaches them gives:
#   GetPathPoints  <- InitGuardPath2 (slow/medium/fast guards via InitGuard;
#                     the lorry-exit guard via InitGuardLorry) and
#                     InitCamera3 (ID_CAMERA and ID_CAMERA_LASER, the latter
#                     falling in via InitCameraLaser2 -> InitCamera2)
#   GetSentinelLookDirs <- InitSentinel (ID_SENTINEL)
# NOT here (verified they never reach either reader): dogs (chase via
# GetDirToPlayer), alert guards (chase; e.g. room 127's ID_GUARD_ALERT),
# elevator guards (InitGuardElevat/Relieve use a hardcoded DestinationX),
# desert-security, shooters. Lorry-exit/camera-laser spawn or activate a moment
# after entry, so they aren't in view at first but DO consume a route.
# Sentinels consume DIR routes; the rest consume WALK routes.
PATH_FOLLOWERS = ("ID_GUARD_SLOW", "ID_GUARD_MEDIUM", "ID_GUARD_FAST",
                  "ID_CAMERA", "ID_CAMERA_LASER", "ID_SENTINEL",
                  "ID_GUARD_EXIT_LORRY")
DIR_FOLLOWERS = ("ID_SENTINEL",)               # route bytes are facings, not X/Y


def _read(path):
    """World-aware read via mgmap (D3): IDX_F follows the active world, the
    route blocks in PATHS_F are shared by all worlds."""
    import mgmap
    return mgmap.read_text(path)


def _write(path, text):
    import mgmap
    mgmap.write_text(path, text)


def _num(tok):
    """One asm byte literal: `40h`/`0A8h` = hex, bare `10`/`2` = decimal."""
    tok = tok.strip()
    if tok.endswith(("h", "H")):
        return int(tok[:-1], 16)
    return int(tok)


def _bytes_on_line(operand):
    """Comma-separated db operands (comment already stripped) -> [int, ...]."""
    return [_num(t) for t in operand.split(",") if t.strip()]


# ---- parsing ----------------------------------------------------------------
# Labels matched: original `Path_*`/`Paths_*` AND the editor-managed `PathEd_*`/
# `PathsEd_*` (a `PathEd_`-prefixed name is never matched as `Path_*` since the
# char after "Path" is "E", not "_"). The whole file is scanned so the managed
# region can sit anywhere (it is inserted just before idxRoomPaths).
_BLOCK_RE = r'^(Path(?:Ed)?_\w+):\s*db\s+(.*)$'
_LIST_RE = r'^(Paths(?:Ed)?_\w+):\s*dw\s+(\w+)'


def parse_path_blocks(src):
    """{Path*_label: [count, payload...]} in file order. A block is its `db` line
    plus every following `db` continuation up to the next label (blank/comment
    lines are skipped but do not end the block -- this preserves the stray
    trailing bytes after Path_031_02, which sit before the next label)."""
    blocks, cur = {}, None
    for ln in src.splitlines():
        code = ln.split(";", 1)[0].rstrip()
        m = re.match(_BLOCK_RE, code)
        if m:
            cur = m.group(1)
            blocks[cur] = _bytes_on_line(m.group(2))
            continue
        m2 = re.match(r'^\s+db\s+(.*)$', code)
        if m2 and cur is not None:
            blocks[cur] += _bytes_on_line(m2.group(1))
        elif re.match(r'^\w+:', code):              # any other label ends the block
            cur = None
    return blocks


def parse_path_lists(src):
    """{Paths*_label: [Path*_label, ...]} (order preserved; labels may repeat)."""
    lists, cur = {}, None
    for ln in src.splitlines():
        code = ln.split(";", 1)[0]
        m = re.match(_LIST_RE, code)
        if m:
            cur = m.group(1); lists[cur] = [m.group(2)]; continue
        if re.match(r'^idxRoomPaths:', code):       # the index, not a path-list
            cur = None; continue
        m2 = re.match(r'^\s+dw\s+(\w+)', code)
        if m2 and cur is not None:
            lists[cur].append(m2.group(1))
        elif re.match(r'^\w+:', code.strip()):
            cur = None
    return lists


def parse_idx(src):
    """idxRoomPaths -> [Paths_label per room] (room index = position)."""
    m = re.search(r'^idxRoomPaths:(.*)', src, re.S | re.M)
    out = []
    for ln in m.group(1).splitlines():
        code = ln.split(";", 1)[0]
        mm = re.search(r'\bdw\s+(\w+)', code)
        if mm:
            out.append(mm.group(1))
        elif re.match(r'^\w+:', code.strip()) and out:
            break
    return out


# ---- classification ---------------------------------------------------------
def classify(raw):
    """[count, payload...] -> dict describing the route. Shape is structural:
        WALK  payload == 2*count  -> points [(y,x)...]
        DIR   payload == count    -> dirs   [b...]
    Excess payload (only Path_031_02 in stock) is preserved as `tail` so the
    round-trip is byte-exact; a block that fits neither is 'irregular'."""
    cnt = raw[0] if raw else 0
    pl = raw[1:]
    if len(pl) == 2 * cnt:
        shape, pts, dirs, tail = "walk", pl, [], []
    elif len(pl) == cnt:
        shape, pts, dirs, tail = "dir", [], pl, []
    elif len(pl) > 2 * cnt:
        shape, pts, dirs, tail = "walk", pl[:2 * cnt], [], pl[2 * cnt:]
    elif len(pl) > cnt:
        shape, pts, dirs, tail = "dir", [], pl[:cnt], pl[cnt:]
    else:
        return {"count": cnt, "shape": "irregular", "points": [], "dirs": [],
                "tail": pl, "raw": list(raw)}
    points = [{"y": pts[i], "x": pts[i + 1]} for i in range(0, len(pts), 2)]
    return {"count": cnt, "shape": shape, "points": points, "dirs": list(dirs),
            "tail": list(tail), "raw": list(raw)}


def to_bytes(route):
    """Model route dict -> the byte list it serialises to (must equal raw)."""
    out = [route["count"]]
    for p in route["points"]:
        out += [p["y"] & 0xFF, p["x"] & 0xFF]
    out += [d & 0xFF for d in route["dirs"]]
    out += [b & 0xFF for b in route["tail"]]
    return out


# ---- actor followers (advisory join) ----------------------------------------
def _decode_pos(pos_mn, pos_tok):
    """Actor position -> (y, x). `dw WORD` = y low byte / x high byte; `db Y,X`."""
    if pos_mn == "dw":
        w = _num(pos_tok[0])
        return w & 0xFF, (w >> 8) & 0xFF
    return _num(pos_tok[0]), _num(pos_tok[1])


def room_followers():
    """{room: [{idx, id, y, x}]} of path-following actors, in actor-list order.
    Best-effort via mgmap; empty on any failure (codec never depends on it)."""
    try:
        import mgmap as M
        m = M.load_model()
        by = M.actors_by_room(m["actor_slots"], m["actor_blocks"])
    except Exception:
        return {}
    out = {}
    for room, entries in by.items():
        fol, k = [], 0
        for idtok, pos_mn, pos_tok in entries:
            if idtok in PATH_FOLLOWERS:
                y, x = _decode_pos(pos_mn, pos_tok)
                fol.append({"idx": k, "id": idtok, "y": y, "x": x}); k += 1
        if fol:
            out[room] = fol
    return out


# ---- model ------------------------------------------------------------------
def model():
    src = _read(PATHS_F)
    blocks = parse_path_blocks(src)
    lists = parse_path_lists(src)
    idx = parse_idx(_read(IDX_F))
    paths = {lab: classify(raw) for lab, raw in blocks.items()}
    followers = room_followers()
    rooms = []
    for r in range(len(idx)):
        lab = idx[r]
        plabels = lists.get(lab, [])
        nf, nr = len(followers.get(r, [])), len(plabels)
        # a route is "shared" if editing it in place would touch another room:
        # its LIST is used by >1 room (idxRoomPaths) OR its block is in >1 list.
        # (The editor forks the whole room on save, so editing is always safe;
        # the flag just tells the user the data is not private to this room.)
        list_shared = idx.count(lab) > 1
        rooms.append({
            "room": r, "label": lab, "managed": lab.startswith("PathsEd_"),
            "paths": [{"label": pl, "shared": list_shared or _shared(pl, lists),
                       **paths.get(pl, {})}
                      for pl in plabels],
            "followers": followers.get(r, []),
            # actor<->route pairing is positional: each path-follower needs a route
            # at its index. A shortfall means a late actor reuses the last route.
            "align_ok": nf <= nr,
            "align_msg": ("" if nf <= nr else
                          "%d path-followers but only %d route(s) — actor#%d+ reuse the last route"
                          % (nf, nr, nr)),
        })
    return {"rooms": rooms, "paths": paths, "path_lists": lists, "idx": idx}


def _shared(plabel, lists):
    """True if a Path_* is referenced more than once across all lists (editing
    it would affect several actors -- an editor must fork a private copy)."""
    n = sum(pl == plabel for labs in lists.values() for pl in labs)
    return n > 1


def room_paths(room):
    for r in model()["rooms"]:
        if r["room"] == room:
            return r
    return {"room": room, "label": None, "paths": [], "followers": []}


# ---- surgical edit (managed region + idxRoomPaths repoint) -------------------
# Editing a room forks ALL its routes into private PathEd_<room>_<n> blocks and a
# PathsEd_<room> list, then repoints idxRoomPaths[room] -> that list. This fully
# isolates the room (its Paths_/Path_ may be shared with others, which stay
# untouched). Re-saving a room overwrites just its managed blocks (idempotent).
ED_BEGIN = "; === EDITOR PATH BLOCKS (managed by tools/mgpath.py) ==="
ED_END = "; === END EDITOR PATH BLOCKS ==="


def _emit_route_lines(label, route):
    """ASM for one forked route block (count byte + payload). Walk = (Y,X) pairs;
    dir = single facing bytes (sentinel)."""
    if route.get("shape") == "dir":
        vals = [int(d) & 0xFF for d in route.get("dirs", [])]
        out = ["%-18sdb\t%d" % (label + ":", len(vals))]
        out += ["\t\t    db\t%d" % d for d in vals]
    else:
        pts = route.get("points", [])
        out = ["%-18sdb\t%d" % (label + ":", len(pts))]
        out += ["\t\t    db\t0%02Xh,0%02Xh" % (int(p["y"]) & 0xFF, int(p["x"]) & 0xFF)
                for p in pts]
    return out


def _emit_managed(managed):
    """managed = {room: {'orig': label|None, 'routes': [route,...]}} -> region text."""
    lines = [ED_BEGIN]
    for room in sorted(managed):
        info = managed[room]
        labels = []
        for i, r in enumerate(info["routes"], 1):
            lab = "PathEd_%03d_%02d" % (room, i)
            labels.append(lab)
            lines += _emit_route_lines(lab, r) + [""]
        listlab = "PathsEd_%03d" % room
        orig = info.get("orig")
        lines.append("%-18sdw\t%s%s" % (listlab + ":", labels[0],
                     "\t; orig=%s" % orig if orig else ""))
        lines += ["\t\t    dw\t%s" % l for l in labels[1:]]
        lines.append("")
    lines.append(ED_END)
    return "\n".join(lines)


def _parse_managed(src):
    """Read the managed region -> {room: {'orig': label|None, 'routes': [route]}}."""
    m = re.search(re.escape(ED_BEGIN) + r"(.*?)" + re.escape(ED_END), src, re.S)
    if not m:
        return {}
    region = m.group(1)
    blocks = parse_path_blocks(region)
    lists = parse_path_lists(region)
    out = {}
    for lab, plabels in lists.items():
        mm = re.match(r'PathsEd_(\d+)$', lab)
        if not mm:
            continue
        room = int(mm.group(1))
        om = re.search(re.escape(lab) + r":.*?;\s*orig=(\w+)", region)
        out[room] = {"orig": om.group(1) if om else None,
                     "routes": [classify(blocks[pl]) for pl in plabels if pl in blocks]}
    return out


def _write_managed_region(src, managed):
    """The managed (forked) route blocks live in data/paths.asm with the rest
    of the SHARED route pool - appended at EOF when first created (the index
    is a separate file since the D4 split)."""
    region = _emit_managed(managed) if managed else ""
    if ED_BEGIN in src:
        return re.sub(re.escape(ED_BEGIN) + r".*?" + re.escape(ED_END),
                      lambda _m: region, src, flags=re.S)
    if not region:
        return src
    return src.rstrip("\n") + "\n\n\n" + region + "\n"


def _write_idx(src, labels):
    """Regenerate the idxRoomPaths dw table (the index file's last section)."""
    rows = ["idxRoomPaths:\t    dw %s" % labels[0]] + \
           ["\t\t    dw %s" % l for l in labels[1:]]
    return re.sub(r'(?ms)^idxRoomPaths:.*\Z', "\n".join(rows) + "\n", src)


def set_room_paths(room, routes):
    """Editor write. `routes` = ordered list of {shape:'walk',points:[{y,x}]} or
    {shape:'dir',dirs:[..]} (position = actor pairing); None reverts the room to
    its original path-list. Forks into the managed region and repoints
    idxRoomPaths[room]. Idempotent."""
    room = int(room)
    src = _read(PATHS_F)
    idx_src = _read(IDX_F)
    idx = parse_idx(idx_src)
    if not 0 <= room < MAX_ROOMS:
        raise ValueError("room %d out of range 0..%d" % (room, MAX_ROOMS - 1))
    # Phase A growth (docs/LIMITS-PLAN.md): rooms beyond the current table get
    # an entry on demand. The filler repeats the last pointer (stock's own
    # style — see the trailing Paths_141 run); harmless, a room without
    # path-followers never reads its entry.
    while len(idx) <= room:
        idx.append(idx[-1])
    managed = _parse_managed(src)
    if routes is None:                                 # revert to stock
        info = managed.pop(room, None)
        if info and info.get("orig"):
            idx[room] = info["orig"]
    else:
        cur = idx[room]
        orig = managed.get(room, {}).get("orig") if cur.startswith("PathsEd_") else cur
        managed[room] = {"orig": orig, "routes": [dict(r) for r in routes]}
        idx[room] = "PathsEd_%03d" % room
    src = _write_managed_region(src, managed)
    _write(PATHS_F, src)
    _write(IDX_F, _write_idx(idx_src, idx))
    return room_paths(room)


# ---- selftest ---------------------------------------------------------------
def selftest():
    src = _read(PATHS_F)
    blocks = parse_path_blocks(src)
    lists = parse_path_lists(src)
    idx = parse_idx(_read(IDX_F))
    errs, warns = [], []

    if not STOCK_N_ROOMS <= len(idx) <= MAX_ROOMS:
        errs.append("idxRoomPaths has %d entries (expected %d..%d)"
                    % (len(idx), STOCK_N_ROOMS, MAX_ROOMS))

    # byte-exact round-trip: model(block) re-serialises to the parsed bytes
    walk = dirn = irregular = 0
    for lab, raw in blocks.items():
        route = classify(raw)
        if to_bytes(route) != raw:
            errs.append("%s round-trip mismatch: %s -> %s" % (lab, raw, to_bytes(route)))
        walk += route["shape"] == "walk"
        dirn += route["shape"] == "dir"
        if route["shape"] == "irregular":
            irregular += 1
            errs.append("%s irregular shape (count=%d payload=%d)"
                        % (lab, route["count"], len(raw) - 1))
        if route["tail"]:
            warns.append("%s has %d stray trailing byte(s) preserved as tail"
                         % (lab, len(route["tail"])))

    # referential integrity: every referenced label must be defined
    for lab in lists:
        for pl in lists[lab]:
            if pl not in blocks:
                errs.append("%s references undefined %s" % (lab, pl))
    for room, lab in enumerate(idx):
        if lab not in lists:
            errs.append("room %d -> undefined path-list %s" % (room, lab))

    # advisory cross-check: a DIR-shaped route should be consumed by a sentinel,
    # a WALK-shaped route by a walking follower. Mismatches only warn (they flag
    # spots where the reverse-engineered shape rule disagrees with actor data).
    followers = room_followers()
    for room, lab in enumerate(idx):
        fol = followers.get(room, [])
        for k, pl in enumerate(lists.get(lab, [])):
            sh = classify(blocks[pl])["shape"] if pl in blocks else None
            if k < len(fol) and sh in ("walk", "dir"):
                wants_dir = fol[k]["id"] in DIR_FOLLOWERS
                if sh == "dir" and not wants_dir:
                    warns.append("room %d route %d (%s) is DIR but actor #%d is %s"
                                 % (room, k, pl, k, fol[k]["id"]))
                if sh == "walk" and wants_dir:
                    warns.append("room %d route %d (%s) is WALK but actor #%d is %s"
                                 % (room, k, pl, k, fol[k]["id"]))
        if len(fol) > len(lists.get(lab, [])):
            warns.append("room %d has %d path-followers but only %d routes"
                         % (room, len(fol), len(lists.get(lab, []))))

    if errs:
        print("SELFTEST FAIL:")
        for e in errs[:40]:
            print("  -", e)
        return False
    print("SELFTEST PASS: %d rooms, %d routes (%d walk, %d dir), %d path-lists; "
          "round-trip byte-exact" % (len(idx), len(blocks), walk, dirn, len(lists)))
    if warns:
        print("  %d advisory warning(s):" % len(warns))
        for w in warns[:20]:
            print("    ~", w)
    return True


# ---- CLI --------------------------------------------------------------------
def _dump_room(r):
    print("room %3d (%s):" % (r["room"], r["label"] or "-"))
    for k, p in enumerate(r["paths"]):
        drives = ""
        if k < len(r["followers"]):
            f = r["followers"][k]
            drives = "  <- actor #%d %s @ (%d,%d)" % (f["idx"], f["id"], f["x"], f["y"])
        tag = "%s%s" % (p.get("shape", "?"), " shared" if p.get("shared") else "")
        print("  [%d] %-14s %-11s%s" % (k, p["label"], tag, drives))
        if p.get("shape") == "walk":
            pts = " ".join("(%d,%d)" % (pt["x"], pt["y"]) for pt in p["points"])
            print("       pts:", pts)
        elif p.get("shape") == "dir":
            print("       dirs:", " ".join(str(d) for d in p["dirs"]))
        if p.get("tail"):
            print("       tail:", " ".join("%02Xh" % b for b in p["tail"]))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "dump":
        m = model()
        if len(sys.argv) >= 3:
            _dump_room(room_paths(int(sys.argv[2])))
        else:
            for r in m["rooms"]:
                if r["paths"]:
                    _dump_room(r)
        return
    print(__doc__)


if __name__ == "__main__":
    main()
