"""
mgsprite.py -- decode Metal Gear MSX2 enemy/actor sprites and composite them
onto a room-sized overlay, for the map editor's "actor sprites" overlay.

Pipeline (mirrors the engine):
  * a spriteset (SprSet*) is a list of (firstPattern, gfxLabel) segments that
    UnpackGfx-decompress into the VRAM sprite-pattern generator (base 0F800h).
    Pattern N lives at byte N*8.
  * an actor ID indexes NumSprEnemies (plane count), idxActorSprCols (per-plane
    colour byte: low nibble = colour, bit6 = CC colour-OR with previous plane)
    and -- via a curated default-pose table here -- idxSprites (the sprite def:
    a control byte + pattern list, with per-plane offsets either inline as
    (dy,dx,pat) triples or from a shared SprOffsetsN table).
  * MSX2 16x16 sprites = 4 8x8 quadrants (TL,BL,TR,BR), 1bpp; colour comes from
    the plane's colour byte, CC planes OR their colour into the lower plane.
  * palette = DefaultPalette + the spriteset's SprsetPal* overrides.

Public:
  actor_sprite(id_token)            -> Sprite | None   (cached)
  render_overlay(actors, scale)     -> (PIL RGBA 256*s x 192*s, [bbox|None])
  actor_bbox(id_token)              -> (x,y,w,h) anchor-relative, or None
"""
import os, re, functools
from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj, mgmap, mgrender, mggfx

ROOM_W_PX, ROOM_H_PX = 256, 192
SPR_DEFS_F = "data/actorspriteattr.asm"
SPRSETS_F  = "data/spritesets.asm"
SPRGFX_F   = "gfx/sprites.asm"
ENUMS_F    = "constants/Enums.asm"
ENGINE_F   = "Banks0123.asm"          # SprOffsets*, idxSprOffsets, DefaultPalette
PALS_F     = "data/palettes.asm"
ITEMGFX_F  = "gfx/items.asm"          # GfxItems 3bpp sheet (loaded to VRAM page1 0B000h)
ITEMS_F    = "data/itemsinrooms.asm"  # idxRoomItemsIdx / idxRoomItems / ItemXxx blocks
ITEMXY_F   = "data/itemgfxxy.asm"     # ItemGfxXY  (page1 coords, items)
WEAPXY_F   = "data/weapongfxxy.asm"   # WeaponGfxXY (page1 coords, weapons id 1..8)
SPRSETS_F  = "data/spritesets.asm"    # SpritesetRooms[room] -> spriteset id (sprite palette)
ITEM_ROOM_BASE = 122                  # idxRoomItemsIdx[room-122]
COLORS_ITEMS = (0x00, 0x06, 0x07, 0x08, 0x0A, 0x0C, 0x0E, 0x0F)  # ColorsItems 3bpp->reg map


def _s8(v):                            # byte -> signed offset
    return v - 256 if v > 127 else v


def clear_caches():
    """Drop every lru_cache in this module -- call after an .asm write so decoded
    sprites/items/palettes reflect the edit."""
    for v in list(globals().values()):
        if hasattr(v, "cache_clear"):
            v.cache_clear()


mgproj.on_switch(clear_caches)


# ---- low-level asm parsing -------------------------------------------------
@functools.lru_cache(maxsize=None)
def _enum_ids():
    """ID_* token -> integer value, from constants/Enums.asm."""
    out = {}
    for ln in open(mgproj.path(ENUMS_F), encoding="latin-1"):
        m = re.match(r'^(ID_\w+):\s*equ\s+([0-9A-Fa-fh]+)', ln.split(';')[0].strip())
        if m:
            t = m.group(2)
            out[m.group(1)] = int(t[:-1], 16) if t[-1] in "hH" else int(t)
    return out


@functools.lru_cache(maxsize=None)
def _consts():
    """All `NAME: equ value` constants from constants/Enums.asm (item/weapon ids)."""
    out = {}
    for ln in open(mgproj.path(ENUMS_F), encoding="latin-1"):
        m = re.match(r'^(\w+):\s*equ\s+([0-9A-Fa-fh]+)', ln.split(';')[0].strip())
        if m:
            t = m.group(2)
            try:
                out[m.group(1)] = int(t[:-1], 16) if t[-1] in "hH" else int(t)
            except ValueError:
                pass
    return out


def _flat(path, label):
    """Flat byte list for a `label: db ...` block (+ db continuations)."""
    return mggfx.parse_block(path, label)


