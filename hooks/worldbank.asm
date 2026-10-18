;----------------------------------------------------------------------------
;
; World-data bank support (docs/LIMITS-PLAN.md Phase C, WORLDBANK feature).
;
; The world tables (items-in-rooms, actors-in-rooms) live in segment WORLD_SEG
; (BanksWorld.asm, org #6000). Readers map that segment into the #6000-#7FFF
; window only - the #8000/#A000 windows stay put, so THIS code (which lives in
; Banks456's segment 5/6 region) keeps executing while the world data is in
; view.
;
; Interrupt safety: the ISR and SetSoundEntry restore banks from the BankIn60/
; BankIn80 shadow variables, so a swap is safe iff the shadow is updated under
; DI together with the mapper register (same discipline as SetBanks).
;
;----------------------------------------------------------------------------

; This whole file must live in segment 6 (#A000-#BFFF): MapSeg60 and the shims
; are called under mappings where #6000 (and sometimes #8000) hold OTHER
; segments - e.g. AddRoomItems'/ChkSaveGameStatus' callers use SetBankInA0_6.
; Data evictions above this include shift it around; assert loudly if it ever
; slips below #A000 (see TRAP #5 in docs/LIMITS-PLAN.md).
		    ASSERT  $ >= #A000

; Map segment A into #6000-#7FFF (shadow-correct single-window switch)
MapSeg60:
		    di
		    ld	    (BankIn60), a
		    ld	    (6000h), a
		    ei
		    ret

; Map segment A into #8000-#9FFF (same discipline; used by the 16KB layout
; window - see CacheRoomLayout)
MapSeg80:
		    di
		    ld	    (BankIn80), a
		    ld	    (8000h), a
		    ei
		    ret

; CacheRoomLayout (plan C5): copy the current room's 8x6 metatile layout (48
; bytes via idxRooms) + its MetaTileSetIDs nibble into RAM (CurRoomLayout /
; CurRoomMetaSet). The layout region spans TWO world segments assembled as one
; contiguous #6000-#9FFF window (WORLD_LSEG1/WORLD_LSEG2), so idxRooms
; pointers stay plain 16-bit. Called from RenderRoom's head under a 4_5_6
; bracket; the stock SetBanks_D_E_F that follows re-normalizes every window,
; so no restore is needed here (shadows stay correct DURING the copy, which is
; all the ISR requires).
CacheRoomLayout:
		    ld	    a, (CurWorldSeg)	    ; layout segments = world seg +1 / +2
		    inc	    a
		    call    MapSeg60
		    ld	    a, (CurWorldSeg)
		    add	    a, 2
		    call    MapSeg80
		    ld	    de,	(LDIR_ROOMS)	    ; via layout directory (D2)
		    call    GetRoomPointer
		    ex	    de,	hl			    ; HL = layout (#6000-#9FFF)
		    ld	    de,	CurRoomLayout
		    ld	    bc,	48
		    ldir
		    ld	    hl,	(LDIR_META)	    ; via layout directory (D2)
		    call    GetNibbleRoom
		    dec	    a
		    ld	    de,	(LDIR_MSET)		    ; ALSO in the layout segments (it
		    call    GetPointerDE2A		    ; sits inside data/rooms.asm) - but
		    ld	    (CurRoomMetaPtr), de	    ; its VALUES are BanksDEF addresses,
		    ret					    ; so cache the RESOLVED pointer

; AddRoomItems world shim: bracket the stock body (AddRoomItems_, follows this
; include) with world-segment mapping. Callers are unchanged; the body has many
; early `ret`s, so it is wrapped rather than edited. NOTE the callers do NOT
; run under SetBanks_4_5_6 - they use SetBankInA0_6 (seg 6 at #A000 only, seg 1
; still at #6000) - so the previous #6000 segment MUST be restored from the
; BankIn60 shadow, never assumed.
AddRoomItems:
		    ld	    a, (BankIn60)
		    push    af			    ; remember the caller's #6000 segment
		    ld	    a, (CurWorldSeg)
		    call    MapSeg60
		    call    AddRoomItems_
		    pop	    af
		    jp	    MapSeg60		    ; tail: restore the caller's #6000 segment

; CacheRoomConns (plan C2): copy RoomConnsFull[Room] (4 bytes N,S,W,E) into
; CurRoomConns. Hooked into SetRoomPal right after its CacheRoomFlags bracket,
; which runs on every room change (incl. binocular room flips) BEFORE any
; GetNextRoomNum use — so the cache is always current. Restores the caller's
; #6000 segment (SetRoomPal goes on to read palette data from segment 4 there).
; Room 251 ("Ending") reads the segment's FF pad — harmless, never navigated.
CacheRoomConns:
		    ld	    a, (BankIn60)
		    push    af
		    ld	    a, (CurWorldSeg)
		    call    MapSeg60
		    ld	    a, (Room)
		    ld	    l, a
		    ld	    h, 0
		    add	    hl, hl
		    add	    hl, hl			    ; HL = Room * 4
		    ld	    de, (WDIR_CONNS)	    ; via world directory (D2)
		    add	    hl, de
		    ld	    de, CurRoomConns
		    ld	    bc, 4
		    ldir
		    pop	    af
		    jp	    MapSeg60

; GetRoomPathList (plan D4): HL = the ACTIVE world's path list for (Room).
; The room->routes INDEX lives per world (WDIR_PATHS in the world segment);
; the route blocks it points into stay in Banks456's paths bank, shared by
; every world. Callers (GetPathPoints / GetSentinelLookDirs, Banks0123 seg 0)
; have just done SetBanks_4_5_6; the caller's #6000 segment is restored from
; the BankIn60 shadow before returning so the pointer dereferences into the
; shared paths bank. Preserves B (the caller's guard/sentinel index).
GetRoomPathList:
		    ld	    a, (BankIn60)
		    push    af			    ; caller's #6000 segment (4)
		    ld	    a, (CurWorldSeg)
		    call    MapSeg60
		    ld	    a, (Room)
		    ld	    l, a
		    ld	    h, 0
		    add	    hl, hl
		    ld	    de, (WDIR_PATHS)	    ; this world's idxRoomPaths
		    add	    hl, de
		    ld	    e, (hl)
		    inc	    hl
		    ld	    d, (hl)		    ; DE = Paths_* list (Banks456 addr)
		    pop	    af
		    call    MapSeg60		    ; restore the paths bank at #6000
		    ex	    de, hl
		    ret

; MapSeg60/MapSeg80 and the shims must sit OUTSIDE the windows they swap:
; CacheRoomLayout swaps BOTH #6000 and #8000, so this code must be in the
; #A000-#BFFF window (segment 6)
		    ASSERT  $ >= #A000
AddRoomItems_:
