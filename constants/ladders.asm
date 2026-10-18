;----------------------------------------------------------------------------
; Ladder / stairs cluster room ids (editable).
;
; The ladder rooms are climbed via walk-off up/down (ChkNextLadderRoom -> ExitRoom
; -> the normal room-change path). Under WORLDBANK=1 connections are per-room, so
; the block can be RELOCATED to different ids by editing the constants below; under
; WORLDBANK=0 the 208-227 exit-table remapping locks them in place (see
; docs/SPECIAL-ROOMS.md #1). Values reproduce the stock map.
;
; DESIGN CONSTRAINT (docs/LIMITS-PLAN.md A6): the door table (idxDoors / the world
; directory) leaves a GAP for rooms LADDER_NODOOR_FIRST..239 and compacts the
; elevator door slots down by ELEV_DOOR_SKIP. Only the first ladder room
; (LADDER_FIRST) carries a door (the 6Bh Big Boss door). Moving the block UP shrinks
; the gap and can overflow the door slot table, so a large move needs the A6 rework
; first. Moving within/near 224 is safe.
;----------------------------------------------------------------------------
LADDER_FIRST	    equ 224	; first ladder room (ladder exit + bottom limit + region base; carries door 6Bh)
LADDER_LAST	    equ 226	; last ladder room (top limit)
BIG_BOSS_ROOM	    equ 119	; Big Boss room (ladder-mode entry via door 6Bh)

LADDER_NODOOR_FIRST equ LADDER_FIRST+1		; rooms here..239 carry no door data (idxDoors gap)
ELEV_DOOR_SKIP	    equ ELEVATOR_FIRST-LADDER_NODOOR_FIRST	; = 15; elevator door slots compact down by this
