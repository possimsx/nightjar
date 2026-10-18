;----------------------------------------------------------------------------
;
; Index	of indexes of items in the rooms
;
;----------------------------------------------------------------------------
idxRoomItemsIdx_w1:    db	12h,   0,   0,	 0,   1,   2,	3,   0,	28h,   0,   4,	 0,   0,   7,	0,   6
		    db	  5,   9,   8,	 0, 0Bh, 0Ah,	0,   0,	  0, 0Dh,   0, 0Ch,   0, 0Eh,	0, 29h
		    db	  0,   0, 11h, 10h, 23h,   0, 13h,   0,	2Ah, 2Eh,   0,	 0,   0,   0, 14h, 19h
		    db	17h, 16h, 2Bh,	 0, 18h, 15h, 1Ch, 1Bh,	1Ah, 0Fh,   0, 1Dh,   0, 1Eh, 1Fh, 20h
		    db	  0, 21h, 24h,	 0,   0, 25h, 26h,   0,	  0,   0, 2Fh, 23h,   0,   0, 27h,   0
		    db	  0,   0,   0,	 0,   0,   0,	0,   0,	  0,   0,   0,	 0, 2Ah,   0, 2Fh,   0
		    db	0			    ; slot 96 = room 218. Stock had 2Dh here but cp 218
						    ; made it DEAD (never loaded). Phase A derives the bound
						    ; from the table length (219), so this slot is now LIVE
						    ; and must be 0 to keep stock behaviour (no item in 218).

