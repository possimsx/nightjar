# Testing the ROM in openMSX (headless, scripted)

How to drive the built ROM in openMSX from a script, read/write live state, and
prove a change behaves — the method used to verify the codec-gate engine swaps
(rocket item gate, text→flag, one-shot doors, flag pool). All of it is
reproducible from the command line; no GUI interaction.

The reusable scripts live in `tools/*.tcl`. This doc explains how they work so you
can write new ones.

---

## 1. Invocation

```bash
# from the repo root, after `python tools/build.py`
"D:/Games/Emu/OpenMSX21/openmsx.exe" -machine C-BIOS_MSX2 -carta MetalGear.rom \
    -romtype konami -script tools/<yourtest>.tcl
```

- **`-romtype konami` is REQUIRED.** openMSX mis-detects the mapper on this image
  (and hangs at boot on >128KB ROMs) without it.
- **`-machine C-BIOS_MSX2`** — no disk BIOS needed; boots straight to the cart.
- Wrap it in bash with a **timeout** so a hung run can't block:
  `timeout 120 "…/openmsx.exe" … >/dev/null 2>&1`.
- Paths openMSX writes to (logs, screenshots) must be **space-free** — use
  `C:/DevMSX/mgshots`, never a path under "MetalGear AI".
- openMSX is at `MG_OPENMSX` (default `D:/Games/Emu/OpenMSX21/openmsx.exe`); the
  editor's `run_openmsx` uses the same.

## 2. Script skeleton

```tcl
set throttle off                              ;# run as fast as the host allows
set LOG "C:/DevMSX/mgshots/out.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
proc lg {m} { global LOG; set f [open $LOG a]; puts $f $m; close $f }
# … schedule work …
after time 48.0 { exit }                       ;# ALWAYS exit or the run hangs
```

- **`set throttle off`** compresses emulated time — a 48s-emu-time script finishes
  in a few wall seconds.
- **`after time <t> { … }`** fires at emulated-time `t` seconds (counts only while
  the CPU runs). Use for a scripted timeline.
- **`after realtime <t> { … }`** fires after wall-clock `t`. Use for **polling**
  loops (see the warp poller), because a breakpoint pause freezes emu-time but not
  realtime.
- Parameterise with env vars (`MGLOG`, `MGFLAG`, `MGTID`, …) so one script covers
  many cases and the bash driver can loop over them.
- Log to a file (not stdout) — stdout is swallowed by `>/dev/null`.

## 3. Booting into gameplay

A fresh boot sits at the title (room 218). To reach in-game play you mash
**SPACE** and **RETURN** through the title + intro radio call:

```tcl
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"      ;# SPACE
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"  ;# RETURN
  set t [expr {$t + 0.65}]
}
# by ~t=39.5 you are playing, in the dock (room 121), GameMode=0
```

`keymatrixdown <row> <mask>` / `keymatrixup` press/release a key by MSX matrix
position: **SPACE = row 8 bit 1**, **RETURN = row 7 bit 128**.

## 4. Reading & writing state

```tcl
debug read memory  0xc130            ;# -> a byte (decimal)
debug write memory 0xc130 185        ;# poke a byte
reg PC ; reg SP ; reg A ; reg BC ; reg F     ;# read a register
reg PC 0x5ef4                          ;# write a register
```

**Key RAM addresses** (from `MetalGear.lst`; see §8):

| Addr | Name | Meaning |
|---|---|---|
| `0xC130` | Room | current room id |
| `0xC133` | NextRoomDirect | edge crossed: 1=N 2=S 3=W 4=E |
| `0xC136` | PreviousRoom | |
| `0xC151` | GameMode | 0=play,1=NextRoom,4=Radio,7=OpenDoor,A=Text,… |
| `0xC182` / `0xC184` | PlayerY / PlayerX | |
| `0xC185` | PlayerDir | |
| `0xC450` | DoorOpenArray | per-door 0=open/1=closed, index = doorid-1 |
| `0xC4FC` | IdDoorEnter | door id to walk through |
| `0xC5D0` | ItemsInTheRoom | 3 × 0x10: +0 id, +1 size, +2 Y, +3 X |
| `0xC610` | OpenBigBossDoor | story flag |
| `0xC617` | GateFlags | general flag pool (0..8) |
| `0xC62C` | DoorBuild2LockedF | story flag |
| `0xC661/2/3` | JeniRocketF / SchneiderCaptured / JeniOpenDoorF | story flags |
| `0xCEF0` | TextId | last text shown |

