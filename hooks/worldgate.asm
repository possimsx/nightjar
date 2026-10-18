;----------------------------------------------------------------------------
;
; Gateway resolver BODY (docs/LIMITS-PLAN.md Phase D2, WORLDBANK feature).
;
; Lives INSIDE every world's data segment at the fixed offset #6020 (right
; after the 32-byte directory): the caller in logic/nextroom.asm maps the
; ACTIVE world at #6000 and does `call WGATE`, so this always reads its own
; world's GatewayTable and costs zero bytes in the packed Banks0123 group.
;
; The INCLUDING file must define a unique global label (WorldGate /
; WorldGate_w1 / ...) immediately before this include - the dot-labels here
; are local to it, so multiple inclusions don't collide.
;
; In:  C = destination byte (252-254), (Room) = source room, this world's
;      segment mapped at #6000.
; Out: C = destination room; CurWorldSeg switched on a match. Unmatched
;      sentinel -> C = current room (stay put; authoring error).
;      Clobbers A/D/HL (the caller preserves DE around the call).
;
;----------------------------------------------------------------------------

		    ASSERT  $ = #6020		    ; fixed WGATE entry contract

		    ld	    hl, (WDIR_GATEWAY)	    ; this world's gateway table
		    ld	    a, (Room)
		    ld	    d, a		    ; D = source room

.scan:
		    ld	    a, (hl)
		    cp	    0FFh		    ; end of table?
		    jr	    z, .miss
		    cp	    d			    ; entry source room?
		    jr	    nz, .next
		    inc	    hl
		    ld	    a, (hl)		    ; entry sentinel
		    dec	    hl
		    cp	    c
		    jr	    nz, .next

		    inc	    hl			    ; matched: src, sentinel, WORLD, room
		    inc	    hl
		    ld	    a, (hl)		    ; destination world index
		    ld	    d, a
		    add	    a, a
		    add	    a, d		    ; x3 (data + 2 layout segments/world)
		    add	    a, WORLD_SEG
		    ld	    (CurWorldSeg), a	    ; switch the active world
		    inc	    hl
		    ld	    c, (hl)		    ; destination room
		    ret

.next:
		    ld	    a, 4
		    call    ADD_HL_A
		    jr	    .scan

.miss:
		    ld	    a, (Room)		    ; stay in the current room
		    ld	    c, a
		    ret
