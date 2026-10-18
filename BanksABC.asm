;----------------------------------------------------------------------------
;
;
; MegaROM banks A, B and C
;
;
;----------------------------------------------------------------------------

		    org	#6000


	include	"data/playersprite.asm"

	include	"data/spritesets.asm"

	include	"data/weaponspratt.asm"
		    
	include	"gfx/sprites.asm"

	include	"data/laserconfig.asm"

	include	"data/musicradioconfig.asm"

	IF (JAPANESE)
	include	"data/textsjp.asm"
	ELSE
	include	"data/texts.asm"
	ENDIF

;----------------------------------------------------------------------------
;
; Initialize Metal Gear	logic
;
;----------------------------------------------------------------------------

InitMetalGear_:
		    ld	    a, (MetalGear_KO)		    ; Metal Gear destroyed. Self destruction activated
		    or	    a
		    jp	    nz,	DismissActor2_

		    ld	    hl,	MetalGear_KO		    ; Metal Gear destroyed. Self destruction activated
		    ld	    (ix+ACTOR.BASE_SPR_ID), l
		    ld	    (ix+ACTOR.KO_POINTER_H), h
		    ld	    (ix+ACTOR.COLLISION_CFG), 3	    ; Bit0 = Check collision with player, Bit1 = Check player shots, bit2 = Pitfall is closed

ChkDrawMetalGear:
		    ld	    a, (EnemyList)		    ; Array of enemies in the room
		    cp	    ID_METAL_GEAR
		    ret	    nz				    ; There is no Metal	Gear

		    ld	    (ix+ACTOR.Status), 0
		    ld	    de,	6020h
		    jp	    DrawMetalGear_


RemoveMetalGear:
		    ld	    de,	6020h
		    jp	    EraseMetalGear_


;----------------------------------------------------------------------------
; Unified per-room flags (data-driven). Read once per room load into the
; CurRoomFlags / CurRoomFlags2 RAM bytes (see InitRoom); every check then tests one bit:
;   RoomFlags:  bit0 dark (flashlight)  bit1 gas (gas mask)  bit2 electric floor
;               bit3 water  bit4 deep water (shadow tiles)
;               bit5 moving lasers (Banks0123 DrawMovingLasers)  bit6 laser-beam room
;               (drawlaserbeams.asm)  bit7 short camera lasers (lasershot/damagelaser.asm)
;   RoomFlags2: bit0 capture trap (see common.asm)   bits1-7 spare (room for future flags)
; This routine lives here in seg 12 (BanksABC) where there is room; ADD_HL_A is in
; the always-mapped seg 0, so it is callable. Caller maps A/B/C and restores.
;----------------------------------------------------------------------------
CacheRoomFlags:
		    ld	    a, (Room)
		    ld	    hl,	RoomFlags
		    call    ADD_HL_A
		    ld	    a, (hl)
		    ld	    (CurRoomFlags), a
		    ld	    a, (Room)
		    ld	    hl,	RoomFlags2
		    call    ADD_HL_A
		    ld	    a, (hl)
		    ld	    (CurRoomFlags2), a
		    ret

RoomFlags:	    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	4, 0, 0, 0, 0, 0, 0, 0, 40h, 40h, 0, 0, 0, 2, 0, 0
		    db	0, 0, 0, 0, 0, 4, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 8, 0, 60h, 8, 8, 0, 0, 8, 8, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0
		    db	2, 2, 2, 0, 2, 2, 0, 0, 0, 18h, 18h, 8, 0, 0, 4, 80h
		    db	2, 0, 2, 0, 4, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 18h, 18h, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

RoomFlags2:	    db	0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
		    db	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

		    ; Fill empty space
		    ds      (#C000-$),#ff
		    ASSERT  $=#C000

