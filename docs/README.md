# Metal Gear (MSX2, RC750) — Project Documentation

This folder is a **reusable knowledge base** for the fully-commented disassembly of
Konami's *Metal Gear* (MSX2, 1987, code RC750), disassembled by Manuel Pazos.

The goal of these documents is twofold:

1. **Understand the original game completely** — how it is built, how the engine works,
   where every object lives, and how the story advances.
2. **Reuse the engine to build a new game** — the code is structured as a reusable
   "Konami action-adventure engine". These docs tell you which data tables to swap and
   which logic to keep.

> ## 🚧 New game in progress
> The new game built on this engine is codename **NIGHTJAR**:
> * **[NEWGAME-PLOT.md](NEWGAME-PLOT.md)** — the master plot / story bible.
> * **[NEWGAME-BEATSHEET.md](NEWGAME-BEATSHEET.md)** — the room-by-room build work order
>   (per-room: tileset, items, enemies, doors, radio caller + line) for editing the `data/`
>   tables.
>
> Docs 01–06 below describe the original engine these are built on.

## Document index

| File | What it covers |
|------|----------------|
| [NEWGAME-PLOT.md](NEWGAME-PLOT.md) | **The new game's story bible (codename NIGHTJAR)** — full plot, cast, zones, bosses, items, ending, and how each beat maps onto the engine. |
| [NEWGAME-BEATSHEET.md](NEWGAME-BEATSHEET.md) | **Room-by-room build work order** — per critical-path room: tileset, items, enemies, doors, radio caller + the exact line; plus zone map, filler-room rule, and per-file edit checklist. |
| [01-BUILD.md](01-BUILD.md) | How to compile the ROM with `sjasm.exe`, build flags, output verification, JP/EN versions, region lock. |
| [02-ARCHITECTURE.md](02-ARCHITECTURE.md) | MegaROM bank layout, memory map, the two state machines (GameStatus + GameMode), the actor system, data structures, rendering, the main loop. |
| [03-STORY-INDEX.md](03-STORY-INDEX.md) | The full game narrative: intro, radio-call script (who, where, what they say), boss encounters, and the ending — in story order. |
| [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md) | Every item/weapon/equipment object: ID, what it is for, where it is found, and when it is needed to progress. |
| [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md) | Room map, building structure, door-locking system, the critical path, and the checkpoint/save system. |
| [SPECIAL-ROOMS.md](SPECIAL-ROOMS.md) | The room-number address space (which id bands mean what) + a full inventory of every **hardcoded-by-room-number** behaviour (parachute, elevators, bridges, hazards, bosses) — what's data vs. ASM, for safe topology rework. |
| [CODEC-GATE-PLAN.md](CODEC-GATE-PLAN.md) | Making **codec/progression gates** editable — items/doors locked until a radio call sets a story flag (rocket launcher, compass door), plus the antenna-zone table that silences the radio. Data-table + interpreter rework so the editor can author them. PLANNED. |
| [HAZARD-FLAGS-PLAN.md](HAZARD-FLAGS-PLAN.md) | Making room hazards (dark/gas) **data-driven** instead of hardcoded `cp <id>` — the `RoomFlags` proposal + the shipped `DarkRooms` list (v1), with the bank/RAM analysis. |
| [HAZARD-EDITOR-FEATURES.md](HAZARD-EDITOR-FEATURES.md) | **TODO for the map editor**: which room-hazard authoring features are still missing (dark/gas toggles, electric floor, water, laser-beams) vs. already editable as actors, prioritized F1–F6. |
| [06-REWORK-GUIDE.md](06-REWORK-GUIDE.md) | A practical recipe for re-skinning / re-designing the game while reusing the engine: which files are *data* (safe to change) vs *logic* (the engine). |
| [07-TEXT-ENCODING.md](07-TEXT-ENCODING.md) | The text format (glyph map, control codes, the 92-entry dictionary) and **`tools/mgtext.py`** — decode/encode/patch in-game text in plain English. |
| [08-GRAPHICS.md](08-GRAPHICS.md) | The graphics formats (palettes, font, 1/2/3bpp tiles) and **`tools/mggfx.py`** — decode/preview compressed tile graphics as PNG. |
| [ROM-TESTING.md](ROM-TESTING.md) | How to test the built ROM in **openMSX headlessly from a script** (`tools/*.tcl`): boot/mash into gameplay, read/write live RAM, warp to any room, A/B ROM diffs, forced subroutine calls, Konami bank paging, finding addresses in the `.lst`. The method used to verify the codec-gate engine swaps. |

## The 30-second summary

* **Platform:** MSX2, 128 KB Konami MegaROM (mapper without SCC).
* **Assembler:** Sjasm 0.39 (`C:\DevMSX\sjasm039j\sjasm.exe`).
* **Genre:** Top-down stealth action-adventure. Solid Snake infiltrates *Outer Heaven*.
* **World:** 3 buildings + outdoor/desert/basement areas, ~124 playable rooms (room IDs up to 250 including elevators, lorries, ladders, dark rooms).
* **Engine shape:** Everything is **data-driven**. Rooms, items, enemies, doors, radio
  calls and texts are all lookup tables indexed by room number. The Z80 logic is generic;
  the *content* lives in `data/`.
* **Core loop:** All gameplay runs inside the **VBLANK interrupt handler**, dispatched by
  two jump tables: `GameStatusLogic` (title/menu/play/ending) and `GameLogic`
  (the per-frame in-game mode: walking, menus, radio, elevator, dead, etc.).

> See [02-ARCHITECTURE.md](02-ARCHITECTURE.md) for the deep dive.
