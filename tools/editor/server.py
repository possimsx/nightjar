#!/usr/bin/env python3
"""
NIGHTJAR map editor - backend (Step 1: read-only viewer).

A zero-dependency local web server (Python stdlib http.server) that wraps the
existing toolchain so the map can be browsed in a browser exactly as the engine
renders it:

  mgmap    -> world model (rooms, connections, tilesets, doors, items, actors)
  mgrender -> real-pixel room PNGs (+ collision overlay) and metatile atlas
  mgmove   -> engine-accurate openings / walk-off-escape model

No game logic is reimplemented here; endpoints are thin adapters. The .asm files
stay the source of truth (loaded via mgmap.load_model()).

Run:
  python tools/editor/server.py            # serves http://127.0.0.1:8765
  python tools/editor/server.py --port N --open

Endpoints:
  GET /                              static/index.html
  GET /static/<file>                 static assets
  GET /api/map                       decoded world model (mgmap export doc)
  GET /api/validate[?start=121]      reachability + new walk-off escapes + asym
  GET /api/room/<id>/render.png      ?scale=2&collision=0   (mgrender)
  GET /api/room/<id>/actors.png      ?scale=2     transparent actor-sprite overlay
  GET /api/room/<id>/atlas.png       ?collision=0           metatile set atlas
  GET /api/room/<id>/openings        reachable exits + exit ranges (mgmove)
"""
import io, os, sys, json, argparse, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
STATIC = os.path.join(HERE, "static")
sys.path.insert(0, TOOLS)

import mgproj                            # noqa: E402  active-project resolver
import mgmap, mgrender, mgmove, mggfx    # noqa: E402  (after sys.path tweak)
import mgradio, mgtext                   # noqa: E402  radio calls + text codec
import mgprisoner                        # noqa: E402  prisoner rescue dialogue
import mgsprite                          # noqa: E402  actor/boss sprite overlay
import mgpath                            # noqa: E402  enemy patrol-route codec
import mghideguard                        # noqa: E402  entry-dependent guard culling
import mgcodecgate                        # noqa: E402  codec/progression gates (antenna zones)
import mgrespawn                           # noqa: E402  alert-reinforcement (respawn) table
import mgnorespawn                         # noqa: E402  no-respawn-on-alert room list


# ---------------------------------------------------------------------------
# data adapters (thin wrappers over the existing modules)
# ---------------------------------------------------------------------------
def _save_lines(file, lines):
    """Write `lines` back to a data file, preserving the original file's EOF
    newline state (mgmap._write always appends one; doors.asm has none, so using
    it there would create a spurious 1-line diff). World-aware (D3): per-world
    files are routed to the ACTIVE world's copy with labels re-suffixed."""
    mgmap.write_text(file, "\n".join(lines) + "\n", preserve_eof=True)


_REACH_CACHE = None


def _reach_file():
    return mgproj.state_file("reach")


def _on_project_switch():
    """Drop server-side caches whose content depends on the active project."""
    global _REACH_CACHE
    _REACH_CACHE = None
    _STOCK_LAYOUTS.clear()


mgproj.on_switch(_on_project_switch)


def _layout_hash(layout):
    import hashlib
    return hashlib.md5(bytes(layout)).hexdigest()[:12]


def room_reach(model):
    """{room: ['N','S',...]} of edges the player can actually walk to and cross,
    per mgmove.reachable_exits (the same pixel-walk model the openings panel uses).
    Cached to disk keyed by per-room layout hash: a full recompute is ~18s, so only
    rooms whose layout changed are recomputed on later calls."""
    global _REACH_CACHE
    if _REACH_CACHE is None:
        try:
            with open(_reach_file(), encoding="utf-8") as f:
                _REACH_CACHE = json.load(f)
        except Exception:
            _REACH_CACHE = {}
    conns, layouts = model["connections"], model["layouts"]
    out, dirty = {}, False
    for r in range(len(conns)):
        lay = layouts[r]
        if lay is None:
            continue
        h = _layout_hash(lay)
        ent = _REACH_CACHE.get(str(r))
        if ent and ent.get("h") == h:
            out[r] = ent["reach"]
        else:
            reach = sorted(mgmove.reachable_exits(r, conns[r], lay))
            _REACH_CACHE[str(r)] = {"h": h, "reach": reach}
            out[r] = reach
            dirty = True
    if dirty:
        try:
            with open(_reach_file(), "w", encoding="utf-8") as f:
                json.dump(_REACH_CACHE, f)
        except Exception:
            pass
    return out


def get_map_doc():
    """Decode the .asm sources to the mgmap export doc. Read-only: builds the doc
    in memory and does NOT write tools/map.json, so merely opening the editor
    never dirties it — only actual edits (which go through export_json) do.
    Enriches each non-placeholder room with its metatile-set id (MetaTileSetIDs
    nibble), which the codec export doesn't carry, plus `reach` (walkable exit
    edges) so the map view can tell real connections from stale ROM conn bytes."""
    model = mgmap.load_model()
    doc = mgmap.build_doc(model)
    reach = room_reach(model)
    for r in doc["rooms"]:
        if not r.get("placeholder"):
            r["metaset"] = mgrender.nibble("data/rooms.asm", "MetaTileSetIDs", r["id"])
            if r["id"] in reach:
                r["reach"] = reach[r["id"]]
    # Offer extended tilesets (gfx 8+) only when both the bank file exists AND the
    # build flag is on, so the dropdown never lists a tileset the ROM can't load.
    if get_extgfx()["enabled"] and os.path.exists(mgproj.path("BanksExtGfx.asm")):
        n = len(mgmap.parse_label_order(mgmap._read("BanksExtGfx.asm"), "idxTileSetsExt"))
        doc["tileset_names"] = list(doc["tileset_names"]) + ["Building (ext)" if i == 0
                               else "ext %d" % (8 + i) for i in range(n)]
    doc["extgfx"] = get_extgfx()["enabled"]
    doc["world"] = mgmap.current_world()               # D3: active world
    doc["world_count"] = mgmap.world_count()
    doc["project"] = mgproj.active_slug()              # multi-project
    doc["project_protected"] = mgproj.is_protected()
    return doc


_STOCK_LAYOUTS = {}                       # {world: {room: layout}} (D3)


def _stock_layouts():
    """Room layouts baseline for the walk-off-escape lint. Immutable for the life
    of the server, so it is built once per world (cleared on project switch).

    Base project: git-HEAD layouts (one `git show`). Derived projects live under
    projects/<slug>/ and are UNTRACKED, so they have no git HEAD to diff against
    -- we instead snapshot their own starting layouts once (see _project_baseline).
    Without a baseline _new_escapes treats every room as changed and simulates all
    122 (~40s) on every connection/layout edit."""
    w = mgmap.current_world()
    if w not in _STOCK_LAYOUTS:
        if mgproj.is_base():
            try:
                _STOCK_LAYOUTS[w] = mgrender._orig_layouts()
            except Exception:
                _STOCK_LAYOUTS[w] = {}
        else:
            _STOCK_LAYOUTS[w] = _project_baseline(w)
    return _STOCK_LAYOUTS[w]


