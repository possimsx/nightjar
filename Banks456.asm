;----------------------------------------------------------------------------
;
;
; MegaROM banks 4, 5 and 6
;
;
;----------------------------------------------------------------------------

		    org	#6000


	include	"sound/sound.asm"
	

	include	"data/weapondamage.asm"

	include	"data/shapes.asm"


	include	"data/itemtaketextid.asm"
	
	include	"data/itemtakeamount.asm"


	include	"data/palettes.asm"

	include	"data/elevatorrooms.asm"

	IF (WORLDBANK)
	; connections moved to BanksWorld.asm (RoomConnsFull, 251x4 canonical);
	; this stock 156-slot table is only assembled in flag-off builds
	ELSE
	include	"data/roomsconnections.asm"
	ENDIF
	
	
	IF (WORLDBANK)
	; actors-in-rooms + N_ACTORROOMS moved to BanksWorld.asm (world-data bank)
	ELSE
	include	"data/actorsinrooms.asm"

; Phase	A (docs/LIMITS-PLAN.md): the actor-room engine bound follows the table
; length. Lives	HERE (not in the data file) so the editor's "restore original"
; can revert the data without losing the symbol. idxActorsRooms must stay the
; last thing in	its file for $ to be the table end.
N_ACTORROOMS:	     equ ($ - idxActorsRooms)/2
	ENDIF

	include	"data/actorspriteattr.asm"


	include	"data/paths.asm"

	IF (WORLDBANK)
	; the per-room path INDEX moved to BanksWorld.asm (one copy per world,
	; read through WDIR_PATHS - plan D4); the route blocks above are SHARED
	ELSE
	include	"data/pathindex.asm"
	ENDIF

	include	"data/respawninfo.asm"
	
	include	"data/maths.asm"
	

	include	"gfx/targetspr.asm"


	include	"gfx/items.asm"

	include	"gfx/alerticon.asm"

	include	"gfx/radio.asm"
	
	include	"gfx/camera.asm"
	
	
	
	include	"data/menuweapontexts.asm"

	include	"data/menuequipmenttexts.asm"

	include	"data/menuradiotexts.asm"



	include	"data/weapongfxxy.asm"
	IF (JAPANESE)
	include	"data/weaponnamesjp.asm"
	ELSE
	include	"data/weaponnames.asm"
	ENDIF



	include	"data/weaponcursorxy.asm"



	include	"data/itemgfxxy.asm"

	IF (JAPANESE)
	include	"data/itemnamesjp.asm"
	ELSE
	include	"data/itemnames.asm"
	ENDIF
	
	include	"data/itemcursorxy.asm"



	IF (WORLDBANK)
	; items-in-rooms + ITEMROOM_* moved to BanksWorld.asm (world-data bank)
	ELSE
	include	"data/itemsinrooms.asm"

; Phase	A (docs/LIMITS-PLAN.md): item-room bounds follow the idxRoomItemsIdx
; length (kept out of the data file for	the same restore reason	as above)
ITEMROOM_BASE:	     equ 122
ITEMROOM_END:	     equ ITEMROOM_BASE + (idxRoomItems - idxRoomItemsIdx)
	ENDIF

	include	"logic/spawnitem.asm"

	IF (WORLDBANK)
	include	"hooks/worldbank.asm"	; MapSeg60 + AddRoomItems world shim (ends AddRoomItems_:)
	ENDIF
	include	"logic/addroomitems.asm"

	include	"logic/drawitemsinroom.asm"



	include	"logic/gamedemo.asm"

	include	"logic/checkpoints.asm"

	IF (WORLDBANK)
	; checkpoint pairs moved to BanksWorld.asm (one list per world, read
	; through WDIR_CHKPT - plan D4); the scanner CODE above stays here
	ELSE
	include	"data/checkpoints.asm"
	ENDIF

	include	"logic/passwords.asm"


; (dark rooms are now bit0 of RoomFlags -- see BanksABC.asm / CacheRoomFlags)

		    ; Fill empty space
		    ds      (#C000-$),#ff
		    ASSERT  $=#C000
