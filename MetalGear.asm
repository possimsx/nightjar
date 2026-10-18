;----------------------------------------------------------------------------
;
; Metal	Gear (RC750)
;
; Copyright Konami 1987
;
;----------------------------------------------------------------------------
;
; Main Program:
;	Hiroyuki Fukui
;
; Sub Program:
;	Tomonori Otsuka
;	Koji Toyohara
;
; Graphic Design:
;	Masami Tabata
;	Azusa Fujimoto
;
; Main Sound Effect:
;	Iku Mizutani
;
; Subsound Effect:
;	Shigehiro Takenouchi
;	Motoaki Furukawa
;
; Game Design:
;	Hideo Kojima
;
;----------------------------------------------------------------------------
;
; Disassembled by Manuel Pazos 2017
; @ManuelPazosMSX
;
;----------------------------------------------------------------------------


JAPANESE	equ	0	; 1 = Japanese version, 0 = English version

		include	"features.asm"		; engine-addition flags (EXTGFX, ...)

;----------------------------------------------------------------------------
;
; Includes
;
;----------------------------------------------------------------------------

		include	"constants/bios.asm"
		include	"constants/SystemVariables.asm"
		include	"constants/structures.asm"
		include	"constants/Enums.asm"
		include	"constants/parachute.asm"
		include	"constants/elevators.asm"
		include	"constants/ladders.asm"
		include	"Variables.asm"


;----------------------------------------------------------------------------
;
; Banks
;
;----------------------------------------------------------------------------
		
		include	"Banks0123.asm"
		include	"Banks456.asm"
		include	"Banks789.asm"
		include	"BanksABC.asm"
		include	"BanksDEF.asm"

		IF (EXTGFX)
		include	"BanksExtGfx.asm"	; extended tilesets (gfx 8-15), segs 10h-12h
		ENDIF

		IF (WORLDBANK)
		include	"BanksWorld.asm"	; world-data bank (items/actors), seg WORLD_SEG

		IF (WORLDS-1)
		include	"BanksWorld1.asm"	; world 1 (generated; assembled when WORLDS > 1)
		ENDIF
		ENDIF

		end