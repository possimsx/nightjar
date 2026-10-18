;----------------------------------------------------------------------------
;
; "No respawn on alert" rooms.
;
; A room in this set does NOT respawn guards when an alert is triggered there:
; the alert sets NumRespawnGuards = 0 (SetAlertMode) and AlertRespawnTimer = 0
; (SetRespawnTime). This used to be a single hardcoded `cp 216` (the 4th desert
; lorry / entrance to building 3) at those two sites; it is now a data list
; (NoRespawnRooms) + a shared test (IsNoRespawnRoom), so the behaviour is
; editable as data and assignable to any room id.
;
; See tools/mgnorespawn.py (proves the list reproduces the original 216-only
; behaviour across every room id before it ships).
;
;----------------------------------------------------------------------------


;----------------------------------------------------------------------------
;
; IsNoRespawnRoom
;
; In:   A = room id
; Out:  Z set   iff the room is in NoRespawnRooms (suppress alert respawns)
;       Z clear otherwise
; Preserves BC, DE, HL, IX.  Clobbers A and flags.
;
;----------------------------------------------------------------------------

IsNoRespawnRoom:
		    push    hl
		    push    bc
		    ld	    c, a			    ; C = room to match
		    ld	    hl,	NoRespawnRooms

INRR_Scan:
		    ld	    a, (hl)
		    inc	    hl
		    cp	    0FFh			    ; end of list?
		    jr	    z, INRR_NotFound
		    cp	    c
		    jr	    nz,	INRR_Scan		    ; not this one -> keep scanning
		    pop	    bc				    ; match: Z still set from `cp c`
		    pop	    hl
		    ret

INRR_NotFound:
		    or	    1				    ; force NZ (A is clobbered anyway)
		    pop	    bc
		    pop	    hl
		    ret


;----------------------------------------------------------------------------
;
; NoRespawnRooms  (editable via tools/mgnorespawn.py)
;
; Flat list of room ids that suppress guard respawns on alert; 0FFh terminates.
; Scanned by IsNoRespawnRoom.
;
;----------------------------------------------------------------------------

NoRespawnRooms:
		    db	    216	    ; 4th desert lorry / entrance to building 3
		    db	    0FFh			    ; end of list
