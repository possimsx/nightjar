;----------------------------------------------------------------------------
;
; Gateways OUT of this world (docs/LIMITS-PLAN.md Phase D2).
; Entry: db srcRoom, sentinel(252-254), destWorldIdx, destRoom  -  0FFh ends.
; A gateway fires when a door's DESTINATION byte is the sentinel value and the
; player enters it in srcRoom; the resolver (hooks/worldgate.asm) switches the
; active world and the normal room load does the rest.
;
; TEST/DEMO entry below: room 5 sentinel 252 -> world 1 room 5. Inert unless a
; door in room 5 has dest 252 (tools/gwtest.tcl pokes one at runtime).
;
;----------------------------------------------------------------------------
GatewayTable:	    db	    5, 252, 1, 5
		    db	    0FFh
