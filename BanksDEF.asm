;----------------------------------------------------------------------------
;
;
; MegaROM banks D, E and F
;
;
;----------------------------------------------------------------------------

		    org	#6000

	IF (WORLDBANK)
	; room layouts moved to BanksWorld.asm layout segments (plan C5)
	ELSE
	include	"data/rooms.asm"
	ENDIF

	include	"data/metatiles.asm"

	include	"data/doortiles.asm"

	IF (WORLDBANK)
	; per-room door data moved to BanksWorld.asm (plan C4); the tile pairs
	; above stay here for the draw/erase paths
	ELSE
	include	"data/doors.asm"
	ENDIF

	include	"gfx/powerswitch.asm"

	include	"data/tileblocks.asm"

	IF (WORLDBANK)
	; radio calls moved to BanksWorld.asm (plan C3)
	ELSE
	IF (JAPANESE)
	include	"data/radiocallsjp.asm"
	ELSE
	include	"data/radiocalls.asm"
	ENDIF
	ENDIF
	
	IF (WORLDBANK)
; TRAP #5 (docs/LIMITS-PLAN.md): the code files below are called through
; SetBankInA0_F, which maps segment F at #A000 ONLY (their callers execute in
; segs 1/2 and must stay mapped). Evicting data from this bank shifts
; everything down — without this pad the code slides out of segment F and the
; callers execute whatever seg 2 holds at those addresses. So pin the code
; block to #A000 (= segment F). The pad is exactly the reclaimed headroom:
; grow metatiles/tile data above, and this pad shrinks to keep code pinned.
		    ds	    (#0A000-$),#ff
		    ASSERT  $=#0A000
	ENDIF
	include	"logic/updatesprites.asm"
	
	include "logic/saveload.asm"

	include	"logic/ending.asm"

	include	"logic/drawlaserbeams.asm"

		    ; Fill empty space
		    ds      (#C000-$),#ff
		    ASSERT  $=#C000
