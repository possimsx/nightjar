# 02 — Engine Architecture

This is the technical core. Read it once and the rest of the codebase becomes navigable.

---

## 1. ROM format & bank layout {#bank-layout}

The cartridge is a **128 KB Konami MegaROM** using the standard Konami mapper *without*
SCC. The ROM is divided into **16 banks of 8 KB**. The Z80 only sees 64 KB, so the game
pages banks into three 8 KB windows in the upper half of the address space:

```
CPU address space          Mapper register   Contents
-----------------          ---------------    --------
#0000-#3FFF  (page 0)         (BIOS / RAM via slots)
#4000-#5FFF  (page 1 lo)      fixed = Bank 0   <- never paged out: core code, ISR, header
#6000-#7FFF  (page 1 hi)      write #6000      <- swappable bank
#8000-#9FFF  (page 2 lo)      write #8000      <- swappable bank
#A000-#BFFF  (page 2 hi)      write #A000      <- swappable bank
#C000-#FFFF  (page 3)         RAM              <- all game variables (see memory map)
```

Writing a bank number to address `#6000`, `#8000`, or `#A000` selects which 8 KB ROM bank
appears there. Banks are paged in **groups of three consecutive banks** by the helper
routines in `Banks0123.asm`:

| Routine | #6000 | #8000 | #A000 | Holds |
|---------|:-----:|:-----:|:-----:|-------|
| `SetBanks1_2_3` | 1 | 2 | 3 | Main code continuation |
| `SetBanks_4_5_6` | 4 | 5 | 6 | Sound driver + most data tables |
| `SetBanks_7_8_9` | 7 | 8 | 9 | Room tilesets, big graphics, intro/menu |
| `SetBanks_A_B_C` | A | B | C | Sprites, palettes, all text strings |
| `SetBanks_D_E_F` | D | E | F | Rooms, doors, radio calls, save/load, ending |

These map onto the source files:

| Source file | Bank group | `org` |
|-------------|-----------|-------|
| `Banks0123.asm` | 0 (fixed) + 1/2/3 | `#4000` |
| `Banks456.asm` | 4/5/6 | `#6000` |
| `Banks789.asm` | 7/8/9 | `#6000` |
| `BanksABC.asm` | A/B/C | `#6000` |
| `BanksDEF.asm` | D/E/F | `#6000` |

`BankIn60`, `BankIn80`, `BankInA0` (in RAM) always hold a copy of what's currently paged,
so the interrupt handler can restore banks after it temporarily swaps in the sound driver.

### Calling across banks: the trampoline table

Bank 0 (`#4000-#5FFF`) is always present, so it holds:
* the ROM header,
* the interrupt handler,
* a few tiny shared math helpers (`ADD_HL_A`, `ADD_DE_A`, `JumpIndex`, …),
* and a big block of **trampolines** (lines ~64–397 of `Banks0123.asm`).

A trampoline lets code in one bank call a routine that needs *other* banks paged in. The
pattern is everywhere:

```asm
SetText_:
        call    SetText               ; do the work (may live in banks 1/2/3)
        jr      SetBanks_1_2_X___     ; restore caller's banks and return
```

When you see a label that's a normal name with a trailing underscore (`DrawRadio_`,
`LoadRoomTiles_`, `EraseMetalGear_`), it's the bank-safe entry point for the underscore-less
routine. **Call the underscore version from another bank; call the plain version when the
right banks are already paged.**

---

## 2. Boot & the main loop

`Start` (`Banks0123.asm:552`) runs once at power-on:

1. `DI`, set stack to `Stack`.
2. Find the cartridge slot (`RSLREG`/`EXPTBL`/`ENASLT`) and enable it in page 2.
3. Zero the RAM variable area (`#C000…` for `#30EF` bytes).
4. `SetBanks1_2_3`, `RegionLock`, clear the "fixed bank" overrides.
5. `InitHardware` — PSG, VDP, VRAM (`logic/inithardware.asm`).
6. **Hook the VBLANK interrupt:** patch `HTIMI` with `JP InterruptTick`.
7. `EI`, then `DummyLoop: jr $` — the main thread does **nothing** forever.

> **Key insight:** there is no conventional main loop. *All* game logic is driven by the
> 50/60 Hz VBLANK interrupt. `DummyLoop` just spins; `InterruptTick` is the heartbeat.

### `InterruptTick` (`Banks0123.asm:440`)

Every VBLANK:

1. Clear the VDP interrupt flag (`RDVDP`).
2. Page in banks 4/5 and call `UpdateSound` (music + SFX), then restore previous banks.
3. **Re-entrancy guard:** if `TickInProgress` is already set, skip (the previous frame's
   logic is still running — a slowdown frame). Otherwise set the flag, `EI`, and call
   **`GameStatusLogic`** (the whole game), then clear the flag.

