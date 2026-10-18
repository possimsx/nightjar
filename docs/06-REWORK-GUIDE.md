# 06 — Rework Guide: reusing the engine for a new game

The whole point of this disassembly is that Metal Gear is a **data-driven engine**. The Z80
code is generic; the *game* is a stack of lookup tables indexed by room number. To make a
new game you mostly rewrite **data**, not **logic**.

This guide separates "**content** (safe to rewrite)" from "**engine** (the machinery)" and
gives concrete recipes.

---

## 1. The golden rule

> **Content lives in `data/`, `gfx/`, `sound/` and the text/radio tables.
> The engine lives in `Banks0123.asm` and `logic/`.**

If you want a *new game with the same feel* (top-down stealth, rooms, doors, radio, bosses),
you can get very far touching only content. If you want *new mechanics*, you edit `logic/`.

Always keep the build green: after each change, rebuild (see [01-BUILD.md](01-BUILD.md)) and
watch for `ASSERT $=#C000` failures (bank overflow).

---

## 2. What each layer controls

| You want to change… | Edit these files | Engine code involved (usually leave alone) |
|---------------------|------------------|-------------------------------------------|
| Room layouts | `data/rooms.asm` (8×6 metatile grids), `data/roomtileset.asm` | `LoadRoomTiles` |
| How rooms connect | `data/roomsconnections.asm` (N/S/W/E) | `NextRoomLogic` |
| Where items are | `data/itemsinrooms.asm` (+ `idxRoomItemsIdx`) | `ChkTakeItems`, `AddRoomItems` |
| Which enemies/bosses per room | `data/actorsinrooms.asm` | actor spawner, `logic/actors/*` |
| Doors & locks | `data/doors.asm` (`DoorsRoomNNN`, `IdDoorsLogic`) | `logic/doors/*` |
| The story / dialogue | `data/radiocalls.asm` + `data/texts.asm` | `RadioLogic`, `MessageLogic` |
| Item names / menus | `data/itemnames.asm`, `data/menu*texts.asm` | menu logic |
| Graphics | `gfx/*.asm`, palettes in `data/palettes.asm` | tile/sprite decoders |
| Music & SFX | `sound/music/*`, `sound/sfx/*`, `sound/sounddata.asm` | `bgmdriver`, `UpdateSound` |
| Tuning (damage, ammo caps, paths) | `data/weapondamage.asm`, `data/respawninfo.asm`, `data/paths.asm`, `Variables.asm` defaults | various |

---

## 3. Recipes

### A. Re-skin a room
1. Open `room_images/MGEAR1_00NN.png` to see the original.
2. Edit `RoomNNN` in `data/rooms.asm` — it's 6 rows × 8 metatile IDs. Reuse existing
   metatile IDs from the room's tileset, or add metatiles in `data/metatiles.asm`.
3. Adjust the room's palette/tileset via `data/roomtileset.asm` if needed.
4. Fix exits in `data/roomsconnections.asm` so neighbors line up.
5. Rebuild.

### B. Move or add an item
1. Pick the room. Look up its current set index in `idxRoomItemsIdx` (`data/itemsinrooms.asm`).
2. Either point the room at a different existing set, or add a new `ItemXxx:` block:
   ```asm
   ItemMyStuff:  db CARD5
                 dw 7050h        ; YX (Y=#70, X=#50)
                 db AMMO_CRATE
                 dw 0A040h
                 db 0FFh         ; end of list
   ```
   then add `dw ItemMyStuff` to `idxRoomItems` and put its (1-based) index into
   `idxRoomItemsIdx` for that room.
3. Item IDs come from `enum ITEMS` (`Enums.asm`). Up to **3 items per room**.
4. Rebuild. The pickup, HUD, and inventory logic all work automatically.

### C. Change which enemy/boss is in a room
1. Edit the room's `ActorsRoomNNN` block in `data/actorsinrooms.asm`:
   ```asm
   ActorsRoom050:  db 1                ; count
                   db ID_HIND_D        ; actor ID (enum ACTORS)
                   dw 8040h            ; YX
   ```
2. Use any `ID_*` from `Enums.asm`. The matching behavior file in `logic/actors/` runs
   automatically.
3. To create a **new** enemy type you must add: an `ID_*`, an entry in the actor init/update
   jump tables, a behavior file in `logic/actors/`, plus sprite data in
   `data/spritesets.asm` / `gfx/sprites.asm`. (This is the one genuinely "engine" task.)

