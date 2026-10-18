;----------------------------------------------------------------------------
; Parachute / skydive cluster room ids (editable).
;
; The parachute is a fixed-shape subgraph (see docs/SPECIAL-ROOMS.md #2): one
; free-fall room, three jump sources (roof + two moving bridges) and three
; landings. These constants let the cluster be RELOCATED to different room
; numbers; the shape is fixed and each slot must stay the right KIND of room
; (the roof keeps its jump door 91h, the bridges stay bridge rooms, the fall
; room keeps the bricks-wall layout). Door ids 91h/5Bh/81h are not room ids and
; are not changed here. Values below reproduce the stock map.
;----------------------------------------------------------------------------
PARACHUTE_ROOM	    equ 204	; free-fall "bricks wall" room
PARA_SRC_ROOF	    equ 117	; jump source: roof (via door 91h)
PARA_SRC_BRIDGE1    equ 45	; jump source: moving bridge 1 (-> landing 1)
PARA_SRC_BRIDGE2    equ 46	; jump source: moving bridge 2 (-> landing 2)
PARA_LAND_BRIDGE1   equ 5	; landing from bridge 1 (3-lorries yard)
PARA_LAND_BRIDGE2   equ 6	; landing from bridge 2 (dogs yard left)
PARA_LAND_ROOF	    equ 10	; landing from roof / default (dogs yard right)