---

## 3. The two state machines

The game is a hierarchy of two dispatchers, both implemented with `JumpIndex` (read an
index, jump through a `dw` table that follows the `call`).

### 3a. `GameStatusLogic` — the top-level mode (`Banks0123.asm:10058`)

Indexed by `GameStatus` (variable at `#C000`):

| # | Handler | Meaning |
|---|---------|---------|
| 0 | `GS_KonamiLogo` | Konami logo + load intro gfx |
| 1 | `GS_WaitMenu` | Title / main menu (`logic/mainmenu.asm`) |
| 2 | `GS_DemoPlay` | Attract-mode demo + tutorial (`logic/gamedemo.asm`) |
| 3 | `GS_PlayStart` | "Play start" transition effect |
| 4 | `GS_StartGame` | Initialize a new/continued game |
| 5 | **`GS_Playing`** | **Actual gameplay** → calls `GameLogic` |
| 6 | `GS_GameOver` | Game-over screen |
| 7 | `GS_Pause` | Pause / save / load (`logic/saveload.asm`, `logic/passwords.asm`) |
| 8 | `GS_Ending` | Ending sequence (`logic/ending.asm`) |

If `GameStatus < 3` it also pushes `ChkAnykeyStart` so a keypress jumps to the menu.

### 3b. `GameLogic` / `GameModeLogic` — the in-game mode (`Banks0123.asm:12015`)

While `GS_Playing` is active, each frame it renders the HUD/Snake/enemy sprites, then
dispatches on `GameMode`:

| # | Constant | Handler | Meaning |
|---|----------|---------|---------|
| 0 | `GAME_MODE_PLAYING` | `Playing` | Free control of Snake |
| 1 | `GAME_MODE_NEXT_ROOM` | `NextRoomLogic` | Scrolling/teleporting between rooms |
| 2 | `GAME_MODE_WEAPONS` | `MenuWeapon` | Weapon select menu |
| 3 | `GAME_MODE_EQUIPMENT` | `MenuEquip` | Equipment select menu |
| 4 | `GAME_MODE_RADIO` | `RadioLogic` | Radio/transceiver screen |
| 5 | `GAME_MODE_LORRY` | `LorryLogic` | Riding a moving lorry/truck |
| 6 | `GAME_MODE_ELEVATOR` | `ElevatorRoom` | Inside a moving elevator |
| 7 | `GAME_MODE_OPEN_DOOR` | `OpenDoorLogic` | Door-opening animation |
| 8 | `GAME_MODE_BINOCULARS` | `BinocularMode` | Looking through binoculars |
| 9 | `GAME_MODE_DEAD` | `DeadLogic` | Death animation |
| A | `GAME_MODE_TEXT_BOX` | `MessageLogic` | A text window is open |
| B | `GAME_MODE_CAPTURED` | `CaptureLogic_` | Snake captured → prison |
| C | (Madnar moved) | `EventMadnarMoved` | Special "it's too late" event |

`GameMode` is the single most important state variable for understanding behavior. Many
routines check it before acting (e.g. you can't pick up items, pause, or shoot while a text
box is open).

The deeper `Playing` handler (`Banks0123.asm:12106`) runs the per-frame gameplay pipeline:
F-keys → alarm timer → destruction timer → **player control** → weapon fire → player-shot
movement → **enemy logic** → `CommonLogic` → poison check.

`CommonLogic` is the shared collision/interaction pass:
`ChkPlayerShots`, `ChkTouchEnemies`, `ChkOnBridge`, `ChkElectricFloor`, `ChkGasRooms`,
**`ChkDoors`**, **`ChkPickItems`**.

---

## 4. Memory map (RAM, `#C000`+)

All variables are declared in `Variables.asm` with `map #c000` and `#` (Sjasm "reserve")
directives, so each label is just an address. Highlights you'll touch constantly:

### Global game state
| Variable | Purpose |
|----------|---------|
| `GameStatus` / `GameSubstatus` | Top-level state machine (see §3a). |
| `GameMode` | In-game mode (see §3b). |
| `TickCounter`, `WaitCounter`, `TickInProgress` | Frame timing / ISR guard. |
| `ControlsTrigger` / `ControlsHold` | Joystick+keyboard: bit5 Fire2, 4 Fire, 3 R, 2 L, 1 D, 0 U. |
| `FKeysTrigger` / `FKeysHold` | Function keys (F1–F5, RET). |

