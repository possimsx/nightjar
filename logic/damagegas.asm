

;----------------------------------------------------------------------------
;
; Check	if the player is in a gas room
;
;----------------------------------------------------------------------------

ChkGasRooms:
		    ld	    a, (CurRoomFlags)		    ; unified hazard flags (cached at room load)
		    bit	    1, a			    ; bit1 = gas room
		    jr	    nz,	ChkGasMask
		    ret


;----------------------------------------------------------------------------
;
; Check	if the player is using the gas mask
;
;----------------------------------------------------------------------------

ChkGasMask:
		    ld	    a, (SelectedItem)
		    cp	    SELECTED_GAS_MASK
		    ret	    z				    ; The gas mask is selected

		    ld	    c, 10h			    ; Damage delay

DecrementLife_C:
		    ld	    a, (DamageDelayTimer)
		    and	    a
		    ret	    nz				    ; Wait a bit to avoid continuous damage

		    ld	    a, c
		    ld	    (DamageDelayTimer),	a	    ; Set damage delay

DecrementLife_2:
		    ld	    b, 2
		    jp	    DecrementLife_B



; (gas rooms are now bit1 of RoomFlags -- see BanksABC.asm / CacheRoomFlags)