@functools.lru_cache(maxsize=None)
def _dw_words(path, label):
    """Read a numeric `label: dw N / dw N ...` table -> tuple of ints."""
    out, coll = [], False
    for ln in open(mgproj.path(path), encoding="latin-1").read().splitlines():
        code = ln.split(';', 1)[0].rstrip()
        m = re.match(r'^(\w+):\s*dw\s+(.*)$', code.strip())
        if m and m.group(1) == label:
            out.append(m.group(2)); coll = True; continue
        if coll:
            m2 = re.match(r'^\s*dw\s+(.*)$', code)
            if m2:
                out.append(m2.group(1))
            elif code.strip() == "":
                continue
            else:
                break
    vals = []
    for t in out:
        t = t.strip()
        vals.append(int(t[:-1], 16) if t and t[-1] in "hH" else int(t))
    return tuple(vals)


@functools.lru_cache(maxsize=None)
def _label_order(path, idx_label):
    return tuple(mgmap.parse_label_order(mgmap._read(path), idx_label))


# ---- RLE (UnpackGfx) -------------------------------------------------------
def unpack_gfx(data):
    """Expand the engine's UnpackGfx RLE into a flat byte list.
      bit7 set  -> literal run of (b & 7Fh) bytes  (0x80 = set-new-addr, skipped)
      bit7 clear-> fill run: next byte repeated b times
      0x00      -> end"""
    out, i, n = [], 0, len(data)
    while i < n:
        b = data[i]; i += 1
        if b == 0:
            break
        if b & 0x80:
            cnt = b & 0x7F
            if cnt == 0:                # 0x80 new VRAM address (not used mid-actor)
                i += 2; continue
            out += data[i:i + cnt]; i += cnt
        else:
            out += [data[i]] * b; i += 1
    return out


def pack_gfx(dec):
    """Inverse of unpack_gfx: encode a flat byte list into an UnpackGfx RLE stream.
    Greedy: a run of >=3 identical bytes -> fill run (count<128, value); otherwise a
    literal run (0x80|len, len<=0x7F bytes), broken when a >=3 identical run begins.
    Terminated by 0x00. Not guaranteed byte-identical to the original encoding, but
    unpack_gfx(pack_gfx(x)) == x for every Spr* label (see selftest)."""
    out, i, n = [], 0, len(dec)
    while i < n:
        j = i
        while j < n and dec[j] == dec[i] and (j - i) < 127:
            j += 1
        if j - i >= 3:                                 # fill run
            out += [j - i, dec[i]]; i = j
        else:                                          # literal run
            k, lit = i, []
            while k < n and len(lit) < 0x7F:
                if k + 2 < n and dec[k] == dec[k + 1] == dec[k + 2]:
                    break                              # a fill run starts -> stop literal
                lit.append(dec[k]); k += 1
            out += [0x80 | len(lit)] + lit; i = k
    out.append(0)
    return out


# ---- spritesets -> VRAM pattern buffer -------------------------------------
@functools.lru_cache(maxsize=None)
def _spriteset_labels():
    return _label_order(SPRSETS_F, "idxSprSet")


@functools.lru_cache(maxsize=None)
def _spriteset_segments(label):
    """SprSet* block -> tuple of (firstPattern, gfxLabel) until 0FFh."""
    lines = mgmap._read(SPRSETS_F)
    _, _, rows = mgmap.block_tokens(lines, label)
    flat = []                            # interleaved: db firstPat / dw gfxLabel
    for mn, toks in rows:
        for t in toks:
            flat.append(t)
    segs, i = [], 0
    while i < len(flat):
        t = flat[i]
        v = int(t[:-1], 16) if t[-1] in "hH" else (int(t) if t.lstrip('-').isdigit() else None)
        if v == 0xFF:
            break
        segs.append((v, flat[i + 1])); i += 2
    return tuple(segs)


@functools.lru_cache(maxsize=None)
def vram_for_spriteset(spriteset_idx):
    """Build the 256-pattern * 8-byte VRAM generator buffer for a spriteset id."""
    buf = bytearray(256 * 8)
    label = _spriteset_labels()[spriteset_idx]
    for first, gfx in _spriteset_segments(label):
        dec = unpack_gfx(_flat(SPRGFX_F, gfx))
        base = first * 8
        for k, v in enumerate(dec):
            if base + k < len(buf):
                buf[base + k] = v
    return bytes(buf)


def _sprite_quad(buf, pattern):
    """16x16 list of rows (each 16 ints 0/1) for a sprite pattern number."""
    base = pattern * 8
    rows = []
    for r in range(16):
        row = []
        for c in range(16):
            bi = base + (0 if c < 8 else 16) + r
            row.append((buf[bi] >> (7 - (c & 7))) & 1 if bi < len(buf) else 0)
        rows.append(row)
    return rows


# ---- sprite definitions (idxSprites) ---------------------------------------
@functools.lru_cache(maxsize=None)
def _idx_sprites():
    return _label_order(SPR_DEFS_F, "idxSprites")


@functools.lru_cache(maxsize=None)
def _sproffsets_index():
    """idxSprOffsets order -> SprOffsetsN labels (predefined offset tables)."""
    return _label_order(ENGINE_F, "idxSprOffsets")


