;---------------------------------------------------------------------------
;
; Rooms	where the game progress	is stored to continue from there.
; When passing from first room to second room
;
; 0FFh-terminated [room, prevRoom] pairs - any count (docs/LIMITS-PLAN.md
; Phase	A). The	scanner	in logic/checkpoints.asm reads to the terminator.
;
;---------------------------------------------------------------------------
SaveStatRooms_w1:	    db	121, 121
		    db	121,   0			    ; Begining
		    db	240,   3			    ; Elevator West 1st	floor building 1
		    db	240,  31			    ; Elevator West 2nd	floor building 1
		    db	242,  39			    ; Elevator East 3rd	floor building 1
		    db	241,  15			    ; Elevator East 1st	floor building 1
		    db	241,  27			    ; Elevator East 2nd	floor building 1
		    db	242,  53			    ; Elevator 1st floor building 1
		    db	241,  63			    ; Elevator roof building 1
		    db	243,  72			    ; Elevator West 1st	floor building 2
		    db	245, 206			    ; Elevator East 1st	floor building 2
		    db	243,  95			    ; Elevator West basement building 2	(firetrooper)
		    db	245, 207			    ; Elevator East basement building 2
		    db	244,  88			    ; Elevator West roof building 2
		    db	246, 154			    ; Elevator East roof building 2
		    db	243,  81			    ; Elevator West 2nd	floor building 2
		    db	245, 205			    ; Elevator East 2nd	floor building 2
		    db	247, 109			    ; Elevator 1st floor building 3
		    db	250, 115			    ; Elevator basement	building 3
		    db	165,   8			    ; Arrested room to prison
		    db	 10, 204			    ; Landing on yard
		    db	 64,  11			    ; Exit to desert from building 1
		    db	 73,  69			    ; Entering from desert to building 2 from 1
		    db	125,  93			    ; Entering dark room in basement building 2
		    db	 56, 123			    ; Exit dark	room in	basement building 2
		    db	102,  75			    ; Entering from desert from	building 3 to 2
		    db	108, 104			    ; Entering from desert to building 3
		    db	105,  78			    ; Water channel building 2 south
		    db	110, 107			    ; Water channel building 2 north
		    db	118, 116			    ; Enter Metal Gear room
		    db	123,  56			    ; Enter dark rooms from south
		    db	0FFh				    ; End of list (any number of pairs above)