## 5. Warping to a room

The engine derives the destination from `Room` + `NextRoomDirect`, so you don't
walk — you poke a transition and let the engine run it.

**Spatial room** (has walk-off neighbours): set the *source* room + direction +
a walkable coord, then `GameMode=1` (NextRoom):

```tcl
after time 40.0 {
  debug write memory 0xc182 96 ; debug write memory 0xc184 128   ;# player Y,X
  debug write memory 0xc130 83 ; debug write memory 0xc133 4     ;# from room 83, heading E
  debug write memory 0xc151 1                                     ;# GameMode=NextRoom -> lands in 86
}
```

**Door-only room** (lorries / item rooms, ids 126–207): there is no walk-off, so
enter its door. Open it in `DoorOpenArray`, set `IdDoorEnter`, `GameMode=1`, and
**poll** until you arrive (the transition can eat a single poke, so re-fire):

```tcl
proc stage2 {} {
  set r [debug read memory 0xc130]
  if {$r == 86} {                              ;# in the door's room
    debug write memory 0xc498 0                ;# open door 73 (C450 + 73-1)
    debug write memory 0xc4fc 73               ;# IdDoorEnter = 73
    debug write memory 0xc133 0
    debug write memory 0xc151 1                ;# fire
  }
  if {$r != 185} { after realtime 0.3 stage2 } ;# keep polling until arrived
}
after time 41.0 stage2
```

Compute the door chain to any room with the editor's planner:
`python -c "import sys;sys.path.insert(0,'tools/editor');import server;print(server._warp_door(185))"`
→ `(83, 4, [(86, 73, 185)])` = warp 83→E→86, then door 73 → 185.

⚠ **Walk-off trap:** poking `Room` to a door-only id and letting the player walk
off the edge resolves to `0FFh`, which `SetNextRoom` misreads as an elevator →
RAM trash → reset (see [SPECIAL-ROOMS.md §1b](SPECIAL-ROOMS.md)). Always enter
door-only rooms through their (opened) door, never by a bare `Room` poke + walk.

## 6. A/B ROM comparison (the neutrality proof)

The strongest way to show a refactor is behaviour-neutral: run the **same script**
on the OLD and NEW ROMs and diff the logs.

```bash
git stash            # or build from HEAD into MG_old.rom
python tools/build.py && cp MetalGear.rom C:/DevMSX/mgshots/MG_old.rom
git stash pop
python tools/build.py && cp MetalGear.rom C:/DevMSX/mgshots/MG_new.rom
for rom in old new; do
  MGLOG="wb_$rom.txt" timeout 120 "…/openmsx.exe" … -carta "C:/DevMSX/mgshots/MG_$rom.rom" … -script tools/wbtest.tcl
done
diff C:/DevMSX/mgshots/wb_old.txt C:/DevMSX/mgshots/wb_new.txt && echo IDENTICAL
```

`wbtest.tcl` is a ready-made sweep (navigates several rooms, dumps room/actors/
items/doors/map-checksum). **Gotcha:** rebuild the "stock" ROM *before* the
baseline run — a leftover edited `MetalGear.rom` silently contaminates the
baseline (this bit me once: the "stock" run showed an edited result).

## 7. Forced subroutine call (unit-testing a routine)

To exercise one routine without driving the whole game: set its inputs, push a
sentinel return address, breakpoint the sentinel, and set `PC` to the routine.
The breakpoint fires on `ret`, where you read the outputs.