@functools.lru_cache(maxsize=None)
def _sproffsets(label):
    flat = _flat(SPR_DEFS_F, label)            # SprOffsets* live in actorspriteattr.asm
    return tuple((_s8(flat[i]), _s8(flat[i + 1])) for i in range(0, len(flat) - 1, 2))


def _sprite_planes(pose_label, nplanes):
    """Return [(dy, dx, pattern), ...] for a sprite-def label, nplanes planes.

    MSX sprite Y is an 8-bit value, so `spriteY = (actorY + dy) & 0xFF` wraps at
    256. An offset far ABOVE the anchor (dy <= -64 — in stock data only the
    rolling-barrel end-cap planes at -128) is really a mod-256 wrap to the BOTTOM
    of the sprite column, not a plane 128px overhead. Fold it to +128 so the
    sprite renders (and its bbox bounds) as the continuous cylinder the hardware
    draws. Real upward extents (tall bosses) never exceed -48, so they're safe."""
    flat = _flat(SPR_DEFS_F, pose_label)
    if not flat:
        return []
    head = flat[0]
    if 0x91 <= head <= 0xA5:                       # predefined shared offsets
        offs = _sproffsets(_sproffsets_index()[head - 0x91])
        pats = flat[1:]
        out = []
        for k, p in enumerate(pats[:nplanes] if nplanes else pats):
            dy, dx = offs[k] if k < len(offs) else (0, 0)
            out.append((dy, dx, p))
    else:                                          # inline (dy, dx, pattern) triples
        out = []
        for i in range(0, len(flat) - 2, 3):
            out.append((_s8(flat[i]), _s8(flat[i + 1]), flat[i + 2]))
        out = out[:nplanes] if nplanes else out
    return [(dy + 256 if dy <= -64 else dy, dx, p) for (dy, dx, p) in out]


# ---- per-enemy attribute tables --------------------------------------------
@functools.lru_cache(maxsize=None)
def _num_spr():
    return _flat(SPR_DEFS_F, "NumSprEnemies")


@functools.lru_cache(maxsize=None)
def _actor_col_labels():
    return _label_order(SPR_DEFS_F, "idxActorSprCols")


@functools.lru_cache(maxsize=None)
def _color_stream():
    """Physical ROM byte stream of the ActorSprColors* region + each label's start
    offset. The engine's SetActorSprColors loop reads NumSprites colour bytes
    sequentially from a colour label, spilling past a short table into the bytes of
    whatever table physically follows (ROM adjacency) -- e.g. Coward Duck has 4
    planes but ActorSprColors13 is only `db 2, 4Dh`, so planes 2-3 come from the
    next label (ActorSprColors8 = 2, 4Dh). Returns (bytes_tuple, {label: offset})."""
    flat, offsets, capturing = [], {}, False
    for ln in open(mgproj.path(SPR_DEFS_F), encoding="latin-1"):
        code = ln.split(';', 1)[0].rstrip()
        m = re.match(r'^(\w+):\s*(.*)$', code)
        label, rest = (m.group(1), m.group(2)) if m else (None, code.strip())
        if label and re.match(r'ActorSprColors\d+$', label):
            capturing = True
        if not capturing:
            continue
        if label == "ActorSprNoColor":                 # end of the region
            offsets[label] = len(flat)
            break
        if label:
            offsets[label] = len(flat)
        m2 = re.match(r'^db\s+(.*)$', rest.strip())
        if m2:
            for tok in m2.group(1).split(','):
                tok = tok.strip()
                if tok:
                    flat.append(int(tok[:-1], 16) if tok[-1] in "hH" else int(tok))
    return tuple(flat), offsets


def _actor_colors(enemy_id, nplanes):
    labels = _actor_col_labels()
    if not (1 <= enemy_id <= len(labels)):
        return [0x0F] * nplanes
    lab = labels[enemy_id - 1]
    if lab == "ActorSprNoColor":
        return [0x0F] * nplanes
    flat, offsets = _color_stream()
    off = offsets.get(lab)
    if off is None:
        return [0x0F] * nplanes
    return [flat[off + k] if off + k < len(flat) else 0x0F for k in range(nplanes)]


# ---- palette ---------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _sprset_pal_labels():
    return _label_order(PALS_F, "idxSprSetPals")


def _apply_pal_block(pal, path, label):
    """Apply a `label: db idx, RB, G ... 0FFh` palette-override block (same encoding
    as mgrender.apply_room_palette, but from an arbitrary file/label)."""
    v = _flat(path, label)
    i = 0
    while i + 2 < len(v) and v[i] != 0xFF:
        idx, rb, g = v[i], v[i + 1], v[i + 2]
        pal[idx & 15] = (mgrender._c3(rb >> 4), mgrender._c3(g), mgrender._c3(rb))
        i += 3
    return pal