### D. Lock a door behind a card / event
1. Add a door to the room's `DoorsRoomNNN` list in `data/doors.asm`:
   `db DoorID, RenderType, DrawY, DrawX, DestRoom`.
2. Set that **DoorID's** byte in `IdDoorsLogic`: low nibble = open-logic (e.g. `3` =
   needs Card 2), bits 7-6 = start open/closed. (See
   [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md#3-the-door-system).)
3. For an *event*-opened door, reuse `ChkBigBossDoor`/`ChkCompassDoor` patterns: they just
   gate on a RAM flag you set from a story trigger.

### E. Rewrite the story
1. **Dialogue text:** add strings to `data/texts.asm` and an entry in `idxTexts`. (Text uses
   a dictionary/token encoding — bytes ≥ `#80` are dictionary words, `#FE`/`#FD` are line
   breaks, `#FF` ends a string. The simplest path is to copy the structure of an existing
   short string and keep tokens you understand, or extend the dictionary.)
2. **Who calls, where, and what:** edit `data/radiocalls.asm`. For a room, define a
   `RadioRoom_NNN` block of `(caller-flags, textID)` pairs and point `idxRoomRadio[room]`
   at it. Flags = `RADIO_BIGBOSS|RADIO_AUTOREPLY|RADIO_END` etc. (`enum RADIO`,
   `enum FREQUENCIES`).
3. **Triggers/events** (capture, "switch off MSX", Madnar-moved, Schneider-captured) live in
   small files like `logic/madnarbigbossevent.asm`, `logic/capturescene.asm`. Copy one as a
   template for a new scripted beat; they set a RAM flag and/or `GameMode`.

### F. Re-tune gameplay
* Weapon damage: `data/weapondamage.asm`. Ammo caps: `MaxAmmo*` defaults.
* Item quantities on pickup: `data/itemtakeamount.asm`.
* Enemy patrol routes: `data/paths.asm`. Respawns: `data/respawninfo.asm`.
* Starting life / class: initialization in `GS_StartGame` / `Variables.asm`.

---

## 4. Things to respect (engine constraints)

* **Bank budget.** Each bank group fills to `#C000`. Adding data can overflow it (`ASSERT`
  failure). Spread new data across whichever bank group (`Banks456/789/ABC/DEF`) has free
  `#ff` padding, and remember cross-bank calls need the **trampoline** entry points
  (underscore-suffixed) — see [02-ARCHITECTURE.md](02-ARCHITECTURE.md#calling-across-banks-the-trampoline-table).
* **Fixed structure sizes.** Actors are 128 bytes, items 4 bytes, doors 16 bytes. Tables are
  indexed by multiplying by these — don't change a struct size without auditing every reader.
* **Room count / index tables.** `idxRooms`, `idxDoors`, `idxRoomRadio`, `idxRoomItemsIdx`
  are parallel arrays indexed by room ID. If you add rooms, extend **all** of them
  consistently (and `data/roomsconnections.asm`).
* **Everything runs in the VBLANK ISR.** Keep per-frame logic short; a frame that overruns
  is simply skipped (`TickInProgress`), causing slowdown.
* **Two number spaces for items** (pickup ID vs. `SELECTED_*`). When writing logic that
  reads `SelectedItem`, use the `SELECTED_*` enum; when placing items in the world, use the
  `ITEMS` enum.

---

## 5. Suggested workflow for a full reskin

1. **Build the original unchanged** and run it in openMSX with the `.sym` file — confirm your
   toolchain works and you can debug.
2. **Map your new game onto the room grid.** Decide your room count and draw connections in
   `data/roomsconnections.asm`. Reuse `room_images/` numbering for your own design notes.
3. **Lay out content per room:** rooms → items → enemies → doors, room by room, rebuilding
   often.
4. **Write the story tables** (`radiocalls` + `texts`) last, once the world is navigable.
5. **Swap graphics/sound** incrementally (they're the bulkiest and most independent).
6. Keep `JAPANESE equ 0` unless you specifically want the JP text path.

---

## 6. Fastest "is this data or engine?" lookups

* A file under `data/` whose name is a plural noun (`rooms`, `doors`, `items*`, `texts`,
  `radiocalls`, `actorsinrooms`, `palettes`) → **content**, rewrite freely.
* A file under `logic/` or the big `Banks0123.asm` → **engine**, change with care.
* A label starting `idx…` → an **index/jump table** parallel to room or item IDs.
* A label ending `_` (underscore) in `Banks0123.asm` → a **bank trampoline**, not real logic.
* `enum`s in `constants/Enums.asm` → the shared vocabulary tying data to logic; extend, don't
  renumber.
