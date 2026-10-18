;----------------------------------------------------------------------------
;
; Entry-dependent guard culling.
;
; When a room's guards/sentinels spawn, one of them is removed depending on
; where the player entered, so the player never materialises on top of an
; enemy. This used to be 9 hardcoded per-room routines (HideGuardRoom1..39);
; it is now a single data table (HideGuardRules) + a generic interpreter
; (ApplyHideGuardRules), so the rules are editable as data.
; See docs/HIDE-GUARD-PLAN.md and tools/mghideguard.py (byte-for-byte proven
; equal to the original routines over every entry case).
;
;----------------------------------------------------------------------------


;----------------------------------------------------------------------------
;
; ApplyHideGuardRules
;
; For the current actor (IX), find the current Room in HideGuardRules; the first
; matching condition (entry direction / previous room / else) selects a
; (flags, coord); the actor is culled iff  actor.X/Y  ==/!=  coord.
;
; Reads (Room),(NextRoomDirect),(PreviousRoom) from memory, so it is callable
; from any init path with no register set-up. Preserves B (guard path index),
; DE and IX; clobbers A, C, HL. Culls via HideGuardSpr (which returns to the
; caller through HideSprColor); otherwise returns.
;
;----------------------------------------------------------------------------

ApplyHideGuardRules:
		    push    de
		    ld	    a, (NextRoomDirect)		    ; D = entry direction (4=R,3=L,2=D,1=U)
		    ld	    d, a
		    ld	    a, (PreviousRoom)		    ; E = room the player came from
		    ld	    e, a
		    ld	    hl,	HideGuardRules

AHGR_NextRoom:
		    ld	    a, (hl)			    ; Room field (0FFh = end of table)
		    inc	    a
		    jr	    z, AHGR_NoCull		    ; No rule for any room left -> no cull
		    dec	    a

		    ld	    c, a			    ; C = this block's room
		    ld	    a, (Room)
		    cp	    c
		    jr	    z, AHGR_Found

		    inc	    hl				    ; -> nEntries
		    ld	    a, (hl)
		    inc	    hl				    ; -> first entry
		    add	    a, a
		    add	    a, a			    ; A = 4 * nEntries (entry = 4 bytes)
		    call    ADD_HL_A			    ; Skip this block
		    jr	    AHGR_NextRoom

AHGR_Found:
		    inc	    hl				    ; -> nEntries
		    ld	    a, (hl)
		    ld	    c, a			    ; C = entries remaining
		    inc	    hl				    ; -> first entry (condition byte)

AHGR_Entry:
		    ld	    a, (hl)			    ; Condition type
		    cp	    COND_ELSE
		    jr	    z, AHGR_Match		    ; else: always matches

		    inc	    hl				    ; -> value
		    cp	    COND_DIR
		    jr	    nz, AHGR_ChkPrev

		    ld	    a, (hl)			    ; value vs entry direction
		    dec	    hl
		    cp	    d
		    jr	    z, AHGR_Match
		    jr	    AHGR_Adv

AHGR_ChkPrev:					    ; COND_PREV
		    ld	    a, (hl)			    ; value vs previous room
		    dec	    hl
		    cp	    e
		    jr	    z, AHGR_Match

AHGR_Adv:
		    ld	    a, 4
		    call    ADD_HL_A			    ; -> next entry
		    dec	    c
		    jr	    nz, AHGR_Entry

AHGR_NoCull:
		    pop	    de
		    ret

; A rule matched: HL -> its condition byte. Read flags (+2) and coord (+3),
; then cull this actor iff its X/Y satisfies the flags' axis+op vs coord.

AHGR_Match:
		    inc	    hl
		    inc	    hl				    ; -> flags
		    ld	    c, (hl)			    ; C = flags
		    inc	    hl				    ; -> coord
		    ld	    a, (hl)
		    ld	    l, a			    ; L = target coord (HL free after)

		    bit	    0, c			    ; flags b0: 1 = X axis
		    jr	    nz, AHGR_UseX
		    ld	    a, (ix+ACTOR.Y)
		    jr	    AHGR_Cmp

