# Banks0123 — reclaimable dead code

`Banks0123.asm` (the 4 lower/always-present engine segments, `org #4000`, filled to
`#C000` by `ds (#C000-$),#ff` + `ASSERT $=#C000`) is the tightest bank in the ROM —
it periodically sits at **0–2 free bytes**. When a rework needs code space *there*
(e.g. adding an actor-movement state to the capture script), pull it from the dead
code catalogued below rather than relocating logic across segments.

Removing dead code just grows the `ds` fill, so the `ASSERT $=#C000` keeps holding and
the ROM still builds. Anchors are **searchable text** (labels / comments), not line
numbers — the line numbers drift every time the file is edited.

_Current free space: check the `ds (#C000-$)` line in `MetalGear.lst` → `0xC000 −
<content-end-addr>`. As of the 2026-07-12 reclaim: **~37 bytes**._

## How a block qualifies as safe to remove

All of these are **confirmed dead** by three independent checks:
1. **Dev-flagged** — the original disassembly author marked it `; Unused` / `; (!?) Not used` / `; (!?) Unused code`.
2. **Unreachable** — the immediately-preceding instruction is an unconditional `ret`/`jp`, and the block's entry has **no label** (nothing can fall into or jump to it).
3. **Unreferenced** — no `call`/`jp`/`jr`/`dw` to any label inside it, anywhere in the codebase (`grep` the label across all `*.asm`, excluding `projects/`).

To hunt for more: list every label defined in `Banks0123.asm`, count whole-word
occurrences across all base `*.asm`; a label with **1** occurrence (its own definition)
is a candidate — but only truly dead if it's *also* preceded by an unconditional
terminator (otherwise it's a fall-through continuation label that's reachable, just
unnamed-elsewhere — see the false-positives list).

## Already reclaimed (2026-07-12)

| Block | Marker | ~Bytes | Notes |
|-------|--------|-------:|-------|
| `WriteVRAM` routine | `; Unused` | 14 | VRAM-write helper; preceded by `pop de / ret`. Gone. |
| enemy-spawn loop (`loc_10168A`) | `; (!?) Unused code` | 25 | `inc hl … call AddEnemy … djnz loc_10168A / ret`; preceded by `HideEnemySprs`'s `ret`; `loc_10168A` only referenced by its own `djnz`. Gone. |

Total reclaimed: **~39 bytes** (this is where the current ~37 free bytes came from).

## Available — not yet removed

Small, but individually confirmed safe. Anchor on the marker comment + the instruction.

### A. `AlertRespawnTimer` write — ~5 bytes
Search: `; (!?) Not used` (the one directly above `ld (AlertRespawnTimer), a`).
```
; (!?) Not used
		    ld	    a, 1
		    ld	    (AlertRespawnTimer), a
```
- Preceded by `jp SetAreaMusic2` (unconditional) → unreachable.
- No label on the block. `TransformAlertGuard:` (the real routine) follows and is unaffected.
- Bytes: `ld a,1` (2) + `ld (AlertRespawnTimer),a` (3) = **5**.

### B. `ErasePrintTxt` call — ~3 bytes
Search: `; (!?) Unused code` (the one directly above `call ErasePrintTxt`).
```
; (!?) Unused code

		    call    ErasePrintTxt
```
- Preceded by `ErasePrintTxt`'s own `jp PrintTextXY` (unconditional) → unreachable.
- No label on the `call` line. `ChgRadioFreq:` (the real routine) follows and is unaffected.
- Bytes: `call ErasePrintTxt` = **3**.

Removing A + B frees **~8 more bytes** (→ ~45 total available with the two above).

## Checked and NOT dead (don't re-investigate)

These came up as zero-cross-reference labels but are **reachable by fall-through**
(the code above them doesn't end in a terminator) — the label is just a documentation
name nothing jumps to. Leave them:

- `DummyLoop` — `jr $` (intentional hang after `ei`; reached by fall-through).
- `ChkFlashLight` — falls through from the `bit 0,a / jr z` above.
- `dummyAddr5` — `jp SetActorSpeed`, fall-through tail of `GetSpeedToPoint2`.
- `dummyAddr6` — the `ret` at the end of a routine (fall-through).
- `SetPlayerSpeed` — fall-through continuation of `ResetPlayerSpd`.
- `SelectWeapon_` — `jr SelectWeapon2`, fall-through after `xor a`.

## Other markers (NOT reclaimable)

The many other `; (!?)` comments in `Banks0123.asm` annotate **quirky-but-live** code
(the disassembly author's questions about the original logic), not dead blocks — e.g.
`Pause_1_F5_2` "(!?) Is it used anywhere?" is written here but **read** elsewhere
(`ld a,(Pause_1_F5_2)`), so it's live. Don't remove on the strength of a `(!?)` alone;
apply the three-check test above.
