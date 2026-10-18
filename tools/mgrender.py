#!/usr/bin/env python3
"""
mgrender.py - render a Metal Gear (MSX) room to PNG so layouts can be authored
and verified visually (the missing piece for the NIGHTJAR map rework).

Recipe (from Banks0123.asm RenderRoom / UnpackMetatiles / LoadRoomTiles):
  * room        = 8x6 metatiles (data/rooms.asm RoomNNN, codec via mgmap).
  * metatile    = 4x4 tiles, 16 bytes, 1-based id, in Metatiles{1..6}
                  (data/rooms.asm). Room's set = idxMetatileSet[MetaTileSetIDs[room]-1].
  * tiles       = 3bpp (Load3bppTiles); the room's gfx tileset = idxTileSets[
                  RoomGfxSetIds[room]] -> TileSet* config of up-to-3 blocks:
                    normal block flags<0x40 : count,dest,gfx -> decode count tiles to dest
                    flip   block bit6        : reuse prev count+gfx, mirror -> dest
                    colli  block bit7        : stop (collision tiles, not drawn)
                  colortab = ColorsTileset = [1,3,5,8,9,Ch,Eh,Fh].
  * palette     = DefaultPalette (16 colors) overlaid by RoomPalette[IdsRoomPal[room]]
                  (V9938 RB0G: byte0=(R<<4)|B, byte1=G; channels 0-7).

Usage:
  python tools/mgrender.py <room> [-o out.png] [--scale N]
  python tools/mgrender.py validate <room>     # render + report vs room_images/
"""
import sys, os, re, argparse
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mggfx, mgmap, mgproj

ROOM_W, ROOM_H = 8, 6
MT = 4                                  # tiles per metatile side (4x4)


def _c3(v):                             # 3-bit channel -> 0..255
    return (v & 7) * 255 // 7


def default_palette():
    v = mggfx.parse_block("Banks0123.asm", "DefaultPalette")
    pal = []
    for i in range(16):
        rb, g = v[2 * i], v[2 * i + 1]
        pal.append((_c3(rb >> 4), _c3(g), _c3(rb)))     # R, G, B
    return pal


def apply_room_palette(pal, label):
    v = mggfx.parse_block("data/palettes.asm", label)
    i = 0
    while i + 2 < len(v) and v[i] != 0xFF:
        idx, rb, g = v[i], v[i + 1], v[i + 2]
        pal[idx & 15] = (_c3(rb >> 4), _c3(g), _c3(rb))
        i += 3
    return pal


