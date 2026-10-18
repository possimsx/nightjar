;---------------------------------------------------------------------------
;
; Checkpoints
;
; The game progress is saved when moving from room A to	B
; So it	is possible to continue	from that points after a game over
;
;---------------------------------------------------------------------------

ChkSaveGameStatus:
		    ld	    a, (MetalGear_KO)		    ; Metal Gear destroyed. Self destruction activated
		    and	    a
		    ret	    nz				    ; The game status is not saved after destroying Metal Gear

	IF (WORLDBANK)
; Plan D4: the checkpoint list lives PER WORLD (WDIR_CHKPT in the world
; segment). Map the ACTIVE world at #6000 for the scan; the callers run under
; SetBankInA0_6 (segment 6 at #A000 ONLY), so the previous #6000 segment MUST
; be restored from the BankIn60 shadow on BOTH exits - the match result rides
; in the carry flag across the restore (ld/call/MapSeg60 preserve flags; a
; push af/pop af would destroy it). B is scratch at both call sites.
		    ld	    a, (BankIn60)
		    ld	    b, a			    ; B = caller's #6000 segment
		    ld	    a, (CurWorldSeg)
		    call    MapSeg60
		    call    ChkSaveGameStatus1		    ; carry = a pair matched
		    ld	    a, b
		    call    MapSeg60			    ; restore (flags preserved)
		    jr	    c, StoreGameStat
		    ret

ChkSaveGameStatus1:
		    ld	    hl,	(WDIR_CHKPT)		    ; this world's checkpoint list
	ELSE
		    ld	    hl,	SaveStatRooms		    ; List of rooms that work as checkpoints
	ENDIF
		    ld	    a, (Room)
		    ld	    d, a
		    ld	    a, (PreviousRoom)
		    ld	    e, a

ChkSaveGameStatus2:
		    ld	    a, (hl)
		    cp	    0FFh			    ; End of checkpoint	list
		    ret	    z
		    inc	    hl
		    cp	    d
		    jr	    nz,	ChkSaveGameStatus3

		    ld	    a, (hl)
		    cp	    e
	IF (WORLDBANK)
		    scf					    ; carry = match; the end-of-list
		    ret	    z				    ; exit's `cp 0FFh` leaves carry 0
	ELSE
		    jr	    z, StoreGameStat
	ENDIF

ChkSaveGameStatus3:
		    inc	    hl
		    jr	    ChkSaveGameStatus2


;---------------------------------------------------------------------------
;
; Restore checkpoint
;
;---------------------------------------------------------------------------

RestoreGameStat:
		    xor	    a
		    call    SaveGameStaus2

		    xor	    a
		    ld	    (DamageDelayTimer),	a
		    ret


;---------------------------------------------------------------------------
;
; Create checkpoint (savestate)
;
;---------------------------------------------------------------------------

StoreGameStat:
		    ld	    a, 1			    ; Save mode

SaveGameStaus2:
		    ld	    ix,	TempData
		    ld	    (ix+0), a

		    ld	    de,	GameProgressBuffer
		    ld	    hl,	GameDataAreas

SaveGameStaus3:
		    ld	    c, (hl)
		    inc	    c
		    ret	    z				    ; FF = End list

		    dec	    c
		    inc	    hl
		    ld	    b, (hl)			    ; BC = Address
		    inc	    hl
		    ld	    a, (hl)			    ; A	= Number of bytes
		    inc	    hl
		    push    hl

		    ld	    l, c
		    ld	    h, b
		    ld	    c, a
		    ld	    b, 0

		    bit	    0, (ix+0)			    ; Store or restore game status?
		    jr	    nz,	SaveGameStaus4

		    ex	    de,	hl			    ; Swap source and destination addresses

SaveGameStaus4:
		    ldir				    ; Transfer data

		    bit	    0, (ix+0)
		    jr	    nz,	SaveGameStaus5

		    ex	    de,	hl

SaveGameStaus5:
		    pop	    hl
		    jr	    SaveGameStaus3



;---------------------------------------------------------------------------
;
; Game memory blocks used to save/restore checkpoints
; DW address
; DB Number of bytes

; FF = End
;---------------------------------------------------------------------------
GameDataAreas:	    dw Room
		    db 20h
		    dw PlayerControlMod			    ; 8=Intro scene, 7=Ladders climb, 6=ladders	walk, 5=Air flow, 4=Parachute, 3=Dead, 2=Elevator, 1=Punch, 0=Walk
		    db 20h
		    dw MaxAmmoGun
		    db 50h
		    dw DoorOpenArray			    ; 0=Open/1=Closed status of	all doors
		    db 0D8h
		    dw Equipment			    ; +0 Item ID, +1 tens/units, +2 hundreds, +3 unused
		    db 90h
		    dw GameDataArea
		    db 0A0h
	IF (WORLDBANK)
		    dw CurWorldSeg			    ; Phase D2: the active world survives
		    db 1				    ; checkpoint restore / game-over continue
	ENDIF
		    db 0FFh

; (SaveStatRooms moved to data/checkpoints.asm - included right after this
; file in Banks456.asm - so the	map editor's "restore original"	can revert the
; checkpoint DATA without touching the terminator-scanner CODE above.)
