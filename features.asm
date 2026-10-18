;----------------------------------------------------------------------------
;
; Feature flags — engine ADDITIONS, toggled here.
;
; Convention (see docs/ENGINE-HOOKS.md): every addition to the engine lives in a
; separate file under hooks/ (or its own Banks*.asm) and is reached from the stock
; code ONLY through a thin `IF (FLAG) include "hooks/x.asm" ELSE <stock> ENDIF`
; shim. With every flag 0 the assembled engine is byte-identical to the original
; disassembly. (Game CONTENT in data/ and gfx/ is a separate axis — revert with
; git to get stock content.)
;
; sjasm appends output sequentially and cannot inject bytes at an earlier ROM
; offset, so a hook that sits at a fixed stock address keeps a 3-line shim inline;
; only its code BODY moves to hooks/.
;
;----------------------------------------------------------------------------

EXTGFX		equ	0	; 1 = extended-graphics tilesets (gfx ids 8-15) in segments
				;     10h+ (hooks/extgfx.asm + BanksExtGfx.asm); ROM auto-grows
				;     to 256KB. 0 = stock 128KB. Toggle from the map editor
				;     ("Extended banks") or here.

WORLDBANK	equ	0	; 1 = world-data bank (docs/LIMITS-PLAN.md Phase C): items-in-rooms
				;     + actors-in-rooms move to segment WORLD_SEG (BanksWorld.asm,
				;     hooks/worldbank.asm), freeing ~2.1KB of Banks456 for paths/
				;     routes; ROM auto-grows to 256KB. 0 = stock 128KB layout.

WORLD_SEG	equ	16 + (EXTGFX*3)	; first segment after the stock 16 (and ext gfx)
WORLD_LSEG1	equ	WORLD_SEG + 1	; room-layout segments: assembled as ONE contiguous
WORLD_LSEG2	equ	WORLD_SEG + 2	; 16KB #6000-#9FFF window (BanksWorld.asm, plan C5)

; World-directory offsets (Phase D2): each world's DATA segment begins with a
; pointer directory at #6000 (dw per table), its first LAYOUT segment likewise.
; The engine reads all top-level tables through these, so every world can lay
; out its content freely - only the directory position is a fixed contract.
WDIR_ACTORS	equ	#6000
WDIR_ITEMSIDX	equ	#6002
WDIR_ITEMS	equ	#6004
WDIR_DOORS	equ	#6006
WDIR_DOORLOGIC	equ	#6008
WDIR_DOORDAT	equ	#600A
WDIR_RADIO	equ	#600C
WDIR_CONNS	equ	#600E
WDIR_GATEWAY	equ	#6010
WDIR_PATHS	equ	#6012	; D4: per-world room->routes index (route blocks stay in Banks456)
WDIR_CHKPT	equ	#6014	; D4: per-world checkpoint [room,prevRoom] pairs
LDIR_ROOMS	equ	#6000
LDIR_META	equ	#6002
LDIR_MSET	equ	#6004
WORLDS	equ	2		; number of worlds assembled (0 = canonical data/; genworld bumps this)
WGATE	equ	#6020		; fixed in-world gateway-resolver entry (after the 32-byte directory)
