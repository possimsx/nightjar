# 01 — Building the ROM

## Tool

The project assembles with **Sjasm 0.39j** (Konamiman's fork). On this machine it lives at:

```
C:\DevMSX\sjasm039j\sjasm.exe
```

Sjasm is a single self-contained Z80 assembler executable. No install, no dependencies.

## Quick build

From the project root (`c:\DevMSX\MetalGear AI`):

```sh
"C:/DevMSX/sjasm039j/sjasm.exe" MetalGear.asm MetalGear.rom
```

Expected output:

```
SjASM Z80 Assembler v0.39j
Pass 1 complete (0 errors)
Pass 2 complete
Errors: 0
```

This produces **`MetalGear.rom`** — exactly **131072 bytes (128 KB)**. That is the
MegaROM image you load into an MSX2 emulator (openMSX, blueMSX, WebMSX, …) or flash to a
cartridge.

### Command-line form

```
sjasm [-options] sourcefile [targetfile [listfile [exportfile]]]
```

Useful options:

| Flag | Effect |
|------|--------|
| `-s` | Also emit a `.sym` symbol file (great for debugging in openMSX's debugger). |
| `-l` | Include the label table in the listing. |
| `-q` | Quiet (no listing). |
| `-v` | Visual-Studio-format error messages (put it **first**). |
| `-i<path>` | Add an include search path. |

Example with symbols + listing for debugging:

```sh
"C:/DevMSX/sjasm039j/sjasm.exe" -s MetalGear.asm MetalGear.rom MetalGear.lst MetalGear.sym
```

> The repo's `.gitignore` already ignores `*.rom`, `*.lst`, `*.sym`, `*.out`, so build
> artifacts won't be committed.

## What gets assembled

`MetalGear.asm` is the **top-level file**. It does almost nothing except set one flag and
`include` everything in order:

```asm
JAPANESE  equ  0          ; 1 = Japanese version, 0 = English version

          include "constants/bios.asm"
          include "constants/SystemVariables.asm"
          include "constants/structures.asm"
          include "constants/Enums.asm"
          include "Variables.asm"

          include "Banks0123.asm"   ; fixed code bank 0 + banks 1/2/3
          include "Banks456.asm"    ; sound + most data tables
          include "Banks789.asm"    ; room tiles, big graphics, intro/menu
          include "BanksABC.asm"    ; sprites, palettes, texts, Metal Gear init
          include "BanksDEF.asm"    ; rooms, doors, radio, save/load, ending
          end
```

Each `BanksXXX.asm` begins with `org #6000` and ends with a
`ds (#C000-$),#ff` / `ASSERT $=#C000` pair. That padding fills each 24 KB bank-group to its
boundary and the assertion guarantees a bank group never overflows — **if you add code/data
and the build fails on an ASSERT, you've overrun a bank** (see
[02-ARCHITECTURE.md](02-ARCHITECTURE.md#bank-layout)).

## Build flags

### `JAPANESE` (in `MetalGear.asm`, line 38)

* `JAPANESE equ 0` → English version (CRC32 `E85C5731`).
* `JAPANESE equ 1` → Japanese version (CRC32 `FAFE1303`).

The flag switches which text/data files are included (e.g. `data/texts.asm` vs
`data/textsjp.asm`, `data/weaponnames.asm` vs `data/weaponnamesjp.asm`, etc.) via `IF
(JAPANESE) … ELSE … ENDIF` blocks in the bank files.

### Region lock

The **Japanese** build is region-locked — it resets on a non-Japanese machine. The check
is `logic/regionlock.asm`, called from `Start` and from the Konami-logo state. To disable
the lock, reduce that file to just:

```asm
RegionLock:
        ret
```

The English build's `RegionLock` is already effectively a no-op.

## Verifying a build

* **Size must be 131072 bytes.** Anything else means an `org`/padding problem.
* For byte-exact parity with an original dump, compare CRC32 against the values above.
* Load in openMSX with an MSX2 machine + the disassembly's `.sym` file for symbol-level
  debugging.

## Common pitfalls

* **Run from the project root** so the relative `include "data/…"` paths resolve.
* The source uses **tabs**; keep them if you edit (Sjasm is whitespace-tolerant, but the
  comment columns line up on tabs).
* If you add data and trip an `ASSERT $=#C000`, you overflowed a bank group — move some
  data to a bank that still has free space (the `ds (#C000-$),#ff` line shows how much
  `#ff` padding was free before your change).