def nibble(file, label, room):
    v = mgmap.parse_flat(mgmap._read(file), label)
    byte = v[room // 2]
    return (byte >> 4) & 0xF if room % 2 == 0 else byte & 0xF


EXT_TS_FILE = "BanksExtGfx.asm"     # extended tilesets (gfx ids 8-15), 512KB ROM


def find_gfx_file(label):
    gdir = mgproj.path("gfx")
    for fn in os.listdir(gdir):
        if not fn.endswith(".asm"):
            continue
        for ln in open(os.path.join(gdir, fn), encoding='latin-1'):
            if re.match(r'^%s:' % re.escape(label), ln):
                return "gfx/" + fn
    extp = mgproj.path(EXT_TS_FILE)          # extended gfx live at the source root
    if os.path.exists(extp):
        for ln in open(extp, encoding='latin-1'):
            if re.match(r'^%s:' % re.escape(label), ln):
                return EXT_TS_FILE
    raise KeyError("gfx label not found: %s" % label)


def resolve_tileset(gid):
    """(TileSet* label, source .asm file) for gfx-tileset id `gid`. ids 0-7 are
    the stock tilesets (idxTileSets in roomtileset.asm); 8-15 are extended
    tilesets (idxTileSetsExt in BanksExtGfx.asm)."""
    if gid >= 8 and os.path.exists(mgproj.path(EXT_TS_FILE)):
        order = mgmap.parse_label_order(mgmap._read(EXT_TS_FILE), "idxTileSetsExt")
        return order[gid - 8], EXT_TS_FILE
    order = mgmap.parse_label_order(mgmap._read("data/roomtileset.asm"), "idxTileSets")
    return order[gid], "data/roomtileset.asm"


def flip_tile(tile):
    return [row[::-1] for row in tile]


def tileset_config_tokens(tslabel, fname="data/roomtileset.asm"):
    """Collect a TileSet* config's db/dw operands, spanning the blank lines that
    separate its 3 blocks, until the next label/section. (block_tokens stops at
    blanks, which would drop blocks 2-3 -> tanks/crates render black.)"""
    lines = mgmap._read(fname)
    toks, started = [], False
    for ln in lines:
        code = mgmap._code(ln)
        m = re.match(r'^%s:\s*(db|dw)\s+(.*)$' % re.escape(tslabel), code)
        if m:
            started = True
            for t in mgmap._toks(m.group(2)):
                toks.append(("lbl", t) if m.group(1) == "dw" else ("num", mgmap._vals(t)[0]))
            continue
        if not started:
            continue
        m2 = re.match(r'^\s+(db|dw)\s+(.*)$', code)
        if m2:
            for t in mgmap._toks(m2.group(2)):
                toks.append(("lbl", t) if m2.group(1) == "dw" else ("num", mgmap._vals(t)[0]))
        elif re.match(r'^\w+:', code):       # next label/section ends the config
            break
    return toks


def tileset_tiles(tslabel, fname="data/roomtileset.asm"):
    """Build {tile_number: 8x8 tile of palette-index} for a TileSet* config,
    plus the shared crate tiles (loaded by LoadGfxCrates to tiles 0A0h/0D0h)."""
    toks = tileset_config_tokens(tslabel, fname)
    colors = mggfx.parse_block("Banks0123.asm", "ColorsTileset")[:8]
    tiles = {}
    i = blocks = 0
    prev_count = prev_gfx = None
    while blocks < 3 and i < len(toks):
        flags = toks[i][1]
        if flags & 0x80:                      # collision block: stop
            break
        if flags & 0x40:                      # flip block: reuse prev count+gfx
            dest, cnt, gfx, flip = toks[i + 1][1], prev_count, prev_gfx, True
            i += 2
        else:
            cnt, dest, gfx = toks[i + 1][1], toks[i + 2][1], toks[i + 3][1]
            prev_count, prev_gfx, flip = cnt, gfx, False
            i += 4
        data = mggfx.parse_block(find_gfx_file(gfx), gfx)
        for k, tile in enumerate(mggfx.decode_tiles(data, 3, cnt, colors)):
            tiles[dest + k] = flip_tile(tile) if flip else tile
        blocks += 1
    # power-switch / elevator-panel tiles: LoadPowSwitTiles -> VRAM 9048h = tile 092h (4)
    pdata = mggfx.parse_block(find_gfx_file("gfxPowSwitch"), "gfxPowSwitch")
    for k, tile in enumerate(mggfx.decode_tiles(pdata, 3, 4, colors)):
        tiles[0x92 + k] = tile
    # shared crate tiles: LoadGfxCrates -> VRAM 9400h=tile 0A0h (8), flip 9840h=0D0h (8)
    if "MetalGear" not in tslabel:            # crates skipped for the Metal Gear tileset
        cdata = mggfx.parse_block(find_gfx_file("GfxCrates"), "GfxCrates")
        for k, tile in enumerate(mggfx.decode_tiles(cdata, 3, 8, colors)):
            tiles[0xA0 + k] = tile
            tiles[0xD0 + k] = flip_tile(tile)
    return tiles


BLANK = [[0] * 8 for _ in range(8)]


def collision_source(gid):
    """(file, label) of the CollTiles* bitmap for gfx-tileset `gid`, or (None, None)
    if out of range. Ext tilesets (gid>=8) live in their own file when present."""
    if gid >= 8 and os.path.exists(mgproj.path(EXT_TS_FILE)):
        file, idx_label, gid = EXT_TS_FILE, "IdxColisTilesExt", gid - 8
    else:
        file, idx_label = "data/roomtileset.asm", "IdxColisTiles"  # 7 entries, tileset 0..6
    order = mgmap.parse_label_order(mgmap._read(file), idx_label)
    return (file, order[gid]) if gid < len(order) else (None, None)


def tileset_collision(gid):
    """{tile_number: 1 if solid else 0} for gfx-tileset id `gid`. The 32-byte
    CollTiles* bitmap is expanded MSB-first (LoadColliTiles: rlca/and 1), so
    tile T is solid iff bit (7-(T&7)) of byte T>>3 is set."""
    file, label = collision_source(gid)
    if not label:
        return {}
    bits = mgmap.parse_flat(mgmap._read(file), label)
    return {T: (bits[T >> 3] >> (7 - (T & 7))) & 1 for T in range(min(256, len(bits) * 8))}


def room_solid_grid(room, layout=None):
    """32x24 grid of 0/1 (solid) for a room, by expanding metatiles -> tiles ->
    per-tile collision. `layout` overrides the on-disk 48 metatile bytes."""
    dlayout, mdefs, _, _ = load_room_assets(room)
    if layout is None:
        layout = dlayout
    gid = nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    coll = tileset_collision(gid)
    grid = [[0] * (ROOM_W * MT) for _ in range(ROOM_H * MT)]
    for my in range(ROOM_H):
        for mx in range(ROOM_W):
            M = layout[my * ROOM_W + mx]
            base = 16 * (M - 1) if M else None
            for ty in range(MT):
                idx = (base + ty * MT) if base is not None else None
                for tx in range(MT):
                    tnum = mdefs[idx + tx] if (idx is not None and idx + tx < len(mdefs)) else 0
                    grid[my * MT + ty][mx * MT + tx] = coll.get(tnum, 0)
    return grid


def load_room_assets(room):
    """Return (layout[48], mdefs, tiles{num:tile}, pal[16]) for a room."""
    rl = mgmap._read("data/rooms.asm")
    order = mgmap.parse_label_order(rl, "idxRooms")
    lab = order[room]
    s, e = mgmap.find_block(rl, lab)
    layout = mgmap.block_vals(rl, s, e)
    msid = nibble("data/rooms.asm", "MetaTileSetIDs", room)
    mset = mgmap.parse_label_order(rl, "idxMetatileSet")[msid - 1]
    mdefs = mgmap.parse_flat(mgmap._read("data/metatiles.asm"), mset)
    gid = nibble("data/roomtileset.asm", "RoomGfxSetIds", room)
    tslabel, tsfile = resolve_tileset(gid)
    tiles = tileset_tiles(tslabel, tsfile)
    pal = room_base_palette()
    pid = nibble("data/palettes.asm", "IdsRoomPal", room)
    porder = mgmap.parse_label_order(mgmap._read("data/palettes.asm"), "idxRoomPalettes")
    apply_room_palette(pal, porder[pid])
    return layout, mdefs, tiles, pal


# Indices the room palettes never touch (12/14/15 etc.) keep whatever the LAST
# palette load left them: the engine's SetPalette only writes the colours a block
# lists. Before gameplay the radio briefing / weapon menu load PalMenuWeapon +
# RadioPalette, which set idx 12->gray, 14->white, 15->black; SetRoomPal then only
# overrides 1,3,5,9, so those persist in-room. The pristine DefaultPalette (green
# idx12, white idx15) is NEVER what a room actually shows. Model that persistent
# base so the editor matches the ROM (verified pixel-exact vs room_images/).
def room_base_palette():
    pal = default_palette()
    for lbl in ("PalMenuWeapon", "RadioPalette"):
        apply_room_palette(pal, lbl)
    return pal


def draw_metatile(px, ox, oy, M, mdefs, tiles, pal):
    """Blit one 4x4-tile metatile (32x32 px) at pixel (ox,oy)."""
    base = 16 * (M - 1) if M else None
    for ty in range(MT):
        for tx in range(MT):
            tnum = mdefs[base + ty * MT + tx] if base is not None else 0
            tile = tiles.get(tnum, BLANK)
            for r in range(8):
                for c in range(8):
                    px[ox + tx * 8 + c, oy + ty * 8 + r] = pal[tile[r][c] & 15]


def render_room(room, scale=2, collision=False, layout=None):
    dlayout, mdefs, tiles, pal = load_room_assets(room)
    if layout is None:
        layout = dlayout
    if len(layout) != ROOM_W * ROOM_H:
        raise ValueError("room %d is a placeholder/empty" % room)
    W, H = ROOM_W * MT * 8, ROOM_H * MT * 8
    img = Image.new("RGB", (W, H), (0, 0, 0))
    px = img.load()
    for my in range(ROOM_H):
        for mx in range(ROOM_W):
            draw_metatile(px, mx * MT * 8, my * MT * 8,
                          layout[my * ROOM_W + mx], mdefs, tiles, pal)
    if collision:                              # red tint on solid (wall) tiles
        grid = room_solid_grid(room, layout)
        for ty in range(ROOM_H * MT):
            for tx in range(ROOM_W * MT):
                if grid[ty][tx]:
                    for r in range(8):
                        for c in range(8):
                            x, y = tx * 8 + c, ty * 8 + r
                            R0, G0, B0 = px[x, y]
                            px[x, y] = (min(255, R0 + 90), G0 // 2, B0 // 2)
    if scale != 1:
        img = img.resize((W * scale, H * scale), Image.NEAREST)
    return img


def check_safety(room, conns, layout=None):
    """Flood-fill the walkable tiles the player can actually reach (seeded from
    the entrances = exit edges, plus the room centre as a spawn fallback). If
    that reachable region touches a no-exit edge (conn==255), the player can
    walk off into a nonexistent room -> black screen. Returns the bad dirs."""
    from collections import deque
    grid = room_solid_grid(room, layout)
    rows, cols = ROOM_H * MT, ROOM_W * MT
    seen, q = set(), deque()

    def seed(r, c):
        if 0 <= r < rows and 0 <= c < cols and grid[r][c] == 0 and (r, c) not in seen:
            seen.add((r, c)); q.append((r, c))

    N, S, W, E = conns
    if N != 255: [seed(0, c) for c in range(cols)]
    if S != 255: [seed(rows - 1, c) for c in range(cols)]
    if W != 255: [seed(r, 0) for r in range(rows)]
    if E != 255: [seed(r, cols - 1) for r in range(rows)]
    seed(rows // 2, cols // 2)                 # player-spawn fallback
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            seed(r + dr, c + dc)

    bad = []
    if N == 255 and any((0, c) in seen for c in range(cols)): bad.append("N")
    if S == 255 and any((rows - 1, c) in seen for c in range(cols)): bad.append("S")
    if W == 255 and any((r, 0) in seen for r in range(rows)): bad.append("W")
    if E == 255 and any((r, cols - 1) in seen for r in range(rows)): bad.append("E")
    return bad


def render_atlas(room, cols=16, scale=2, collision=False):
    """Render every metatile of `room`'s metatile set, labeled with its id.
    If collision: red-tint solid tiles so walls (solid) vs floor (walkable) are
    obvious when picking metatiles to author with."""
    from PIL import ImageDraw
    _, mdefs, tiles, pal = load_room_assets(room)
    coll = tileset_collision(nibble("data/roomtileset.asm", "RoomGfxSetIds", room)) if collision else {}
    n = len(mdefs) // 16                       # metatile count (16 bytes each)
    cell, pad, lab = MT * 8, 4, 10             # 32px tile + label strip
    rows = (n + cols - 1) // cols
    cw, ch = cell + pad, cell + lab + pad
    img = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    px = img.load()
    for m in range(n):
        gx, gy = (m % cols) * cw, (m // cols) * ch
        draw_metatile(px, gx, gy + lab, m + 1, mdefs, tiles, pal)   # ids are 1-based
        if collision:
            mt = mdefs[16 * m:16 * m + 16]
            for ty in range(MT):
                for tx in range(MT):
                    if coll.get(mt[ty * MT + tx], 0):
                        for r in range(8):
                            for c in range(8):
                                x, y = gx + tx * 8 + c, gy + lab + ty * 8 + r
                                R0, G0, B0 = px[x, y]
                                px[x, y] = (min(255, R0 + 90), G0 // 2, B0 // 2)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for m in range(n):
        gx, gy = (m % cols) * cw, (m // cols) * ch
        d.text((gx * scale + 2, gy * scale), "%02X" % (m + 1), fill=(255, 255, 0))
    return img


def cmd_render(args):
    img = render_room(args.room, args.scale, getattr(args, "collision", False))
    out = args.o or ("tools/room_%03d.png" % args.room)
    img.save(mgproj.repo_path(out))
    print("rendered room %d -> %s (%dx%d)" % (args.room, out, img.width, img.height))


def cmd_validate(args):
    out = "tools/room_%03d.png" % args.room
    render_room(args.room, 2).save(mgproj.repo_path(out))
    ref = mgproj.repo_path(os.path.join("room_images", "MGEAR1_%04d.png" % args.room))
    print("rendered -> %s" % out)
    print("reference: %s (%s)" % (ref, "exists" if os.path.exists(ref) else "MISSING"))


def _orig_layouts():
    """Parse the git-HEAD (stock) version of every room's layout, for regression
    comparison. Returns {room: [48 bytes]} (absent if unchanged-from-disk fails).
    World-aware (D3): baselines the ACTIVE world's rooms file, label suffix
    stripped so room labels parse as stock names."""
    import subprocess
    try:
        gitpath = (mgproj.git_prefix()
                   + mgmap.world_file("data/rooms.asm").replace("\\", "/"))
        txt = subprocess.check_output(["git", "show", "HEAD:" + gitpath],
                                      cwd=mgproj.repo_root(), encoding="latin-1")
        if mgmap.current_world():
            import re as _re
            txt = _re.sub(r'_w%d\b' % mgmap.current_world(), '', txt)
    except Exception as e:
        print("  (no git baseline: %s)" % e); return {}
    lines = txt.splitlines()
    order = mgmap.parse_label_order(lines, "idxRooms")
    out = {}
    for room, lab in enumerate(order):
        try:
            s, e = mgmap.find_block(lines, lab)
            v = mgmap.block_vals(lines, s, e)
            if len(v) == ROOM_W * ROOM_H:
                out[room] = v
        except KeyError:
            pass
    return out


def cmd_safety(args):
    """Regression lint: flag rooms whose edit opened a NEW reachable walk-off at a
    no-exit edge (vs the stock git-HEAD layout). Robust to the escape model's
    imprecision -- only *newly* opened edges are reported."""
    conns = mgmap.load_model()["connections"]
    orig = _orig_layouts()
    hi = args.room + 1 if args.room is not None else 122
    lo = args.room if args.room is not None else 0
    flagged = 0
    for room in range(lo, hi):
        if room >= len(conns):
            continue
        cur = check_safety(room, conns[room])
        base = check_safety(room, conns[room], orig[room]) if room in orig else []
        new = [d for d in cur if d not in base]
        if new:
            flagged += 1
            print("room %3d UNSAFE: edit opened walk-off at no-exit edge(s) %s"
                  % (room, "/".join(new)))
    print("checked rooms %d..%d : %d newly-unsafe" % (lo, hi - 1, flagged))


def cmd_atlas(args):
    img = render_atlas(args.room, args.cols, args.scale, getattr(args, "collision", False))
    out = args.o or ("tools/atlas_room%d.png" % args.room)
    img.save(mgproj.repo_path(out))
    print("metatile atlas for room %d's set -> %s (%dx%d)"
          % (args.room, out, img.width, img.height))


def main():
    ap = argparse.ArgumentParser(description="Render a Metal Gear MSX room to PNG")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("render"); sp.add_argument("room", type=int)
    sp.add_argument("-o"); sp.add_argument("--scale", type=int, default=2)
    sp.add_argument("--collision", action="store_true", help="red-tint solid (wall) tiles")
    sp.set_defaults(fn=cmd_render)
    sp = sub.add_parser("safety"); sp.add_argument("room", type=int, nargs="?")
    sp.set_defaults(fn=cmd_safety)
    sp = sub.add_parser("validate"); sp.add_argument("room", type=int)
    sp.set_defaults(fn=cmd_validate)
    sp = sub.add_parser("atlas"); sp.add_argument("room", type=int)
    sp.add_argument("--collision", action="store_true", help="red-tint solid tiles (wall vs floor)")
    sp.add_argument("-o"); sp.add_argument("--cols", type=int, default=16)
    sp.add_argument("--scale", type=int, default=2); sp.set_defaults(fn=cmd_atlas)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
