;----------------------------------------------------------------------------
;
; NIGHTJAR world-data bank (docs/LIMITS-PLAN.md Phase C) - segment WORLD_SEG.
;
; Load-time world tables evicted from Banks456 so patrol routes & co. can grow
; there. Readers swap this segment into the #6000-#7FFF window with MapSeg60
; (hooks/worldbank.asm) and restore segment 4 afterwards; segments 5/6 are
; never displaced, so Banks456-resident code keeps running throughout.
;
; The data files are the same ones the codecs/editor read (tools/mgmap.py is
; label-based, not address-based, so nothing there changes). The engine-bound
; equs (Phase A) move here with their tables.
;
; Current headroom: the two tables are ~2.1KB, leaving ~6KB in this segment
; for the next evictions (connections/radio/doors, plan steps C2-C4).
;
;----------------------------------------------------------------------------

	    org	    #6000

; World directory (Phase D2 contract, offsets = WDIR_* in features.asm): the
; engine reads every top-level table through these pointers, so each world's
; segment can lay out its content freely. Additional worlds (genworld) emit
; the same directory pointing at their own copies.
		    dw	    idxActorsRooms	    ; +0  WDIR_ACTORS
		    dw	    idxRoomItemsIdx	    ; +2  WDIR_ITEMSIDX
		    dw	    idxRoomItems	    ; +4  WDIR_ITEMS
		    dw	    idxDoors		    ; +6  WDIR_DOORS
		    dw	    IdDoorsLogic	    ; +8  WDIR_DOORLOGIC
		    dw	    DoorOpenEnterDat	    ; +10 WDIR_DOORDAT
		    dw	    idxRoomRadio	    ; +12 WDIR_RADIO
		    dw	    RoomConnsFull	    ; +14 WDIR_CONNS
		    dw	    GatewayTable	    ; +16 WDIR_GATEWAY
		    dw	    idxRoomPaths	    ; +18 WDIR_PATHS (D4)
		    dw	    SaveStatRooms	    ; +20 WDIR_CHKPT (D4)
		    ds	    32-22, 0FFh		    ; spare directory slots

; Gateway resolver at the fixed WGATE offset (#6020) - see hooks/worldgate.asm
WorldGate:
	include	"hooks/worldgate.asm"

; Gateways out of THIS world (D2) - authoring surface, copied per world
	include	"data/gateways.asm"

	include	"data/actorsinrooms.asm"

; the actor-room engine bound follows the table length (idxActorsRooms must
; stay the last thing in its file for $ to be the table end)
N_ACTORROOMS:	     equ ($ - idxActorsRooms)/2

	include	"data/itemsinrooms.asm"

; item-room bounds follow the idxRoomItemsIdx length
ITEMROOM_BASE:	     equ 122
ITEMROOM_END:	     equ ITEMROOM_BASE + (idxRoomItems - idxRoomItemsIdx)

; full per-room connections (251 x 4, plan C2) - replaces the stock 156-slot
; RoomConnections + the GetNextRoomNum remap chain; CacheRoomConns copies the
; current room's row to CurRoomConns at room load (SetRoomPal hook)
	include	"data/roomconnsfull.asm"

; radio calls (plan C3) - idxRoomRadio + RadioRoom_* chains; the single reader
; (UpdateRadio, Banks0123) maps this segment instead of SetBanks_D_E_F
	IF (JAPANESE)
	include	"data/radiocallsjp.asm"
	ELSE
	include	"data/radiocalls.asm"
	ENDIF

; per-room door data (plan C4): DoorOpenEnterDat + DoorsRoom_* blocks +
; idxDoors + IdDoorsLogic. Readers AddDoorsData/SetDefaultDoorLock copy to the
; RAM DoorsList/DoorOpenArray at room load / game init; the DoorClosedTiles/
; DoorOpenTiles pairs stay in BanksDEF (data/doortiles.asm) for the draw paths
	include	"data/doors.asm"

; per-world path INDEX (plan D4): one dw per room -> that room's Paths_* list.
; The route blocks it points into (Path_*/Paths_* in data/paths.asm) stay in
; Banks456 and are SHARED by all worlds - only the room->routes mapping
; switches with the world. Readers GetPathPoints/GetSentinelLookDirs fetch the
; list pointer through GetRoomPathList (hooks/worldbank.asm).
	include	"data/pathindex.asm"

; per-world checkpoint pairs (plan D4): [room, prevRoom] save triggers,
; 0FFh-terminated; the scanner (logic/checkpoints.asm) reads them through
; WDIR_CHKPT with this segment mapped at #6000
	include	"data/checkpoints.asm"

		    ; Fill empty space
		    ds	    (#8000-$),#ff
		    ASSERT  $=#8000

;----------------------------------------------------------------------------
; Room-layout segments (plan C5): WORLD_LSEG1 + WORLD_LSEG2, assembled as one
; contiguous #6000-#9FFF region so idxRooms pointers stay plain 16-bit.
; CacheRoomLayout (hooks/worldbank.asm) maps BOTH segments (#6000 + #8000) and
; copies the current room's 48-byte layout + MetaTileSetIDs nibble to RAM;
; RenderRoom/UnpackMetatiles then read the RAM copy while the metatile
; definitions stay in BanksDEF exactly as stock.
;----------------------------------------------------------------------------
		    org	    #6000

; Layout directory (Phase D2 contract, offsets = LDIR_* in features.asm)
		    dw	    idxRooms		    ; +0 LDIR_ROOMS
		    dw	    MetaTileSetIDs	    ; +2 LDIR_META
		    dw	    idxMetatileSet	    ; +4 LDIR_MSET
		    ds	    8-6, 0FFh		    ; spare

	include	"data/rooms.asm"

		    ; Fill empty space (rest of the 16KB layout window)
		    ds	    (#0A000-$),#ff
		    ASSERT  $=#0A000