### The player ("Snake")
| Variable | Purpose |
|----------|---------|
| `Room` | Current room ID (also doubles as logo timer in title state). |
| `PreviousRoom` | Room you came from (used for checkpoints). |
| `NextRoomDirect` | Exit direction (4=R,3=L,2=D,1=U). |
| `Life` / `MaxLife` | Health. |
| `Class` | Rank (stars). |
| `PlayerY/PlayerX` (+ `…dec` fractional) | Position. |
| `PlayerDirection` | 1=U 2=D 3=L 4=R. |
| `PlayerControlMod` | 0=Walk 1=Punch 2=Elevator 3=Dead 4=Parachute 5=AirFlow 6=LadderWalk 7=LadderClimb 8=Intro. |
| `PlayerAnimation` | Visual state (normal/punch/water/parachute/ladder/dead/box). |
| `SelectedWeapon` / `SelectedItem` | Currently equipped weapon / item. |
| `Poisoned`, `RescuedCnt`, `EquipRemoved` | Status flags. |

### Inventory (see [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md))
`Weapons` (7×4-byte slots), `InvSupressor`, `Equipment`+`CigarsUnits` (25 item slots),
the `…Taken` byte flags (`WeaponsTaken`, `ItemsTaken`, `Card1Taken`…`Card8Taken`,
`UniformTaken`, …), and `MaxAmmoGun`…`MaxAmmoMissile` / `MaxRations`.

### Room contents (rebuilt every time you enter a room)
| Variable | Purpose |
|----------|---------|
| `ItemsInTheRoom` (`#30`) | Up to 3 active item pickups: `ID, size, Y, X`. |
| `SpawnItemData` | A dynamically-spawned drop (ration/ammo/card7/card8/suppressor). |
| `DoorsList` (`#80`) | Active `DOOR` structures for the room. |
| `DoorOpenArray` (`#A0`) | Persistent open/closed state of **every** door in the game. |
| `EnemyList` / `EnemyListEntry1/2` | The room's active actors (`ACTOR` structures). |
| `RoomTileBuffer` (`#500`) | Decoded background tiles of the current room. |
| `CollisionTiles` (`#100`) | Per-tile collision bit (bit0 = solid). |

### Event / boss flags (the "story bits")
`AlertMode`, `RoomAlert`, `RedAlertFlag`, `PowerSwitchOn`, `BossHindD_KO`, `BossTank_KO`,
`Bulldozer_KO`, `MetalGear_KO`, `FireTrooper_KO`, `BigBossStat`, `DoorBuild2LockedF`,
`MadnarMoved`, `JeniOpenDoorF` (compass door), `OpenBigBossDoor`, `SchneiderCaptured`,
`SwitchOffMSXF`, `LeavedOuterHeaven`, `RescuedArray`, `PrisonWall1Life`/`PrisonWall2Life`.
These are exactly the bytes saved by the checkpoint system (see
[05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md)).

### Save buffer
`GameProgressBuffer` (`#220`, last byte is a checksum) is the snapshot blob written at
checkpoints and to tape (`logic/saveload.asm`).

---

## 5. The actor system

Enemies, bosses, NPCs, bullets, gas, bridges, the Metal Gear itself — all are **actors**.

* Each actor occupies a **fixed 128-byte (`#80`) structure** (`STRUCT ACTOR` etc. in
  `constants/structures.asm`). The first ~0x35 bytes are a common header; the rest is
  scratch space reinterpreted per actor type.
* `constants/structures.asm` is 3700 lines because it re-declares that same 128-byte block
  once per actor type (`PITFALL`, `BOOMERANG`, `PRISONER`, `GAS`, `ALERT_GUARD`, `BRIDGE`,
  `FIRE_TROPPER`, …). They're **overlays of the same memory**, just with type-specific field
  names and comments. You only need to learn the common header once.

Common header fields (offset → name):

| Off | Field | Notes |
|----:|-------|-------|
| 0 | `ID` | Actor type (`ID_*` in `Enums.asm`). Bit 7 = killed. |
| 1 | `Status` | Per-actor state-machine index. |
| 2–5 | `Ydec,Y,Xdec,X` | Position (8.8 fixed point). |
| 6 | `MOVING` | 0 = stationary. |
| 7–10 | `speedYdec,SpeedY,speedXdec,SpeedX` | Velocity. |
| 11 | `SpriteId` | Base sprite/animation set. |
| 12 | `ANIM_CNT` | Animation timer. |
| 13 | `LIFE` | 0 ⇒ actor dies. |
| 14 | `COLLISION_CFG` | bit0 collide w/player, bit1 collide w/player shots, bit2 misc. |
| 18 | `Direction` | 1=U 2=D 3=L 4=R. |
| 0x1E | `TOUCH_INFO` | bit7 touched player, bit6 punched, bits4-0 which player shot hit. |
| 0x20 | `NumSprites` + 4× `(Layer,Y,X,Pattern,Color)` | The hardware sprites this actor draws. |
| 0x40+ | `GuardStatus`, `SEE_PLAYER_F`, `AwakeTime`, … | Guard AI scratch. |

