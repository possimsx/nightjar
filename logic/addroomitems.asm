;---------------------------------------------------------------------------
;
; Add room items
; Get information about	the items in the current room
;
;---------------------------------------------------------------------------

	IF (WORLDBANK)
	; AddRoomItems label comes from hooks/worldbank.asm (world-segment shim,
	; included just before this file in Banks456.asm); the body below then
	; assembles as AddRoomItems_
	ELSE
AddRoomItems:
	ENDIF
		    ld	    hl,	ItemsInTheRoom		    ; ID, size,	Y, X
		    ld	    de,	 ItemsInTheRoom+1	    ; ID, size,	Y, X
		    ld	    bc,	2Fh
		    ld	    (hl), b
		    ldir

		    ld	    a, (Room)
		    cp	    ITEMROOM_END		    ; From this	room on, there are no items (follows idxRoomItemsIdx length)
		    ret	    nc

		    cp	    ITEMROOM_BASE		    ; Isolated rooms-lorries
		    ret	    c				    ; There are	no items in "open" rooms

		    sub	    ITEMROOM_BASE

	IF (WORLDBANK)
		    ld	    de,	(WDIR_ITEMSIDX)	    ; item index via world directory (D2)
		    call    ADD_DE_A		    ; plain helper: the stock __ variant would
	ELSE					    ; SetBanks_1_2_X and unmap the world segment
		    ld	    de,	idxRoomItemsIdx
		    call    ADD_DE_A__
	ENDIF

		    ld	    a, (de)
		    and	    a
		    ret	    z				    ; No items in the room

		    dec	    a
	IF (WORLDBANK)
		    ld	    de,	(WDIR_ITEMS)	    ; item sets via world directory (D2)
		    call    GetPointerDE2A	    ; plain (see above)
	ELSE
		    ld	    de,	idxRoomItems
		    call    GetPointerDE2A_
	ENDIF

		    ld	    hl,	ItemsInTheRoom		    ; ID, size,	Y, X

AddRoomItems2:
		    ld	    a, (de)
		    inc	    a
		    ret	    z				    ; FF = End

		    dec	    a
		    ld	    b, a
		    call    ChkItemGate			    ; table-driven story-flag gate (was cp ROCKET_LAUNCHER + JeniRocketF)
		    ret	    c				    ; gated item whose flag is still clear -> stop adding items

AddRoomItems3:
		    ld	    a, b
		    cp	    9
		    ld	    bc,	WeaponsTaken
		    jr	    c, AddRoomItems4

		    sub	    8
		    ld	    bc,	ItemsTaken

AddRoomItems4:
		    dec	    a
		    add	    a, c
		    ld	    c, a
		    jr	    nc,	AddRoomItems5
		    inc	    b

AddRoomItems5:
		    ld	    a, (bc)
		    and	    a				    ; Was the item/weapon taken	before?
		    jr	    z, AddItemToRoom

		    inc	    de
		    inc	    de
		    inc	    de
		    jr	    AddRoomItems2


AddItemToRoom:
		    ld	    a, (de)
		    ld	    (hl), a			    ; Item ID

		    inc	    de
		    inc	    hl
		    inc	    hl
		    ld	    a, (de)
		    ld	    (hl), a			    ; Item Y

		    inc	    de
		    inc	    hl
		    ld	    a, (de)
		    ld	    (hl), a			    ; Item X

		    inc	    hl
		    inc	    de
		    ld	    (hl), 0

		    ld	    a, 0Ch
	IF (WORLDBANK)
		    call    ADD_HL_A		    ; plain (see above)
	ELSE
		    call    ADD_HL_A_
	ENDIF
		    jr	    AddRoomItems2


;---------------------------------------------------------------------------
;
; Item spawn gate (docs/CODEC-GATE-PLAN.md Table B, items)
;
; Some items only appear once a radio/story event sets a flag (stock: the
; rocket launcher, gated behind JeniRocketF after Jennifer's call). This
; replaces the hardcoded "cp ROCKET_LAUNCHER / ld a,(JeniRocketF)" with a
; small table so the gate is data, not code.
;
; In:  B  = item ID being considered
; Out: CY set  = item is gated behind a flag that is still clear -> abort the
;                item list (identical to the stock rocket "ret z")
;      CY clear= place the item (ungated, or its flag is set)
; Preserves B, DE, HL.
;
;---------------------------------------------------------------------------

ChkItemGate:
		    push    hl
		    push    de
		    ld	    hl,	GateItems

ChkItemGate2:
		    ld	    a, (hl)
		    inc	    a
		    jr	    z, ChkItemGateOk		    ; 0FFh = end of table -> not gated
		    dec	    a
		    cp	    b
		    inc	    hl				    ; -> flag address low byte
		    jr	    z, ChkItemGateFound
		    inc	    hl				    ; skip flag address (2 bytes)
		    inc	    hl
		    jr	    ChkItemGate2

ChkItemGateFound:
		    ld	    e, (hl)
		    inc	    hl
		    ld	    d, (hl)			    ; DE = flag RAM address
		    ld	    a, (de)
		    and	    a
		    jr	    z, ChkItemGateBlocked	    ; flag clear -> item stays hidden

ChkItemGateOk:
		    pop	    de
		    pop	    hl
		    or	    a				    ; CY = 0 -> place the item
		    ret

ChkItemGateBlocked:
		    pop	    de
		    pop	    hl
		    scf					    ; CY = 1 -> gated, abort
		    ret


; item ID, dw flag address ; 0FFh-terminated. Editable by tools/mgcodecgate.py.
GateItems:
		    db	    ROCKET_LAUNCHER
		    dw	    JeniRocketF
		    db	    0FFh
