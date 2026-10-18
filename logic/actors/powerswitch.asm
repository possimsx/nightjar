;----------------------------------------------------------------------------
;
; Initialize power switch
;
;----------------------------------------------------------------------------

InitPowerSwitch:
		    ld	    (ix+POWER_SWITCH.BRIGHT), 4	    ; Palette RGB component start value

		    ld	    a, 1			    ; Fade in mode
		    ld	    (ix+POWER_SWITCH.BRIGHT_DELTA), a
		    ld	    (PowerSwitchOn), a		    ; Power switch status 1=On,	0=Off/destroyed
		    ret



;----------------------------------------------------------------------------
;
; Power	switch
; Fades	in/out the electrified floor color
;
;----------------------------------------------------------------------------

PowerSwitchLogic:
		    ld	    a, (ix+POWER_SWITCH.ANIM_CNT)
		    and	    3
		    ret	    nz

		    ld	    a, (ix+POWER_SWITCH.BRIGHT)
		    add	    a, (ix+POWER_SWITCH.BRIGHT_DELTA) ;	Increment or decrement the bright value
		    ld	    (ix+POWER_SWITCH.BRIGHT), a

		    cp	    7				    ; Max. bright value? (RGB component	0-7)
		    call    nc,	ChkRevertFade

		    ld	    a, (ix+POWER_SWITCH.BRIGHT)
		    ld	    d, a
		    rlca
		    rlca
		    rlca
		    rlca
		    or	    d
		    ld	    e, d
		    ld	    d, a			    ; DE = RGB color value

		    ld	    a, (CurrentTileSet)		    ; the electric-floor palette slot depends on the tileset, not the room
		    ld	    hl,	ElectricColorSlot
		    call    ADD_HL_A
		    ld	    a, (hl)
		    jp	    SetPaletteColor		    ; Change the electric floor	color


;----------------------------------------------------------------------------
;
; Swap fade in / fade out animation
;
;----------------------------------------------------------------------------

ChkRevertFade:
		    inc	    a
		    ld	    b, 6
		    jr	    nz,	ChkRevertFade2

		    ld	    b, 1

ChkRevertFade2:
		    ld	    (ix+POWER_SWITCH.BRIGHT), b	    ; Set the next bright value

		    ld	    a, (ix+POWER_SWITCH.BRIGHT_DELTA)
		    ld	    b, -1			    ; Fade out value
		    dec	    a
		    jr	    z, ChkRevertFade3

		    ld	    b, 1			    ; Fade in value

ChkRevertFade3:
		    ld	    (ix+POWER_SWITCH.BRIGHT_DELTA), b ;	Set the	new delta
		    ret


;----------------------------------------------------------------------------
; Electric-floor palette slot per tileset (SetPaletteColor index). The pulsing
; floor color is a per-tileset property, so a power switch works in any room.
; Stock: tileset 0 (building, rooms 37/110) = slot 9; tileset 1 (basement,
; room 116) and tileset 2 (roof, room 40) = slot 5.
;----------------------------------------------------------------------------
ElectricColorSlot:
		    db	9			    ; gfx 0 (building)
		    db	5			    ; gfx 1 (basement)
		    db	5			    ; gfx 2 (roof)
		    db	9, 9, 9, 9, 9		    ; gfx 3..7 (default)
