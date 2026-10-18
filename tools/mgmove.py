#!/usr/bin/env python3
"""
mgmove.py - engine-accurate player-movement model for the NIGHTJAR map rework.

Simulates exactly how the Metal Gear player walks and crosses room edges, so
topology/layout edits can be validated offline (which edges are real openings,
where the player lands on entry, whether an edit opens an escape).

Model (reverse-engineered from Banks0123.asm + logic/collisions.asm + nextroom.asm):
  * tile collision: CollisionTiles[ roomTile(x>>3,y>>3) ] bit0 = solid.
  * player hitbox = BoxColliderDat shape 0; a move in a direction tests that
    direction's TWO leading-edge points; if either is solid the move is blocked:
        Up    (dy,dx) = (-5,-6),(-5,+5)      Down  = (+4,-6),(+4,+5)
        Left  = (-4,-8),(+3,-8)              Right = (-4,+7),(+3,+7)
  * exit thresholds (ChkExitRoom): x<12 Left, x>=244 Right, y<16 Up, y>=186 Down.
  * entry (SetRoomEntryXY/EntryRoomXY): Up->y=184, Down->y=18, Left->x=242,
    Right->x=12; the perpendicular coord is preserved from the exit.

Usage:
  python tools/mgmove.py openings <room>     reachable exit edges (accurate)
  python tools/mgmove.py validate            compare reachable-exits vs stock
                                             connections over the open grid
"""
import sys, os, argparse
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgrender as R, mgmap as M

W, H = 256, 192                            # room pixel size (32x24 tiles)
# Movement is named by the EDGE it heads toward: N=up, S=down, W=left, E=right.
# hitbox leading-edge points per direction: edge -> [(dy,dx),(dy,dx)] (box shape 0)
BOX = {"N": [(-5, -6), (-5, 5)], "S": [(4, -6), (4, 5)],
       "W": [(-4, -8), (3, -8)], "E": [(-4, 7), (3, 7)]}
STEP = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}
THRESH = {"W": lambda x, y: x < 12, "E": lambda x, y: x >= 244,
          "N": lambda x, y: y < 16, "S": lambda x, y: y >= 186}


_DOORS = None
def door_edges(room, doors=None):
    """Edges of a room that hold ANY door/wall-door. Walking into a door
    transitions via the door's own DEST_ROOM (or is blocked until opened), NOT
    the connection table -- so a door-edge is never a connection 'escape'.
    render 1-4 = N/S/W/E door (by type); others (elevator/breakable walls/
    parachute) -> by draw position (y near 0/184 = N/S, x near 0/224 = W/E).

    Pass `doors` (model["doors"]) to use a live snapshot; otherwise the module
    caches load_model()["doors"] once (fine for one-shot CLI runs, but stale in
    a long-running server after a door edit -- callers there should pass it)."""
    global _DOORS
    if doors is None:
        if _DOORS is None:
            _DOORS = M.load_model()["doors"]
        doors = _DOORS
    out = set()
    for did, rend, dy, dx, dest in doors.get(room, []):
        if rend in (1, 2, 3, 4):
            out.add({1: "N", 2: "S", 3: "W", 4: "E"}[rend]); continue
        if dy <= 0x28: out.add("N")
        elif dy >= 0x98: out.add("S")
        if dx <= 0x28: out.add("W")
        elif dx >= 0xC0: out.add("E")
    return out


def solidfn(room, layout=None):
    grid = R.room_solid_grid(room, layout)  # [24][32] of 0/1
    def solid(x, y):
        if 0 <= x < W and 0 <= y < H:
            return grid[y >> 3][x >> 3]
        return 1                           # out of bounds = wall (unless a threshold)
    return solid