**Per-actor behavior** lives in `logic/actors/` (one file per actor: `guard.asm`,
`tank.asm`, `hindd.asm`, `bigboss.asm`, `metalgear`…, `scorpion.asm`, `prisoner.asm`,
`camera.asm`, `dog.asm`, etc.). Each actor type has an init handler and a per-frame
`Status` dispatcher.

**Spawning:** when you enter a room, `addroomitems`/the enemy loader reads
`data/actorsinrooms.asm` (the list of `ID + XY` per room) and instantiates actors.
`data/actorspriteattr.asm`, `data/spritesets.asm`, `data/paths.asm` and
`data/respawninfo.asm` feed the actor system.

Full ID list: see `constants/Enums.asm` (`ID_NONE`=0 … `ID_BIG_EXPLOSION`=#41). Notable:
`ID_GUARD_SLOW/MEDIUM/FAST`, `ID_CAMERA`, `ID_TANK`, `ID_HIND_D`, `ID_METAL_GEAR`,
`ID_BIG_BOSS`, `ID_BULLDOZER`, `ID_FIRE_TROOPER`, `ID_SHOT_GUNNER`, `ID_MACH_GUN_KID`,
`ID_ARNOLD`, `ID_GREY_FOX`, `ID_MADNAR`, `ID_FAKE_MADNAR`, `ID_ELLEN`, `ID_COWARD_DUCK`,
`ID_SCORPION`, `ID_PRISONER1`, `ID_SENTINEL`, `ID_DESERT_SECURITY`.

---

## 6. Rooms & rendering

* A room is an **8 columns × 6 rows grid of metatiles** (`data/rooms.asm`, label
  `RoomNNN`, indexed by `idxRooms`). Each byte is a metatile ID.
* A **metatile** (`data/metatiles.asm`, `data/tileblocks.asm`) expands to a block of
  VDP pattern tiles; `data/roomtileset.asm` chooses which tileset/graphics a room uses.
* `LoadRoomTiles` decodes the room into `RoomTileBuffer` and builds `CollisionTiles`
  (bit0 = solid) so movement and shots can test collisions cheaply.
* Graphics are stored compressed (1bpp/2bpp/3bpp) in `gfx/*.asm` and unpacked at runtime
  by `Load1bppTiles`/`Load2bppTile`/`Load3bppTile` into VRAM.
* Palettes: `data/palettes.asm`, applied per-room via `ChkRoomPal`/`SetRoomPal`.

Room connectivity is a separate table, `data/roomsconnections.asm`: 4 bytes per room =
`North, South, West, East` neighbor room IDs (`255` = no exit). See
[05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md).

---

## 7. Sound

`sound/` holds a complete PSG sound engine: `bgmdriver.asm` (music player), `setsound.asm`
(`SetSoundEntry`), `instruments.asm`, `sounddata.asm`, plus `sound/music/` and `sound/sfx/`.
`UpdateSound` is called from the ISR every frame (with banks 4/5 paged in). Trigger a
sound from anywhere with `SetSoundEntry`/`SetSoundEntryChk` (ID in `A`). The ROM header
even exports the sound work-area pointers for an external cartridge to reuse the driver.

---

## 8. Where to look — quick map of the tree

```
MetalGear.asm           top-level: JAPANESE flag + includes
Variables.asm           RAM memory map (#C000+)
constants/
  bios.asm              MSX BIOS entry points & system var addresses
  SystemVariables.asm   MSX system work area labels
  structures.asm        ACTOR/DOOR/ITEM/PLAYER_SHOT layouts
  Enums.asm             *** all IDs: items, weapons, actors, doors, modes ***
Banks0123.asm           core engine: ISR, state machines, player, menus, collisions...
Banks456.asm            sound + data tables (items, rooms-connections, palettes...)
Banks789.asm            room tilesets, big graphics, intro/menu, lorry, events
BanksABC.asm            sprites, palettes, texts, Metal Gear init
BanksDEF.asm            rooms, metatiles, doors, radio calls, save/load, ending
data/                   *** all content tables (the "level design") ***
gfx/                    compressed graphics
logic/                  engine logic, split by feature
  actors/               one file per enemy/boss/NPC behavior
  doors/                draw/open/enter/erase doors
  weapon/               one file per weapon behavior
sound/                  PSG music + SFX engine and data
room_images/            PNG renders of every room (reference art, not built into ROM)
```
