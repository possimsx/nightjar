
;----------------------------------------------------------------------------
;
; Check	if the player is on an electrified floor
;
;----------------------------------------------------------------------------

ChkElectricFloor:
		    ld	    a, (CurRoomFlags)		    ; unified hazard flags (cached at room load)
		    bit	    2, a			    ; bit2 = electrified floor room
		    ret	    z				    ; not an electric-floor room
		    ld	    a, (CurrentTileSet)		    ; which tiles are "live" depends on the tileset
		    add	    a, a			    ; *2 (word entries)
		    ld	    hl,	ElectricTiles
		    call    ADD_HL_A
		    ld	    c, (hl)
		    inc	    hl
		    ld	    b, (hl)			    ; bc = electrified tile pair for this tileset
		    ld	    a, b
		    or	    c
		    ret	    z				    ; this tileset defines no electrified tiles

ChkElectricFloor2:
		    ld	    a, (PowerSwitchOn)		    ; Power switch status 1=On,	0=Off/destroyed
		    and	    a				    ; Is the power switch on?
		    ret	    z				    ; No, it is	off or destroyed

		    push    bc
		    call    GetTilePlayer		    ; Get the tiles where the player is
		    pop	    bc

		    ld	    a, h			    ; Right tile
		    cp	    b				    ; Is it an electrified floor tile?
		    jr	    z, ChkElectricFloor3	    ; Yes

		    cp	    c				    ; Is it an electrified floor tile?
		    jr	    z, ChkElectricFloor3	    ; Yes

		    ld	    a, l			    ; Left tile
		    cp	    b				    ; Is it an electrified floor tile?
		    jr	    z, ChkElectricFloor3	    ; Yes

		    cp	    c				    ; Is it an electrified floor tile?
		    ret	    nz				    ; No

ChkElectricFloor3:
		    ld	    a, (DamageDelayTimer)
		    and	    a				    ; Was the player electrified recently?
		    ret	    nz				    ; Yes, wait	a bit to avoid continuous damage

		    ld	    a, 18h			    ; SFX electric damage
		    call    SetSoundEntry

		    ld	    a, 8			    ; Damage delay
		    ld	    (DamageDelayTimer),	a

		    jr	    DecrementLife_2		    ; Decrement	two points of life


;----------------------------------------------------------------------------
; Electrified-floor tile pair per gfx tileset id (0..7). The "live" floor tile
; sits at a different number in each tileset; 0 = this tileset has none. Edit in
; the map editor to define electric floors on new tilesets.
;----------------------------------------------------------------------------
ElectricTiles:
		    dw 6061h			    ; gfx 0 (Building): tiles 60h,61h
		    dw 4041h			    ; gfx 1 (basement): 40h,41h
		    dw 4546h			    ; gfx 2 (roof): 45h,46h
		    dw 0, 0, 0, 0, 0		    ; gfx 3..7: none