;----------------------------------------------------------------------------
;
; Index	of Items sets
;
;----------------------------------------------------------------------------
idxRoomItems_w1:	    dw ItemRation_w1
		    dw ItemCard1_w1
		    dw ItemBinoculars_w1
		    dw ItemMines_w1
		    dw ItemGasMask_w1
		    dw ItemSMG_w1
		    dw ItemCard4_w1
		    dw ItemMines2_w1
		    dw ItemGoggles_w1
		    dw ItemParachute_w1			    ; 10
		    dw ItemPBombAmmo_w1
		    dw ItemAmmo_w1
		    dw ItemMissile_w1
		    dw ItemGrenade_w1
		    dw ItemPBomb_w1
		    dw ItemCard2_w1
		    dw ItemBox_w1
		    dw ItemCard3_w1
		    dw ItemMineDetect_w1
		    dw ItemBag_w1				    ; 20
		    dw ItemRation2_w1
		    dw ItemArmor_w1
		    dw ItemBombSuit_w1
		    dw ItemPBomb2_w1
		    dw ItemUniform_w1
		    dw ItemAntenna_w1
		    dw ItemUniMineAmm_w1
		    dw ItemFlashLight_w1
		    dw ItemAmmox3_w1
		    dw ItemAntidote_w1			    ; 30
		    dw ItemCompass_w1
		    dw ItemRocket_w1
		    dw ItemCard5Ammo_w1
		    dw ItemRation3_w1
		    dw ItemRation3_w1			    ; shared: was ItemRation4 (dup of #34, RATION@4820h)
		    dw ItemCard6_w1
		    dw ItemBombAmmRat_w1
		    dw ItemAmmox2_w1
		    dw ItemOxygen_w1
		    dw ItemGun_w1
		    dw ItemPBomb3_w1
		    dw ItemAmmo2_w1
		    dw ItemPBombAmmo2_w1
		    dw ItemAmmo3_w1
		    dw ItemRation5_w1
		    dw ItemMissile_w1			    ; shared: was ItemMissile2 (dup of #13, MISSILE@4820h)
		    dw ItemAmmox2__w1
		    
		    
;----------------------------------------------------------------------------
; Items
;
; Item ID, Y, X
; FF = End
;
;----------------------------------------------------------------------------
ItemRation_w1:         db RATION
                    dw 5050h
                    db 0FFh

ItemCard1_w1:          db CARD1
                    dw 7050h
                    db 0FFh

ItemBinoculars_w1:     db BINOCULARS
                    dw 7040h
                    db 0FFh

ItemMines_w1:          db LAND_MINE
                    dw 6040h
                    db 0FFh

ItemGasMask_w1:        db GAS_MASK
                    dw 4820h
                    db 0FFh

ItemSMG_w1:            db SUB_MACHINE_GUN
                    dw 4020h
                    db 0FFh

ItemCard4_w1:          db CARD4
                    dw 8060h
                    db 0FFh

ItemMines2_w1:         db LAND_MINE
                    dw 4820h
                    db 0FFh

ItemGoggles_w1:        db GOGGLES
                    dw 4820h
                    db 0FFh

ItemParachute_w1:      db PARACHUTE
                    dw 4820h
                    db 0FFh

ItemPBombAmmo_w1:      db PLASTIC_BOMB
                    dw 5080h
                    db AMMO_CRATE
                    dw 0B080h
                    db 0FFh

ItemAmmo_w1:           db AMMO_CRATE
                    dw 0A020h
                    db 0FFh

ItemMissile_w1:        db MISSILE
                    dw 4820h
                    db 0FFh

ItemGrenade_w1:        db GRENADE_LAUNCHER
                    dw 8020h
                    db 0FFh

ItemPBomb_w1:          db PLASTIC_BOMB
                    dw 8820h
                    db 0FFh

ItemCard2_w1:          db CARD2
                    dw 4820h
                    db 0FFh

ItemBox_w1:            db CARDBOARD_BOX
                    dw 4860h
                    db 0FFh

ItemCard3_w1:          db CARD3
                    dw 4270h
                    db AMMO_CRATE
                    dw 0A040h
                    db 0FFh

ItemMineDetect_w1:     db MINE_DETECTOR
                    dw 4820h
                    db 0FFh

ItemBag_w1:            db BAG
                    dw 8820h
                    db 0FFh

ItemRation2_w1:        db RATION
                    dw 6040h
                    db 0FFh

ItemArmor_w1:          db ARMOR
                    dw 8820h
                    db 0FFh

ItemBombSuit_w1:       db BOMB_SUIT
                    dw 4820h
                    db 0FFh

ItemPBomb2_w1:         db PLASTIC_BOMB
                    db 60h
                    db 60h
                    db 0FFh

ItemUniform_w1:        db UNIFORM
                    db  20h, 48h
                    db 0FFh

ItemAntenna_w1:        db ANTENNA
                    db 20h
                    db 48h
                    db 0FFh

ItemUniMineAmm_w1:     db LAND_MINE
                    dw 8070h
                    db AMMO_CRATE
                    dw 4040h
                    db UNIFORM
                    dw 4820h
                    db 0FFh

ItemFlashLight_w1:     db FLASH_LIGHT
                    dw 4820h
                    db 0FFh

ItemAmmox3_w1:         db AMMO_CRATE
                    dw 7030h
                    db AMMO_CRATE
                    dw 3840h
                    db AMMO_CRATE
                    dw 0B880h
                    db 0FFh

ItemAntidote_w1:       db ANTIDOTE
                    dw 4820h
                    db 0FFh

ItemCompass_w1:        db COMPASS
                    dw 4820h
                    db 0FFh

ItemRocket_w1:         db ROCKET_LAUNCHER
                    dw 4020h
                    db 0FFh

ItemCard5Ammo_w1:      db CARD5
                    dw 4820h
                    db AMMO_CRATE
                    dw 0A880h
                    db 0FFh

ItemRation3_w1:        db RATION
                    dw 4820h
                    db 0FFh

ItemCard6_w1:          db CARD6
                    dw 4820h
                    db 0FFh

ItemBombAmmRat_w1:     db PLASTIC_BOMB
                    dw 2848h
                    db AMMO_CRATE
                    dw 0C048h
                    db RATION
                    dw 0C060h
                    db 0FFh

ItemAmmox2_w1:         db AMMO_CRATE
                    dw 6818h
                    db AMMO_CRATE
                    dw 4050h
                    db 0FFh

ItemOxygen_w1:         db OXYGEN
                    dw 8820h
                    db 0FFh

ItemGun_w1:            db HAND_GUN
                    dw 4060h
                    db 0FFh

ItemPBomb3_w1:         db PLASTIC_BOMB
                    dw 3038h
                    db 0FFh

ItemAmmo2_w1:          db AMMO_CRATE
                    dw 6830h
                    db 0FFh

ItemPBombAmmo2_w1:     db AMMO_CRATE
                    dw 402Ah
                    db PLASTIC_BOMB
                    dw 0A870h
                    db 0FFh

ItemAmmo3_w1:          db AMMO_CRATE
                    dw 1850h
                    db 0FFh

ItemRation5_w1:        db RATION
                    dw 4840h
                    db 0FFh

ItemAmmox2__w1:        db AMMO_CRATE
                    dw 6050h
                    db AMMO_CRATE
                    dw 0A870h
                    db 0FFh