@functools.lru_cache(maxsize=None)
def _ingame_base_palette():
    """The 16 screen registers as they actually stand during gameplay: the verified
    room base (DefaultPalette + PalMenuWeapon + RadioPalette; idx12 gray, 14 white,
    15 BLACK) PLUS SnakePal -- the player palette, always loaded, which owns idx 7 &
    0x0A. Room tiles never use 7/0x0A so room rendering didn't expose them, but items
    and some sprites do: without SnakePal idx7 stays DefaultPalette cyan instead of
    the real gray. Returns a fresh copy each call."""
    pal = mgrender.room_base_palette()
    _apply_pal_block(pal, ENGINE_F, "SnakePal")        # SnakePal lives inline in Banks0123.asm
    return list(pal)


@functools.lru_cache(maxsize=None)
def room_spriteset(room):
    """The spriteset id the engine loads for a room (SpritesetRooms[room]). This
    selects the sprite PALETTE the room's enemies actually use — the engine looks
    it up per room in SetSprPal (Banks0123.asm), NOT per enemy type. Rooms that
    reuse the same guard GFX under a different spriteset id get a different
    palette (e.g. room 87 = set 30 -> reg2 dark-blue, room 3 = set 29 -> reg2
    dark-red), which is why guards there aren't the usual grey. None if OOR."""
    tbl = _flat(SPRSETS_F, "SpritesetRooms")
    return tbl[room] if 0 <= room < len(tbl) else None


@functools.lru_cache(maxsize=None)
def _palette_for_spriteset(spriteset_idx):
    # Sprites share the 16 screen palette registers -> use the in-game persistent
    # base (see _ingame_base_palette), then the spriteset's own SprsetPal override.
    # COPY the base: _ingame_base_palette() is lru-cached and returns one shared list;
    # apply_room_palette mutates in place, so without the copy every spriteset (and
    # item_sprite, which reads the base) would clobber each other's palettes.
    pal = list(_ingame_base_palette())
    lab = _sprset_pal_labels()[spriteset_idx]
    if lab != "SprsetPalNone":
        mgrender.apply_room_palette(pal, lab)
    return pal


# ---- curated default pose: enemy ID -> (spriteset idx, sprite-def label) ----
# spriteset idx selects which gfx pack to load (so the pose's pattern numbers
# resolve); pose label is a calm idle/down-facing frame. None/absent = no sprite
# (invisible mine/pitfall, tile-drawn objects, pure spawners) -> box/badge only.
_GUARD = (2, "GuardDown")
POSE = {
    "ID_GUARD_SLOW": _GUARD, "ID_GUARD_MEDIUM": _GUARD, "ID_GUARD_FAST": _GUARD,
    "ID_GUARD_ALERT": _GUARD, "ID_GUARD_REDALERT": _GUARD, "ID_GUARD_SILENCER": _GUARD,
    "ID_GUARD_EXIT_LORRY": _GUARD, "ID_GUARD_ELEVATOR": _GUARD, "ID_GUARD_SWITCH": _GUARD,
    "ID_SPAWN_GUARD_ELEV": _GUARD, "ID_LORRY_SHOOTER": _GUARD, "ID_SHOOTER": _GUARD,
    "ID_SENTINEL": _GUARD, "ID_DESERT_SECURITY": _GUARD, "ID_CAPTURE_GUARD": _GUARD,
    "ID_DOG": (6, "DogDown1"), "ID_DOG_BASEMENT": (6, "DogDown1"), "ID_SPAWN_DOG": (6, "DogDown1"),
    "ID_SCORPION": (4, "ScorpionDR1"),
    "ID_CAMERA": (22, "CameraDown"),
    "ID_CAMERA_LASER": (20, "CameraDown"), "ID_LASER": (20, "CameraDown"),
    "ID_BIG_BOSS": (18, "BigBossDown1"),
    "ID_BULLDOZER": (14, "Bulldozer"),
    "ID_TANK": (13, "Tank1"),
    # ID_HIND_D: body is background tiles, only rotors are sprites -> box/badge only
    "ID_MACH_GUN_KID": (11, "MachGunKid1"),
    "ID_SHOT_GUNNER": (10, "ShotGunner"),
    "ID_FIRE_TROOPER": (16, "FireTrooperFD"),
    "ID_COWARD_DUCK": (17, "CowardDuck1"),
    "ID_ARNOLD": (15, "ArnoldRight1"),
    "ID_PRISONER1": (3, "Prisoner"), "ID_GREY_FOX": (9, "Prisoner"),   # room 164 loads SprSetPrisoner2
    "ID_ELLEN": (8, "Prisoner"), "ID_MADNAR": (7, "Prisoner"), "ID_FAKE_MADNAR": (7, "Prisoner"),
    "ID_GAS": (24, "Gas1"),   # colours set at runtime -> COLOR_OVERRIDE
    "ID_ROLLING_BARREL": (19, "RollBarrels1"),
    "ID_BRIDGE": (21, "Bridge"),
    "ID_JETPACK_TAKEOFF": (5, "JetPackDown"), "ID_JETPACK": (5, "JetPackDown"),
    "ID_SLEEPING_SIGN": (2, "Zzz1"),
}

