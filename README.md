# Metal Gear (RC750, MSX2)

This is a modified fork of the fully annotated disassembly of Konami's *Metal Gear* for MSX2 by
Manuel Pazos ([GuillianSeed/MetalGear](https://github.com/GuillianSeed/MetalGear)). His original
README is kept unchanged below.


## About this fork

This is a solo hobby project. I wanted to make my own game on top of the Metal Gear engine, so I
built a **map editor**, called **NIGHTJAR**, that works directly on the annotated assembly source.

The name comes from my first experiment: using AI to replot the whole game with a new story,
cast and map, codenamed NIGHTJAR. The editor grew out of that work, and I kept the name for it.

Most of the editor and the assembly changes were written with heavy AI assistance (Claude), with
me steering the design and testing the results.

The original code hardcodes a lot of things: room numbers, special-case behaviours and table
sizes. To make the editor useful, I changed parts of the ASM to be more flexible. Several of
those hardcoded checks are now data tables or named constants, so the editor can change them
without touching the engine code.

### What the editor can do

The editor is a local web app (Python standard library only, no extra dependencies). It reads
and writes the `.asm` data files directly. Saves are surgical, so they only touch the blocks you
edited. It covers:

- **Rooms and connections**: the floor plan, room links, tilesets, doors and checkpoints
- **Items and actors**: placing items, enemies and bosses, with real MSX2 sprites drawn on the
  room preview
- **Enemy patrol paths**: drag-to-edit routes, with wall and coverage checks
- **Alert behaviour**: reinforcement respawns, rooms with no respawn, and guards hidden on entry
- **Text**: story and menu strings, item and weapon names, radio calls and frequencies, and what
  freed prisoners say
- **Graphics**: a pixel editor for items, actor sprites and player sprites, plus palettes
- **Special rooms**: parachute, ladder and elevator clusters, capture traps and hazards
- **Projects**: separate project folders, so new games can be built without touching the base
  game
- **Bigger worlds**: optional ROM growth up to 512KB (Konami mapper) and support for more than
  255 rooms

It can also build the ROM and launch it in an emulator from the browser.

### Running it

    python tools/editor/server.py --open

This opens the editor at `http://127.0.0.1:8765`. To build the ROM with automatic size padding:

    python tools/build.py

The [docs/](docs/README.md) folder covers the engine, the editor and the changes I made to the
assembly in detail.

The legal notice at the bottom of this page applies to this fork too.


## Original README

This repository contains the fully annotated disassembly of the original Metal Gear game, released by Konami for [MSX2](https://en.wikipedia.org/wiki/MSX) in 1987 with code RC750. I hope you will find the code comments useful to understand how the game works.


## Why?

I like to learn how things work, and to explain to others what I have learned.

This was a good oportunity to find out how Konami made games in the old good days, how all their games use the same structure, how they reused the same "libraries" in different games (e.g. the routine used to calculate the trajectory of a shot), etc.

Also, I like to find oddities (unused graphics, rooms, texts, musics, code...) and find bugs.

Last but not least, I wanted to be able to modify the game in order to fix bugs, and make it work on different MSX models (e.g. my MSX Turbo R can't save or load game data because it does not have a cassette port).


## How to assemble

Use [Sjasm 0.39](https://github.com/Konamiman/Sjasm) or a compatible assembler:

    sjasm MetalGear.asm MetalGear.rom


## Japanese vs English versions

It is possible to build both Japanese (CRC32 FAFE1303) and English (CRC32 E85C5731) versions of the game, by setting the `JAPANESE` constant to 1 or 0 in the `MetalGear.asm` file.

The Japanese version is region locked, this means that it won't work on a MSX computer with a non-Japanese ROM (the computer will just reset). If you want to disable the region lock just change the `logic/regionlock.asm` file so that it just contains this:

    RegionLock:
      ret


## Legal notice

This repository is provided "as is" for education purposes only. Any non-educational use of this repository might be illegal if you do not own an original copy of the game.

Also, the repository will be removed if Konami or their legal representatives ask me to do so.
