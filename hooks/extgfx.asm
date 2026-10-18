;----------------------------------------------------------------------------
; EXTGFX hook: extended-tileset divert, placed in the unused cartridge-header
; padding (#4014-#402F) by Banks0123.asm via `IF (EXTGFX) include ... ELSE`.
;
; Replaces the post-crates `call SetBanks_7_8_9` in LoadRoomTiles (that call site
; is the matching `IF (EXTGFX) call ExtDivert ELSE call SetBanks_7_8_9` shim). For
; gfx id<8 it is byte-equivalent (jp SetBanks_7_8_9); for id>=8 it maps segments
; 16/17/18 through SetBanks (keeping the BankIn shadows correct) and rets into
; LoadExtDispatch (BanksExtGfx.asm) instead of the stock tile path.
;
; The trailing `ds (#4030-$),0` keeps the sound pointers anchored at #4030, so the
; assembled span is identical in size to the stock padding it replaces.
;----------------------------------------------------------------------------
ExtDivert:	    ld	    a, (CurrentTileSet)
		    cp	    8
		    jp	    c, SetBanks_7_8_9	    ; id<8: byte-equivalent stock path
		    pop	    hl			    ; id>=8: drop ext_ret + the af pushed pre-crates
		    pop	    hl
		    ld	    hl, LoadExtDispatch
		    push    hl			    ; SetBanks will 'ret' into the ext dispatcher
		    push    af			    ; SetBanks pops this (bank base set below)
		    di
		    ld	    a, 10h
		    jp	    SetBanks		    ; map 16/17/18 (+BankIn shadows), ei, ret->dispatch
		    ds	    (#4030-$), 0	    ; keep the sound pointers at #4030