# Actors whose sprite colours are set by their logic at runtime rather than by the
# static idxActorSprCols table (which holds 0 = transparent for them, so they'd
# render invisible). Value = per-plane colour bytes (same encoding as the table:
# low nibble = colour, bit6 = CC). ID_GAS: GasWait sets a=2, c=4Dh (gas.asm).
COLOR_OVERRIDE = {
    "ID_GAS": (0x02, 0x4D),
}


class Sprite:
    __slots__ = ("img", "ax", "ay", "w", "h")
    def __init__(self, img, ax, ay):
        self.img, self.ax, self.ay = img, ax, ay      # anchor offset (px) of actor (X,Y)
        self.w, self.h = img.size


@functools.lru_cache(maxsize=None)
def actor_sprite(id_token, pal_spriteset=None):
    """Render an actor's default sprite -> Sprite (tight RGBA + anchor), or None
    for actors with no drawable pose. GFX (shape) comes from the curated POSE
    spriteset; the PALETTE comes from `pal_spriteset` when given (the room's own
    spriteset id, per SetSprPal) else the pose spriteset — so enemies match the
    room-specific sprite colours the engine loads (see room_spriteset)."""
    spec = POSE.get(id_token)
    if spec is None:
        return None
    spriteset_idx, pose = spec
    ids = _enum_ids()
    eid = ids.get(id_token)
    if eid is None:
        return None
    num = _num_spr()
    nplanes = num[eid - 1] if 1 <= eid <= len(num) else 0
    if not nplanes:
        return None
    planes = _sprite_planes(pose, nplanes)
    if not planes:
        return None
    colors = _actor_colors(eid, len(planes))
    ov = COLOR_OVERRIDE.get(id_token)
    if ov:
        colors = [ov[k] if k < len(ov) else colors[k] for k in range(len(planes))]
    buf = vram_for_spriteset(spriteset_idx)
    pal = _palette_for_spriteset(spriteset_idx if pal_spriteset is None else pal_spriteset)

    minx = min(dx for _, dx, _ in planes)
    miny = min(dy for dy, _, _ in planes)
    maxx = max(dx for _, dx, _ in planes) + 16
    maxy = max(dy for dy, _, _ in planes) + 16
    W, H = maxx - minx, maxy - miny
    cidx = [[0] * W for _ in range(H)]              # colour index buffer, 0 = transparent
    for (dy, dx, pat), col in zip(planes, colors):
        quad = _sprite_quad(buf, pat)
        color = col & 0x0F
        cc = col & 0x40
        if color == 0:
            continue                                 # colour 0 = transparent plane
        for r in range(16):
            for c in range(16):
                if not quad[r][c]:
                    continue
                y, x = (dy - miny) + r, (dx - minx) + c
                if cc and cidx[y][x]:
                    cidx[y][x] |= color
                elif cidx[y][x] == 0:
                    cidx[y][x] = color
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    any_px = False
    for y in range(H):
        for x in range(W):
            ci = cidx[y][x]
            if ci:
                r, g, b = pal[ci]
                px[x, y] = (r, g, b, 255); any_px = True
    if not any_px:
        return None
    return Sprite(img, minx, miny)                  # actor (X,Y) sits at (-minx,-miny) in img


def actor_bbox(id_token):
    s = actor_sprite(id_token)
    return None if s is None else (s.ax, s.ay, s.w, s.h)


# ---- editable-object model (for the object pixel editor) -------------------
def pattern_source(spriteset_idx, pattern):
    """(gfxLabel, byte_offset_in_decoded_stream) owning sprite `pattern` within a
    spriteset -- the segment with the greatest firstPattern <= pattern. The 16x16
    sprite occupies 32 bytes from that offset. None if no segment covers it."""
    label = _spriteset_labels()[spriteset_idx]
    best = None
    for first, gfx in _spriteset_segments(label):
        if first <= pattern and (best is None or first > best[0]):
            best = (first, gfx)
    if best is None:
        return None
    first, gfx = best
    return (gfx, (pattern - first) * 8)


def bits_to_sprite_bytes(grid):
    """16x16 on/off grid -> the 32 bytes of a 1bpp MSX sprite as stored in the gfx
    stream (inverse of _sprite_quad): bytes[0..15] = left half rows 0..15, MSB=col0;
    bytes[16..31] = right half rows 0..15."""
    data = bytearray(32)
    for r in range(16):
        for c in range(16):
            if grid[r][c]:
                if c < 8:
                    data[r] |= 1 << (7 - c)
                else:
                    data[16 + r] |= 1 << (7 - (c - 8))
    return bytes(data)


