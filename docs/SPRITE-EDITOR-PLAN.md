# Object / Player / Actor Pixel Editor — plan

> **Status: IMPLEMENTED (all phases).** All three classes editable in the map editor
> via the 🎨 **sprites** toolbar button (`#objmodal`). `mgsprite.pack_gfx` +
> `python tools/mgsprite.py selftest` (87/87 round-trip); server `/api/objects`,
> `/api/object/<token>[/render.png]` (accepts `?pose=`), POST `plane`/`pixels`/`colors`;
> frontend picker + plane-stack editor / item canvas. The main canvas shows the
> full CC-composited sprite (real colours) with the active plane highlighted.
> **Phase 4 done:** inline 🔨 build button surfaces bank overflow. **Pose picker done:**
> actors expose all frames of their name family (`actor_poses`, grouped by
> `_pose_prefix`) via a pose/frame dropdown; edits target the selected pose's patterns.
> Palette cache-aliasing bug fixed (`_palette_for_spriteset` now copies the base).
> Verified end-to-end incl. rebuild (128KB, no overflow) and headless-Chrome UI checks.
> Remaining optional follow-ups: openMSX "test this actor" one-click; add/remove sprites.
> The notes below are the original design; kept for reference.


Add pixel editing for the game's *movable graphics* — pickable items/weapons,
enemy/actor sprites, and the player (Snake) — to the map editor
(`tools/editor`). This is the sprite-side counterpart to the existing **room
tile** pixel painter (`/api/room/<id>/tile/<t>`), reusing the same
decode → canvas → splice-back-to-`.asm` loop.

Decided scope: **all three classes** in scope; actor/player sprites use a
**plane-stack editor with a live composite preview** (faithful to the 1bpp
per-plane hardware model), items use a true-colour canvas.

## Background: three formats, one editor

The overlay decode pipeline (`tools/mgsprite.py`, see the
`actor-sprite-overlay` memory) already reads all of these faithfully. They
differ in how they store pixels and colour, which drives the UI:

| Class | Gfx storage | Colour model | Edit unit |
|---|---|---|---|
| **Pickable items / weapons** — `GfxItems` (`gfx/items.asm`) | 3bpp **uncompressed** 8×8 tiles | true indexed: 8-colour `ColorsItems` sub-palette, colour **per pixel** | reuse `mggfx.decode_tiles`/`pack_tiles`/`write_block` (already round-trips) |
| **Enemy / actor sprites** — `Spr*` (`gfx/sprites.asm`) | 1bpp planes, **RLE-compressed per label** (each label is its own `UnpackGfx` stream) | colour is **per-plane**, not per-pixel (`idxActorSprCols` byte: low nibble = colour, bit6 = CC colour-OR onto previous plane) | paint on/off **bits** per plane + edit plane colour bytes |
| **Player (Snake)** — `SprSnake*` (`gfx/sprites.asm`, indexed by `idxSnakeSpr` in `data/playersprite.asm`) | same 1bpp RLE planes | per-frame plane colours from `idxSnakeSprAttr` records (`SetSnakeSprCol`); palette regs 7/0x0A from `SnakePal` | same plane-stack editor as actors + Snake colour/palette controls |

Key consequence: an actor/player "pixel editor" is **not** a paint-any-colour
canvas. A 16×16 sprite is a *stack of 1bpp planes*; you paint set/clear bits in
each plane, and colour is assigned to the whole plane (with CC planes OR-ing
their colour into the plane below). Only **items** are a true indexed-colour
canvas.

## The one missing primitive (validated)

`mgsprite.unpack_gfx()` decodes the RLE, but there is **no encoder** — needed to
write edited sprite pixels back. Add:

```
mgsprite.pack_gfx(flat_bytes) -> list[int]      # inverse of unpack_gfx
```

Greedy scheme matching the engine's `UnpackGfx`:
- run of ≥3 identical bytes → fill run `[count, value]` (bit7 clear),
- otherwise a literal run `[0x80|len, bytes…]`, `len ≤ 0x7F`, breaking the
  literal when a ≥3 identical run begins,
- `0x00` terminator.

**Prototype result: round-trips all 87 `Spr*` labels; total size 15637 vs
15612 original bytes (+25 across the whole set, 15 labels grew by a byte or
two).** Size drift is irrelevant to VRAM (patterns land at `firstPattern*8`
regardless) and sjasm re-resolves every label/address; the only real constraint
is **bank capacity**, verified by a `/api/build` after save. Add a `selftest`
that asserts `unpack_gfx(pack_gfx(unpack_gfx(raw))) == unpack_gfx(raw)` for
every `Spr*` label, mirroring `mggfx selftest`.