AHGR_UseX:
		    ld	    a, (ix+ACTOR.X)

AHGR_Cmp:
		    cp	    l				    ; Z = (actor coord == target coord)
		    jr	    z, AHGR_Eq

		    bit	    1, c			    ; not equal: flags b1: 2 = "!=" op
		    jr	    z, AHGR_NoCull2		    ; op is "==", not equal -> keep
		    jr	    AHGR_Cull			    ; op is "!=", not equal -> cull

AHGR_Eq:
		    bit	    1, c			    ; equal: cull only if op is "=="
		    jr	    nz, AHGR_NoCull2		    ; op is "!=", equal -> keep

AHGR_Cull:
		    pop	    de
		    jp	    HideGuardSpr		    ; Remove this guard (returns to caller)

AHGR_NoCull2:
		    pop	    de
		    ret


;----------------------------------------------------------------------------
;
; Mark the current actor as a removed guard (shared removal tail).
;
;----------------------------------------------------------------------------

HideGuardSpr:
		    ld	    (ix+ACTOR.REMOVE_GUARD), 1	    ; This flag	is set when a guard is removed to prevent the player to	come to	an enemy when entering a room
		    ld	    (ix+ACTOR.COLLISION_CFG), 0	    ; Disable collsiong	with the player	and his	shots
		    ld	    (ix+ACTOR.NumSprites), 0	    ; (!?)
		    jp	    HideSprColor		    ; (!?) Setting 0 sprites this call does nothing


;----------------------------------------------------------------------------
;
; HideGuardRules  (editable via tools/mghideguard.py)
;
; Format:  db room, nEntries ; then per entry: db cond, val, flags, coord
;          flags bit0: 1 = X axis (else Y);  bit1: 2 = "!=" op (else "==")
; Scanned by ApplyHideGuardRules; 0FFh terminates the table.
;
;----------------------------------------------------------------------------

HideGuardRules:
		    db	  1, 2
		      db  COND_DIR,    1, 0, 0B0h	    ; from S    -> cull Y == 0B0h
		      db  COND_ELSE,   0, 0, 018h	    ; else	-> cull Y == 018h
		    db	 13, 1
		      db  COND_PREV, 137, 1, 088h	    ; from rm137 -> cull X == 088h
		    db	 15, 1
		      db  COND_DIR,    4, 1, 010h	    ; from W    -> cull X == 010h
		    db	 17, 2
		      db  COND_DIR,    1, 2, 030h	    ; from S    -> cull Y != 030h
		      db  COND_ELSE,   0, 0, 030h	    ; else	-> cull Y == 030h
		    db	 18, 2
		      db  COND_DIR,    1, 2, 013h	    ; from S    -> cull Y != 013h
		      db  COND_ELSE,   0, 0, 013h	    ; else	-> cull Y == 013h
		    db	 19, 2
		      db  COND_PREV, 141, 0, 078h	    ; from rm141 -> cull Y == 078h
		      db  COND_DIR,    1, 0, 0A8h	    ; from S    -> cull Y == 0A8h
		    db	 22, 2
		      db  COND_PREV,  20, 1, 020h	    ; from rm20  -> cull X == 020h
		      db  COND_ELSE,   0, 1, 0F0h	    ; else	-> cull X == 0F0h
		    db	 35, 2
		      db  COND_PREV, 156, 0, 028h	    ; from rm156 -> cull Y == 028h
		      db  COND_PREV,  33, 1, 018h	    ; from rm33  -> cull X == 018h
		    db	 39, 2
		      db  COND_PREV, 242, 0, 048h	    ; from rm242 -> cull Y == 048h
		      db  COND_ELSE,   0, 0, 0B0h	    ; else	-> cull Y == 0B0h
		    db 0FFh				    ; end of table
