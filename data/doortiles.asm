;----------------------------------------------------------------------------
;
; Door tile pairs used by the DRAW/ERASE paths (DrawDoorSouth/PutDoorCollTiles,
; SetOpenDoorTiles). Split out of data/doors.asm so they can STAY in BanksDEF
; when WORLDBANK moves the per-room door data to the world bank (plan C4) -
; the draw paths read them under stock mappings.
;
;----------------------------------------------------------------------------
DoorClosedTiles:    db	  2,   2,   2,	 2,   2,   2,	2,   2
		    db	  2,   2,   2,	 2,   2,   2,	2,   2

DoorOpenTiles:	    db	  1,   1,   1,	 1,   1,   1,	1,   1
		    db	  1,   1,   1,	 1,   1,   1,	1,   1