```tcl
proc report {} {                                ;# runs when the routine returns
  lg "carry=[expr {[reg F] & 1}] flag=[debug read memory 0xc617]"
  exit
}
after time 39.5 {
  debug write memory 0xc617 0                   ;# clear inputs
  reg A 90                                       ;# A = argument
  reg BC 0xc000                                  ;# other args
  set sp [expr {[reg SP] - 2}] ; reg SP $sp      ;# push return addr 0xE010 (LE)
  debug write memory $sp 0x10 ; debug write memory [expr {$sp+1}] 0xe0
  debug set_bp 0xe010 {} { report }              ;# trap the return
  reg PC 0x5ef4                                  ;# jump into the routine
}
```

Read results in the callback: **carry = `[reg F] & 1`** (DoorUnlocked does `scf`,
DoorLocked does `and a`), other registers via `reg`, side effects via
`debug read memory`. `0xE010` is just an unused RAM address to land on; the bp
fires before it executes anything.

## 8. Bank paging for forced calls

The Konami mapper (this ROM) has **`0x4000–0x5FFF` fixed to segment 0**; the
`0x6000`, `0x8000`, `0xA000` windows are switchable. A forced-call target in the
fixed window (e.g. `SetTextGateFlag` @ `0x5EF4`) is always mapped and just works.
A target in a switchable window (e.g. `ChkGateDoor` @ `0x79C0`, only paged in
during door checks) must have its **segment paged first**:

```tcl
debug write memory 0x6000 1     ;# map ROM segment 1 into 0x6000-0x7FFF
```

Find the right segment empirically — write each candidate to `0x6000` and read the
routine's first opcode until it matches:

```tcl
for {set s 0} {$s < 16} {incr s} {
  debug write memory 0x6000 $s
  lg "seg $s -> [debug read memory 0x79c0]"     ;# want 213 (0xD5 = push de)
}
```

## 9. Finding addresses in MetalGear.lst

`python tools/build.py` writes `MetalGear.lst`.

- **Instructions** show the real address + bytes, e.g.
  `5EEE 21 61 C6   ld hl, JeniRocketF` → `JeniRocketF = 0xC661`.
  So `grep -nE "ld .*JeniRocketF" MetalGear.lst` gives the address from the operand.
- **Reserve directives** (`Label: # N`) show `0000` in the address column, so
  compute a var address by counting `# size` entries from a known neighbour, or by
  finding any instruction that references it. (Ex: `GateFlags` had no reference; I
  counted from `OpenBigBossDoor=0xC610` and cross-checked from `DoorBuild2LockedF=0xC62C`.)
- Routine labels show their address directly: `grep -nE "ChkGateDoor:" MetalGear.lst`.

## 10. Existing scripts (tools/*.tcl)

| Script | What it does |
|---|---|
| `boot.tcl` | boot + timed screenshots (sanity that it runs) |
| `start.tcl` | boot, climb the dock ladder, log rooms |
| `wbtest.tcl` | room/actor/item/door/map sweep — the A/B neutrality workhorse |
| `rockettest.tcl` | warp to room 185, dump items; gate-flag value + **address** via `MGFLAG`/`MGFLAGADDR` |
| `texttest.tcl` | forced call to `SetTextGateFlag(A=MGTID)`, read story flags + an extra addr (`MGXADDR`) |
| `doortest.tcl` | forced call to `ChkGateDoor` (pages segment 1), read carry + flags |
| `radio.tcl`, `sweep.tcl`, `diag.tcl`, `cptest.tcl`, `gwtest.tcl`, `d4test.tcl` | earlier feature checks (radio, reachability, checkpoints, world-bank, gateways) |

## 11. Gotchas checklist

- Rebuild before a "stock" baseline run (don't trust a leftover `MetalGear.rom`).
- Always `exit` (and wrap in `timeout`) — an unterminated script hangs.
- Log/screenshot paths must be space-free (`C:/DevMSX/mgshots`).
- Poll door-only warps (`after realtime`), re-firing until `Room` matches the dest.
- Never bare-poke `Room` to a door-only id and walk off an edge (reset trap).
- Page the segment before a forced call into a switchable window.
- Interrupts can fire mid forced-call; keep the routine short and it's a non-issue.