# pose-family grouping: an actor animates through many idxSprites labels (walk/idle per
# direction). They share a CamelCase name stem before the direction/frame suffix, so we
# group by that stem to list all of an actor's editable poses.
_POSE_DIRS = ["WalkUp", "WalkDown", "WalkLeft", "WalkRight", "Up", "Down", "Left", "Right",
              "DR", "DL", "UR", "UL", "FD", "FU", "Fire", "Lying", "Listening", "Takeoff",
              "Climb", "Punch", "Water", "Dead", "Leaned"]


def _pose_prefix(lab):
    s = lab.rstrip("0123456789")
    for d in sorted(_POSE_DIRS, key=len, reverse=True):
        if s.endswith(d) and len(s) > len(d):
            return s[:-len(d)]
    return s


@functools.lru_cache(maxsize=None)
def actor_poses(id_token):
    """Ordered, de-duped list of pose labels in the actor's name family (all its
    directions/frames), or [] . The curated POSE label is always included."""
    spec = POSE.get(id_token)
    if spec is None:
        return ()
    pf = _pose_prefix(spec[1])
    seen, out = set(), []
    for l in _idx_sprites():
        if _pose_prefix(l) == pf and l not in seen:
            seen.add(l); out.append(l)
    return tuple(out)


def actor_planes_model(id_token, pose=None):
    """[{dy,dx,pattern,color,cc,src:(label,offset),bits:16x16}] for an actor pose (the
    curated POSE frame by default, or any label in actor_poses(id_token)), or None.
    `bits` come from the assembled spriteset VRAM buffer; `src` is where to write them
    back. `color` is the plane colour byte's low nibble (0..15)."""
    spec = POSE.get(id_token)
    if spec is None:
        return None
    spriteset_idx, curated = spec
    pose = pose if (pose and pose in actor_poses(id_token)) else curated
    eid = _enum_ids().get(id_token)
    if eid is None:
        return None
    num = _num_spr()
    nplanes = num[eid - 1] if 1 <= eid <= len(num) else 0
    planes = _sprite_planes(pose, nplanes) if nplanes else []
    if not planes:
        return None
    colors = _actor_colors(eid, len(planes))
    ov = COLOR_OVERRIDE.get(id_token)
    if ov:
        colors = [ov[k] if k < len(ov) else colors[k] for k in range(len(planes))]
    buf = vram_for_spriteset(spriteset_idx)
    out = []
    for (dy, dx, pat), col in zip(planes, colors):
        out.append({"dy": dy, "dx": dx, "pattern": pat,
                    "color": col & 0x0F, "cc": bool(col & 0x40),
                    "src": pattern_source(spriteset_idx, pat),
                    "bits": _sprite_quad(buf, pat)})
    return out


def actor_palette(id_token):
    spec = POSE.get(id_token)
    return _palette_for_spriteset(spec[0]) if spec else _ingame_base_palette()


# ---- player (Snake) frames -- same plane model as actors -------------------
PLAYER_F = "data/playersprite.asm"


@functools.lru_cache(maxsize=None)
def _snake_gfx_labels():
    return _label_order(PLAYER_F, "idxSnakeSpr")


@functools.lru_cache(maxsize=None)
def _snake_attr_for_gfx(glab):
    """The SnakeAttr* label whose frame first references gfx label `glab` (frames map
    1:1 onto SnakeSprAttIds -> idxSnakeSprAttr)."""
    gfx = _snake_gfx_labels()
    attids = _flat(PLAYER_F, "SnakeSprAttIds")
    attrs = _label_order(PLAYER_F, "idxSnakeSprAttr")
    for i, g in enumerate(gfx):
        if g == glab and i < len(attids) and attids[i] < len(attrs):
            return attrs[attids[i]]
    return None


def _snake_attr_planes(attr_label):
    """Parse a SnakeAttr* block: `db count` then count * (dy, dx, pattern, color).
    Returns [(dy, dx, pattern, colorbyte)] skipping off-screen (dy>=0x80) records."""
    flat = _flat(PLAYER_F, attr_label)
    if not flat:
        return []
    cnt = flat[0]
    out = []
    for k in range(cnt):
        b = 1 + k * 4
        if b + 3 >= len(flat) + 1 or b + 3 > len(flat):
            break
        dy, dx, pat, col = flat[b], flat[b + 1], flat[b + 2], flat[b + 3]
        if dy >= 0x80 and dx == 0 and pat == 0:          # parked/unused sprite slot
            continue
        out.append((_s8(dy), _s8(dx), pat, col))
    return out


def player_gfx_labels():
    """Unique Snake gfx labels (editable player frames), in index order."""
    seen, out = set(), []
    for g in _snake_gfx_labels():
        if g not in seen:
            seen.add(g); out.append(g)
    return out


