;----------------------------------------------------------------------------
; Elevator cluster room ids (partly editable).
;
; ELEVATOR_FIRST (240 = 0F0h) is the band base: rooms >= ELEVATOR_FIRST are
; elevator rooms, and 240 itself is the first elevator (no connections). It is
; the shared constant referenced by the ladder door-slot math (ladders.asm
; ELEV_DOOR_SKIP) and by every "is this an elevator room" range check.
;
; PINNED to 240: several elevator checks are `and 0F0h` nibble-masks (high nibble
; == 0xF0) which are NOT parameterized here, so moving ELEVATOR_FIRST off the
; 16-aligned 0xF0 boundary would break them (and there is no other aligned slot in
; the high-id space anyway). Relocation would need those masks rewritten to range
; checks first. Under WORLDBANK=1 the 241-250 connections are per-room; at
; WORLDBANK=0 they use the exit-table remap (sub 13 -> room-95).
;
; LONG_ELEV_* are the long underground elevator floors (247-250, don't-stop logic),
; derived as fixed offsets from the band base.
;----------------------------------------------------------------------------
ELEVATOR_FIRST	    equ 240		    ; = 0F0h; first elevator / ">= is elevator room" boundary
LONG_ELEV_UPPER	    equ ELEVATOR_FIRST+7    ; 247 long-elevator upper floor
LONG_ELEV_A	    equ ELEVATOR_FIRST+8    ; 248 long-elevator don't-stop floor
LONG_ELEV_B	    equ ELEVATOR_FIRST+9    ; 249 long-elevator don't-stop floor
LONG_ELEV_C	    equ ELEVATOR_FIRST+10   ; 250 long-elevator don't-stop floor