## Backend (`tools/editor/server.py`) — mirror the tile editor

New model helpers in `mgsprite.py` (decode side) + splice helpers reusing
`mggfx.write_block` / server's `_splice_gfx_bytes`:

- **Enumerate editable objects.** Actors from the `POSE` map (id_token →
  spriteset+pose); items/weapons from `WeaponGfxXY`/`ItemGfxXY` id tables;
  player frames from `idxSnakeSpr`. Each entry carries a "used by" list
  (which actors/rooms reference the same `Spr*` label / spriteset) so the UI
  can warn that gfx is **shared** — exactly like the metatile editor's
  "shared by N rooms" banner.

- **GET `/api/object/<id_token>`** →
  ```
  { class: "actor"|"item"|"player",
    planes: [ { bits:[[0/1]*16]*16, dy, dx, pattern, color, cc } ],   # sprites
    pixels: [[idx]*w]*16, swatches:[rgb*8],                            # items
    palette: [rgb*16], composite_png_url, used_by:[…] }
  ```
- **POST `/api/object/<id_token>/plane/<n>`** `{bits}` → set a sprite plane's
  16×16 bits: rebuild that pattern's 8-byte quadrants, splice new bytes for the
  whole `Spr*` label via `pack_gfx` + `_splice_gfx_bytes`.
- **POST `/api/object/<id_token>/pixels`** `{pixels}` → item path: `pack_tiles`
  the affected 8×8 tiles + `write_block` (already proven by the room-tile path).
- **POST `/api/object/<id_token>/colors`** `{planes:[byte]}` → rewrite the
  actor's `ActorSprColors*` bytes (`idxActorSprCols`) / for the player the
  `idxSnakeSprAttr` colour fields; SnakePal registers via the existing palette
  editor plumbing.

Routing follows the existing `parts[:2]==["api","object"]` style already used
for `/api/room/<id>/…`.

## Frontend (`tools/editor/static/index.html`)

New **"Objects"** view, peer of `map`/`metatile`:

- **Left — object picker**: grouped list (Actors / Items / Player), each row a
  live sprite thumbnail (reuse `object_sprite` → PNG). Click selects.
- **Right — editor**:
  - *Items*: single true-colour canvas (copy `#tile-grid`: drag-to-paint,
    8 `ColorsItems` swatches, right-click pick, Ctrl+Z undo).
  - *Actors/Player*: **plane-stack editor** — one layer tab per plane
    (each shows its assigned colour), a monochrome bit canvas for the active
    plane, and a **live composite preview** (all planes with CC-OR applied,
    through the resolved palette). Plane-colour dropdown per plane; for the
    player, SnakePal swatches too.
  - "Used by …" warning banner when the gfx/spriteset is shared.
- Reuse the room-tile canvas helpers (drag paint, undo stack, pixelated
  rendering) rather than writing new ones.

## Build / verify

1. Save → `.asm` splice (idempotent, same machinery as tile/metatile saves).
2. Offer **`/api/build`** and surface bank-overflow errors (the only real
   failure mode from size drift).
3. **`/api/run`** / `warp_room` to eyeball the edited sprite in openMSX.

## Phasing

1. **Items** — uncompressed, true-colour; near-direct reuse of the tile
   painter. Proves the end-to-end loop in the new view.
2. **`pack_gfx` + selftest**, then **actor sprite planes** (the core).
3. **Plane colours** (`idxActorSprCols`) + **player** (`idxSnakeSpr` frames,
   `idxSnakeSprAttr` colours, `SnakePal`).
4. **Build/verify integration** (auto-build, openMSX warp).

## Risks / notes

- **Shared gfx**: one `Spr*` label / spriteset feeds many actors and many
  poses of the same actor. Editing changes all of them — surface the "used by"
  list prominently (metatile-editor precedent).
- **Multi-pose**: an actor has many pose labels; v1 edits the label(s) behind
  the curated `POSE` frame. A pose picker (all labels in the actor's spriteset)
  is a natural follow-up.
- **Bit-vs-colour mental model**: the plane-stack UI must make it obvious that
  painting toggles a *mask bit*, and colour is a per-plane property — hence the
  always-on composite preview.