def reachable_exits(room, conns, layout=None):
    """BFS the player's reachable pixel positions (seeded from the entry lines of
    connected edges + centre); return the set of edges whose exit threshold the
    player can actually cross. `layout` overrides the on-disk room layout."""
    solid = solidfn(room, layout)
    N, S, Wn, E = conns
    seen, q = set(), deque()

    def standable(x, y):                   # not inside a wall (centre tile free)
        return 0 <= x < W and 0 <= y < H and not solid(x, y)

    def seed(x, y):
        if standable(x, y) and (x, y) not in seen:
            seen.add((x, y)); q.append((x, y))

    if N != 255: [seed(x, 18) for x in range(12, 244)]
    if S != 255: [seed(x, 184) for x in range(12, 244)]
    if Wn != 255: [seed(12, y) for y in range(16, 186)]
    if E != 255: [seed(242, y) for y in range(16, 186)]
    seed(128, 96)                          # spawn fallback

    exits = set()
    while q:
        x, y = q.popleft()
        for d, (dx, dy) in STEP.items():
            nx, ny = x + dx, y + dy
            if THRESH[d](nx, ny):          # crossing the screen edge = an exit
                exits.add(d); continue
            if any(solid(nx + ox, ny + oy) for oy, ox in BOX[d]):
                continue                   # hitbox hit a wall -> blocked
            if (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    return exits


def exit_ranges(room, conns, layout=None):
    """Like reachable_exits but also returns, per reachable edge, the range of
    the PRESERVED (perpendicular) coordinate at which the player crosses it:
      N/S edges -> (minX,maxX);  W/E edges -> (minY,maxY).
    Two edges can be safely connected only if these ranges overlap (the engine
    preserves that coord on entry, so it must land in the dest's opening)."""
    solid = solidfn(room, layout)
    N, S, Wn, E = conns
    seen, q = set(), deque()

    def standable(x, y):
        return 0 <= x < W and 0 <= y < H and not solid(x, y)

    def seed(x, y):
        if standable(x, y) and (x, y) not in seen:
            seen.add((x, y)); q.append((x, y))

    if N != 255: [seed(x, 18) for x in range(12, 244)]
    if S != 255: [seed(x, 184) for x in range(12, 244)]
    if Wn != 255: [seed(12, y) for y in range(16, 186)]
    if E != 255: [seed(242, y) for y in range(16, 186)]
    seed(128, 96)
    rng = {}

    def note(d, coord):
        lo, hi = rng.get(d, (999, -999))
        rng[d] = (min(lo, coord), max(hi, coord))

    while q:
        x, y = q.popleft()
        for d, (dx, dy) in STEP.items():
            nx, ny = x + dx, y + dy
            if THRESH[d](nx, ny):
                note(d, x if d in "NS" else y); continue
            if any(solid(nx + ox, ny + oy) for oy, ox in BOX[d]):
                continue
            if (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    return rng


def cmd_ranges(args):
    conns = M.load_model()["connections"]
    rng = exit_ranges(args.room, conns[args.room])
    print("room %d exit-opening ranges (preserved coord):" % args.room)
    for d in "NSWE":
        if d in rng:
            print("  %s: %s %d..%d" % (d, "X" if d in "NS" else "Y", *rng[d]))


def cmd_checklink(args):
    """Is a proposed bidirectional connection A.<dir>=B safe? Compares A's exit
    opening on <dir> with B's opening on the opposite edge: they must overlap,
    and ideally match (each contained in the other) so neither side strands the
    player on entry (the engine preserves the perpendicular coordinate)."""
    OPP = {"N": "S", "S": "N", "W": "E", "E": "W"}
    conns = M.load_model()["connections"]
    A, d, B = args.a, args.dir.upper(), args.b
    o = OPP[d]
    rA = exit_ranges(A, conns[A]).get(d)
    rB = exit_ranges(B, conns[B]).get(o)
    print("proposed link  %d.%s = %d   (reverse %d.%s = %d)" % (A, d, B, B, o, A))
    print("  %d.%s opening: %s" % (A, d, rA))
    print("  %d.%s opening: %s" % (B, o, rB))
    if not rA or not rB:
        print("  UNSAFE: one side has no walkable opening there (would strand/dead).")
        return
    lo, hi = max(rA[0], rB[0]), min(rA[1], rB[1])
    if lo > hi:
        print("  UNSAFE: openings don't overlap -> player enters into a wall.")
    elif abs(rA[0] - rB[0]) <= 8 and abs(rA[1] - rB[1]) <= 8:
        print("  SAFE: openings match (bidirectional).")
    else:
        print("  PARTIAL: overlap %d..%d but ranges differ -> safe only where they "
              "overlap; exits outside it strand. Carve openings to match." % (lo, hi))


def cmd_openings(args):
    conns = M.load_model()["connections"]
    r = args.room
    if r >= len(conns):
        sys.exit("room %d has no connection entry" % r)
    ex = reachable_exits(r, conns[r])
    f = lambda v: "-" if v == 255 else str(v)
    print("room %d conn N=%s S=%s W=%s E=%s" %
          (r, f(conns[r][0]), f(conns[r][1]), f(conns[r][2]), f(conns[r][3])))
    print("reachable exits (accurate): %s" % ("".join(sorted(ex)) or "(none)"))


_DIDX = {"N": 0, "S": 1, "W": 2, "E": 3}


def room_escapes(room, conns, layout=None, doors=None):
    """The walk-off-escape edges (subset of 'NSWE') contributed by ONE room: a
    reachable edge with no connection and no door. Each room is independent of
    every other, so a caller editing one room can recompute just that room's
    escapes instead of flood-filling all 122 (see editor server validation)."""
    if room >= len(conns):
        return set()
    ex = reachable_exits(room, conns[room], layout)
    de = door_edges(room, doors)
    return {d for d in "NSWE"
            if d in ex and conns[room][_DIDX[d]] == 255 and d not in de}


def escapes_for(conns, layouts=None, doors=None):
    """Set of (room,edge) where the player can walk off a no-exit, no-door edge."""
    out = set()
    for r in range(122):
        lay = layouts.get(r) if layouts else None
        for d in room_escapes(r, conns, lay, doors):
            out.add((r, d))
    return out


def cmd_validate(args):
    conns = M.load_model()["connections"]
    cur = escapes_for(conns)
    stock = escapes_for(conns, R._orig_layouts())   # same layouts unless edited
    new = sorted(cur - stock)
    print("ACCURATE movement model over open grid (rooms 0-121):")
    print("  stock baseline escapes (door-dest / special rooms): %d" % len(stock))
    print("  escapes introduced by current edits: %d %s" % (len(new), new))
    if not new:
        print("  -> no NEW player-walk-off-into-nowhere created. SAFE.")


def main():
    ap = argparse.ArgumentParser(description="Engine-accurate player movement model")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("openings"); sp.add_argument("room", type=int); sp.set_defaults(fn=cmd_openings)
    sp = sub.add_parser("ranges"); sp.add_argument("room", type=int); sp.set_defaults(fn=cmd_ranges)
    sp = sub.add_parser("checklink"); sp.add_argument("a", type=int)
    sp.add_argument("dir"); sp.add_argument("b", type=int); sp.set_defaults(fn=cmd_checklink)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