def _project_baseline(world):
    """Baseline layouts ({room: [48 bytes]}) for an untracked project's world.
    Loads a persisted snapshot; the first time, captures the CURRENT on-disk
    layouts and writes it. Diffing against the project's OWN starting state (not
    the base game, which a blank template shares nothing with) means a pure
    connection edit changes no layout and short-circuits every room -> instant."""
    path = os.path.join(os.path.dirname(mgproj.state_file("map")),
                        "baseline_w%d.json" % world)
    try:
        with open(path, encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        pass
    layouts = mgmap.load_model()["layouts"]
    snap = {r: l for r, l in enumerate(layouts) if l is not None}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({str(r): l for r, l in snap.items()}, f)
    except OSError:
        pass
    return snap


def _new_escapes(model):
    """Walk-off escapes introduced by LAYOUT edits vs the git-HEAD baseline.

    The old code flood-filled all 122 rooms twice (current + baseline) on every
    save (~30s). But escapes are per-room and a room whose layout is unchanged
    from HEAD yields identical current/baseline escapes (connection changes hit
    both passes equally and cancel), so it can never contribute a NEW escape.
    We therefore only simulate the rooms that actually differ from baseline --
    typically a handful -- making this near-instant."""
    conns, layouts, doors = model["connections"], model["layouts"], model["doors"]
    stock = _stock_layouts()
    if not stock:              # no baseline -> "new vs stock" is undefined; never
        return []              # fall into the all-122-room simulation (~40s)
    out = []
    for r in range(122):
        if r >= len(conns):
            continue
        cur_l = layouts[r] if r < len(layouts) else None
        st_l = stock.get(r)
        if cur_l == st_l:                              # unchanged -> no new escape
            continue
        cur_e = mgmove.room_escapes(r, conns, cur_l, doors)
        st_e = mgmove.room_escapes(r, conns, st_l, doors)
        for d in sorted(cur_e - st_e):
            out.append([r, d])
    return out


def get_validation(start=121, model=None, include_paths=False):
    """Reachability flood-fill + the walk-off-escape regression vs stock. Pass a
    pre-loaded `model` to avoid re-parsing the .asm sources. `include_paths`
    adds the enemy-route alignment sweep (skipped on the per-save path since it
    re-parses paths.asm)."""
    m = model or mgmap.load_model()
    adj = mgmap.build_graph(m)
    seen, frontier = {start}, [start]
    while frontier:
        nxt = []
        for r in frontier:
            for v in adj.get(r, ()):
                if v not in seen:
                    seen.add(v); nxt.append(v)
        frontier = nxt
    defined = {i for i, l in enumerate(m["layouts"]) if l is not None}
    reachable = sorted(seen & defined)
    unreachable = sorted(defined - seen)

    new_escapes = _new_escapes(m)
    asym = mgmap.asymmetric_edges(m)            # one-way edges over EFFECTIVE connections
    return {
        "start": start,
        "defined_count": len(defined),
        "reachable_count": len(reachable),
        "reachable": reachable,
        "unreachable": unreachable,
        "new_escapes": new_escapes,
        "asymmetric_edges": asym,
        "path_align": path_alignment() if include_paths else [],
    }


def render_png(room, scale, collision, layout=None):
    img = mgrender.render_room(room, scale=scale, collision=collision, layout=layout)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


def actors_png(room, scale):
    """Transparent overlay (room*scale) with each actor's default sprite and each
    pickable item drawn at its position -- composited over render.png client-side."""
    objs = room_objects(room)["actors"] + mgsprite.room_items(room)
    img, _ = mgsprite.render_overlay(objs, scale=scale, pal_spriteset=mgsprite.room_spriteset(room))
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


def room_paths(room):
    """The room's enemy patrol routes + paired path-following actors, plus the
    24x32 solid-tile grid so the editor can flag waypoints landing in a wall."""
    m = mgpath.room_paths(room)
    try:
        m["solid"] = mgrender.room_solid_grid(room)     # [24][32] of 0/1
    except Exception:
        m["solid"] = None
    return m


def set_room_paths_api(room, routes):
    """Editor write for enemy patrol routes (None reverts the room to stock)."""
    return mgpath.set_room_paths(room, routes)


def path_alignment():
    """Rooms where path-following actors outnumber the routes the engine will
    read for them. Actor<->route binding is positional (route k drives the k-th
    path-follower), so a late follower with no route of its own silently reuses
    the last route. The per-room panel already warns while you edit that room;
    this is the global sweep, so an actor add/remove is caught even from another
    room. Best-effort: an empty list on any parse failure (never blocks saves)."""
    try:
        return [{"room": r["room"], "followers": len(r["followers"]),
                 "routes": len(r["paths"]), "msg": r["align_msg"]}
                for r in mgpath.model()["rooms"] if not r["align_ok"]]
    except Exception:
        return []


def room_hideguards(room):
    """The room's entry-dependent guard-cull rules, joined to its actors."""
    return mghideguard.room_model(room)


def set_room_hideguards(room, rules):
    """Editor write: replace the room's cull rules (list of dicts; [] clears)."""
    return mghideguard.set_room_rules(room, rules)


def room_zone(room):
    """The room's building/area zone (idxMapZones nibble) — read-only identity.
    Antenna & bug-alarm requirements are decoupled per-room flags (edited via
    POST /api/room/<id>/{antenna,bugalarm}). Also carries the RoomsMusic
    area-music track + isolated-room flag (edited via POST /api/room/<id>/music),
    a separate table from idxMapZones."""
    z = mgcodecgate.zone_model(room)
    mus = mgradio.room_music(room) or {}
    z["music"] = mus.get("music", 0)
    z["isolated"] = mus.get("isolated", False)
    z["musicnames"] = mgradio.MUSIC_NAMES
    return z


def set_room_antenna(room, on):
    """Editor write: set whether the room needs the antenna (idxAntennaRooms bit),
    independent of its music zone. Rebuild to apply."""
    return mgcodecgate.set_antenna_room(room, bool(on))


def set_room_bug_alarm(room, on):
    """Editor write: set whether carrying the enemy bug (TransmiTaken) trips the
    alarm in this room (idxBugAlarmRooms bit), independent of its music zone."""
    return mgcodecgate.set_bug_alarm_room(room, bool(on))


# Curated weapon names for the item-gate picker.
_GATE_WEAPONS = {1: "Hand Gun", 2: "Sub Machine Gun", 3: "Grenade Launcher",
                 4: "Rocket Launcher", 5: "Plastic Bomb", 6: "Land Mine", 7: "Missile"}


def codec_gates():
    """The three flag-gate tables (text->flag, item->flag, door-type->flag) plus
    the labels the editor needs. Editing writes ASM, so a rebuild is required.
    Flag display names come from mgcodecgate (stock defaults + project overrides)."""
    m = mgcodecgate.gates_model()
    m["weapon_names"] = _GATE_WEAPONS
    m["flag_desc"] = m["flag_labels"]     # already merged (override else default)
    return m


def set_codec_gates(body):
    """Editor write: rewrite whichever gate tables are present in `body`
    (`texts` / `items` / `doors`). Surgical per-table; rebuild to apply."""
    if "texts" in body:
        mgcodecgate.set_text_gates(body["texts"])
    if "items" in body:
        mgcodecgate.set_item_gates(body["items"])
    if "doors" in body:
        mgcodecgate.set_door_gates(body["doors"])
    return {"ok": True, "gates": codec_gates(), "rebuild": True}


def get_labels():
    """Editable cosmetic display names for story flags."""
    return mgcodecgate.labels_model()


def set_label(body):
    """Rename a flag (cosmetic; empty label reverts to the stock default).
    No rebuild needed — labels never reach the ROM."""
    kind = body.get("kind")
    if kind == "flag":
        mgcodecgate.set_flag_label(body["key"], body.get("label", ""))
    else:
        return {"ok": False, "error": "kind must be 'flag'"}
    return {"ok": True, "labels": mgcodecgate.labels_model()}


# route colours cycle per path index; matches the overlay legend the panel shows.
PATH_COLORS = [(70, 198, 208), (240, 142, 60), (150, 210, 90), (220, 110, 200),
               (250, 210, 70), (120, 150, 255), (240, 96, 110), (150, 235, 200)]
# sentinel look-direction byte (0-based, per GetSentinelLookDirs) -> unit (dx,dy).
DIR_VEC = {0: (0, -1), 1: (0, 1), 2: (-1, 0), 3: (1, 0)}


def paths_png(room, scale):
    """Transparent overlay drawing each WALK route as a numbered, colour-keyed
    closed polyline (routes loop in-engine) and each DIR (sentinel) route as
    facing arrows at its paired actor. Composited over render.png client-side.

    Only the routes a path-following actor actually CONSUMES are drawn (route k
    is used iff actor k exists). idxRoomPaths is a dense per-room table, so most
    actorless rooms point at a shared/filler list the engine never reads for
    them -- drawing those would be misleading 'ghost' routes."""
    rp = mgpath.room_paths(room)
    fol = rp.get("followers", [])
    img = Image.new("RGBA", (256 * scale, 192 * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(1, scale)
    rad = 3 * scale
    for k, p in enumerate(rp.get("paths", [])[:len(fol)]):
        col = PATH_COLORS[k % len(PATH_COLORS)]
        if p.get("shape") == "walk" and p.get("points"):
            pts = [(pt["x"] * scale, pt["y"] * scale) for pt in p["points"]]
            if len(pts) >= 2:
                d.line(pts + [pts[0]], fill=col + (235,), width=lw)   # closed loop
            for j, (x, y) in enumerate(pts):
                r = rad + (scale if j == 0 else 0)                    # start node bigger
                d.ellipse([x - r, y - r, x + r, y + r],
                          fill=col + (255,), outline=(0, 0, 0, 220))
                d.text((x + r + 1, y - r - 1), str(j), fill=col + (255,))
        elif p.get("shape") == "dir" and k < len(fol):
            cx, cy = fol[k]["x"] * scale, fol[k]["y"] * scale
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                      fill=col + (255,), outline=(0, 0, 0, 220))
            L = 9 * scale
            for facing in p.get("dirs", []):
                vx, vy = DIR_VEC.get(facing, (0, 0))
                d.line([(cx, cy), (cx + vx * L, cy + vy * L)], fill=col + (235,), width=lw)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


from PIL import Image, ImageDraw                     # noqa: E402


GRID_COLORS = {0: None, 1: (48, 54, 66), 2: (96, 104, 126), 3: (150, 162, 196)}


def _grid(img, cell, level=2):
    """Draw 1px separator lines every `cell` px. level 0=off, 1=faint, 2=medium, 3=strong."""
    color = GRID_COLORS.get(int(level), GRID_COLORS[2])
    if color is None or cell <= 0:
        return img
    d = ImageDraw.Draw(img)
    for x in range(0, img.width + 1, cell):
        d.line([(x, 0), (x, img.height)], fill=color)
    for y in range(0, img.height + 1, cell):
        d.line([(0, y), (img.width, y)], fill=color)
    return img


def metatile_sheet(room, cols=16, scale=2, collision=False, grid=2):
    """A padding-free grid of every metatile in `room`'s set (cell = 32px*scale),
    so the front-end can slice it as a brush palette and composite rooms client-
    side. Metatile id = index+1 (engine ids are 1-based). Optional red collision
    tint flags solid (wall) metatile tiles."""
    _, mdefs, tiles, pal = mgrender.load_room_assets(room)
    coll = mgrender.tileset_collision(
        mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)) if collision else {}
    n = len(mdefs) // 16
    cell = mgrender.MT * 8                          # 32px
    rows = max(1, (n + cols - 1) // cols)
    img = Image.new("RGB", (cols * cell, rows * cell), (0, 0, 0))
    px = img.load()
    for m in range(n):
        gx, gy = (m % cols) * cell, (m // cols) * cell
        mgrender.draw_metatile(px, gx, gy, m + 1, mdefs, tiles, pal)
        if collision:
            mt = mdefs[16 * m:16 * m + 16]
            for ty in range(mgrender.MT):
                for tx in range(mgrender.MT):
                    if coll.get(mt[ty * mgrender.MT + tx], 0):
                        for r in range(8):
                            for c in range(8):
                                x, y = gx + tx * 8 + c, gy + ty * 8 + r
                                R0, G0, B0 = px[x, y]
                                px[x, y] = (min(255, R0 + 90), G0 // 2, B0 // 2)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    _grid(img, cell * scale, grid)
    buf = io.BytesIO(); img.save(buf, "PNG")
    return buf.getvalue(), n, cols, cell * scale


def metatile_info(room, cols=16, scale=2):
    _, mdefs, _, _ = mgrender.load_room_assets(room)
    n = len(mdefs) // 16
    m = mgmap.load_model()
    layout = m["layouts"][room]
    grid = None if layout is None else [layout[r * 8:(r + 1) * 8] for r in range(6)]
    return {"room": room, "count": n, "cols": cols, "cell": mgrender.MT * 8 * scale,
            "metaset": mgrender.nibble("data/rooms.asm", "MetaTileSetIDs", room),
            "gfxset": mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room),
            "grid": grid}


def save_grid(room, grid):
    """Persist an 8x6 metatile grid for `room` SURGICALLY: rewrite only that
    room's RoomNNN block in data/rooms.asm, leaving every other byte of the file
    untouched (no whole-file reformat churn). Then refresh tools/map.json and
    re-validate. The ROM bytes are unaffected by db formatting."""
    if len(grid) != 6 or any(len(r) != 8 for r in grid):
        raise ValueError("grid must be 6 rows x 8 cols")
    flat = [int(v) & 0xFF for row in grid for v in row]
    rl = mgmap._read(mgmap.ROOMS_F)
    order = mgmap.parse_label_order(rl, "idxRooms")
    if room >= len(order):
        raise ValueError("room %d out of range (max %d)" % (room, len(order) - 1))
    lab = order[room]
    mgmap.replace_block(rl, lab, mgmap.fmt_db(lab, flat, perline=mgmap.ROOM_W))
    _save_lines(mgmap.ROOMS_F, rl)
    model = mgmap.load_model()
    mgmap.export_json(model, mgproj.state_file("map"))
    v = get_validation(121, model)
    return {"ok": True, "room": room,
            "new_escapes": v["new_escapes"], "reachable_count": v["reachable_count"],
            "defined_count": v["defined_count"]}


def atlas_png(room, collision):
    img = mgrender.render_atlas(room, collision=collision)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


import re                                            # noqa: E402

DIRIDX = {"N": 0, "S": 1, "W": 2, "E": 3}
OPP = {"N": "S", "S": "N", "W": "E", "E": "W"}
_NUMTOK = re.compile(r'[0-9A-Fa-f]+h|\d+')


def _conn_line_indices(lines):
    """Absolute line indices of each RoomConnections `db` row, in room order."""
    s, e = mgmap.find_block(lines, "RoomConnections")
    return [i for i in range(s, e) if "db" in lines[i].split(";", 1)[0]]


def eff_conn_slot(room):
    """The RoomConnections slot a room navigates through (canonical impl in mgmap;
    see docs/SPECIAL-ROOMS.md §1b)."""
    return mgmap.eff_conn_slot(int(room))


def _edit_conn_line(line, dir_idx, value):
    """Splice `value` into the dir_idx-th of the 4 numeric values on a conn line,
    preserving the line's exact prefix, separators, column width, radix, and
    trailing `; room` comment (no reformat -> 1-line diff)."""
    ci = line.find(";")
    head, tail = (line, "") if ci < 0 else (line[:ci], line[ci:])
    m = re.search(r'\bdb\b', head)
    pre, operand = head[:m.end()], head[m.end():]
    toks = list(_NUMTOK.finditer(operand))
    if len(toks) < 4:
        raise ValueError("connection line has <4 values: %r" % line)
    t = toks[dir_idx]
    old = t.group(0)
    if old.endswith("h"):                          # preserve hex radix if used
        nv = "%Xh" % value
        if nv[0].isalpha():
            nv = "0" + nv
    else:
        nv = str(value)
    return pre + operand[:t.start()] + nv + operand[t.start() + len(old):] + tail


def set_connection(room, direction, dest, reciprocal=True):
    """Set room's `direction` neighbor to `dest` (255/None = wall) by a SURGICAL
    in-place edit of just that room's connection line (and, if reciprocal and
    dest is a real room, dest's opposite edge). No whole-block reformat -> the
    file's original decimal/comments/alignment are preserved. Refreshes map.json
    + re-validates."""
    direction = direction.upper()
    if direction not in DIRIDX:
        raise ValueError("bad direction %r" % direction)
    full_active = mgmap.load_model().get("connections_full") is not None
    cl = mgmap._read(mgmap.CONNS_F)
    idxs = _conn_line_indices(cl)
    slot = eff_conn_slot(room)                          # exit-table/elevator rooms edit their borrowed slot
    if slot is None and not full_active:
        raise ValueError("room %d is door-only / has no connection slot (navigated by doors)" % room)
    dest = 255 if dest in (None, -1, 255, "255") else int(dest) & 0xFF
    # stock table: keep it in sync wherever the edit is representable, so
    # flag-off (128KB) builds keep matching the authored world. WORLD 0 ONLY:
    # the stock table is shared and belongs to world 0's flag-off build;
    # worlds >0 exist only flag-on and navigate via their own RoomConnsFull.
    touched = [room]
    if mgmap.current_world() == 0:
        if slot is not None and slot < len(idxs):
            cl[idxs[slot]] = _edit_conn_line(cl[idxs[slot]], DIRIDX[direction], dest)
        if reciprocal and dest != 255:
            dslot = eff_conn_slot(dest)                 # write the reverse edge into dest's effective slot
            if dslot is not None and dslot < len(idxs):
                cl[idxs[dslot]] = _edit_conn_line(cl[idxs[dslot]], DIRIDX[OPP[direction]], room)
        _save_lines(mgmap.CONNS_F, cl)
    if reciprocal and dest != 255:
        touched.append(dest)
    # full per-room table (canonical when present — plan C2): every room,
    # including door rooms, owns its row; surgical value splice
    if full_active:
        _set_packed_byte(mgmap.FULLCONNS_F, "RoomConnsFull",
                         room * 4 + DIRIDX[direction], dest)
        if reciprocal and dest != 255:
            _set_packed_byte(mgmap.FULLCONNS_F, "RoomConnsFull",
                             dest * 4 + DIRIDX[OPP[direction]], room)
    model = mgmap.load_model()
    mgmap.export_json(model, mgproj.state_file("map"))
    eff = lambda r: mgmap.eff_conns(model, r) or [255] * 4
    v = get_validation(121, model)
    return {"ok": True, "touched": {str(r): dict(zip("NSWE", eff(r))) for r in touched},
            "new_escapes": v["new_escapes"], "reachable_count": v["reachable_count"],
            "defined_count": v["defined_count"], "unreachable": v["unreachable"],
            "asymmetric_edges": v["asymmetric_edges"]}


# stock gfx-tileset <-> metatile-set pairings (see map-codec-tool memory)
STOCK_META = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 1, 7: 1}


def _set_packed_byte(file, label, byte_index, new_byte):
    """Surgically splice `new_byte` into the byte_index-th value of a packed db
    block, preserving prefix/separators/radix/width/comment (1-line diff)."""
    lines = mgmap._read(file)
    s, e = mgmap.find_block(lines, label)
    idx = 0
    for i in range(s, e):
        ci = lines[i].find(";")
        head, tail = (lines[i], "") if ci < 0 else (lines[i][:ci], lines[i][ci:])
        m = re.search(r'\bdb\b', head)
        if not m:
            continue
        pre, operand = head[:m.end()], head[m.end():]
        toks = list(_NUMTOK.finditer(operand))
        if idx + len(toks) <= byte_index:
            idx += len(toks); continue
        t = toks[byte_index - idx]
        old = t.group(0)
        if old.endswith("h"):
            nv = "%Xh" % new_byte
            if nv[0].isalpha():
                nv = "0" + nv
        else:
            nv = str(new_byte)
        lines[i] = pre + operand[:t.start()] + nv + operand[t.start() + len(old):] + tail
        _save_lines(file, lines)
        return
    raise ValueError("byte_index %d out of range for %s" % (byte_index, label))


def _set_nibble(file, label, room, val):
    """Set one room's nibble in a packed-nibble table (even room=high nibble),
    preserving the other nibble (incl. the trailing pad nibble)."""
    val = int(val) & 0xF
    cur = mgmap.parse_flat(mgmap._read(file), label)[room // 2]
    nb = (val << 4) | (cur & 0x0F) if room % 2 == 0 else (cur & 0xF0) | val
    _set_packed_byte(file, label, room // 2, nb)


def _splice_block_bytes(file, label, start, values):
    """Splice a contiguous run of `values` starting at byte index `start` across a
    db block, preserving each token's radix/width/separators (right-to-left per
    line). EOF-preserving write."""
    lines = mgmap._read(file)
    s, e = mgmap.find_block(lines, label)
    idx = 0; end = start + len(values)
    for i in range(s, e):
        ci = lines[i].find(";")
        head, tail = (lines[i], "") if ci < 0 else (lines[i][:ci], lines[i][ci:])
        m = re.search(r'\bdb\b', head)
        if not m:
            continue
        pre, operand = head[:m.end()], head[m.end():]
        toks = list(_NUMTOK.finditer(operand)); changed = False
        for ti in range(len(toks) - 1, -1, -1):
            gi = idx + ti
            if start <= gi < end:
                t = toks[ti]; old = t.group(0)
                nv = _fmt_radix(old, values[gi - start])
                operand = operand[:t.start()] + nv + operand[t.start() + len(old):]; changed = True
        if changed:
            lines[i] = pre + operand + tail
        idx += len(toks)
        if idx >= end:
            break
    _save_lines(file, lines)


def tile_atlas_png(room, scale=3, collision=False, grid=2):
    """16x16 grid of the room's gfx-tileset 8x8 tiles (tile id = row*16+col;
    absent tiles black, solid tiles red-tinted). Lets the front-end pick tiles by
    id for the metatile editor / browse the tile vocabulary."""
    _, _, tiles, pal = mgrender.load_room_assets(room)
    gid = mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    coll = mgrender.tileset_collision(gid) if collision else {}
    base = Image.new("RGB", (128, 128), (0, 0, 0)); bpx = base.load()
    for t in range(256):
        tile = tiles.get(t); ox, oy = (t % 16) * 8, (t // 16) * 8
        if tile:
            for r in range(8):
                for c in range(8):
                    bpx[ox + c, oy + r] = pal[tile[r][c] & 15]
        if collision and coll.get(t, 0):
            for r in range(8):
                for c in range(8):
                    R, G, B = bpx[ox + c, oy + r]; bpx[ox + c, oy + r] = (min(255, R + 90), G // 2, B // 2)
    img = base.resize((128 * scale, 128 * scale), Image.NEAREST)
    _grid(img, 8 * scale, grid)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


def _metaset_for_room(room):
    rl = mgmap._read(mgmap.ROOMS_F)
    msid = mgrender.nibble("data/rooms.asm", "MetaTileSetIDs", room)
    return rl, msid, mgmap.parse_label_order(rl, "idxMetatileSet")[msid - 1]


def metatile_def(room, m):
    """The 16 tile bytes of metatile `m` (1-based) of the room's metatile set,
    plus set id/label/count and how many rooms share that set."""
    rl, msid, setlabel = _metaset_for_room(room)
    mdefs = mgmap.parse_flat(mgmap._read("data/metatiles.asm"), setlabel)
    count = len(mdefs) // 16
    if not 1 <= m <= count:
        raise ValueError("metatile %d out of range (1..%d)" % (m, count))
    nibs = mgmap.parse_flat(rl, "MetaTileSetIDs"); allids = []
    for b in nibs:
        allids += [(b >> 4) & 0xF, b & 0xF]
    shared = sum(1 for x in allids[:251] if x == msid)
    return {"room": room, "metatile": m, "set": msid, "set_label": setlabel,
            "count": count, "cells": mdefs[16 * (m - 1):16 * (m - 1) + 16], "shared_rooms": shared}


def add_metatile(room, fill=0):
    """Append a new (blank) metatile to the room's metatile set (one 16-byte db
    line in MetatilesN). The set is shared, so this grows the palette for every
    room using it. Bank space is limited (~5 metatiles of BanksDEF headroom) —
    the build will error if the bank overflows."""
    rl, msid, setlabel = _metaset_for_room(room)
    lines = mgmap._read("data/metatiles.asm")
    s, e = mgmap.find_block(lines, setlabel)
    lines.insert(e, "\t\t    db\t" + ",\t".join(mggfx._tok(int(fill) & 0xFF) for _ in range(16)))
    _save_lines("data/metatiles.asm", lines)
    cnt = metaset_count(msid)
    return {"ok": True, "metatile": cnt, "count": cnt, "set": msid}


def set_metatile(room, m, cells):
    """Write the 16 tile bytes of metatile `m` to the room's metatile set block
    (surgical run-splice). Affects EVERY room using that set."""
    if len(cells) != 16:
        raise ValueError("metatile needs 16 cells")
    _, msid, setlabel = _metaset_for_room(room)
    _splice_block_bytes("data/metatiles.asm", setlabel, 16 * (m - 1), [int(c) & 0xFF for c in cells])
    return {**metatile_def(room, m), "ok": True}


def _decode_tile_idx(d):
    """24 bytes (3bpp: 8 rows x 3 planes, plane0=low bit) -> 8x8 of palette index 0-7."""
    g = []
    for r in range(8):
        p0, p1, p2 = d[r * 3], d[r * 3 + 1], d[r * 3 + 2]
        g.append([((p0 >> (7 - c)) & 1) | (((p1 >> (7 - c)) & 1) << 1) | (((p2 >> (7 - c)) & 1) << 2)
                  for c in range(8)])
    return g


def _encode_tile_idx(g):
    out = bytearray()
    for r in range(8):
        planes = [0, 0, 0]
        for c in range(8):
            idx = g[r][c] & 7
            for p in range(3):
                if (idx >> p) & 1:
                    planes[p] |= (1 << (7 - c))
        out += bytes(planes)
    return bytes(out)


def _tile_source(room, tile):
    """(gfx_label, byte_offset, editable) for `tile` in room's gfx tileset. Editable
    only when it comes from a NORMAL gfx block (not a flip/crate/powswitch tile)."""
    gid = mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    tslabel, tsfile = mgrender.resolve_tileset(gid)
    toks = mgrender.tileset_config_tokens(tslabel, tsfile)
    i = blocks = 0
    prev_cnt = prev_gfx = None
    while blocks < 3 and i < len(toks):
        flags = toks[i][1]
        if flags & 0x80:
            break
        if flags & 0x40:                                   # flip block (mirror of prev gfx)
            dest, cnt, gfx, flip = toks[i + 1][1], prev_cnt, prev_gfx, True
            i += 2
        else:
            cnt, dest, gfx = toks[i + 1][1], toks[i + 2][1], toks[i + 3][1]
            prev_cnt, prev_gfx, flip = cnt, gfx, False
            i += 4
        if dest <= tile < dest + cnt:
            return (gfx, (tile - dest) * 24, not flip)
        blocks += 1
    return (None, 0, False)


def _splice_gfx_bytes(file, label, start, values):
    """Splice a run of bytes into a gfx db block at byte index `start`, spanning
    internal blank lines (some gfx blocks have them), stopping at the next label."""
    lines = mgmap._read(file)
    si = next((i for i, ln in enumerate(lines)
               if re.match(r'^%s:\s*db' % re.escape(label), ln.split(";", 1)[0])), None)
    if si is None:
        raise ValueError("gfx label %s not found" % label)
    idx, end, i = 0, start + len(values), si
    while i < len(lines):
        code = lines[i].split(";", 1)[0]
        if i > si and re.match(r'^\w+:', code):
            break
        m = re.search(r'\bdb\b', code)
        if m:
            ci = lines[i].find(";")
            head, tail = (lines[i], "") if ci < 0 else (lines[i][:ci], lines[i][ci:])
            pre, operand = head[:m.end()], head[m.end():]
            toks = list(_NUMTOK.finditer(operand)); changed = False
            for ti in range(len(toks) - 1, -1, -1):
                gi = idx + ti
                if start <= gi < end:
                    t = toks[ti]; old = t.group(0)
                    operand = operand[:t.start()] + _fmt_radix(old, values[gi - start]) + operand[t.start() + len(old):]
                    changed = True
            if changed:
                lines[i] = pre + operand + tail
            idx += len(toks)
            if idx >= end:
                break
        i += 1
    _save_lines(file, lines)


def get_tile(room, tile):
    """An editable tile's 8x8 palette-index pixels + the 8 RGB swatches (the tileset
    colortab through the room palette). Non-normal tiles return editable:false."""
    _, mdefs, tiles, pal = mgrender.load_room_assets(room)
    colors = mggfx.parse_block("Banks0123.asm", "ColorsTileset")[:8]
    swatches = [list(pal[colors[i] & 15]) for i in range(8)]
    gfx, off, editable = _tile_source(room, tile)
    if gfx is not None:
        data = mggfx.parse_block(mgrender.find_gfx_file(gfx), gfx)
        grid = _decode_tile_idx(data[off:off + 24])
    else:                                                  # display-only (flip/crate/powswitch): invert colortab
        inv = {}
        for i, c in enumerate(colors):
            inv.setdefault(c & 15, i)
        vg = tiles.get(tile) or [[0] * 8 for _ in range(8)]
        grid = [[inv.get(vg[r][c] & 15, 0) for c in range(8)] for r in range(8)]
    gid = mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    return {"room": room, "tile": tile, "editable": bool(editable and gfx is not None),
            "pixels": grid, "swatches": swatches, "gfx": gfx,
            "gid": gid, "solid": bool(mgrender.tileset_collision(gid).get(tile, 0))}


def set_tile(room, tile, pixels):
    """Write an edited tile's pixels back to its Gfx* block (3bpp). Affects EVERY
    room/metatile using that tile (gfx is shared per tileset)."""
    gfx, off, editable = _tile_source(room, tile)
    if not (editable and gfx is not None):
        raise ValueError("tile 0x%02X is not editable (flip/crate/shared object tile)" % tile)
    if len(pixels) != 8 or any(len(r) != 8 for r in pixels):
        raise ValueError("pixels must be 8x8")
    _splice_gfx_bytes(mgrender.find_gfx_file(gfx), gfx, off, list(_encode_tile_idx(pixels)))
    return {"ok": True, "tile": tile, "gfx": gfx}


def set_tile_collision(room, tile, solid):
    """Set/clear tile number `tile`'s solid (wall) bit in this room's tileset
    collision bitmap (CollTiles*). Per-tile and per-tileset, so it affects EVERY
    room using that tileset. Surgical single-byte splice; rebuild to apply."""
    gid = mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    file, label = mgrender.collision_source(gid)
    if not label:
        raise ValueError("no collision bitmap for tileset %d" % gid)
    bits = list(mgmap.parse_flat(mgmap._read(file), label))
    byte_i, mask = tile >> 3, 1 << (7 - (tile & 7))
    if byte_i >= len(bits):
        raise ValueError("tile 0x%02X out of range for the collision bitmap" % tile)
    newb = (bits[byte_i] | mask) if solid else (bits[byte_i] & ~mask)
    if newb != bits[byte_i]:
        _splice_gfx_bytes(file, label, byte_i, [newb])
    return {"ok": True, "tile": tile, "gid": gid, "solid": bool(solid)}


# ---- room-editor "stamps" (editor-only reusable metatile structures) --------
# A stamp is {"n": name, "g": [[metatile_id,...],...]} — a small rectangle of
# metatile ids stamped into a room. Editor-only (no ROM impact); stored per
# project as editor state, seeded with the canonical Building structures.
DEFAULT_STAMPS = [
    {"n": "Room frame", "g": [[0x08, 0x09, 0x0A, 0x0A, 0x0A, 0x0A, 0x09, 0x0B],
                              [0x17, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x0E],
                              [0x19, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x14],
                              [0x19, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x14],
                              [0x19, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x14],
                              [0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0F]]},
    {"n": "TL corner", "g": [[0x08, 0x09], [0x17, 0x1F]]},
    {"n": "TR corner", "g": [[0x09, 0x0B], [0x1F, 0x0E]]},
    {"n": "Top wall", "g": [[0x0A], [0x1F]]},
    {"n": "Left wall", "g": [[0x19]]},
    {"n": "Right wall", "g": [[0x14]]},
    {"n": "Bottom wall", "g": [[0x0D]]},
    {"n": "BL corner", "g": [[0x0C]]},
    {"n": "BR corner", "g": [[0x0F]]},
    {"n": "Floor", "g": [[0x07]]},
    {"n": "Opening", "g": [[0xB3]]},
]


def _valid_stamp(s):
    if not isinstance(s, dict) or not isinstance(s.get("g"), list) or not s["g"]:
        return False
    g = s["g"]
    return (all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1)                 # rectangular


def load_stamps():
    """The active project's room-editor stamps (editor-only). Seeded with the
    canonical defaults when no stamps file exists yet."""
    try:
        with open(mgproj.state_file("stamps"), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(_valid_stamp(s) for s in data):
            return data
    except (OSError, ValueError):
        pass
    return [dict(s) for s in DEFAULT_STAMPS]


def save_stamps(stamps):
    """Persist the whole stamp list (the editor manages add/rename/delete/reorder
    client-side and saves the result). Validates each is a rectangular grid."""
    if not isinstance(stamps, list) or not all(_valid_stamp(s) for s in stamps):
        raise ValueError("each stamp needs a rectangular 'g' grid of metatile ids")
    clean = [{"n": str(s.get("n") or "stamp")[:40],
              "g": [[int(v) & 0xFF for v in row] for row in s["g"]]} for s in stamps]
    sf = mgproj.state_file("stamps")
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


# ---- object (sprite / item) pixel editor -----------------------------------
# Edits movable graphics: pickable items/weapons (3bpp uncompressed GfxItems tiles),
# enemy/actor sprites and the player (1bpp RLE Spr* planes). Token scheme:
#   "ID_*"  -> actor      "Spr*" -> player frame      else -> item constant / id
SPRGFX_FILE = "gfx/sprites.asm"
ITEMGFX_FILE, ITEMGFX_LABEL = "gfx/items.asm", "GfxItems"


def _obj_class(token):
    if token.startswith("ID_"):
        return "actor"
    if token.startswith("Spr"):
        return "player"
    return "item"


def _pal_rgb(pal):
    return [list(c) for c in pal]


def _planes_json(planes):
    return [{"index": i, "dy": p["dy"], "dx": p["dx"], "pattern": p["pattern"],
             "color": p["color"], "cc": p["cc"], "bits": p["bits"],
             "src": list(p["src"]) if p["src"] else None,
             "editable": p["src"] is not None} for i, p in enumerate(planes)]


def object_list():
    """Editable objects grouped for the picker."""
    actors = sorted(t for t in mgsprite.POSE if mgsprite.actor_sprite(t))
    weap = mgsprite._dw_words(mgsprite.WEAPXY_F, "WeaponGfxXY")
    itms = mgsprite._dw_words(mgsprite.ITEMXY_F, "ItemGfxXY")
    consts = mgsprite._consts()
    rev = {}
    # canonical names first: the tokens the asm actually uses for placed items
    for ents in mgsprite._item_set_blocks().values():
        for nm, _y, _x in ents:
            if nm in consts:
                rev.setdefault(consts[nm], nm)
    for k, v in consts.items():                              # fall back for unplaced ids
        rev.setdefault(v, k)
    items = []
    for iid in list(range(1, len(weap) + 1)) + list(range(9, 9 + len(itms))):
        tok = rev.get(iid, str(iid))
        if mgsprite.item_sprite(tok if not tok.isdigit() else iid):
            items.append({"token": tok, "id": iid, "kind": "weapon" if iid < 9 else "item"})
    return {"actors": actors, "items": items, "players": mgsprite.player_gfx_labels()}


def _item_region(token):
    """(item_id, srcX, srcY, w, [tilenums]) for an item token, or raise."""
    iid = int(token) if token.isdigit() else mgsprite._consts().get(token)
    if not iid:
        raise ValueError("unknown item: %s" % token)
    coord = mgsprite._item_gfx_coord(iid)
    if coord is None:
        raise ValueError("item %s has no gfx" % token)
    sx, sy, w = coord
    c0, r0, cols = sx // 8, sy // 8, w // 8
    tiles = [(r0 + rr) * 32 + (c0 + cc) for rr in range(2) for cc in range(cols)]
    return iid, sx, sy, w, tiles


def get_object(token, pose=None):
    cls = _obj_class(token)
    if cls == "item":
        iid, sx, sy, w, tiles = _item_region(token)
        data = mggfx.parse_block(ITEMGFX_FILE, ITEMGFX_LABEL)
        cols = w // 8
        pixels = [[0] * w for _ in range(16)]
        for k, tn in enumerate(tiles):
            rr, cc = k // cols, k % cols
            grid = _decode_tile_idx(data[tn * 24:tn * 24 + 24])
            for y in range(8):
                for x in range(8):
                    pixels[rr * 8 + y][cc * 8 + x] = grid[y][x]
        pal = mgsprite._ingame_base_palette()
        swatches = [list(pal[mgsprite.COLORS_ITEMS[i] & 15]) for i in range(8)]
        return {"class": "item", "token": token, "w": w, "h": 16,
                "pixels": pixels, "swatches": swatches, "shared": []}
    if cls == "actor":
        poses = list(mgsprite.actor_poses(token))
        cur = pose if (pose and pose in poses) else mgsprite.POSE[token][1]
        planes = mgsprite.actor_planes_model(token, cur)
        if not planes:
            raise ValueError("no editable sprite for %s" % token)
        ss = mgsprite.POSE[token][0]
        shared = sorted(t for t in mgsprite.POSE
                        if t != token and mgsprite.POSE.get(t, (None,))[0] == ss
                        and mgsprite.actor_sprite(t))
        return {"class": "actor", "token": token, "pose": cur, "poses": poses,
                "palette": _pal_rgb(mgsprite.actor_palette(token)),
                "planes": _planes_json(planes), "shared": shared}
    planes = mgsprite.player_planes_model(token)
    shared = [g for g in mgsprite._snake_gfx_labels() if g == token]
    return {"class": "player", "token": token,
            "palette": _pal_rgb(mgsprite._ingame_base_palette()),
            "planes": _planes_json(planes), "shared": []}


def set_object_pixels(token, pixels):
    """Write an item's edited pixels (0..7 ColorsItems indices) back to GfxItems."""
    if _obj_class(token) != "item":
        raise ValueError("pixels edit is for items only")
    iid, sx, sy, w, tiles = _item_region(token)
    if len(pixels) != 16 or any(len(r) != w for r in pixels):
        raise ValueError("pixels must be 16 x %d" % w)
    cols = w // 8
    for k, tn in enumerate(tiles):
        rr, cc = k // cols, k % cols
        sub = [[pixels[rr * 8 + y][cc * 8 + x] & 7 for x in range(8)] for y in range(8)]
        _splice_gfx_bytes(ITEMGFX_FILE, ITEMGFX_LABEL, tn * 24, list(_encode_tile_idx(sub)))
    mgsprite.clear_caches()
    return {"ok": True, "token": token}


def set_object_plane(token, index, bits, pose=None):
    """Write a sprite plane's 16x16 on/off bits back to its Spr* label (re-RLE the
    whole label). Affects every actor/pose sharing that gfx."""
    cls = _obj_class(token)
    if cls not in ("actor", "player"):
        raise ValueError("plane edit is for sprites only")
    if len(bits) != 16 or any(len(r) != 16 for r in bits):
        raise ValueError("bits must be 16x16")
    planes = (mgsprite.actor_planes_model(token, pose) if cls == "actor"
              else mgsprite.player_planes_model(token))
    if not planes or not (0 <= index < len(planes)):
        raise ValueError("plane %s out of range" % index)
    src = planes[index]["src"]
    if src is None:
        raise ValueError("plane %d has no editable gfx source" % index)
    label, off = src[0], src[1]
    dec = mgsprite.unpack_gfx(mggfx.parse_block(SPRGFX_FILE, label))
    new = mgsprite.bits_to_sprite_bytes(bits)
    dec[off:off + 32] = list(new)
    mggfx.write_block(SPRGFX_FILE, label, mgsprite.pack_gfx(dec))
    mgsprite.clear_caches()
    return {"ok": True, "token": token, "plane": index, "label": label}


def set_object_colors(token, colors):
    """Set per-plane colour bytes (low nibble = colour 0..15, cc=True -> bit6). For
    actors this rewrites the actor's own ActorSprColors* bytes; for the player the
    SnakeAttr* record colour fields."""
    cls = _obj_class(token)
    vals = [((c["color"] & 0x0F) | (0x40 if c.get("cc") else 0)) for c in colors]
    if cls == "actor":
        eid = mgsprite._enum_ids().get(token)
        lab = mgsprite._actor_col_labels()[eid - 1]
        if lab == "ActorSprNoColor":
            raise ValueError("%s has no editable colour table" % token)
        own = mggfx.parse_block(mgsprite.SPR_DEFS_F, lab)     # this label's own bytes only
        n = min(len(vals), len(own))                          # don't spill into next label
        _splice_gfx_bytes(mgsprite.SPR_DEFS_F, lab, 0, vals[:n])
    elif cls == "player":
        attr = mgsprite._snake_attr_for_gfx(token)
        if not attr:
            raise ValueError("%s has no attribute set" % token)
        for k, v in enumerate(vals):
            _splice_gfx_bytes(mgsprite.PLAYER_F, attr, 1 + k * 4 + 3, [v])
    else:
        raise ValueError("colour edit is for sprites only")
    mgsprite.clear_caches()
    return {"ok": True, "token": token}


def object_png(token, scale=6):
    cls = _obj_class(token)
    if cls == "item":
        s = mgsprite.item_sprite(int(token) if token.isdigit() else token)
        img = s.img if s else Image.new("RGBA", (1, 1))
    elif cls == "actor":
        s = mgsprite.actor_sprite(token)
        img = s.img if s else Image.new("RGBA", (1, 1))
    else:
        r = mgsprite.compose_planes(mgsprite.player_planes_model(token),
                                    mgsprite._ingame_base_palette())
        img = r[0] if r else Image.new("RGBA", (1, 1))
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    buf = io.BytesIO(); img.save(buf, "PNG")
    return buf.getvalue()


def metaset_count(meta):
    """Number of metatiles in metatile-set `meta` (1-based)."""
    rl = mgmap._read(mgmap.ROOMS_F)
    lab = mgmap.parse_label_order(rl, "idxMetatileSet")[meta - 1]
    return len(mgmap.parse_flat(mgmap._read("data/metatiles.asm"), lab)) // 16


def set_tileset(room, gfx=None, meta=None):
    """Assign a room's gfx tileset (RoomGfxSetIds nibble) and/or metatile set
    (MetaTileSetIDs nibble), each a surgical nibble edit. Returns the new values
    plus guard info: metatiles in the room's layout that exceed the new set's
    count (would render garbage), and whether the gfx/meta pairing is non-stock."""
    if gfx is not None:
        gfx = int(gfx) & 0xF
        if gfx > 7 and not get_extgfx()["enabled"]:
            raise ValueError("gfx tileset must be 0..7 - enable 'Extended banks' "
                             "(EXTGFX) to use extended tilesets 8..15")
        _set_nibble(mgmap.TILES_F, "RoomGfxSetIds", room, gfx)
    if meta is not None:
        meta = int(meta)
        if not 1 <= meta <= 6:
            raise ValueError("metatile set must be 1..6")
        _set_nibble(mgmap.ROOMS_F, "MetaTileSetIDs", room, meta)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    g = mgrender.nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    m = mgrender.nibble("data/rooms.asm", "MetaTileSetIDs", room)
    cnt = metaset_count(m)
    layout = mgmap.load_model()["layouts"][room] or []
    oob = sorted({v for v in layout if v > cnt})
    return {"ok": True, "room": room, "gfx": g, "meta": m, "metatile_count": cnt,
            "oob": oob, "stock_meta": STOCK_META.get(g), "nonstock": STOCK_META.get(g) != m}


PAL_F = "data/palettes.asm"
SJASM = os.environ.get("MG_SJASM", "C:/DevMSX/sjasm039j/sjasm.exe")
OPENMSX = os.environ.get("MG_OPENMSX", "D:/Games/Emu/OpenMSX21/openmsx.exe")
ROM = "MetalGear.rom"
MGSRC = "features.asm"          # engine-addition flags (EXTGFX, ...) live here


def radio_overrides():
    """The state-conditional radio-reply overrides (RadioOverrides) + the caller
    roster and the curated condition-flag list, for the radio modal."""
    return mgradio.overrides_model()


def set_radio_overrides(entries):
    """Editor write: replace the RadioOverrides table (list of {person,flag,text}).
    Rebuild to apply."""
    return mgradio.set_overrides(entries or [])


def set_switchoff_room(room):
    """Editor write: set which room arms the 'switch off your MSX' event."""
    mgradio.set_switchoff_room(int(room))
    return radio_overrides()


def set_madnar_room(room):
    """Editor write: set which room fires the 'Madnar moved / it's too late' event."""
    mgradio.set_madnar_room(int(room))
    return radio_overrides()


def radio_overview():
    """Persons (id/name/frequency) + every room that currently has a call + the
    reply-mode list, for the global radio panel/modal."""
    m = mgradio.model()
    return {"persons": m["persons"],
            "rooms": [r for r in m["rooms"] if r["persons"]],
            "allocated": mgradio.allocated_texts(),
            "modes": [["auto", "auto-reply + auto-tune"],
                      ["wait", "wait for player to call"],
                      ["reply", "auto-reply (no tune)"]]}


def room_radio(room):
    """A room's radio call + the data the editor needs to edit it: the person
    roster (with frequencies) and, per caller, the decoded text and its label."""
    r = mgradio.room_radio(room)
    return {"room": room, "label": r["label"], "persons": r["persons"],
            "incoming": r.get("incoming", False),
            "roster": mgradio.model()["persons"],
            "modes": [["auto", "auto-reply + auto-tune"],
                      ["wait", "wait for player to call"],
                      ["reply", "auto-reply (no tune)"]]}


def set_room_radio(room, persons):
    return mgradio.set_room_call(room, persons or [])


def set_room_music(room, body):
    """Set any of a room's RoomsMusic fields (music nibble, incoming-call sign,
    isolated flag) - each optional; omitted fields keep their value."""
    return mgradio.set_room_music(
        room, music=body.get("music"), incoming=body.get("incoming"),
        isolated=body.get("isolated"))


def _hexbyte(value):
    """Parse a frequency byte from "85", "85h" or "#85" (hex), or an int."""
    s = str(value).strip().lstrip("#").rstrip("hH") if isinstance(value, str) else value
    return (int(s, 16) if isinstance(s, str) else int(s)) & 0xFF


def set_radio_freq(person, value):
    return mgradio.set_freq(int(person), _hexbyte(value))


def set_radio_character(person, name, freq):
    """Rename a character and/or set its frequency (RadioFreqs comment + byte)."""
    out = mgradio.rename_character(int(person), name or "")
    if freq is not None and str(freq).strip() != "":
        out.update(mgradio.set_freq(int(person), _hexbyte(freq)))
    return {"ok": True, **out}


def new_radio_character(name, freq):
    """Add a new radio character (frequency + name) -> new person id (max 15)."""
    try:
        return mgradio.add_character(name or "", _hexbyte(freq or 0))
    except ValueError as e:
        return {"ok": False, "error": str(e)}


def delete_radio_character(person):
    """Delete the last character if unused (person ids are positional)."""
    try:
        return mgradio.delete_character(int(person))
    except ValueError as e:
        return {"ok": False, "error": str(e)}


def new_radio_text(text):
    """Allocate a fresh Text ID with its own dialogue (radio box) so a call can
    carry original lines without touching any shared text. Returns {text_id,...}."""
    return mgradio.alloc_text(text or "...", box=0x13)


def delete_radio_text(text_id):
    """Delete/free an editor-allocated (txtNew*) Text ID that is unused."""
    try:
        return mgradio.delete_text(int(text_id))
    except ValueError as e:
        return {"ok": False, "error": str(e)}


def set_radio_text(text_id, text):
    """Edit the dialogue string behind a Text ID (affects every call using it).
    Routed through the text codec, preserving the box type."""
    label = mgradio.text_label(int(text_id))
    if not label:
        return {"ok": False, "error": "no text for id %d" % int(text_id)}
    mgtext.patch_label(label, text)
    return {"ok": True, "text_id": int(text_id), "label": label,
            "text": mgradio.text_preview(int(text_id))}


def texts_overview():
    """Everything the 📝 text editor edits: the story/menu/mission strings in
    data/texts.asm (each with its box type + idxTexts ids), the HUD item / weapon
    name tables, and the positioned HUD/menu/title/ending texts. All content is
    decoded to plain, editable strings."""
    menus = [{"slug": s, "title": mgtext.POSFILES[s][1],
              "groups": mgtext.list_positioned(s)} for s in mgtext.POSFILES]
    texts = mgtext.list_texts()
    # annotate each text with what triggers it (radio room(s) / prisoner room(s) /
    # engine event), so it's clear which are data-bound vs hardcoded.
    rmap = {}
    for r in mgradio.model()["rooms"]:
        for p in r["persons"]:
            rmap.setdefault(p["text_id"], set()).add(r["room"])
    pcache = {}
    for t in texts:
        ids = t["ids"]
        radio = sorted({rm for i in ids for rm in rmap.get(i, ())})
        pris = sorted({rm for i in ids
                       for rm in pcache.setdefault(i, mgradio.prisoner_text_used_by(i))})
        allocated = t["label"].startswith("txtNew")
        t["used"] = {"radio": radio, "prisoner": pris, "allocated": allocated}
    return {"texts": texts,
            "names": {"items": mgtext.list_names("items"),
                      "weapons": mgtext.list_names("weapons")},
            "menus": menus}


def set_positioned(slug, line, text):
    """Edit one positioned HUD/menu/title/ending text line (surgical, keeps its
    screen-position word + terminator)."""
    nb, dec = mgtext.patch_positioned(str(slug), int(line), text)
    return {"ok": True, "slug": slug, "line": int(line), "bytes": nb, "text": dec}


def room_norespawn(room):
    """Whether an alert triggered in `room` suppresses guard respawns
    (NoRespawnRooms list, logic/norespawn.asm). Data-driven replacement for the
    stock hardcoded `cp 216`."""
    return {"room": int(room), "no_respawn": mgnorespawn.is_no_respawn(int(room))}


def set_room_norespawn(room, on):
    """Add/remove `room` from the no-respawn-on-alert list (surgical, idempotent)."""
    mgnorespawn.set_room(int(room), bool(on))
    return room_norespawn(room)


def room_respawn(room):
    """The room's alert-reinforcement entry (enemy type + two spawn locations)."""
    return mgrespawn.room_entry(room)


def set_room_respawn(room, enemy, loc1, loc2):
    """Set a room's respawn entry. `loc1`/`loc2` are {x,y} in room pixels (snapped
    to the 16px grid) or a raw {byte}."""
    def _byte(loc):
        if loc is None:
            return 0
        if "byte" in loc and loc.get("byte") is not None:
            return int(loc["byte"]) & 0xFF
        return mgrespawn.xy_byte(int(loc.get("x", 0)), int(loc.get("y", 0)))
    return mgrespawn.set_entry(int(room), int(enemy) & 0xFF, _byte(loc1), _byte(loc2))


def set_text(label, text, box=None):
    """Edit a story/menu string in data/texts.asm (surgical, via the text codec).
    box=None preserves the existing TextBoxType."""
    if box is not None and str(box).strip() != "":
        box = _hexbyte(box)
    else:
        box = None
    nb, dec = mgtext.patch_label(str(label), text, box=box)
    return {"ok": True, "label": label, "bytes": nb, "text": dec}


def set_name(table, label, text):
    """Edit a HUD item/weapon name (data/itemnames.asm / weaponnames.asm)."""
    nb, dec = mgtext.patch_name_label(str(table), str(label), text)
    return {"ok": True, "table": table, "label": label, "bytes": nb, "text": dec}


def room_prisoner(room):
    """The prisoner (if any) in `room` and its editable rescue-dialogue slot(s),
    so the room panel can show/edit what the prisoner says when freed."""
    return {"room": room, "prisoner": mgprisoner.prisoner(room)}


def set_prisoner_text(room, text_id, slot="text"):
    """Repoint a prisoner's rescue line at a Text ID (surgical edit of
    logic/actors/prisoner.asm). `slot` picks the line for the hardcoded specials."""
    try:
        return {"ok": True, "prisoner": mgprisoner.set_text_id(room, text_id, slot=slot)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


def set_prisoner_dialogue(text_id, text):
    """Edit the dialogue STRING behind a prisoner's Text ID (affects everywhere the
    id is used). Routed through the text codec, preserving the box type."""
    label = mgprisoner.text_label(int(text_id))
    if not label:
        return {"ok": False, "error": "no text for id %d" % int(text_id)}
    mgtext.patch_label(label, text)
    return {"ok": True, "text_id": int(text_id), "label": label,
            "text": mgprisoner.text_preview(int(text_id))}


def new_prisoner_text(text):
    """Allocate a fresh Text ID (in-game message box) for a prisoner's own line."""
    return mgprisoner.alloc_text(text or "RESCUED!")


def get_extgfx():
    """Read the EXTGFX equ flag from MetalGear.asm. When 1, the extended-graphics
    tilesets (gfx ids 8-15, BanksExtGfx.asm) are included and the ROM auto-grows
    to 256KB; when 0 the build is stock 128KB."""
    path = mgproj.path(MGSRC)
    txt = open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'^EXTGFX\s+equ\s+([0-9]+)', txt, re.MULTILINE)
    return {"enabled": bool(int(m.group(1))) if m else False, "found": bool(m)}


def set_extgfx(enabled):
    """Flip the EXTGFX equ flag in MetalGear.asm (0/1), preserving line endings
    and touching nothing else. Caller rebuilds to apply (size adjusts itself)."""
    path = mgproj.path(MGSRC)
    txt = open(path, encoding="utf-8", errors="replace", newline="").read()
    val = "1" if enabled else "0"
    new, n = re.subn(r'^(EXTGFX\s+equ\s+)[0-9]+', r'\g<1>' + val, txt,
                     count=1, flags=re.MULTILINE)
    if n == 0:
        return {"ok": False, "error": "EXTGFX flag not found in MetalGear.asm"}
    if new != txt:
        open(path, "w", encoding="utf-8", newline="").write(new)
    return {"ok": True, "enabled": enabled}


def get_worldbank():
    """Read the WORLDBANK equ flag (features.asm). When 1, items-in-rooms +
    actors-in-rooms live in the world-data bank (BanksWorld.asm, ROM grows to
    256KB) freeing ~2.1KB of Banks456 for paths/routes. docs/LIMITS-PLAN.md C1."""
    txt = open(mgproj.path(MGSRC), encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'^WORLDBANK\s+equ\s+([0-9]+)', txt, re.MULTILINE)
    return {"enabled": bool(int(m.group(1))) if m else False, "found": bool(m)}


def set_worldbank(enabled):
    """Flip the WORLDBANK equ flag (0/1). Caller rebuilds to apply. Enabling
    also seeds data/roomconnsfull.asm (behaviour-neutral expansion) if missing —
    BanksWorld.asm includes it."""
    if enabled:
        mgmap.gen_full_conns()
    path = mgproj.path(MGSRC)
    txt = open(path, encoding="utf-8", errors="replace", newline="").read()
    val = "1" if enabled else "0"
    new, n = re.subn(r'^(WORLDBANK\s+equ\s+)[0-9]+', r'\g<1>' + val, txt,
                     count=1, flags=re.MULTILINE)
    if n == 0:
        return {"ok": False, "error": "WORLDBANK flag not found in features.asm"}
    if new != txt:
        open(path, "w", encoding="utf-8", newline="").write(new)
    return {"ok": True, "enabled": enabled}


# ---- multi-world (docs/LIMITS-PLAN.md D3) -----------------------------------
def get_worlds():
    """World roster + the editor's ACTIVE world. Worlds >0 require WORLDBANK
    (they only assemble flag-on); the switcher is hidden otherwise."""
    n = mgmap.world_count()
    return {"count": n, "current": mgmap.current_world(),
            "worldbank": get_worldbank()["enabled"],
            "worlds": [{"id": i, "label": "World 0 (base)" if i == 0 else "World %d" % i}
                       for i in range(n)]}


def set_active_world(n):
    """Switch the editor's active world: every per-world read/write (layouts,
    conns, doors, items, actors, radio, paths index, checkpoints, gateways)
    now targets data/worldN/. Shared layers (tilesets, palettes, metatiles,
    texts, route blocks, hazard flags) are unaffected — an edit there shows in
    every world, matching the engine."""
    mgmap.set_world(int(n))
    mgsprite.clear_caches()               # lru caches key by path, not world
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, **get_worlds()}


def new_world():
    """Clone world 0 into the next data/worldN/ set (tools/mgworld.py gen):
    emits BanksWorldN.asm, wires MetalGear.asm and bumps WORLDS. The new world
    is inert until a gateway points at it; rebuild to assemble it."""
    import mgworld
    n = mgmap.world_count()
    if n >= 15:                            # 3 segs/world; keep well inside 512KB
        return {"ok": False, "error": "world limit reached"}
    mgworld.gen(n)
    return {"ok": True, **get_worlds(),
            "note": "world %d created — rebuild to assemble it" % n}


# ---- multi-project (docs/PROJECTS-PLAN.md) ----------------------------------
def get_projects():
    """Project roster + which one every codec is currently pointed at. The base
    (repo root, the pristine Metal Gear source) is always first and protected."""
    return {"active": mgproj.active_slug(), "protected": mgproj.is_protected(),
            "projects": [{"slug": p["slug"], "name": p["name"],
                          "protected": bool(p.get("protected")),
                          "template": p.get("template", ""),
                          "created": p.get("created", "")}
                         for p in mgproj.list_projects()]}


def activate_project(slug):
    """Retarget every codec at projects/<slug>/ (or the base). mgproj fires the
    registered cache invalidations (mgmap model+world, mgsprite, reach cache,
    stock layouts); the UI reloads itself after this returns."""
    mgproj.activate(slug)
    return {"ok": True, **get_projects()}


def create_project_api(name, template="duplicate", source=None):
    """Create projects/<slug>/ and switch to it. template 'duplicate' copies
    `source` (default: the active project); 'blank' generates the cleared
    new-plot template (tools/mgnewgame.py) from the base."""
    if (template or "duplicate") == "blank":
        import mgnewgame
        meta = mgnewgame.create_blank(name)
    else:
        meta = mgproj.create_project(name, source=source or mgproj.active_slug(),
                                     template="duplicate")
    mgproj.activate(meta["slug"])
    return {"ok": True, "slug": meta["slug"], **get_projects()}


def delete_project_api(slug):
    if slug == mgproj.active_slug():
        raise ValueError("switch to another project before deleting this one")
    mgproj.delete_project(slug)
    return {"ok": True, **get_projects()}


GATE_SENTINELS = (252, 253, 254)


def get_gateways():
    """The ACTIVE world's GatewayTable + the door hooks pointing at it: a door
    whose dest byte is a sentinel (252-254) fires the matching [src room,
    sentinel] gateway entry."""
    g = mgmap.parse_gateways()
    return {"world": mgmap.current_world(), "count": mgmap.world_count(),
            "sentinels": list(GATE_SENTINELS),
            "gateways": [{"index": i, "src": e[0], "sentinel": e[1],
                          "dest_world": e[2], "dest_room": e[3]}
                         for i, e in enumerate(g)]}


def gateway_add(src, sentinel, dest_world, dest_room):
    sentinel = int(sentinel)
    if sentinel not in GATE_SENTINELS:
        raise ValueError("sentinel must be 252-254")
    if not 0 <= int(dest_world) < mgmap.world_count():
        raise ValueError("dest world %s out of range (have 0..%d)"
                         % (dest_world, mgmap.world_count() - 1))
    g = mgmap.parse_gateways()
    if any(e[0] == int(src) and e[1] == sentinel for e in g):
        raise ValueError("room %s already has a gateway on sentinel %d" % (src, sentinel))
    g.append([int(src) & 0xFF, sentinel, int(dest_world), int(dest_room) & 0xFF])
    mgmap.write_gateways(g)
    return {"ok": True, **get_gateways()}


def gateway_set(index, src=None, sentinel=None, dest_world=None, dest_room=None):
    g = mgmap.parse_gateways()
    i = int(index)
    if not 0 <= i < len(g):
        raise ValueError("gateway %d out of range" % i)
    if src is not None:
        g[i][0] = int(src) & 0xFF
    if sentinel is not None:
        if int(sentinel) not in GATE_SENTINELS:
            raise ValueError("sentinel must be 252-254")
        g[i][1] = int(sentinel)
    if dest_world is not None:
        if not 0 <= int(dest_world) < mgmap.world_count():
            raise ValueError("dest world out of range")
        g[i][2] = int(dest_world)
    if dest_room is not None:
        g[i][3] = int(dest_room) & 0xFF
    mgmap.write_gateways(g)
    return {"ok": True, **get_gateways()}


def gateway_remove(index):
    g = mgmap.parse_gateways()
    i = int(index)
    if not 0 <= i < len(g):
        raise ValueError("gateway %d out of range" % i)
    del g[i]
    mgmap.write_gateways(g)
    return {"ok": True, **get_gateways()}


def build_rom():
    """Assemble MetalGear.rom via sjasm, then adaptively pad it to the smallest
    Konami-legal size (128/256/512KB) that holds the content. See tools/build.py.
    Reports error count, final size, raw content size, and tail of output."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mgbuild", os.path.join(TOOLS, "build.py"))
    mgbuild = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mgbuild)
    return mgbuild.build()


EMU_DIR = os.environ.get("MG_EMUDIR", "C:/DevMSX/mgshots")   # space-free path openMSX likes
EMU_STATE = EMU_DIR + "/emustate.txt"
EMU_WARP = EMU_DIR + "/warp.txt"
# player RAM: Room C130, NextRoomDirect C133, SelectedItem C135, PrevRoom C136, GameMode
# C151, PlayerY C182, PlayerX C184, Dir C185, IdDoorEnter C4FC, Card1..8Taken C5AD-C5B4,
# Equipment inventory array C530 (28 slots x 4 bytes: +0 item id, +1 units, +2 hundreds).
# Warp = simulate a real transition FROM a neighbour INTO the target (set Room=neighbour,
# NextRoomDirect=entry dir, GameMode=1). A direct Room poke underflows SetRoomEntryXY's
# 4-entry direction table (dec 0 -> 0FFh -> garbage pos -> off-screen -> re-loop). Door-only
# targets use a staged warp: transition into the first door-room, then ::mgpending holds a
# flat "room doorid destroom ..." queue of triples. Each stage is fired (IdDoorEnter+
# GameMode=1, NextRoomDirect=0) whenever Room matches its room, and only popped once Room
# is observed to BE the stage's dest. The re-fire matters: NextRoomLogic wipes IdDoorEnter
# near its end (Banks0123.asm ~11879), so a poke landing inside the room-init window is
# eaten -- the poked GameMode=1 then re-runs SetNextRoom with a stale NextRoomDirect, and a
# 0FFh connection there takes the elevator path on garbage data (crash). Zeroing
# NextRoomDirect turns that worst case into a 1-frame reload that the next 0.3s tick
# re-fires correctly. SelectedItem is applied with every fire of the LAST stage (before the
# transition, so e.g. a dark room draws lit); ::mgptries caps re-fires. Every door in the
# chain is also OPENED (DoorOpenArray #C450[id-1]=0) at command time: in real play you can
# only be inside a door-only room with its entry door open, and the engine relies on that --
# with the door closed its enter-box never triggers, the player can walk off the screen edge
# through the (e.g. blown-wall) gap, GetNextRoomNum returns 0FFh and SetNextRoom's cp 0F0h
# misreads it as an elevator: elevator init on room 255 trashes RAM and resets the machine
# (emulator-verified in rooms 115/200). When the
# warp command's trailing cards flag is set (!= "0") it grants all 8 cards so any card door
# can be opened to walk the whole map. When it's "0" it does the opposite: REMOVES every card
# from the Equipment array, clears Card1..8Taken (so the cards respawn / show uncollected on
# the map and are collectable again), and deselects a card if one was the SelectedItem -- so
# card-gated doors can be tested as the player would really meet them. Note CardXTaken doubles
# as the per-card "collected" flag AddRoomItems reads, so there is no separate map bitmap.
# Granting a card needs BOTH the Card?Taken flag (C5AD-C5B4, used by passwords/respawn)
# AND an entry in the Equipment array (card ids SELECTED_CARD1..8 = 0x0E..0x15). The slot
# units byte (+1) must hold the card's ItemTakeAmount, which for cards is the ASCII digit
# 0x31..0x38 ('1'..'8') = cid + 0x23 -- DrawItemHUD renders that byte directly as the card
# number, so units=1 would draw a garbage glyph. The equipment menu (CompactEquipment/
# DrawEquipMenu) is built ONLY from that array, and
# ChkCard opens a door only when its card is the SelectedItem -- which the player can only
# pick from the menu. Setting the taken flag alone (the old behaviour) showed nothing.
EMU_TCL = '''set ::mgpending ""
set ::mgpitem -1
set ::mgptries 0
proc mgpoke {a v} { if {$v >= 0} { debug write memory $a $v } }
proc mgstate {} {
  if {[catch {
    set f [open %s w]
    puts $f "[debug read memory 0xc130] [debug read memory 0xc184] [debug read memory 0xc182] [debug read memory 0xc185] [debug read memory 0xc136]"
    close $f
  }]} {}
  if {[llength $::mgpending] >= 3} {
    if {[catch {
      set r [debug read memory 0xc130]
      if {$r == [lindex $::mgpending 2]} {
        set ::mgpending [lrange $::mgpending 3 end]
        set ::mgptries 0
      } elseif {$r == [lindex $::mgpending 0]} {
        incr ::mgptries
        if {$::mgptries > 30} { set ::mgpending "" } else {
          debug write memory 0xc4fc [lindex $::mgpending 1]
          if {[llength $::mgpending] == 3} { mgpoke 0xc135 $::mgpitem }
          debug write memory 0xc133 0
          debug write memory 0xc151 1
        }
      }
    }]} {}
  }
  if {[catch {
    if {[file exists "%s"]} {
      set h [open "%s" r]; set cmd [string trim [read $h]]; close $h
      file delete "%s"
      if {$cmd ne ""} {
        set p [split $cmd]
        if {[string match {W*} [lindex $p 0]]} {
          debug write memory 0xf131 [string range [lindex $p 0] 1 end]
          set p [lrange $p 1 end]
        }
        set k [lindex $p 0]
        if {[lindex $p 6] ne "0"} {
          for {set i 0xc5ad} {$i <= 0xc5b4} {incr i} { debug write memory $i 1 }
          for {set cid 0x0e} {$cid <= 0x15} {incr cid} {
            set have 0
            for {set s 0xc530} {$s < 0xc594} {incr s 4} {
              if {[debug read memory $s] == $cid} { set have 1; break }
            }
            if {!$have} {
              for {set s 0xc530} {$s < 0xc594} {incr s 4} {
                if {[debug read memory $s] == 0} {
                  debug write memory $s $cid
                  debug write memory [expr {$s + 1}] [expr {$cid + 0x23}]
                  debug write memory [expr {$s + 2}] 0
                  break
                }
              }
            }
          }
        } else {
          for {set i 0xc5ad} {$i <= 0xc5b4} {incr i} { debug write memory $i 0 }
          for {set s 0xc530} {$s < 0xc594} {incr s 4} {
            set id [debug read memory $s]
            if {$id >= 0x0e && $id <= 0x15} {
              debug write memory $s 0
              debug write memory [expr {$s + 1}] 0
              debug write memory [expr {$s + 2}] 0
            }
          }
          set sel [debug read memory 0xc135]
          if {$sel >= 0x0e && $sel <= 0x15} { debug write memory 0xc135 0 }
        }
        debug write memory 0xc180 0
        if {$k eq "s"} {
          debug write memory 0xc4fc 0
          mgpoke 0xc184 [lindex $p 3]
          mgpoke 0xc182 [lindex $p 4]
          mgpoke 0xc135 [lindex $p 5]
          debug write memory 0xc130 [lindex $p 1]
          debug write memory 0xc133 [lindex $p 2]
          debug write memory 0xc151 1
        } elseif {$k eq "d"} {
          debug write memory 0xc4fc 0
          debug write memory [expr {0xc450 + [lindex $p 4] - 1}] 0
          foreach {sr sd st} [lrange $p 8 end] {
            debug write memory [expr {0xc450 + $sd - 1}] 0
          }
          debug write memory 0xc130 [lindex $p 1]
          debug write memory 0xc133 [lindex $p 2]
          debug write memory 0xc151 1
          set ::mgpitem [lindex $p 5]
          set ::mgptries 0
          set ::mgpending [concat [lrange $p 3 4] [list [lindex $p 7]] [lrange $p 8 end]]
        }
      }
    }
  }]} {}
  after realtime 0.3 mgstate
}
after realtime 1 mgstate
''' % (EMU_STATE, EMU_WARP, EMU_WARP, EMU_WARP)


# NextRoomDirect value -> the conns[room] index it reads (N/S/W/E)
_WARP_DIR = [(1, 0), (2, 1), (3, 2), (4, 3)]


def _slot_room(s):
    """Connection-slot index -> real room id. Slots 0-125 are rooms 0-125, but
    126-145 belong to exit-table rooms 208-227 and 146-155 to elevators 241-250
    (docs/SPECIAL-ROOMS.md §1). Poking the raw slot as Room lands in the
    door-only band -> GetNextRoomNum returns 0FFh -> crash."""
    return s if s < 126 else s + 82 if s < 146 else s + 95


def _warp_source(room):
    """Find (neighbour_room, NextRoomDirect) whose connection leads INTO `room`, so
    the warp can replay a real transition (engine places the player at that entry
    edge) instead of poking Room directly (which feeds 0 to SetRoomEntryXY).
    Slots 146-155 (elevator rooms 241-250) are skipped: those N/S bytes are the
    elevator's shaft-traversal data, not walkable edges — replaying one as a walk-in
    loops the room load. Elevator floors are entered through their real doors."""
    m = mgmap.load_model()
    full = m.get("connections_full")
    if full is not None:
        # per-room table: scan rooms directly; elevators 241-250 excluded for
        # the same shaft-data reason as the stock slots 146-155
        for r in range(min(len(full), 241)):
            for d, idx in _WARP_DIR:
                if full[r][idx] == room:
                    return r, d
        return None
    conns = m["connections"]
    for s in range(min(len(conns), 146)):
        for d, idx in _WARP_DIR:
            if conns[s][idx] == room:
                return _slot_room(s), d
    return None


def _longest_free_run_center(solid):
    """Center index of the longest run of False (free) in `solid`, or None."""
    best_s = best_e = -1; s = None
    for i, v in enumerate(list(solid) + [True]):
        if not v and s is None:
            s = i
        elif v and s is not None:
            if i - 1 - s > best_e - best_s:
                best_s, best_e = s, i - 1
            s = None
    return None if best_e < 0 else (best_s + best_e) // 2


def _warp_entry_coord(room, d):
    """Pixel value for the PRESERVED axis (X for vertical entry d1/2, Y for d3/4)
    that lands the player on the widest walkable run at the entry edge, so a warp
    doesn't drop them in a wall. None -> caller uses room centre."""
    try:
        g = mgrender.room_solid_grid(room)            # 24 rows x 32 cols, 1 = solid
    except Exception:
        return None
    rows, cols = len(g), len(g[0])
    if d in (1, 2):                                    # vertical entry: Y fixed, pick walkable X
        rr = min(rows - 1, (184 if d == 1 else 18) // 8)
        band = [max(0, rr - 1), rr, min(rows - 1, rr + 1)]
        col = _longest_free_run_center([any(g[b][c] for b in band) for c in range(cols)])
        return None if col is None else min(248, col * 8 + 4)
    cc = min(cols - 1, (242 if d == 3 else 12) // 8)   # horizontal entry: X fixed, pick walkable Y
    band = [max(0, cc - 1), cc, min(cols - 1, cc + 1)]
    row = _longest_free_run_center([any(g[r][b] for b in band) for r in range(rows)])
    return None if row is None else min(184, row * 8 + 4)


def _warp_door(room):
    """(neighbour, dir, [(door_room, door_id, dest_room), ...]) chain to reach a
    door-only room: BFS backwards through doors until a spatially-enterable room is
    found, then a multi-stage warp: into the first door-room, then through each door
    in turn. Needed for nested cells like 167 (Ellen): 55 --door--> 166 --door--> 167,
    where the intermediate 166 is itself door-only. Each stage carries its dest so
    the control script can confirm arrival before advancing (and re-fire if the
    trigger was eaten by a mid-init poke)."""
    into = {}
    for src, dl in mgmap.load_model()["doors"].items():
        for dr in dl:
            into.setdefault(dr[4], []).append((src, dr[0]))
    from collections import deque
    q = deque([(room, [])])
    seen = {room}
    while q:
        cur, chain = q.popleft()
        for src, did in into.get(cur, []):
            nb = _warp_source(src)
            if nb:
                return nb[0], nb[1], [(src, did, cur)] + chain
            if src not in seen:
                seen.add(src)
                q.append((src, [(src, did, cur)] + chain))
    return None


def warp_room(room, item=None, cards=True):
    """Warp the running emulator's player into `room` (command picked up by the
    control script within ~0.3s). Spatial rooms: replay a neighbour transition and
    pre-set the preserved coord to a walkable run (no wall landings). Door-only
    rooms (lorries/object rooms): 2-stage — warp into the door's room, then trigger
    the door. `item` (3=flashlight) sets SelectedItem so a dark room shows lit.
    `cards` (default True) grants all 8 key cards; pass False to test card-gated doors."""
    room = int(room) & 0xFF
    it = -1 if item is None else (int(item) & 0xFF)
    cf = 1 if cards else 0
    os.makedirs(EMU_DIR, exist_ok=True)
    # D3: pin the emulator to the editor's ACTIVE world before the warp fires
    # (CurWorldSeg poke; the room re-init then loads that world's data). On a
    # flag-off ROM 0xF131 is unused RAM, so only emit it when WORLDBANK is on.
    wp = ""
    if get_worldbank()["enabled"]:
        wp = "W%d " % (16 + (3 if get_extgfx()["enabled"] else 0)
                       + 3 * mgmap.current_world())
    src = _warp_source(room)
    if src:
        s, d = src
        c = _warp_entry_coord(room, d)
        px, py = (c if c is not None else 128, 96) if d in (1, 2) else (128, c if c is not None else 96)
        open(EMU_WARP, "w").write(wp + "s %d %d %d %d %d %d" % (s, d, px, py, it, cf))
        return {"ok": True, "room": room, "method": "transition", "item": item, "cards": cards,
                "world": mgmap.current_world(),
                "via": {"source": s, "dir": d}, "running": emu_state().get("running", False)}
    door = _warp_door(room)
    if door:
        nb, d, chain = door
        r1, d1, t1 = chain[0]
        extra = "".join(" %d %d %d" % st for st in chain[1:])
        open(EMU_WARP, "w").write(wp + "d %d %d %d %d %d %d %d%s"
                                  % (nb, d, r1, d1, it, cf, t1, extra))
        return {"ok": True, "room": room, "method": "door", "item": item, "cards": cards,
                "via": {"door_room": chain[0][0], "door_id": chain[0][1],
                        "stages": len(chain)},
                "running": emu_state().get("running", False)}
    return {"ok": False, "error": "room %d has no spatial entrance or a door leading "
            "into it — can't warp" % room}


def run_openmsx(room=None):
    """Launch openMSX with the built ROM (detached) plus a generated control
    script that writes the live player state (room/X/Y/dir/prev) to EMU_STATE
    every 0.3s so the editor can read it back (GET /api/emu/state)."""
    import subprocess
    if not os.path.exists(OPENMSX):
        return {"ok": False, "error": "openMSX not found at %s (set MG_OPENMSX)" % OPENMSX}
    rom = mgproj.path(ROM)
    if not os.path.exists(rom):
        return {"ok": False, "error": "ROM not built yet — build first"}
    os.makedirs(EMU_DIR, exist_ok=True)
    for stale in (EMU_STATE, EMU_WARP):
        try:
            os.remove(stale)
        except OSError:
            pass
    tcl = EMU_DIR + "/_mgrun.tcl"
    open(tcl, "w").write(EMU_TCL)
    # -romtype is REQUIRED: openMSX auto-detection misidentifies the mapper on
    # >128KB images (verified: 256KB WORLDBANK ROM hung at boot without it)
    subprocess.Popen([OPENMSX, "-machine", "C-BIOS_MSX2", "-carta", rom,
                      "-romtype", "konami", "-script", tcl], cwd=mgproj.root())
    return {"ok": True, "state_file": EMU_STATE}


def emu_state():
    """Latest player state written by the running emulator (stale if file older
    than 3s -> running:false)."""
    import time
    if not os.path.exists(EMU_STATE):
        return {"running": False}
    try:
        parts = open(EMU_STATE).read().split()
        age = time.time() - os.path.getmtime(EMU_STATE)
        if len(parts) >= 5:
            room, x, y, d, prev = (int(p) for p in parts[:5])
            return {"running": age < 3, "age": round(age, 1),
                    "room": room, "x": x, "y": y, "dir": d, "prev": prev}
    except (ValueError, OSError):
        pass
    return {"running": False}


def rom_budget():
    """ROM size + per-8KB-segment used/free (free = trailing run of the segment's
    fill byte, 00 or FF). Konami mapper: 8KB segments, up to 64 (512KB)."""
    romp = mgproj.path(ROM)
    if not os.path.exists(romp):
        return {"size": 0, "banks": [], "bank_size": 8192, "capacity": 512 * 1024}
    data = open(romp, "rb").read()
    BANK = 8192
    banks = []
    for i in range(0, len(data), BANK):
        b = data[i:i + BANK]
        fill = b[-1] if b else 0
        free = 0
        if fill in (0x00, 0xFF):
            for byte in reversed(b):
                if byte == fill:
                    free += 1
                else:
                    break
        banks.append({"bank": i // BANK, "used": len(b) - free, "free": free})
    return {"size": len(data), "banks": banks, "bank_size": BANK, "capacity": 512 * 1024,
            "free_total": sum(x["free"] for x in banks)}


def run_selftest():
    import subprocess, sys as _sys
    p = subprocess.run([_sys.executable, os.path.join(TOOLS, "mgmap.py"), "selftest"],
                       cwd=mgproj.repo_root(), capture_output=True, text=True,
                       env={**os.environ, "MG_PROJECT": mgproj.root()})
    out = (p.stdout or "") + (p.stderr or "")
    return {"pass": "SELFTEST PASS" in out, "output": "\n".join(out.splitlines()[-2:])}


def dashboard():
    """Aggregate every offline check into one report: reachability + walk-off
    escapes + one-way edges (mgmove/mgmap), metatile out-of-range, item out-of-
    range, byte-level codec selftest, and ROM size."""
    model = mgmap.load_model()
    v = get_validation(121, include_paths=True)
    setcnt = {n: metaset_count(n) for n in range(1, 7)}
    mts = mgmap.parse_flat(mgmap._read(mgmap.ROOMS_F), "MetaTileSetIDs")

    def metanib(r):
        b = mts[r // 2]
        return (b >> 4) & 0xF if r % 2 == 0 else b & 0xF

    oob = []
    for r, layout in enumerate(model["layouts"]):
        if layout is None:
            continue
        cnt = setcnt.get(metanib(r), 0)
        bad = sorted({m for m in layout if m and m > cnt})
        if bad:
            oob.append({"room": r, "meta": metanib(r), "bad": bad})
    items_n = len(mgmap.parse_label_order(mgmap._read(mgmap.ITEMS_F), "idxRoomItems"))
    item_oob = [{"room": mgmap.ITEM_ROOM_BASE + i, "value": val}
                for i, val in enumerate(model["item_idx"]) if val > items_n]
    romp = mgproj.path(ROM)
    return {"validation": v, "metatile_oob": oob, "item_oob": item_oob,
            "selftest": run_selftest(),
            "rom_size": os.path.getsize(romp) if os.path.exists(romp) else 0,
            "budget": rom_budget(),
            "sjasm_ok": os.path.exists(SJASM), "openmsx_ok": os.path.exists(OPENMSX)}


def _tokval(s):
    return int(s[:-1], 16) if s.endswith(("h", "H")) else int(s)


def _fmt_radix(old, value):
    if old.endswith("h"):
        nv = "%Xh" % value
        return ("0" + nv) if nv[0].isalpha() else nv
    return str(value)


def _splice_tokens(line, repl):
    """Replace numeric tokens (by operand index) in a db line, preserving width,
    radix, separators, and comment. repl = {token_index: new_value}."""
    ci = line.find(";")
    head, tail = (line, "") if ci < 0 else (line[:ci], line[ci:])
    m = re.search(r'\bdb\b', head)
    pre, operand = head[:m.end()], head[m.end():]
    toks = list(_NUMTOK.finditer(operand))
    for ti in sorted(repl, reverse=True):
        t = toks[ti]; old = t.group(0); nv = _fmt_radix(old, repl[ti])
        operand = operand[:t.start()] + nv + operand[t.start() + len(old):]
    return pre + operand + tail


def _default_pal7():
    """The in-room BASE palette as 16 (r,g,b) triples (channels 0..7): DefaultPalette
    with the persistent PalMenuWeapon + RadioPalette overrides applied. The engine's
    SetPalette leaves un-listed indices from the last palette load, so the menu/radio
    palettes (loaded at the briefing/weapon menu) set idx 12->gray, 14->white,
    15->black and those persist in gameplay; SetRoomPal only overrides 1,3,5,9. So the
    pristine DefaultPalette is never what a room shows -- matches mgrender.room_base_palette."""
    v = mggfx.parse_block("Banks0123.asm", "DefaultPalette")
    pal = [[((v[2 * i] >> 4) & 7), v[2 * i + 1] & 7, v[2 * i] & 7] for i in range(16)]
    for lbl in ("PalMenuWeapon", "RadioPalette"):
        b = mggfx.parse_block(PAL_F, lbl)
        j = 0
        while j + 2 < len(b) and b[j] != 0xFF:
            idx, rb, g = b[j], b[j + 1], b[j + 2]
            pal[idx & 15] = [(rb >> 4) & 7, g & 7, rb & 7]
            j += 3
    return [tuple(c) for c in pal]


def _palette_label(room):
    pid = mgrender.nibble("data/palettes.asm", "IdsRoomPal", room)
    porder = mgmap.parse_label_order(mgmap._read(PAL_F), "idxRoomPalettes")
    return pid, porder[pid]


def room_palette(room):
    """Effective 16-colour palette for a room (DefaultPalette overlaid by its
    RoomPaletteN block), each channel 0..7, marking which indices are overridden,
    plus how many rooms share the same palette id."""
    base = _default_pal7()
    pid, label = _palette_label(room)
    v = mgmap.parse_flat(mgmap._read(PAL_F), label)
    ov = {}; i = 0
    while i + 2 < len(v) and v[i] != 0xFF:
        ov[v[i]] = (v[i + 1], v[i + 2]); i += 3
    colors = []
    for idx in range(16):
        if idx in ov:
            rb, g = ov[idx]; colors.append({"r": (rb >> 4) & 7, "g": g & 7, "b": rb & 7, "override": True})
        else:
            r, g, b = base[idx]; colors.append({"r": r, "g": g, "b": b, "override": False})
    nibs = mgmap.parse_flat(mgmap._read(PAL_F), "IdsRoomPal")
    allids = []
    for byte in nibs:
        allids += [(byte >> 4) & 0xF, byte & 0xF]
    shared = sum(1 for x in allids[:251] if x == pid)
    return {"room": room, "palette_id": pid, "label": label, "colors": colors, "shared_rooms": shared}


def set_palette_color(room, index, r, g, b):
    """Set palette entry `index` (0..15) of the room's RoomPaletteN block to
    (r,g,b) channels 0..7. Updates the triple in place if already overridden,
    else inserts a new (idx,(R<<4)|B,G) triple before the 0FFh terminator. The
    block is label-referenced so growing it is address-safe."""
    index = int(index) & 0xF
    rb = ((int(r) & 7) << 4) | (int(b) & 7)
    G = int(g) & 7
    pid, label = _palette_label(room)
    lines = mgmap._read(PAL_F)
    s, e = mgmap.find_block(lines, label)
    term_i = None; done = False
    for i in range(s, e):
        m = re.search(r'\bdb\b', lines[i].split(";", 1)[0])
        if not m:
            continue
        operand = lines[i].split(";", 1)[0][m.end():]
        toks = list(_NUMTOK.finditer(operand))
        if not toks:
            continue
        first = _tokval(toks[0].group(0))
        if first == 0xFF:
            term_i = i; continue
        if first == index:
            lines[i] = _splice_tokens(lines[i], {1: rb, 2: G}); done = True; break
    if not done:
        if term_i is None:
            raise ValueError("palette block %s has no terminator" % label)
        ind = re.match(r'^(\s*)', lines[term_i]).group(1)
        lines.insert(term_i, ind + "db\t%s, %s, %s" % (mggfx._tok(index), mggfx._tok(rb), mggfx._tok(G)))
    _save_lines(PAL_F, lines)
    return {**room_palette(room), "ok": True}


def _pal_usage(lines=None):
    """(counts, order): rooms-per-palette-id over the 251 real rooms, and the
    idxRoomPalettes label order. A room picks its palette via a 4-bit IdsRoomPal
    nibble, so there are only 16 possible sets (0..15)."""
    lines = lines or mgmap._read(PAL_F)
    nibs = mgmap.parse_flat(lines, "IdsRoomPal")
    allids = []
    for byte in nibs:
        allids += [(byte >> 4) & 0xF, byte & 0xF]
    counts = {i: 0 for i in range(16)}
    for x in allids[:251]:
        counts[x] = counts.get(x, 0) + 1
    return counts, mgmap.parse_label_order(lines, "idxRoomPalettes")


def _pal_overrides(lines, label):
    """The (index, RB, G) override triples of a RoomPaletteN block (before 0FFh)."""
    v = mgmap.parse_flat(lines, label)
    out, i = [], 0
    while i + 2 < len(v) and v[i] != 0xFF:
        out.append((v[i], v[i + 1], v[i + 2])); i += 3
    return out


def palette_sets():
    """All 16 room-palette slots for the set picker: id, label, the room ids using
    it (so the mapping is visible without opening each room), and the effective 16
    colours (DefaultPalette overlaid by the block), plus the list of free (0-room)
    slots available to carve a new set into."""
    lines = mgmap._read(PAL_F)
    _, order = _pal_usage(lines)
    nibs = mgmap.parse_flat(lines, "IdsRoomPal")
    allids = []
    for byte in nibs:
        allids += [(byte >> 4) & 0xF, byte & 0xF]
    rooms_by = {i: [] for i in range(16)}
    for room, pid in enumerate(allids[:251]):
        rooms_by[pid].append(room)
    base = _default_pal7()
    sets = []
    for pid in range(min(16, len(order))):
        ov = dict((idx, (rb, g)) for idx, rb, g in _pal_overrides(lines, order[pid]))
        cols = []
        for idx in range(16):
            if idx in ov:
                rb, g = ov[idx]; cols.append({"r": (rb >> 4) & 7, "g": g & 7, "b": rb & 7})
            else:
                r, g, b = base[idx]; cols.append({"r": r, "g": g, "b": b})
        rids = rooms_by.get(pid, [])
        sets.append({"id": pid, "label": order[pid], "rooms": len(rids),
                     "room_ids": rids, "colors": cols})
    return {"sets": sets, "free": [i for i in range(16) if not rooms_by.get(i)]}


def _git_first_commit(file):
    """The earliest commit touching `file` (its original-import state). Always
    queried against the BASE's history (repo root): 'stock' means the original
    Metal Gear import even when a project copy is active."""
    import subprocess
    return subprocess.check_output(
        ["git", "log", "--reverse", "--format=%H", "--", file],
        cwd=mgproj.repo_root(), encoding="utf-8").splitlines()[0]


def _restore_block_from_git(file, label):
    """Surgically replace one `label:` db block in `file` with its original-import
    version (earliest commit), leaving the rest of the file untouched. Used for
    DefaultPalette, which lives in Banks0123.asm alongside engine code we keep."""
    import subprocess
    commit = _git_first_commit(file)
    stock = subprocess.check_output(["git", "show", "%s:%s" % (commit, file)],
                                    cwd=mgproj.repo_root(),
                                    encoding="latin-1").splitlines()
    s, e = mgmap.find_block(stock, label)
    lines = mgmap._read(file)
    mgmap.replace_block(lines, label, stock[s:e])
    _save_lines(file, lines)
    return commit[:8]


def restore_palettes():
    """Restore the ORIGINAL Metal Gear ROM palette in full:
      * data/palettes.asm -> its first-imported state (room palettes, sprite/enemy
        SprsetPal sets, menu/radio) -- reverts the rework's 'Replotted' recolour
        AND the original room->palette assignments.
      * Banks0123.asm DefaultPalette block -> stock (reverts the 'NIGHTJAR'
        green->teal base-palette shift), surgically, keeping all engine code.
    The player palette (SnakePal) is already stock. All recoverable via git."""
    import subprocess
    restored = []
    try:
        commit = _git_first_commit(PAL_F)
        txt = subprocess.check_output(["git", "show", "%s:%s" % (commit, PAL_F)],
                                      cwd=mgproj.repo_root(), encoding="latin-1")
        open(mgproj.path(PAL_F), "w", encoding="latin-1").write(txt)
        restored.append(PAL_F)
    except Exception as e:
        return {"ok": False, "error": "restore %s failed: %s" % (PAL_F, e)}
    try:
        _restore_block_from_git("Banks0123.asm", "DefaultPalette")
        restored.append("Banks0123.asm:DefaultPalette")
    except Exception as e:
        return {"ok": False, "error": "restored %s but DefaultPalette failed: %s"
                % (PAL_F, e), "restored": restored, **palette_sets()}
    return {"ok": True, "commit": commit[:8], "restored": restored, **palette_sets()}


MAP_FILES = [mgmap.ROOMS_F, mgmap.CONNS_F, mgmap.TILES_F, mgmap.DOORS_F,
             mgmap.ITEMS_F, mgmap.ACTORS_F, mgmap.CHKPT_F, mgmap.FULLCONNS_F,
             mgmap.PATHIDX_F, mgmap.GATE_F]


def restore_map():
    """Restore the ACTIVE world's room/map DATA to its first-imported git state
    (world 0 = the original Metal Gear ROM data; world N = its initial clone):
    room layouts + metatile-set ids, connections, gfx-tileset ids, doors,
    items, actors, checkpoints, path index, gateways. Files already matching
    are left untouched. Recoverable via git. Refreshes map.json."""
    import subprocess
    restored, unchanged = [], []
    for logical in MAP_FILES:
        f = mgmap.world_file(logical)                 # D3: active world's copy
        if mgmap.current_world() and f == logical:
            continue                                  # shared file: world 0's, don't touch
        try:
            try:
                commit = _git_first_commit(f)
            except IndexError:                        # no git history yet (new file)
                unchanged.append(f); continue
            stock = subprocess.check_output(["git", "show", "%s:%s" % (commit, f.replace(os.sep, "/"))],
                                            cwd=mgproj.repo_root(), encoding="latin-1")
            cur = open(mgproj.path(f), encoding="latin-1").read()
            if cur == stock:                          # both text-mode reads (\n-normalized)
                unchanged.append(f); continue
            open(mgproj.path(f), "w", encoding="latin-1").write(stock)
            restored.append(f)
        except Exception as e:
            return {"ok": False, "error": "restore %s failed: %s" % (f, e), "restored": restored}
    try:
        mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    except Exception as e:
        return {"ok": False, "error": "restored files but map.json refresh failed: %s" % e,
                "restored": restored}
    return {"ok": True, "restored": restored, "unchanged": unchanged}


def _fmt_pal_block(label, triples):
    """Render a RoomPaletteN block: one `db idx, RB, G` line per override triple,
    then the `db 0FFh` terminator. Matches the file's label+db column style."""
    out = []
    for j, (idx, rb, g) in enumerate(triples):
        pre = ("%-20sdb\t" % (label + ":")) if j == 0 else "\t\t    db\t"
        out.append(pre + "%s, %s, %s" % (mggfx._tok(idx), mggfx._tok(rb), mggfx._tok(g)))
    pre = ("%-20sdb\t" % (label + ":")) if not triples else "\t\t    db\t"
    out.append(pre + mggfx._tok(0xFF))
    return out


def set_palette_id(room, pid, clone=False):
    """Assign `room` to room-palette set `pid` (0..15) via a surgical IdsRoomPal
    nibble edit. With clone=True, first copy the room's CURRENT palette overrides
    into set `pid`'s block so it starts identical -- use this to fork the look
    into a FREE slot without disturbing the rooms that shared the old set."""
    pid = int(pid)
    if not 0 <= pid <= 15:
        raise ValueError("palette id must be 0..15 (engine packs it in a nibble)")
    lines = mgmap._read(PAL_F)
    counts, order = _pal_usage(lines)
    if pid >= len(order):
        raise ValueError("palette set %d has no idxRoomPalettes slot" % pid)
    if clone:
        cur_pid, cur_label = _palette_label(room)
        if cur_pid != pid:
            if counts.get(pid, 0) > 0:
                raise ValueError("set %d is used by %d room(s) -- cloning would overwrite it; pick a free slot"
                                 % (pid, counts[pid]))
            mgmap.replace_block(lines, order[pid], _fmt_pal_block(order[pid], _pal_overrides(lines, cur_label)))
            _save_lines(PAL_F, lines)
    _set_nibble(PAL_F, "IdsRoomPal", room, pid)
    return {**room_palette(room), "ok": True, **palette_sets()}


DOOR_FIELDS = {"id": 0, "render": 1, "y": 2, "x": 3, "dest": 4}
# IdDoorsLogic[door.id-1] & 0x1F = open-logic type (high bits 7-6 = default open/closed).
DOOR_LOGIC = {1: "Elevator / no card", 2: "Card 1", 3: "Card 2", 4: "Card 3", 5: "Card 4",
              6: "Card 5", 7: "Card 6", 8: "Card 7", 9: "Card 8", 10: "Punch (shotgunner)",
              11: "Lorry / plastic bomb", 12: "Desert door (uniform)", 13: "Compass (Jennifer)",
              14: "Big Boss flag", 15: "Prison wall (punch)", 16: "Basement wall (bomb)"}


def _door_label(room):
    order = mgmap.parse_label_order(mgmap._read(mgmap.DOORS_F), "idxDoors")
    for lab in order:
        if mgmap.label_room(lab) == room:
            return lab
    return None


def room_objects(room):
    """Doors, item, and actors for a room (for the objects panel). Item is the
    1-based index into the idxRoomItems name list (0 = none), valid only for
    item rooms 122..217. Actors are read-only (shared blocks, symbolic ids)."""
    model = mgmap.load_model()
    idl = mgmap.parse_flat(mgmap._read(mgmap.DOORS_F), "IdDoorsLogic")

    def doorrec(d):
        idx = d[0] - 1                                 # door id is 1-based into IdDoorsLogic
        lg = idl[idx] if 0 <= idx < len(idl) else None
        return {"id": d[0], "render": d[1], "y": d[2], "x": d[3], "dest": d[4],
                "logic": lg, "logic_type": (lg & 0x1F) if lg is not None else None,
                "open_default": (lg is not None and (lg & 0xC0) == 0x80)}
    doors = [doorrec(d) for d in model["doors"].get(room, [])]
    items_order = mgmap.parse_label_order(mgmap._read(mgmap.ITEMS_F), "idxRoomItems")
    item_names = [lab[4:] if lab.startswith("Item") else lab for lab in items_order]
    islot = room - mgmap.ITEM_ROOM_BASE
    # Phase A: any room from ITEM_ROOM_BASE up to MAX_ROOM can hold an item —
    # set_item grows idxRoomItemsIdx on demand (engine bound follows the table)
    item_editable = 0 <= islot and room <= mgmap.MAX_ROOM
    item = (model["item_idx"][islot] if 0 <= islot < len(model["item_idx"])
            else (0 if item_editable else None))
    actors = []
    actor_label = None
    if room < len(model["actor_slots"]):
        actor_label = model["actor_slots"][room]
        if actor_label != "NoActorsInRoom":
            for idtok, mn, toks in model["actor_blocks"].get(actor_label, []):
                if mn == "db" and len(toks) >= 2:           # db Y, X
                    y, x = _tokval(toks[0]), _tokval(toks[1])
                elif mn == "dw" and toks:                   # dw word: bytes [Y, X] little-endian
                    w = _tokval(toks[0]); y, x = w & 0xFF, (w >> 8) & 0xFF
                else:
                    y = x = 0
                bb = mgsprite.actor_bbox(idtok)
                rec = {"id": idtok, "pos_mn": mn, "pos": toks, "y": y, "x": x}
                if bb:                                      # absolute sprite footprint (room px)
                    rec["box"] = {"x": x + bb[0], "y": y + bb[1], "w": bb[2], "h": bb[3]}
                actors.append(rec)
        else:
            actor_label = None
    items_pos = []                                      # pickable items physically in the room
    for it in mgsprite.room_items(room):
        bb = mgsprite.item_sprite(it["id"])
        rec = {"id": it["id"], "y": it["y"], "x": it["x"]}
        if bb:
            rec["box"] = {"x": it["x"], "y": it["y"], "w": bb.w, "h": bb.h}
        items_pos.append(rec)
    # is this room's item-set shared with another room? (editing forks a copy)
    idxs, iorder, _b, rbl = _item_state()
    ilab = _item_label_for(idxs, iorder, room)
    item_shared = ilab is not None and len(rbl.get(ilab, [])) > 1
    return {"room": room, "doors": doors, "item": item, "item_editable": item_editable,
            "item_names": item_names, "actors": actors, "actor_label": actor_label,
            "items_pos": items_pos, "item_shared": item_shared, "item_label": ilab,
            "item_ids": item_ids(),
            "door_logic": DOOR_LOGIC, "actor_ids": actor_ids(),
            "actor_shared": actor_label is not None and
            sum(1 for x in model["actor_slots"] if x == actor_label) > 1}


def set_item(room, value):
    """Set the room's item (idxRoomItemsIdx[room-122] byte; 0 = none, else 1-based
    into idxRoomItems). Surgical byte edit. Rooms past the current table end get
    a slot on demand (Phase A growth; the ASM ITEMROOM_END bound follows)."""
    islot = room - mgmap.ITEM_ROOM_BASE
    n = len(mgmap.parse_flat(mgmap._read(mgmap.ITEMS_F), "idxRoomItemsIdx"))
    if islot < 0 or room > mgmap.MAX_ROOM:
        raise ValueError("room %d cannot hold items (valid %d..%d)"
                         % (room, mgmap.ITEM_ROOM_BASE, mgmap.MAX_ROOM))
    if islot >= n:
        lines = mgmap._read(mgmap.ITEMS_F)
        mgmap.grow_item_index(lines, room)
        _save_lines(mgmap.ITEMS_F, lines)
    _set_packed_byte(mgmap.ITEMS_F, "idxRoomItemsIdx", islot, int(value) & 0xFF)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, "room": room, "item": int(value) & 0xFF}


# ---- per-item editing (draggable content + copy-on-write on shared sets) ----
def item_ids():
    """Item/weapon constant tokens for the type picker (only ids that have gfx)."""
    return [it["token"] for it in object_list()["items"]]


def _item_state():
    """(idxs, order, blocks, rooms_by_label): the current item wiring. `idxs` is
    the room-122 index table, `order` the idxRoomItems label list (may repeat),
    `rooms_by_label` maps a set label -> [rooms that resolve to it]."""
    lines = mgmap._read(mgmap.ITEMS_F)
    idxs = mgmap.parse_flat(lines, "idxRoomItemsIdx")
    order, blocks = mgmap.parse_item_sets(lines)
    rooms_by_label = {}
    for r in range(mgmap.ITEM_ROOM_BASE, mgmap.ITEM_ROOM_BASE + len(idxs)):
        lab = _item_label_for(idxs, order, r)
        if lab:
            rooms_by_label.setdefault(lab, []).append(r)
    return idxs, order, blocks, rooms_by_label


def _item_label_for(idxs, order, room):
    islot = room - mgmap.ITEM_ROOM_BASE
    if not (0 <= islot < len(idxs)) or idxs[islot] == 0:
        return None
    si = idxs[islot] - 1
    return order[si] if 0 <= si < len(order) else None


def _item_entries(room):
    """(cur_label, shared, entries) for a room. entries is a mutable copy of the
    room's parsed item-set (each entry [id_token, pos_mnemonic, [pos_tokens]])."""
    idxs, order, blocks, rbl = _item_state()
    lab = _item_label_for(idxs, order, room)
    shared = lab is not None and len(rbl.get(lab, [])) > 1
    entries = [list(e) for e in blocks.get(lab, [])] if lab else []
    return lab, shared, entries


def _item_region_end(lines):
    """Line index just past the last item-set block (insertion point for a new
    private block). The item blocks run contiguously after the idxRoomItems
    table; we take the max end over every referenced label."""
    order = mgmap.parse_label_order(lines, "idxRoomItems")
    end = 0
    for lab in dict.fromkeys(order):
        _s, e, _rows = mgmap.block_tokens(lines, lab)
        end = max(end, e)
    return end


def _item_result(room):
    """Fresh item view for a room after a write. Drops mgsprite's lru caches so
    the re-decoded item-set blocks reflect the edit (item CONTENT edits are the
    only path that changes block bytes at runtime)."""
    mgsprite.clear_caches()
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, **{k: room_objects(room)[k] for k in
            ("room", "items_pos", "item", "item_shared", "item_label")}}


def _set_items(room, entries):
    """Write `entries` as the room's item-set. Forks a SHARED set (or a room with
    no set) into a room-private block (ItemRoomNNN), appending an idxRoomItems
    pointer slot and pointing idxRoomItemsIdx[room] at it — so other rooms are
    never disturbed. A private set is rewritten in place. Empty -> item index 0."""
    islot = room - mgmap.ITEM_ROOM_BASE
    if islot < 0 or room > mgmap.MAX_ROOM:
        raise ValueError("room %d cannot hold items (valid %d..%d)"
                         % (room, mgmap.ITEM_ROOM_BASE, mgmap.MAX_ROOM))
    lab, shared, _cur = _item_entries(room)
    lines = mgmap._read(mgmap.ITEMS_F)

    if not entries:                                            # clear the room's item
        if lab is not None:
            n = len(mgmap.parse_flat(lines, "idxRoomItemsIdx"))
            if islot < n:
                _set_packed_byte(mgmap.ITEMS_F, "idxRoomItemsIdx", islot, 0)
        return _item_result(room)

    if lab is not None and not shared:                         # private -> rewrite in place
        mgmap.replace_label_block(lines, lab, mgmap.item_block_lines(lab, entries))
        _save_lines(mgmap.ITEMS_F, lines)
        return _item_result(room)

    # fork: mint a private block, append a pointer slot, wire the room's index
    order = mgmap.parse_label_order(lines, "idxRoomItems")
    _o2, blocks = mgmap.parse_item_sets(lines)
    newlab = "ItemRoom%03d" % room
    if newlab in (set(order) | set(blocks)):
        newlab = "ItemRoomR%d" % room
    at = _item_region_end(lines)
    lines[at:at] = [""] + mgmap.item_block_lines(newlab, entries)
    # append `dw newlab` as the last idxRoomItems entry (new 1-based index)
    _s, e, _rows = mgmap.block_tokens(lines, "idxRoomItems")
    lines.insert(e, "\t\t    dw\t%s" % newlab)
    new_index = len(order) + 1
    if islot >= len(mgmap.parse_flat(lines, "idxRoomItemsIdx")):
        mgmap.grow_item_index(lines, room)
    _save_lines(mgmap.ITEMS_F, lines)
    _set_packed_byte(mgmap.ITEMS_F, "idxRoomItemsIdx", islot, new_index)
    return _item_result(room)


def item_add(room, id_token, y, x):
    _lab, _shared, entries = _item_entries(room)
    entries.append([str(id_token), "dw", [mgmap._tok(((int(x) & 0xFF) << 8) | (int(y) & 0xFF))]])
    return _set_items(room, entries)


def item_remove(room, index):
    _lab, _shared, entries = _item_entries(room)
    if not 0 <= int(index) < len(entries):
        raise ValueError("item %d out of range" % index)
    del entries[int(index)]
    return _set_items(room, entries)


def item_set(room, index, id_token=None, y=None, x=None):
    _lab, _shared, entries = _item_entries(room)
    i = int(index)
    if not 0 <= i < len(entries):
        raise ValueError("item %d out of range" % index)
    if id_token is not None:
        entries[i][0] = str(id_token)
    if y is not None and x is not None:
        entries[i][1] = "dw"; entries[i][2] = [mgmap._tok(((int(x) & 0xFF) << 8) | (int(y) & 0xFF))]
    return _set_items(room, entries)


def set_door_field(room, door_index, field, value):
    """Set one field of an existing door entry (surgical token splice in the
    DoorsRoomNNN block). field in id/render/y/x/dest. (Add/remove doors needs the
    idxDoors regen path and is not done here.)"""
    if field not in DOOR_FIELDS:
        raise ValueError("bad door field %r" % field)
    lab = _door_label(room)
    if lab is None:
        raise ValueError("room %d has no door block" % room)
    _set_packed_byte(mgmap.DOORS_F, lab, int(door_index) * 5 + DOOR_FIELDS[field], int(value) & 0xFF)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, **{k: room_objects(room)[k] for k in ("room", "doors")}}


def _set_dw_slot(lines, label, slot, newlabel):
    """Point the slot-th `dw` of a pointer table at `newlabel` (preserve comment)."""
    s = mgmap.find_line(lines, r'^%s:' % re.escape(label))
    cnt, i = 0, s
    while i < len(lines):
        code = lines[i].split(";", 1)[0]
        if i != s and re.match(r'^\w+:', code):
            break
        if re.search(r'\bdw\b', code):
            if cnt == slot:
                ci = lines[i].find(";")
                head, tail = (lines[i], "") if ci < 0 else (lines[i][:ci], lines[i][ci:])
                lines[i] = re.sub(r'(\bdw\b\s+)\S+', lambda m: m.group(1) + newlabel, head) + tail
                return
            cnt += 1
        i += 1
    raise ValueError("slot %d not found in %s" % (slot, label))


def door_remove(room, door_index):
    """Delete one door entry from a room's block (rebuilds that one block)."""
    model = mgmap.load_model()
    lab = _door_label(room)
    if lab is None:
        raise ValueError("room %d has no door block" % room)
    entries = list(model["doors"].get(room, []))
    di = int(door_index)
    if not 0 <= di < len(entries):
        raise ValueError("door %d out of range" % di)
    del entries[di]
    lines = mgmap._read(mgmap.DOORS_F)
    if entries:
        mgmap.replace_block(lines, lab, mgmap.door_block_lines(
            lab, entries, term=room not in model.get("door_noterm", set())))
    else:                                              # last door gone -> drop block, slot -> NoDoorsRoom
        s, e = mgmap.find_block(lines, lab)
        del lines[s:e]
        if s < len(lines) and not lines[s].strip():
            del lines[s]
        if room in mgmap.DOOR_SLOT_ROOMS:
            _set_dw_slot(lines, "idxDoors", mgmap.DOOR_SLOT_ROOMS.index(room), "NoDoorsRoom")
    _save_lines(mgmap.DOORS_F, lines)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, **{k: room_objects(room)[k] for k in ("room", "doors")}}


def door_add(room, dest, render=1, y=0, x=0, logic_type=2, open_default=False):
    """Add a door to a room. Mints a fresh DoorID (appends IdDoorsLogic, must stay
    <=160 for the engine's default-status loop), inserts the 5-byte entry (mints a
    DoorsRoomNNN block + wires the idxDoors slot if the room had no doors)."""
    model = mgmap.load_model()
    newid = len(model["iddoorslogic"]) + 1
    if newid > 160:
        raise ValueError("door-logic table full (id %d > 160; extend SetDefaultDoorLock)" % newid)
    logicval = (0x80 if open_default else 0) | (int(logic_type) & 0x1F)
    entry = [newid, int(render) & 0xFF, int(y) & 0xFF, int(x) & 0xFF, int(dest) & 0xFF]
    lines = mgmap._read(mgmap.DOORS_F)

    lab = _door_label(room)
    if lab is not None:                                # rebuild the block with the entry appended
        entries = list(model["doors"].get(room, [])) + [entry]
        mgmap.replace_block(lines, lab, mgmap.door_block_lines(
            lab, entries, term=room not in model.get("door_noterm", set())))
    else:                                              # mint a new block + wire the idxDoors slot
        newlab = "DoorsRoom%03d" % room
        block = mgmap.door_block_lines(newlab, [entry])
        at = mgmap.find_line(lines, r'^NoDoorsRoom:')
        lines[at:at] = block + [""]
        if room not in mgmap.DOOR_SLOT_ROOMS:
            raise ValueError("room %d has no idxDoors slot (225-239 can't have doors)" % room)
        _set_dw_slot(lines, "idxDoors", mgmap.DOOR_SLOT_ROOMS.index(room), newlab)

    s, e = mgmap.find_block(lines, "IdDoorsLogic")     # append the new door's logic byte
    lines.insert(e, "\t\t    db\t%s" % mggfx._tok(logicval))
    _save_lines(mgmap.DOORS_F, lines)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, "new_id": newid, **{k: room_objects(room)[k] for k in ("room", "doors")}}


def set_door_logic(room, door_index, logic_type):
    """Set which method opens a door (the low 5 bits of IdDoorsLogic[door.id-1]):
    e.g. Card 1-8. Preserves the high bits (default open/closed status)."""
    doors = room_objects(room)["doors"]
    if not 0 <= int(door_index) < len(doors):
        raise ValueError("door %d out of range" % door_index)
    idx = doors[int(door_index)]["id"] - 1
    idl = mgmap.parse_flat(mgmap._read(mgmap.DOORS_F), "IdDoorsLogic")
    if not 0 <= idx < len(idl):
        raise ValueError("door id %d out of IdDoorsLogic range" % (idx + 1))
    new = (idl[idx] & 0xE0) | (int(logic_type) & 0x1F)
    _set_packed_byte(mgmap.DOORS_F, "IdDoorsLogic", idx, new)
    return {"ok": True, **{k: room_objects(room)[k] for k in ("room", "doors")}}


def actor_ids():
    """List of ID_* enemy/object symbols from constants/Enums.asm (for the type picker)."""
    out = []
    for ln in mgmap._read("constants/Enums.asm"):
        m = re.match(r'^(ID_\w+):\s*equ\s', ln.split(";", 1)[0])
        if m:
            out.append(m.group(1))
    return out


def _actor_entries(room):
    """Raw model actor entries for a room: [[id_token, pos_mnemonic, [pos_tokens]], ...]."""
    m = mgmap.load_model()
    if room >= len(m["actor_slots"]):
        return m, None, False, []
    lab = m["actor_slots"][room]
    shared = lab != "NoActorsInRoom" and sum(1 for s in m["actor_slots"] if s == lab) > 1
    entries = [list(e) for e in m["actor_blocks"].get(lab, [])] if lab != "NoActorsInRoom" else []
    return m, lab, shared, entries


def _set_actors(room, entries):
    """Write `entries` as room's actor block. Forks a shared block to a room-private
    one (ActorsRoomNNN) so other rooms are unaffected; mints/removes the block and
    wires the idxActorsRooms slot as needed."""
    m = mgmap.load_model()
    slots = m["actor_slots"]
    lines = mgmap._read(mgmap.ACTORS_F)
    if room >= len(slots):
        # Phase A growth: mint NoActorsInRoom slots up to this room; the ASM
        # engine bound (N_ACTORROOMS equ) follows the table length
        mgmap.grow_actor_index(lines, room)          # raises beyond MAX_ROOM
        slots = slots + ["NoActorsInRoom"] * (room + 1 - len(slots))
    lab = slots[room]
    shared = lab != "NoActorsInRoom" and sum(1 for s in slots if s == lab) > 1
    if entries:
        if lab == "NoActorsInRoom" or shared:                  # mint a private block + wire slot
            newlab = "ActorsRoom%03d" % room
            if newlab in (set(slots) | set(m["actor_blocks"])) and newlab != lab:
                newlab = "ActorsRoomR%d" % room
            at = mgmap.find_line(lines, r'^NoActorsInRoom:')
            lines[at:at] = mgmap.actor_block_lines(newlab, entries) + [""]
            _set_dw_slot(lines, "idxActorsRooms", room, newlab)
        else:                                                  # rewrite the room's own block
            mgmap.replace_label_block(lines, lab, mgmap.actor_block_lines(lab, entries))
    else:                                                      # no actors -> slot to NoActorsInRoom (+drop own block)
        if lab != "NoActorsInRoom":
            if not shared:
                s, e, _ = mgmap.block_tokens(lines, lab)
                del lines[s:e]
                if s < len(lines) and not lines[s].strip():
                    del lines[s]
            _set_dw_slot(lines, "idxActorsRooms", room, "NoActorsInRoom")
    _save_lines(mgmap.ACTORS_F, lines)
    mgmap.export_json(mgmap.load_model(), mgproj.state_file("map"))
    return {"ok": True, **{k: room_objects(room)[k] for k in ("room", "actors", "actor_label", "actor_shared")}}


def actor_add(room, id_token, y, x):
    _, _, _, entries = _actor_entries(room)
    entries.append([str(id_token), "db", [mggfx._tok(int(y) & 0xFF), mggfx._tok(int(x) & 0xFF)]])
    return _set_actors(room, entries)


def actor_remove(room, index):
    _, _, _, entries = _actor_entries(room)
    if not 0 <= int(index) < len(entries):
        raise ValueError("actor %d out of range" % index)
    del entries[int(index)]
    return _set_actors(room, entries)


def actor_set(room, index, id_token=None, y=None, x=None):
    _, _, _, entries = _actor_entries(room)
    i = int(index)
    if not 0 <= i < len(entries):
        raise ValueError("actor %d out of range" % index)
    if id_token is not None:
        entries[i][0] = str(id_token)
    if y is not None and x is not None:                        # rewrite as db Y,X
        entries[i][1] = "db"; entries[i][2] = [mggfx._tok(int(y) & 0xFF), mggfx._tok(int(x) & 0xFF)]
    return _set_actors(room, entries)


def get_checkpoints():
    """SaveStatRooms = [room, prevRoom] save-trigger pairs (0FFh-terminated
    since Phase A — any count, docs/LIMITS-PLAN.md)."""
    return {"checkpoints": mgmap.parse_checkpoints(mgmap._read(mgmap.CHKPT_F))}


def set_checkpoint(index, room, prev):
    """Edit one checkpoint pair (surgical byte splice in SaveStatRooms)."""
    cps = mgmap.parse_checkpoints(mgmap._read(mgmap.CHKPT_F))
    if not 0 <= int(index) < len(cps):
        raise ValueError("checkpoint %d out of range (0..%d)" % (index, len(cps) - 1))
    _set_packed_byte(mgmap.CHKPT_F, "SaveStatRooms", int(index) * 2, int(room) & 0xFF)
    _set_packed_byte(mgmap.CHKPT_F, "SaveStatRooms", int(index) * 2 + 1, int(prev) & 0xFF)
    return {**get_checkpoints(), "ok": True}


def add_checkpoint(room, prev):
    """Append a [room, prevRoom] pair: one new db line just above the 0FFh
    terminator (keeps every stock comment intact)."""
    lines = mgmap._read(mgmap.CHKPT_F)
    s, e = mgmap.find_block(lines, "SaveStatRooms")
    lines.insert(e - 1, "\t\t    db\t%3d, %3d" % (int(room) & 0xFF, int(prev) & 0xFF))
    _save_lines(mgmap.CHKPT_F, lines)
    return {**get_checkpoints(), "ok": True}


def remove_checkpoint(index):
    """Delete one checkpoint pair. Pairs are one per line (stock layout); pair 0
    lives on the label line, so deleting it pulls pair 1's values up instead."""
    index = int(index)
    lines = mgmap._read(mgmap.CHKPT_F)
    s, e = mgmap.find_block(lines, "SaveStatRooms")
    cps = mgmap.parse_checkpoints(lines)
    if not 0 <= index < len(cps):
        raise ValueError("checkpoint %d out of range (0..%d)" % (index, len(cps) - 1))
    if len(cps) == 1:
        raise ValueError("cannot remove the last checkpoint (engine needs the list)")
    if index == 0:
        _set_packed_byte(mgmap.CHKPT_F, "SaveStatRooms", 0, cps[1][0])
        _set_packed_byte(mgmap.CHKPT_F, "SaveStatRooms", 1, cps[1][1])
        lines = mgmap._read(mgmap.CHKPT_F)
        s, e = mgmap.find_block(lines, "SaveStatRooms")
        index = 1
    del lines[s + index]                    # line s = pair 0, s+i = pair i
    _save_lines(mgmap.CHKPT_F, lines)
    return {**get_checkpoints(), "ok": True}


def room_openings(room):
    m = mgmap.load_model()
    conns = mgmap.eff_conns(m, room) or [255] * 4       # full-table aware (C2)
    return {
        "room": room,
        "conn": dict(zip("NSWE", conns)),
        "reachable_exits": sorted(mgmove.reachable_exits(room, conns)),
        "exit_ranges": mgmove.exit_ranges(room, conns),
        "door_edges": sorted(mgmove.door_edges(room)),
    }


# Rooms whose behaviour is HARDCODED by room id in the engine (`cp <id>` in logic/
# + Banks0123.asm), NOT a data field -- so moving/renumbering one needs an ASM
# patch or the gimmick breaks. Source of truth: docs/SPECIAL-ROOMS.md (plus the
# dark-room/gas `cp` checks in SetRoomPal / guard init). cat drives the badge.
_SPECIAL = [
    # ---- transition / movement (locked anchors) ----
    ([204], "transition", "Parachute free-fall (bricks wall)"),
    ([5], "transition", "Parachute landing — 3-lorries yard"),
    ([6], "transition", "Parachute landing — dogs yard left"),
    ([10], "transition", "Parachute landing — dogs yard right / roof"),
    ([45], "transition", "Moving bridge 1 (fall-through)"),
    ([46], "transition", "Moving bridge 2 (fall-through)"),
    ([117], "transition", "Roof — roof-jump door (91h)"),
    ([103], "transition", "Desert — get lost without the compass"),
    ([119], "transition", "Big Boss room — special ladder entry"),
    (list(range(224, 228)), "transition", "Ladder room"),
    ([240], "transition", "First elevator (no connections)"),
    (list(range(241, 251)), "transition", "Elevator room (conn = room−95)"),
    # ---- hazard / gimmick ----
    # dark/gas/electric/water/laser are data-driven now (RoomFlags) -> injected live in special_rooms()
    ([111], "hazard", "Laser cameras / door to gas room"),
    ([140], "hazard", "Mines / 3 sleeping guards"),
    ([160], "hazard", "Mine-detector room"),
    ([190], "hazard", "Isolated basement (bldg 2), CARD 1"),
    # ---- boss / event ----
    ([118], "boss", "Metal Gear"),
    ([133], "boss", "Madnar / Big Boss event"),
    ([167], "boss", "Ellen (prisoner)"),
    ([193], "boss", "Coward Duck (prisoner)"),
    # ---- enemy-spawn / scripted NPC ----
    ([7], "npc", "Three lorries, building 1"),
    ([69], "npc", "Desert guards to building 2"),
    ([73], "npc", "Building 2 first room (desert security)"),
    ([127, 128], "npc", "Lorry card rooms (guard alert)"),
    ([137], "npc", "Sub Machine Gun item room"),
    ([139], "npc", "Goggles room (guard switch)"),
    ([206], "npc", "Building 2, elevator east"),
    ([216], "npc", "4th lorry / entrance to building 3"),
    ([242], "npc", "Elevator roof, building 2"),
    ([26, 85], "npc", "Sleepy-guard room"),
    ([138], "npc", "Sleepy guards + Gas Mask item room"),
]
_CAT_RANK = {"boss": 0, "hazard": 1, "transition": 2, "npc": 3}


# unified per-room flags: one byte/room in each of RoomFlags / RoomFlags2 (BanksABC.asm),
# cached to CurRoomFlags / CurRoomFlags2 at room load. kind -> (bit, badge role, table).
# RoomFlags is full (8 bits); capture lives in the spare RoomFlags2 byte.
ROOMFLAGS_FILE = "BanksABC.asm"
HAZARD_BITS = {
    "dark":        (0, "Dark room — needs flashlight", "RoomFlags"),
    "gas":         (1, "Gas room — needs gas mask", "RoomFlags"),
    "electric":    (2, "Electrified floor (kill power first)", "RoomFlags"),
    "water":       (3, "Water room", "RoomFlags"),
    "deepwater":   (4, "Deep water", "RoomFlags"),
    "movinglaser": (5, "Moving lasers — beams sweep (visible with goggles)", "RoomFlags"),
    "laser":       (6, "Laser-beam room — tripwire beams (visible with goggles)", "RoomFlags"),
    "shortlaser":  (7, "Short camera lasers — beams are shorter here (small room, two facing cameras)", "RoomFlags"),
    "capture":     (0, "Capture trap — Snake is caught here (→ prison)", "RoomFlags2"),
}


def _read_flags(label):
    return mgmap.parse_flat(mgmap._read(ROOMFLAGS_FILE), label)


CAPTURE_F = "logic/capturescene.asm"


def _engine_path(rel):
    """Resolve a SHARED engine .asm the active project may not have copied: use
    the project's copy if it exists, else base (the build resolves the include to
    base too). Editing a shared file affects base — that's the intended
    'engine reworks are base-level' behaviour."""
    p = mgproj.path(rel)
    return p if os.path.exists(p) else os.path.join(mgproj.REPO_ROOT, rel)


def _engine_read(rel):
    return open(_engine_path(rel), encoding="latin-1").read()


def _engine_write(rel, txt):
    open(_engine_path(rel), "w", encoding="latin-1").write(txt)


def capture_prison_room():
    """The editable room Snake is sent to after capture (CapturePrisonRoom db,
    stock 165), or None if the byte isn't present (very old project)."""
    import re
    m = re.search(r'(?m)^CapturePrisonRoom:\s*db\s+(\d+)', _engine_read(CAPTURE_F))
    return int(m.group(1)) if m else None


def set_capture_prison_room(room):
    """Editor write: set the post-capture destination room (all capture traps
    share it). Rebuild to apply."""
    import re
    src = _engine_read(CAPTURE_F)
    new = re.sub(r'(?m)^(CapturePrisonRoom:\s*db\s+)\d+',
                 lambda mm: mm.group(1) + str(int(room) & 0xFF), src, count=1)
    if new != src:
        _engine_write(CAPTURE_F, new)
    return {"prison_room": capture_prison_room()}


def room_hazards(room):
    """Per-room unified flags for the editor toggles (read from RoomFlags /
    RoomFlags2) + the global post-capture destination room."""
    room = int(room)
    cache = {}
    def _bit(bit, label):
        arr = cache.get(label)
        if arr is None:
            arr = cache[label] = _read_flags(label)
        b = arr[room] if room < len(arr) else 0
        return bool(b & (1 << bit))
    return {"room": room,
            "flags": {k: _bit(bit, lbl) for k, (bit, _, lbl) in HAZARD_BITS.items()},
            "capture_prison_room": capture_prison_room()}


def set_room_hazard(room, kind, on):
    if kind not in HAZARD_BITS:
        raise ValueError("unknown hazard %r" % kind)
    room = int(room) & 0xFF
    bit, _, lbl = HAZARD_BITS[kind]
    flags = _read_flags(lbl)
    b = flags[room] if room < len(flags) else 0
    mask = 1 << bit
    b = (b | mask) if on else (b & ~mask & 0xFF)
    _set_packed_byte(ROOMFLAGS_FILE, lbl, room, b)
    return room_hazards(room)


# ---------------------------------------------------------------------------
# Special enemy counts (SpecialEnemyCnt table in Banks0123.asm): per-room fixed
# count of a special enemy whose last kill drops an item. Data-driven, editable.
# ---------------------------------------------------------------------------
SPECIALENEMY_FILE = "Banks0123.asm"
# counter symbol -> friendly label. Whitelisted so a write can never inject an
# arbitrary symbol/address into the emitted `dw`.
SPECIAL_ENEMY_COUNTERS = {
    "ArnoldsCnt":       "Arnold (last kill drops CARD 7)",
    "GuardSilencerCnt": "Silencer guard (last kill drops the suppressor)",
}


def _se_block_match(src):
    return re.search(r'(?ms)^SpecialEnemyCnt:.*?\bdb\s+0FFh\b[^\n]*', src)


def _tok_int(t):
    return int(t[:-1], 16) if t.lower().endswith("h") else int(t)


def _parse_special_enemy(src=None):
    """SpecialEnemyCnt -> {room: (counter_symbol, count)}."""
    if src is None:
        src = _engine_read(SPECIALENEMY_FILE)
    m = _se_block_match(src)
    out = {}
    if not m:
        return out
    toks = []
    for line in m.group(0).splitlines():
        code = line.split(";", 1)[0]
        toks += re.findall(r'\b(?:db|dw)\s+(\d[0-9A-Fa-f]*[hH]|[A-Za-z_]\w*|\d+)', code)
    i = 0
    while i < len(toks):
        if _tok_int(toks[i]) == 0xFF:          # terminator
            break
        out[_tok_int(toks[i])] = (toks[i + 1], _tok_int(toks[i + 2]))
        i += 3
    return out


def _emit_special_enemy(model):
    if not model:
        return "SpecialEnemyCnt:    db\t 0FFh"
    out = []
    for k, (room, (sym, cnt)) in enumerate(sorted(model.items())):
        out.append(("SpecialEnemyCnt:    db\t " if k == 0 else "\t\t    db\t ") + str(room))
        out.append("\t\t    dw\t " + sym)
        out.append("\t\t    db\t %d\t\t\t    ; room %d: %s x%d"
                   % (cnt, room, SPECIAL_ENEMY_COUNTERS.get(sym, sym), cnt))
    out.append("\t\t    db\t 0FFh")
    return "\n".join(out)


def room_special_enemy(room):
    room = int(room)
    e = _parse_special_enemy().get(room)
    return {"room": room, "counter": e[0] if e else None,
            "count": e[1] if e else 0, "counters": SPECIAL_ENEMY_COUNTERS}


def set_special_enemy(room, counter, count):
    room = int(room) & 0xFF
    src = _engine_read(SPECIALENEMY_FILE)
    m = _se_block_match(src)
    if not m:
        raise ValueError("SpecialEnemyCnt table not found")
    model = _parse_special_enemy(src)
    if counter in (None, "", "none"):
        model.pop(room, None)
    elif counter in SPECIAL_ENEMY_COUNTERS:
        model[room] = (counter, max(1, min(255, int(count))))
    else:
        raise ValueError("unknown counter %r" % counter)
    new = src[:m.start()] + _emit_special_enemy(model) + src[m.end():]
    if new != src:
        _engine_write(SPECIALENEMY_FILE, new)
    return room_special_enemy(room)


# ---------------------------------------------------------------------------
# Parachute cluster room ids (constants/parachute.asm equ's). Editable so the
# fixed-shape skydive subgraph can be relocated to different room numbers.
# ---------------------------------------------------------------------------
PARACHUTE_FILE = "constants/parachute.asm"
PARACHUTE_FIELDS = [
    ("PARACHUTE_ROOM",    "fall",         "Free-fall room (keeps the bricks-wall layout)"),
    ("PARA_SRC_ROOF",     "src_roof",     "Jump source: roof (needs its jump door 91h)"),
    ("PARA_SRC_BRIDGE1",  "src_bridge1",  "Jump source: moving bridge 1"),
    ("PARA_SRC_BRIDGE2",  "src_bridge2",  "Jump source: moving bridge 2"),
    ("PARA_LAND_BRIDGE1", "land_bridge1", "Landing from bridge 1"),
    ("PARA_LAND_BRIDGE2", "land_bridge2", "Landing from bridge 2"),
    ("PARA_LAND_ROOF",    "land_roof",    "Landing from roof / default"),
]


def get_parachute():
    src = _engine_read(PARACHUTE_FILE)
    fields = []
    for sym, key, label in PARACHUTE_FIELDS:
        m = re.search(r'(?m)^%s\s+equ\s+(\d+)' % sym, src)
        fields.append({"key": key, "sym": sym, "label": label,
                       "room": int(m.group(1)) if m else None})
    return {"fields": fields, "rooms": [f["room"] for f in fields]}


def set_parachute(key, room):
    sym = next((s for s, k, l in PARACHUTE_FIELDS if k == key), None)
    if not sym:
        raise ValueError("unknown parachute field %r" % key)
    room = int(room) & 0xFF
    src = _engine_read(PARACHUTE_FILE)
    new = re.sub(r'(?m)^(%s\s+equ\s+)\d+' % sym,
                 lambda m: m.group(1) + str(room), src, count=1)
    if new != src:
        _engine_write(PARACHUTE_FILE, new)
    return get_parachute()


# ---------------------------------------------------------------------------
# Ladder cluster room ids (constants/ladders.asm). Editable so the ladder block
# can be relocated under WORLDBANK=1 (see docs/LIMITS-PLAN.md A6 for the door-slot
# design constraint that bounds how far it can move).
# ---------------------------------------------------------------------------
LADDER_FILE = "constants/ladders.asm"
LADDER_FIELDS = [
    ("LADDER_FIRST",  "first",   "First ladder room (exit + bottom limit; carries the Big Boss door)"),
    ("LADDER_LAST",   "last",    "Last ladder room (top limit)"),
    ("BIG_BOSS_ROOM", "bigboss", "Big Boss room (ladder-mode entry)"),
]


def get_ladders():
    src = _engine_read(LADDER_FILE)
    fields = []
    for sym, key, label in LADDER_FIELDS:
        m = re.search(r'(?m)^%s\s+equ\s+(\d+)' % sym, src)
        fields.append({"key": key, "sym": sym, "label": label,
                       "room": int(m.group(1)) if m else None})
    by = {f["key"]: f["room"] for f in fields}
    rooms = []
    if by.get("first") is not None and by.get("last") is not None:
        rooms = list(range(by["first"], by["last"] + 1))
    if by.get("bigboss") is not None:
        rooms.append(by["bigboss"])
    return {"fields": fields, "rooms": rooms}


def set_ladders(key, room):
    sym = next((s for s, k, l in LADDER_FIELDS if k == key), None)
    if not sym:
        raise ValueError("unknown ladder field %r" % key)
    room = int(room) & 0xFF
    src = _engine_read(LADDER_FILE)
    new = re.sub(r'(?m)^(%s\s+equ\s+)\d+' % sym,
                 lambda m: m.group(1) + str(room), src, count=1)
    if new != src:
        _engine_write(LADDER_FILE, new)
    return get_ladders()


# ---------------------------------------------------------------------------
# Elevator band base (constants/elevators.asm). ELEVATOR_FIRST is the shared "is
# elevator room" boundary; the long-elevator floors are derived offsets. The base
# is PINNED to 240 (0xF0) by un-parameterized nibble-masks — editing it off 240
# breaks those, so this is a power-user knob (documented in the constants file).
# ---------------------------------------------------------------------------
ELEVATOR_FILE = "constants/elevators.asm"
_LONG_ELEV = [("LONG_ELEV_UPPER", 7, "upper floor"), ("LONG_ELEV_A", 8, "don't-stop"),
              ("LONG_ELEV_B", 9, "don't-stop"), ("LONG_ELEV_C", 10, "don't-stop")]


def get_elevators():
    m = re.search(r'(?m)^ELEVATOR_FIRST\s+equ\s+(\d+)', _engine_read(ELEVATOR_FILE))
    base = int(m.group(1)) if m else None
    floors = [{"sym": s, "room": (base + off) if base is not None else None, "note": note}
              for s, off, note in _LONG_ELEV]
    rooms = list(range(base, base + 11)) if base is not None else []
    return {"base": base, "floors": floors, "rooms": rooms, "pinned": 240}


def set_elevators(room):
    room = int(room) & 0xFF
    src = _engine_read(ELEVATOR_FILE)
    new = re.sub(r'(?m)^(ELEVATOR_FIRST\s+equ\s+)\d+',
                 lambda m: m.group(1) + str(room), src, count=1)
    if new != src:
        _engine_write(ELEVATOR_FILE, new)
    return get_elevators()


def special_rooms():
    """{room_id: {cat, role}} of engine-special rooms. Highest-priority cat wins and
    roles merge. Dark/gas/electric/water badges are read LIVE from the RoomFlags table
    so they track editor toggles instead of a static list."""
    out = {}
    # (rooms, cat, role, editable): _SPECIAL are hardcoded-by-id (warn if moved); the
    # RoomFlags hazards are data-driven (editable via the checkboxes, safe to move).
    entries = [(rooms, cat, role, False) for rooms, cat, role in _SPECIAL]
    try:
        cache = {}
        for kind, (bit, role, lbl) in HAZARD_BITS.items():
            if kind in ("deepwater", "shortlaser", "movinglaser"):
                continue
            flags = cache.get(lbl) or cache.setdefault(lbl, _read_flags(lbl))
            rooms = [r for r, f in enumerate(flags) if f & (1 << bit)]
            if rooms:
                entries.append((rooms, "hazard", role, True))
    except Exception:
        pass
    for rooms, cat, role, editable in entries:
        for r in rooms:
            if r in out:
                if _CAT_RANK[cat] < _CAT_RANK[out[r]["cat"]]:
                    out[r]["cat"] = cat
                if role not in out[r]["role"]:
                    out[r]["role"] += " · " + role
                if not editable:
                    out[r]["editable"] = False   # any hardcoded role -> the room is locked
            else:
                out[r] = {"cat": cat, "role": role, "editable": editable}
    return out


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------
CONTENT = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
           ".css": "text/css", ".png": "image/png", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                      # quieter console
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        try:                                            # browser often cancels img reqs (cache-bust) -> ignore
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _err(self, code, msg):
        try:
            self._send(code, {"error": msg, "trace": traceback.format_exc()})
        except Exception:
            pass

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        q = parse_qs(u.query)
        try:
            if path == "/" or path == "/index.html":
                return self._file(os.path.join(STATIC, "index.html"))
            if path.startswith("/static/"):
                return self._file(os.path.join(STATIC, os.path.basename(path)))
            if path == "/api/map":
                return self._send(200, get_map_doc())
            if path == "/api/validate":
                start = int(q.get("start", ["121"])[0])
                return self._send(200, get_validation(start, include_paths=True))
            if path == "/api/dashboard":
                return self._send(200, dashboard())
            if path == "/api/emu/state":
                return self._send(200, emu_state())
            if path == "/api/checkpoints":
                return self._send(200, get_checkpoints())
            if path == "/api/special-rooms":
                return self._send(200, special_rooms())
            if path == "/api/parachute":
                return self._send(200, get_parachute())
            if path == "/api/ladders":
                return self._send(200, get_ladders())
            if path == "/api/elevators":
                return self._send(200, get_elevators())
            if path == "/api/gates":
                return self._send(200, codec_gates())
            if path == "/api/labels":
                return self._send(200, get_labels())
            if path == "/api/stamps":
                return self._send(200, {"stamps": load_stamps()})
            if path == "/api/palettes":
                return self._send(200, palette_sets())
            if path == "/api/extgfx":
                return self._send(200, get_extgfx())
            if path == "/api/worldbank":
                return self._send(200, get_worldbank())
            if path == "/api/worlds":
                return self._send(200, get_worlds())
            if path == "/api/projects":
                return self._send(200, get_projects())
            if path == "/api/gateways":
                return self._send(200, get_gateways())
            if path == "/api/radio":
                return self._send(200, radio_overview())
            if path == "/api/radio/overrides":
                return self._send(200, radio_overrides())
            if path == "/api/objects":
                return self._send(200, object_list())
            if path == "/api/texts":
                return self._send(200, texts_overview())

            parts = path.strip("/").split("/")        # api room <id> <verb>
            if len(parts) >= 3 and parts[:2] == ["api", "object"]:
                token = unquote(parts[2])
                if len(parts) == 3:
                    return self._send(200, get_object(token, q.get("pose", [None])[0]))
                if len(parts) == 4 and parts[3] == "render.png":
                    return self._send(200, object_png(token, int(q.get("scale", ["6"])[0])), "image/png")
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "room":
                room = int(parts[2]); verb = parts[3]
                if verb == "render.png":
                    scale = int(q.get("scale", ["2"])[0])
                    coll = q.get("collision", ["0"])[0] in ("1", "true")
                    return self._send(200, render_png(room, scale, coll), "image/png")
                if verb == "actors.png":
                    scale = int(q.get("scale", ["2"])[0])
                    return self._send(200, actors_png(room, scale), "image/png")
                if verb == "paths.png":
                    scale = int(q.get("scale", ["2"])[0])
                    return self._send(200, paths_png(room, scale), "image/png")
                if verb == "atlas.png":
                    coll = q.get("collision", ["0"])[0] in ("1", "true")
                    return self._send(200, atlas_png(room, coll), "image/png")
                if verb == "metatiles.png":
                    cols = int(q.get("cols", ["16"])[0])
                    scale = int(q.get("scale", ["2"])[0])
                    coll = q.get("collision", ["0"])[0] in ("1", "true")
                    png, _, _, _ = metatile_sheet(room, cols, scale, coll, int(q.get("grid", ["2"])[0]))
                    return self._send(200, png, "image/png")
                if verb == "metainfo":
                    cols = int(q.get("cols", ["16"])[0])
                    scale = int(q.get("scale", ["2"])[0])
                    return self._send(200, metatile_info(room, cols, scale))
                if verb == "openings":
                    return self._send(200, room_openings(room))
                if verb == "palette":
                    return self._send(200, room_palette(room))
                if verb == "objects":
                    return self._send(200, room_objects(room))
                if verb == "hazards":
                    return self._send(200, room_hazards(room))
                if verb == "radio":
                    return self._send(200, room_radio(room))
                if verb == "prisoner":
                    return self._send(200, room_prisoner(room))
                if verb == "paths":
                    return self._send(200, room_paths(room))
                if verb == "hideguards":
                    return self._send(200, room_hideguards(room))
                if verb == "zone":
                    return self._send(200, room_zone(room))
                if verb == "respawn":
                    return self._send(200, room_respawn(room))
                if verb == "norespawn":
                    return self._send(200, room_norespawn(room))
                if verb == "specialenemy":
                    return self._send(200, room_special_enemy(room))
                if verb == "tileatlas.png":
                    scale = int(q.get("scale", ["3"])[0])
                    coll = q.get("collision", ["0"])[0] in ("1", "true")
                    return self._send(200, tile_atlas_png(room, scale, coll, int(q.get("grid", ["2"])[0])), "image/png")
            if len(parts) == 5 and parts[:2] == ["api", "room"] and parts[3] == "metatile":
                return self._send(200, metatile_def(int(parts[2]), int(parts[4])))
            if len(parts) == 5 and parts[:2] == ["api", "room"] and parts[3] == "tile":
                return self._send(200, get_tile(int(parts[2]), int(parts[4])))
            return self._send(404, {"error": "not found: %s" % path})
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return
        except Exception as e:
            return self._err(500, str(e))

    def do_POST(self):
        u = urlparse(self.path)
        parts = u.path.strip("/").split("/")
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/projects":
                return self._send(200, create_project_api(
                    body["name"], body.get("template"), body.get("source")))
            if u.path == "/api/project/activate":
                return self._send(200, activate_project(body["slug"]))
            if u.path == "/api/project/delete":
                return self._send(200, delete_project_api(body["slug"]))
            # Base-project write guard: the pristine Metal Gear source is
            # read-only in the editor. Building/running/warping and the
            # in-memory world switch don't modify the source, so they pass.
            if mgproj.is_protected() and u.path not in (
                    "/api/build", "/api/run", "/api/emu/warp", "/api/world"):
                return self._send(403, {
                    "error": "'%s' is protected (read-only) — duplicate it to edit"
                             % mgproj.active_slug(),
                    "protected": True})
            if u.path == "/api/build":
                return self._send(200, build_rom())
            if u.path == "/api/gates":
                return self._send(200, set_codec_gates(body))
            if u.path == "/api/parachute":
                return self._send(200, set_parachute(body["field"], body["room"]))
            if u.path == "/api/ladders":
                return self._send(200, set_ladders(body["field"], body["room"]))
            if u.path == "/api/elevators":
                return self._send(200, set_elevators(body["room"]))
            if u.path == "/api/labels":
                return self._send(200, set_label(body))
            if u.path == "/api/stamps":
                return self._send(200, {"ok": True, "stamps": save_stamps(body["stamps"])})
            if u.path == "/api/extgfx":
                return self._send(200, set_extgfx(bool(body.get("enabled"))))
            if u.path == "/api/worldbank":
                return self._send(200, set_worldbank(bool(body.get("enabled"))))
            if u.path == "/api/world":
                return self._send(200, set_active_world(body["world"]))
            if u.path == "/api/world/new":
                return self._send(200, new_world())
            if u.path == "/api/gateway/add":
                return self._send(200, gateway_add(body["src"], body["sentinel"],
                                                   body["dest_world"], body["dest_room"]))
            if u.path == "/api/gateway/set":
                return self._send(200, gateway_set(body["index"], body.get("src"),
                                                   body.get("sentinel"), body.get("dest_world"),
                                                   body.get("dest_room")))
            if u.path == "/api/gateway/remove":
                return self._send(200, gateway_remove(body["index"]))
            if u.path == "/api/radio/freq":
                return self._send(200, set_radio_freq(body["person"], body["freq"]))
            if u.path == "/api/radio/character":
                return self._send(200, set_radio_character(body["person"], body.get("name"), body.get("freq")))
            if u.path == "/api/radio/character/new":
                return self._send(200, new_radio_character(body.get("name"), body.get("freq")))
            if u.path == "/api/radio/character/delete":
                return self._send(200, delete_radio_character(body["person"]))
            if u.path == "/api/radio/text":
                return self._send(200, set_radio_text(body["text_id"], body["text"]))
            if u.path == "/api/radio/text/new":
                return self._send(200, new_radio_text(body.get("text", "...")))
            if u.path == "/api/radio/text/delete":
                return self._send(200, delete_radio_text(body["text_id"]))
            if u.path == "/api/radio/overrides":
                return self._send(200, set_radio_overrides(body.get("overrides")))
            if u.path == "/api/radio/switchoff-room":
                return self._send(200, set_switchoff_room(body["room"]))
            if u.path == "/api/radio/madnar-room":
                return self._send(200, set_madnar_room(body["room"]))
            if u.path == "/api/text":
                return self._send(200, set_text(body["label"], body["text"], body.get("box")))
            if u.path == "/api/name":
                return self._send(200, set_name(body["table"], body["label"], body["text"]))
            if u.path == "/api/postext":
                return self._send(200, set_positioned(body["slug"], body["line"], body["text"]))
            if u.path == "/api/prisoner/dialogue":
                return self._send(200, set_prisoner_dialogue(body["text_id"], body["text"]))
            if u.path == "/api/prisoner/text/new":
                return self._send(200, new_prisoner_text(body.get("text", "RESCUED!")))
            if u.path == "/api/run":
                return self._send(200, run_openmsx(body.get("room")))
            if u.path == "/api/emu/warp":
                return self._send(200, warp_room(body["room"], body.get("item"),
                                                 body.get("cards", True)))
            if u.path == "/api/checkpoint":
                return self._send(200, set_checkpoint(body["index"], body["room"], body["prev"]))
            if u.path == "/api/checkpoint/add":
                return self._send(200, add_checkpoint(body["room"], body["prev"]))
            if u.path == "/api/checkpoint/remove":
                return self._send(200, remove_checkpoint(body["index"]))
            if u.path == "/api/palettes/restore":
                return self._send(200, restore_palettes())
            if u.path == "/api/map/restore":
                return self._send(200, restore_map())
            if len(parts) == 4 and parts[:2] == ["api", "room"]:
                room = int(parts[2])
                if parts[3] == "grid":
                    return self._send(200, save_grid(room, body["grid"]))
                if parts[3] == "conn":
                    return self._send(200, set_connection(
                        room, body["dir"], body.get("dest"), body.get("reciprocal", True)))
                if parts[3] == "tileset":
                    return self._send(200, set_tileset(room, body.get("gfx"), body.get("meta")))
                if parts[3] == "radio":
                    return self._send(200, set_room_radio(room, body.get("persons")))
                if parts[3] == "music":
                    return self._send(200, set_room_music(room, body))
                if parts[3] == "prisoner":
                    return self._send(200, set_prisoner_text(
                        room, body["text_id"], body.get("slot", "text")))
                if parts[3] == "palette":
                    return self._send(200, set_palette_color(
                        room, body["index"], body["r"], body["g"], body["b"]))
                if parts[3] == "paletteset":
                    return self._send(200, set_palette_id(room, body["pid"], body.get("clone", False)))
                if parts[3] == "item":
                    return self._send(200, set_item(room, body["value"]))
                if parts[3] == "itemadd":
                    return self._send(200, item_add(room, body["id"], body["y"], body["x"]))
                if parts[3] == "itemremove":
                    return self._send(200, item_remove(room, body["index"]))
                if parts[3] == "itemset":
                    return self._send(200, item_set(room, body["index"], body.get("id"), body.get("y"), body.get("x")))
                if parts[3] == "hazard":
                    return self._send(200, set_room_hazard(room, body["kind"], body["on"]))
                if parts[3] == "capture-prison":
                    return self._send(200, set_capture_prison_room(body["room"]))
                if parts[3] == "norespawn":
                    return self._send(200, set_room_norespawn(room, body["on"]))
                if parts[3] == "specialenemy":
                    return self._send(200, set_special_enemy(room, body.get("counter"), body.get("count", 1)))
                if parts[3] == "door":
                    return self._send(200, set_door_field(
                        room, body["index"], body["field"], body["value"]))
                if parts[3] == "doorlogic":
                    return self._send(200, set_door_logic(room, body["index"], body["type"]))
                if parts[3] == "metatileadd":
                    return self._send(200, add_metatile(room, body.get("fill", 0)))
                if parts[3] == "dooradd":
                    return self._send(200, door_add(room, body["dest"], body.get("render", 1),
                        body.get("y", 0), body.get("x", 0), body.get("logic_type", 2), body.get("open_default", False)))
                if parts[3] == "doorremove":
                    return self._send(200, door_remove(room, body["index"]))
                if parts[3] == "actoradd":
                    return self._send(200, actor_add(room, body["id"], body["y"], body["x"]))
                if parts[3] == "actorremove":
                    return self._send(200, actor_remove(room, body["index"]))
                if parts[3] == "actorset":
                    return self._send(200, actor_set(room, body["index"], body.get("id"), body.get("y"), body.get("x")))
                if parts[3] == "hideguards":
                    return self._send(200, set_room_hideguards(room, body.get("rules", [])))
                if parts[3] == "respawn":
                    return self._send(200, set_room_respawn(room, body["enemy"],
                                                            body.get("loc1"), body.get("loc2")))
                if parts[3] == "antenna":
                    return self._send(200, set_room_antenna(room, body["on"]))
                if parts[3] == "bugalarm":
                    return self._send(200, set_room_bug_alarm(room, body["on"]))
                if parts[3] == "paths":
                    return self._send(200, set_room_paths_api(
                        room, None if body.get("revert") else body.get("routes", [])))
            if len(parts) == 5 and parts[:2] == ["api", "room"] and parts[3] == "metatile":
                return self._send(200, set_metatile(int(parts[2]), int(parts[4]), body["cells"]))
            if len(parts) == 5 and parts[:2] == ["api", "room"] and parts[3] == "tile":
                if "solid" in body:
                    return self._send(200, set_tile_collision(int(parts[2]), int(parts[4]), bool(body["solid"])))
                return self._send(200, set_tile(int(parts[2]), int(parts[4]), body["pixels"]))
            if len(parts) == 4 and parts[:2] == ["api", "object"]:
                token = unquote(parts[2])
                if parts[3] == "plane":
                    return self._send(200, set_object_plane(token, body["index"], body["bits"], body.get("pose")))
                if parts[3] == "pixels":
                    return self._send(200, set_object_pixels(token, body["pixels"]))
                if parts[3] == "colors":
                    return self._send(200, set_object_colors(token, body["colors"]))
            return self._send(404, {"error": "not found: %s" % u.path})
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return
        except Exception as e:
            return self._err(500, str(e))

    def _file(self, fp):
        if not os.path.isfile(fp):
            return self._send(404, {"error": "missing file: %s" % fp})
        ext = os.path.splitext(fp)[1].lower()
        with open(fp, "rb") as f:
            self._send(200, f.read(), CONTENT.get(ext, "application/octet-stream"))


def main():
    ap = argparse.ArgumentParser(description="NIGHTJAR map editor backend")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true", help="open the browser")
    args = ap.parse_args()
    if not os.environ.get("MG_PROJECT"):      # env override beats persisted state
        mgproj.restore_active()               # resume last session's project
    url = "http://%s:%d/" % (args.host, args.port)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("NIGHTJAR map editor  ->  %s   (Ctrl-C to stop)" % url)
    print("active project: %s%s" % (mgproj.active_slug(),
                                    " (protected)" if mgproj.is_protected() else ""))
    if args.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