def player_planes_model(glab):
    """Plane model for a Snake gfx label (same shape as actor_planes_model). bits come
    from the label's own decoded stream (patterns based at 0); src writes back there."""
    attr = _snake_attr_for_gfx(glab)
    planes = _snake_attr_planes(attr) if attr else []
    dec = unpack_gfx(_flat(SPRGFX_F, glab))
    if not planes:                                       # no attr -> raw: 1 sprite per 32 bytes
        planes = [(0, 0, p, 0x07) for p in range(0, len(dec) // 8, 4)]
    out = []
    for dy, dx, pat, col in planes:
        out.append({"dy": dy, "dx": dx, "pattern": pat,
                    "color": col & 0x0F, "cc": bool(col & 0x40),
                    "src": [glab, pat * 8], "bits": _sprite_quad(dec, pat)})
    return out


# ---- shared plane compositor (actor + player) ------------------------------
def compose_planes(planes, palette):
    """Composite a plane model ([{dy,dx,color,cc,bits}]) through a 16-colour palette
    -> (PIL RGBA tight image, ax, ay) where actor (X,Y) sits at (-ax,-ay). None if
    nothing drawn."""
    drawn = [p for p in planes if p["color"]]
    if not drawn:
        return None
    minx = min(p["dx"] for p in drawn); miny = min(p["dy"] for p in drawn)
    W = max(p["dx"] for p in drawn) + 16 - minx
    H = max(p["dy"] for p in drawn) + 16 - miny
    cidx = [[0] * W for _ in range(H)]
    for p in planes:
        color = p["color"] & 0x0F
        if not color:
            continue
        for r in range(16):
            for c in range(16):
                if not p["bits"][r][c]:
                    continue
                y, x = (p["dy"] - miny) + r, (p["dx"] - minx) + c
                if p["cc"] and cidx[y][x]:
                    cidx[y][x] |= color
                elif cidx[y][x] == 0:
                    cidx[y][x] = color
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load(); any_px = False
    for y in range(H):
        for x in range(W):
            ci = cidx[y][x]
            if ci:
                px[x, y] = (*palette[ci], 255); any_px = True
    return (img, minx, miny) if any_px else None


# ---- pickable items / weapons (3bpp bitmap blitted from VRAM page 1) --------
@functools.lru_cache(maxsize=None)
def _item_sheet():
    """Reconstruct the VRAM page-1 item bitmap GfxItems is decoded into.
    Load3bppTiles writes 0x84 8x8 tiles 32-per-row from page1 (X=0, Y=0x60), so
    tile i -> (col=i%32, row=i//32); sheet Y origin == VRAM Y 0x60. Returns a 2D
    list of palette-register indices (0 = transparent background)."""
    tiles = mggfx.decode_tiles(_flat(ITEMGFX_F, "GfxItems"), 3, 0x84, list(COLORS_ITEMS))
    W, H = 256, ((len(tiles) + 31) // 32) * 8
    sheet = [[0] * W for _ in range(H)]
    for i, t in enumerate(tiles):
        cx, cy = (i % 32) * 8, (i // 32) * 8
        for r in range(8):
            for c in range(8):
                sheet[cy + r][cx + c] = t[r][c]
    return sheet


def _item_gfx_coord(item_id):
    """Page-1 (srcX, srcY, width) for an item/weapon id (DrawRoomItems rule:
    id<9 -> WeaponGfxXY[id-1] (32 wide), else ItemGfxXY[id-9]; bit0 of the low
    byte = 16-wide). Height is always 16."""
    if item_id < 9:
        coord = _dw_words(WEAPXY_F, "WeaponGfxXY")[item_id - 1]
    else:
        tbl = _dw_words(ITEMXY_F, "ItemGfxXY")
        if not (0 <= item_id - 9 < len(tbl)):
            return None
        coord = tbl[item_id - 9]
    low, high = coord & 0xFF, (coord >> 8) & 0xFF
    return (low & 0xFE, high - 0x60, 16 if (low & 1) else 32)


@functools.lru_cache(maxsize=None)
def item_sprite(id_token):
    """Render a pickable item/weapon -> Sprite (anchor 0,0: item (X,Y) is the
    top-left of the blit). id_token is an item constant name (e.g. 'RATION') or
    an int id. None if unknown / off-sheet."""
    iid = id_token if isinstance(id_token, int) else _consts().get(id_token)
    if not iid:
        return None
    coord = _item_gfx_coord(iid)
    if coord is None:
        return None
    sx, sy, w = coord
    sheet = _item_sheet()
    pal = _ingame_base_palette()                    # incl. SnakePal: item reg 7/0x0A = player gray/flesh
    img = Image.new("RGBA", (w, 16), (0, 0, 0, 0))
    px = img.load()
    any_px = False
    for r in range(16):
        for c in range(w):
            yy, xx = sy + r, sx + c
            ci = sheet[yy][xx] if 0 <= yy < len(sheet) and 0 <= xx < 256 else 0
            if ci:
                px[c, r] = (*pal[ci], 255); any_px = True
    return Sprite(img, 0, 0) if any_px else None


@functools.lru_cache(maxsize=None)
def _item_set_blocks():
    """ItemXxx label -> tuple of (id_name, y, x) parsed from the item-set blocks.
    Delegates to mgmap.parse_item_sets so BOTH position encodings are handled:
    `db ID / dw YYXXh` and `db ID / db Y, X` (the latter used by ItemUniform /
    ItemAntenna / ItemPBomb2 — previously rendered empty here). Position byte
    order matches actors (y=low)."""
    _order, blocks = mgmap.parse_item_sets(mgmap._read(ITEMS_F))
    return {lab: tuple((e[0], *mgmap.item_entry_yx(e)) for e in ents)
            for lab, ents in blocks.items()}


def room_items(room):
    """[{'id','y','x'}] pickable items physically in a room (idxRoomItemsIdx ->
    idxRoomItems -> ItemXxx block). Empty for rooms with no item or out of range."""
    islot = room - ITEM_ROOM_BASE
    idxs = mgmap.parse_flat(mgmap._read(ITEMS_F), "idxRoomItemsIdx")
    if not (0 <= islot < len(idxs)) or idxs[islot] == 0:
        return []
    labels = _label_order(ITEMS_F, "idxRoomItems")
    si = idxs[islot] - 1                              # 1-based into idxRoomItems
    if not (0 <= si < len(labels)):
        return []
    return [{"id": nm, "y": y, "x": x} for nm, y, x in _item_set_blocks().get(labels[si], ())]


def object_sprite(id_token, pal_spriteset=None):
    """Dispatch: actor ids are 'ID_*', everything else is an item constant name.
    `pal_spriteset` (the room's spriteset id) overrides the sprite palette for
    actors; items ignore it (they use the item palette)."""
    return (actor_sprite(id_token, pal_spriteset) if str(id_token).startswith("ID_")
            else item_sprite(id_token))


def render_overlay(objects, scale=2, pal_spriteset=None):
    """objects: iterable of dicts with id/x/y (actors as room_objects returns, and/or
    items as room_items returns). Returns (RGBA overlay sized to the room*scale,
    [bbox|None per object]) where bbox = (left, top, w, h) in unscaled room pixels.
    `pal_spriteset` = the room's spriteset id (room_spriteset), so actors use the
    room's own sprite palette instead of the pose default."""
    base = Image.new("RGBA", (ROOM_W_PX, ROOM_H_PX), (0, 0, 0, 0))
    boxes = []
    for a in objects:
        s = object_sprite(a["id"], pal_spriteset)
        if s is None:
            boxes.append(None); continue
        left, top = a["x"] + s.ax, a["y"] + s.ay
        base.alpha_composite(s.img, (left, top))
        boxes.append((left, top, s.w, s.h))
    if scale != 1:
        base = base.resize((ROOM_W_PX * scale, ROOM_H_PX * scale), Image.NEAREST)
    return base, boxes


def object_bbox(id_token):
    s = object_sprite(id_token)
    return None if s is None else (s.ax, s.ay, s.w, s.h)


# ---- cli (debug) -----------------------------------------------------------
def _all_spr_labels():
    """Every `Spr*: db` label in gfx/sprites.asm, in file order."""
    labs = []
    for ln in open(mgproj.path(SPRGFX_F), encoding="latin-1"):
        m = re.match(r'^(Spr\w+):\s*db', ln)
        if m:
            labs.append(m.group(1))
    return labs


if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]:
        ok = bad = grew = to = tn = 0
        for lab in _all_spr_labels():
            raw = _flat(SPRGFX_F, lab)
            dec = unpack_gfx(raw)
            enc = pack_gfx(dec)
            if unpack_gfx(enc) == dec:
                ok += 1
            else:
                bad += 1; print("  RT FAIL", lab)
            to += len(raw); tn += len(enc); grew += len(enc) > len(raw)
        print("pack_gfx round-trip: %d ok, %d fail  (orig %d B -> %d B, %d labels grew)"
              % (ok, bad, to, tn, grew))
        sys.exit(1 if bad else 0)
    ids = sys.argv[1:] or ["ID_GUARD_MEDIUM", "ID_DOG", "ID_SCORPION", "ID_BIG_BOSS"]
    for t in ids:
        s = actor_sprite(t)
        if s is None:
            print("%-22s -> (no sprite)" % t); continue
        out = mgproj.repo_path(os.path.join("tools", "shots", "spr_%s.png" % t))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        s.img.resize((s.w * 6, s.h * 6), Image.NEAREST).save(out)
        print("%-22s -> %dx%d anchor(%d,%d) %s" % (t, s.w, s.h, s.ax, s.ay, out))
