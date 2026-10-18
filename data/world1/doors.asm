;----------------------------------------------------------------------------
;
; OpenOffsetY, OpenNY, OpenOffsetX, OpenNX, EnterOffY, EnterNY,	EnterOffsetX, EnterNY
;
;----------------------------------------------------------------------------

DoorOpenEnterDat_w1:   db	20h,   8,   4, 10h, 10h, 10h,	0, 20h
		    db 0F8h,   8,   8, 10h,   0,   8,	0, 20h
		    db	28h, 10h,   8, 0Ah, 1Ch, 24h,	0,   8
		    db	28h, 10h,0F6h, 0Ah, 1Ch, 24h,	0,   8
		    db	20h,   8,   4, 10h, 10h, 10h,	0, 20h
		    db	18h, 10h,0F8h, 10h, 18h, 10h,	8, 10h
		    db 0F6h, 20h,   0, 20h,   0,   8,	0, 20h
		    db 0F6h, 12h,   0, 20h,   0,   8,	0, 20h
		    db	10h, 40h,   0, 1Ah, 20h, 20h,	8,   8
		    db	10h, 40h,0F6h, 2Ah, 20h, 20h,	0,   8
		    db	10h, 30h,   0, 2Ah, 20h, 20h, 18h,   8
		    db	20h,   8,   8, 10h, 10h, 10h,	0, 20h
		    db 0F6h, 12h,   8, 10h,   0,   8,	0, 20h
		    db	20h, 10h,   0, 1Ah, 20h, 20h,	8,   8
		    db	20h, 10h,0F6h, 1Ah, 20h, 20h,	0,   8
		    db	30h, 2Ah, 10h, 20h, 38h, 10h, 10h, 20h
		    db	10h, 30h,0F6h, 1Ah, 20h, 20h,	0,   8
		    db	10h, 30h,0F6h, 2Ah, 20h, 20h,	0,   8
		    db	10h, 18h,   0, 2Ah,0D0h, 10h,	0, 20h
		    db	28h, 10h,   8,	 8,0F0h, 40h,	0,   8


;----------------------------------------------------------------------------
;
; Doors	in rooms index
;
;----------------------------------------------------------------------------
idxDoors_w1:	    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom003_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom005_w1
		    dw DoorsRoom006_w1
		    dw DoorsRoom007_w1
		    dw DoorsRoom008_w1
		    dw DoorsRoom009_w1
		    dw DoorsRoom010_w1			    ; 10
		    dw DoorsRoom011_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom013_w1
		    dw DoorsRoom014_w1
		    dw DoorsRoom015_w1
		    dw DoorsRoom016_w1
		    dw DoorsRoom017_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom019_w1
		    dw DoorsRoom020_w1			    ; 20
		    dw DoorsRoom021_w1
		    dw DoorsRoom022_w1
		    dw DoorsRoom023_w1
		    dw DoorsRoom024_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom027_w1
		    dw DoorsRoom028_w1
		    dw DoorsRoom029_w1
		    dw DoorsRoom030_w1			    ; 30
		    dw DoorsRoom031_w1
		    dw DoorsRoom032_w1
		    dw DoorsRoom033_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom035_w1
		    dw DoorsRoom036_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom038_w1
		    dw DoorsRoom039_w1
		    dw DoorsRoom040_w1			    ; 40
		    dw DoorsRoom041_w1
		    dw DoorsRoom042_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1			    ; 50
		    dw DoorsRoom051_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom053_w1
		    dw DoorsRoom054_w1
		    dw DoorsRoom055_w1
		    dw DoorsRoom056_w1
		    dw DoorsRoom057_w1
		    dw DoorsRoom058_w1
		    dw DoorsRoom059_w1
		    dw DoorsRoom060_w1			    ; 60
		    dw DoorsRoom061_w1
		    dw DoorsRoom062_w1
		    dw DoorsRoom_063_w1
		    dw DoorsRoom_064_w1
		    dw DoorsRoom065_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom_069_w1
		    dw DoorsRoom070_w1			    ; 70
		    dw DoorsRoom071_w1
		    dw DoorsRoom072_w1
		    dw DoorsRoom_073_w1
		    dw DoorsRoom074_w1
		    dw DoorsRoom075_w1
		    dw DoorsRoom076_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom078_w1
		    dw DoorsRoom079_w1
		    dw NoDoorsRoom_w1			    ; 80
		    dw DoorsRoom081_w1
		    dw DoorsRoom082_w1
		    dw DoorsRoom083_w1
		    dw DoorsRoom084_w1
		    dw DoorsRoom085_w1
		    dw DoorsRoom086_w1
		    dw DoorsRoom_087_w1
		    dw DoorsRoom088_w1
		    dw DoorsRoom089_w1
		    dw NoDoorsRoom_w1			    ; 90
		    dw NoDoorsRoom_w1
		    dw DoorsRoom092_w1
		    dw DoorsRoom093_w1
		    dw DoorsRoom094_w1
		    dw DoorsRoom_095_w1
		    dw DoorsRoom096_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom098_w1
		    dw DoorsRoom099_w1
		    dw DoorsRoom_100_w1			    ; 100
		    dw DoorsRoom101_w1
		    dw DoorsRoom102_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom_104_w1			    ; Seven lorries at desert
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom_108_w1
		    dw DoorsRoom109_w1
		    dw DoorsRoom110_w1			    ; 110
		    dw DoorsRoom111_w1
		    dw DoorsRoom_112_w1
		    dw DoorsRoom113_w1
		    dw DoorRoom_114_w1
		    dw DoorsRoom115_w1
		    dw DoorsRoom_116_w1
		    dw DoorsRoom_117_w1			    ; Roof: Parachute jump (!?)	#14 Render ID does not exits
		    dw DoorsRoom_118_w1			    ; Metal Gear room
		    dw DoorsRoom_119_w1			    ; Big boss fight room
		    dw NoDoorsRoom_w1			    ; 120
		    dw NoDoorsRoom_w1
		    dw DoorsRoom122_w1
		    dw DoorsRoom123_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom125_w1
		    dw DoorsRoom126_w1
		    dw DoorsRoom127_w1
		    dw DoorsRoom128_w1
		    dw DoorsRoom129_w1
		    dw DoorsRoom130_w1			    ; 130
		    dw DoorsRoom131_w1
		    dw DoorsRoom132_w1
		    dw DoorsRoom133_w1
		    dw DoorsRoom134_w1
		    dw DoorsRoom135_w1
		    dw DoorsRoom136_w1
		    dw DoorsRoom137_w1
		    dw DoorsRoom138_w1
		    dw DoorsRoom139_w1
		    dw DoorsRoom140_w1			    ; 140
		    dw DoorsRoom141_w1
		    dw DoorsRoom142_w1
		    dw DoorsRoom143_w1
		    dw DoorsRoom144_w1
		    dw DoorsRoom145_w1
		    dw DoorsRoom146_w1
		    dw DoorsRoom147_w1
		    dw DoorsRoom148_w1
		    dw DoorsRoom149_w1
		    dw DoorsRoom150_w1			    ; 150
		    dw DoorsRoom151_w1
		    dw DoorsRoom152_w1
		    dw DoorsRoom153_w1
		    dw DoorsRoom154_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom156_w1
		    dw DoorsRoom157_w1
		    dw DoorsRoom158_w1
		    dw DoorsRoom159_w1
		    dw DoorsRoom160_w1			    ; 160
		    dw DoorsRoom161_w1
		    dw DoorsRoom162_w1
		    dw DoorsRoom163_w1
		    dw DoorsRoom_164_w1
		    dw DoorsRoom165_w1
		    dw Door_166_w1
		    dw Door_167_w1
		    dw Door_168_w1
		    dw DoorsRoom169_w1
		    dw DoorsRoom170_w1			    ; 170
		    dw DoorsRoom171_w1
		    dw DoorsRoom172_w1
		    dw DoorsRoom173_w1
		    dw DoorsRoom174_w1
		    dw DoorsRoom175_w1
		    dw DoorsRoom176_w1
		    dw DoorsRoom177_w1
		    dw DoorsRoom178_w1
		    dw DoorsRoom179_w1
		    dw DoorsRoom180_w1			    ; 180
		    dw DoorsRoom181_w1
		    dw DoorsRoom182_w1
		    dw DoorsRoom183_w1
		    dw DoorsRoom_184_w1
		    dw DoorsRoom185_w1
		    dw DoorsRoom186_w1
		    dw DoorsRoom187_w1
		    dw DoorsRoom188_w1
		    dw DoorsRoom189_w1
		    dw DoorsRoom190_w1			    ; 190
		    dw DoorsRoom191_w1
		    dw DoorsRoom192_w1
		    dw DoorsRoom193_w1
		    dw DoorsRoom194_w1
		    dw DoorsRoom195_w1
		    dw DoorsRoom196_w1
		    dw DoorsRoom197_w1
		    dw DoorsRoom198_w1
		    dw DoorsRoom199_w1
		    dw DoorsRoom200_w1			    ; 200
		    dw DoorsRoom201_w1
		    dw DoorsRoom202_w1
		    dw DoorsRoom203_w1
		    dw DoorsRoom204_w1			    ; vv
		    dw DoorsRoom205_w1
		    dw DoorsRoom206_w1
		    dw DoorsRoom207_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1			    ; 210
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom213_w1
		    dw DoorsRoom214_w1
		    dw DoorsRoom215_w1
		    dw DoorsRoom216_w1
		    dw DoorsRoom217_w1
		    dw DoorsRoom218_w1
		    dw DoorsRoom219_w1
		    dw NoDoorsRoom_w1			    ; 220
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom_224_w1

; Rooms	225-239	are skipped (have no doors or are not used)

		    dw DoorsRoom240_w1			    ; 240
		    dw DoorsRoom241_w1
		    dw DoorsRoom242_w1
		    dw DoorsRoom243_w1
		    dw DoorsRoom244_w1
		    dw DoorsRoom245_w1
		    dw DoorsRoom246_w1
		    dw DoorsRoom247_w1
		    dw NoDoorsRoom_w1
		    dw NoDoorsRoom_w1
		    dw DoorsRoom250_w1

;----------------------------------------------------------------------------
;
; Door ID, render type ID, drawY, drawX, destination room
;
; Render types:
; 1 = DrawDoorNorth
; 2 = DrawDoorSouth
; 3 = DrawDoorWest
; 4 = DrawDoorEast
; 5 = DrawDoorElevator
; 6 = DrawDoorDummy
; 7 = DrawBasemWall60
; 8 = DrawBasemWall61
; 9 = DrawBasemWall59_96
; A = DrawBasemWall58
; B = DrawBasemWall63
; C = DrawWallPrison2
; D = DrawWallPrison2_
; E = DrawWallPrison1
; F = DrawWallPrison
;10 = DrawWallBuil3_108
;11 = DrawBasemWall93
;12 = DrawBasemWall100
;13 = DrawBasemWall112
;----------------------------------------------------------------------------

DoorsRoom003_w1:	    db	  2,   5,   0, 64h,0F0h
		    db 0FFh

DoorsRoom005_w1:	    db	65h,   1, 44h, 24h, 7Eh
		    db	6Dh,   1, 64h, 64h, 7Fh		    ;
		    db	71h,   1, 44h,0A4h, 80h		    ;
		    db	75h,   1, 44h, 24h,0C7h		    ; Fake door	used to	locate the player when he exits	a moving lorry
		    db	6Ch,   2, 20h, 60h,0CCh
		    db 0FFh

DoorsRoom006_w1:	    db	  3,   1, 40h, 24h, 81h
		    db	  4,   1,   0,0C4h,   7
		    db	40h,   2,0A0h, 80h,0CCh
		    db 0FFh

DoorsRoom007_w1:	    db	  4,   2,0B8h,0C0h,   6
		    db	76h,   1, 84h, 24h, 82h
		    db	  5,   4, 60h,0F0h, 0Bh
		    db	77h,   1, 64h, 44h, 83h
		    db	78h,   1, 64h, 64h, 84h
		    db 0FFh

DoorsRoom008_w1:	    db	  1,   1, 40h, 44h, 8Ah
		    db 0FFh

DoorsRoom009_w1:	    db	74h,   1, 64h,0A4h, 87h
		    db	75h,   1, 64h, 24h,0C7h		    ;
		    db	85h,   1, 64h, 24h,0ADh		    ; Fake door	used to	locate the player when he exits	a moving lorry
		    db	92h,   1, 64h, 24h,0D5h		    ; Fake door	used to	locate the player when he exits	a moving lorry
		    db	98h,   1, 64h, 24h,0DBh		    ; Fake door	used to	locate the player when he exits	a moving lorry
		    db 0FFh

DoorsRoom010_w1:	    db	  7,   1, 40h, 84h, 85h,0FFh

DoorsRoom011_w1:	    db	  5,   3, 60h,	 8,   7
		    db	  6,   1,   0, 64h, 40h
		    db 0FFh
DoorsRoom013_w1:	    db	  8,   3, 60h, 28h, 88h
		    db	  9,   4, 40h,0B0h, 89h
		    db 0FFh

DoorsRoom014_w1:	    db	0Ah,   3, 40h, 48h, 86h,0FFh

DoorsRoom015_w1:	    db	0Bh,   5,   0, 84h,0F1h,0FFh

DoorsRoom016_w1:	    db	15h,   1, 60h, 44h, 8Bh
		    db	16h,   4, 60h,0F0h, 14h
		    db 0FFh

DoorsRoom017_w1:	    db	17h,   4, 40h,0D0h,0C3h
		    db	79h,   3, 20h, 48h, 8Ch
		    db 0FFh

DoorsRoom019_w1:	    db	7Ah,   1, 40h, 84h, 8Dh,0FFh

DoorsRoom020_w1:	    db	19h,   4, 60h,0F0h, 16h
		    db	16h,   3, 60h,	 8, 10h
		    db	9Bh,   1,   0, 44h, 8Fh
		    db 0FFh

DoorsRoom021_w1:	    db	7Ch,   1, 60h, 44h, 8Eh
		    db	7Dh,   1, 60h,0A4h, 8Eh
		    db 0FFh

DoorsRoom022_w1:	    db	19h,   3, 60h,	 8, 14h
		    db	1Ah,   1, 80h, 64h, 90h
		    db 0FFh

DoorsRoom023_w1:	    db	18h,   3, 40h, 28h, 8Eh,0FFh

DoorsRoom024_w1:	    db	1Bh,   1,   0, 44h, 91h,0FFh

DoorsRoom027_w1:	    db	1Ch,   5,   0, 84h,0F1h,0FFh

DoorsRoom028_w1:	    db	1Dh,   3, 60h, 28h, 92h
		    db	1Eh,   3, 20h, 28h, 93h
		    db	1Fh,   1,   0,0C4h, 1Dh
		    db 0FFh

DoorsRoom029_w1:	    db	1Fh,   2,0B8h,0C0h, 1Ch
		    db	20h,   3, 60h,	 8, 94h
		    db 0FFh

DoorsRoom030_w1:	    db	21h,   4, 40h,0D0h, 98h
		    db	7Eh,   3, 60h, 28h, 95h
		    db 0FFh

DoorsRoom031_w1:	    db	22h,   5,   0, 64h,0F0h,0FFh

DoorsRoom032_w1:	    db	7Fh,   1, 60h, 24h, 99h
		    db	80h,   3, 20h, 68h, 99h
		    db 0FFh

DoorsRoom033_w1:	    db	23h,   1, 80h, 64h, 96h
		    db	26h,   4, 60h,0F0h, 23h
		    db 0FFh

DoorsRoom035_w1:	    db	26h,   3, 60h,	 8, 21h
		    db	27h,   1,   0, 44h, 9Ch
		    db 0FFh

DoorsRoom036_w1:	    db	28h,   1, 40h, 24h, 9Eh
		    db	29h,   1, 80h,0C4h, 9Dh
		    db 0FFh

DoorsRoom038_w1:	    db	2Ah,   4, 40h,0D0h, 9Fh,0FFh

DoorsRoom039_w1:	    db	2Bh,   5,   0, 84h,0F2h,0FFh

DoorsRoom040_w1:	    db	2Ch,   1, 60h, 24h,0A0h,0FFh

DoorsRoom041_w1:	    db	2Dh,   4, 40h, 50h,0A1h,0FFh

DoorsRoom042_w1:	    db	82h,   4, 20h, 90h,0A2h,0FFh

DoorsRoom051_w1:	    db	2Eh,   1, 40h,0C4h,0A3h,0FFh

DoorsRoom053_w1:	    db	2Fh,   5,   0, 84h,0F2h,0FFh

DoorsRoom054_w1:	    db	0Ch, 0Ch, 80h, 60h,0A4h
		    db	0Dh,   1,   0, 44h, 37h
		    db 0FFh

DoorsRoom055_w1:	    db	0Dh,   2,0B8h, 40h, 36h
		    db	0Eh,   1, 60h, 84h,0A6h
		    db 0FFh

DoorsRoom056_w1:	    db	83h,   1,   0,0A4h, 7Bh,0FFh

DoorsRoom057_w1:	    db	0Fh,   4, 40h,0F0h, 3Ah
		    db	9Ah,   2,0B8h, 80h,0A8h
		    db	4Ah,   2,0B8h, 20h, 7Ah
		    db 0FFh

DoorsRoom058_w1:	    db	0Fh,   3, 40h,	 8, 39h
		    db	11h,   2,0B8h,0A0h,0ABh
		    db	8Ch, 0Ah,   0, 30h, 3Ah
		    db 0FFh

DoorsRoom059_w1:	    db	10h,   9, 20h,	 0,0A9h,0FFh

DoorsRoom060_w1:	    db	8Eh,   7, 78h,0E0h, 3Ch,0FFh

DoorsRoom061_w1:	    db	12h,   8,0B8h, 60h,0ACh,0FFh

DoorsRoom062_w1:	    db	13h,   3, 40h,	 8,0AAh,0FFh

DoorsRoom_063_w1:	    db	8Dh, 0Bh, 60h, 70h, 3Fh
		    db	14h,   5,   0, 84h,0F1h
		    db 0FFh

DoorsRoom_064_w1:	    db	  6,   2,0B8h, 60h, 0Bh
		    db	84h,   1, 64h, 24h,0AEh
		    db	85h,   1, 64h, 44h,0ADh
		    db 0FFh

DoorsRoom065_w1:	    db	86h,   1, 64h,0C4h,0AFh
		    db	96h,   1, 64h,0C4h,0D9h
		    db	94h,   1, 64h,0C4h,0D7h
		    db 0FFh

DoorsRoom_069_w1:	    db	31h,   1,   0, 84h, 49h,0FFh

DoorsRoom070_w1:	    db	32h,   1,   0, 24h,0B1h
		    db	33h,   1,   0, 64h, 47h
		    db	34h,   1,   0,0A4h,0B0h
		    db 0FFh

DoorsRoom071_w1:	    db	33h,   2,0B8h, 60h, 46h
		    db	35h,   1,   0, 64h, 48h
		    db 0FFh

DoorsRoom072_w1:	    db	35h,   2,0B8h, 60h, 47h
		    db	36h,   5,   0, 64h,0F3h
		    db 0FFh

DoorsRoom_073_w1:	    db	31h,   2,0B8h, 80h, 45h
		    db	38h,   4, 60h,0F0h, 4Ch
		    db 0FFh

DoorsRoom074_w1:	    db	37h,   3, 60h,	 8,0B2h,0FFh

DoorsRoom075_w1:	    db	39h,   4, 80h,0B0h,0B3h
		    db	3Ah,   1,   0, 84h, 66h
		    db 0FFh

DoorsRoom076_w1:	    db	3Bh,   1, 20h, 84h,0CEh
		    db	38h,   3, 60h,	 8, 49h
		    db 0FFh

DoorsRoom078_w1:	    db	3Ch,   4, 40h,0F0h,0B4h,0FFh

DoorsRoom079_w1:	    db	87h,   1,   0, 24h,0B5h,0FFh

DoorsRoom081_w1:	    db	3Dh,   1, 80h, 84h,0B6h
		    db	3Eh,   5,   0, 64h,0F3h
		    db 0FFh

DoorsRoom082_w1:	    db	41h,   1,   0, 24h, 53h
		    db	44h,   1,   0,0C4h, 53h
		    db	72h,   1, 80h, 84h,0CAh
		    db 0FFh

DoorsRoom083_w1:	    db	41h,   2,0B8h, 20h, 52h
		    db	42h,   1,   0, 24h, 54h
		    db	43h,   1,   0, 84h, 54h
		    db	44h,   2,0B8h,0C0h, 52h
		    db	45h,   4, 60h,0F0h, 56h
		    db 0FFh

DoorsRoom084_w1:	    db	42h,   2,0B8h, 20h, 53h
		    db	43h,   2,0B8h, 80h, 53h
		    db 0FFh

DoorsRoom085_w1:	    db	48h,   1, 40h, 84h,0CDh,0FFh

DoorsRoom086_w1:	    db	45h,   3, 60h,	 8, 53h
		    db	46h,   1,   0, 24h,0C6h
		    db	49h,   1, 20h,0C4h,0B9h
		    db 0FFh

DoorsRoom_087_w1:	    db	47h,   1,   0, 24h,0B7h
		    db	4Bh,   1,   0,0C4h,0B8h
		    db 0FFh

DoorsRoom088_w1:	    db	4Ch,   5,   0, 64h,0F4h
		    db	4Dh,   1, 80h, 44h,0BAh
		    db 0FFh

DoorsRoom089_w1:	    db	4Eh,   1, 80h,0A4h,0BBh,0FFh

DoorsRoom092_w1:	    db	25h,   1,   0, 84h, 9Ah,0FFh

DoorsRoom093_w1:	    db	30h,   2,0B8h, 60h, 7Dh
		    db	64h, 11h, 40h,0F0h, 60h
		    db	88h,   1, 60h, 24h,0C4h
		    db 0FFh

DoorsRoom094_w1:	    db	50h,   1, 80h, 44h,0C5h,0FFh

DoorsRoom_095_w1:	    db	51h,   5,   0, 64h,0F3h
		    db	52h,   4, 60h,0F0h, 62h
		    db 0FFh

DoorsRoom096_w1:	    db	55h,   4, 60h,0F0h, 63h
		    db	64h,   9, 40h,	 0, 5Dh
		    db 0FFh

DoorsRoom098_w1:	    db	53h,   1, 80h, 44h,0BCh
		    db	54h,   1, 60h,0C4h,0BDh
		    db	52h,   3, 60h,	 8, 5Fh
		    db 0FFh

DoorsRoom099_w1:	    db	55h,   3, 60h,	 8, 60h
		    db	56h,   1, 20h, 24h,0CBh
		    db	57h,   1, 60h, 84h,0CFh
		    db	58h,   1,   0,0C4h, 64h
		    db 0FFh

DoorsRoom_100_w1:	    db	58h,   2,0B8h,0C0h, 63h
		    db	90h, 12h,   0, 30h, 64h
		    db 0FFh

DoorsRoom101_w1:	    db	89h,   1, 60h, 44h,0BEh
		    db	8Ah,   1, 40h,0C4h,0BFh
		    db 0FFh

DoorsRoom102_w1:	    db	3Ah,   2,0B8h, 80h, 4Bh,0FFh

DoorsRoom_104_w1:	    db	59h,   1,   0, 64h, 6Ch
		    db	92h,   1, 30h,	 8,0D5h
		    db	98h,   1, 30h,0E8h,0DBh
		    db	93h,   1, 30h, 28h,0D6h
		    db	94h,   1, 30h, 48h,0D7h
		    db	95h,   1, 30h, 88h,0D8h
		    db	96h,   1, 30h,0A8h,0D9h
		    db	97h,   1, 30h,0C8h,0DAh
		    db 0FFh

DoorsRoom_108_w1:	    db	9Ch,   3, 60h,	 8,0C9h
		    db	68h, 10h, 18h,0A0h, 6Ch
		    db	59h,   2,0B8h, 60h, 68h
		    db 0FFh

DoorsRoom109_w1:	    db	5Ah,   5,   0, 64h,0F7h,0FFh

DoorsRoom110_w1:	    db	5Ch,   1,   0,0C4h,0C1h
		    db	8Bh,   1,   0, 24h,0C0h
		    db 0FFh

DoorsRoom111_w1:	    db	5Fh,   1,   0,0C4h, 70h,0FFh

DoorsRoom_112_w1:	    db	5Fh,   2,0B8h,0C0h, 6Fh
		    db	60h,   1,   0,0A4h, 71h
		    db	61h, 13h,   0, 28h, 71h
		    db 0FFh

DoorsRoom113_w1:	    db	60h,   2,0B8h,0A0h, 70h
		    db	3Fh,   1,   0,0C4h, 72h
		    db 0FFh

DoorRoom_114_w1:	    db	62h,   1,   0, 24h, 74h
		    db	3Fh,   2,0B8h,0C0h, 71h
		    db 0FFh

DoorsRoom115_w1:	    db	5Dh,   5,   0, 84h,0FAh
		    db	5Eh,   4, 60h,0F0h,0C2h
		    db	73h,   8,0B8h, 80h,0C8h
		    db 0FFh

DoorsRoom_116_w1:	    db	62h,   2,0B8h, 20h, 72h,0FFh

DoorsRoom_117_w1:	    db	91h, 14h, 80h,0E0h,0CCh,0FFh
							    ; Roof: Parachute jump (!?)	#14 Render ID does not exits
DoorsRoom_118_w1:	    db	63h,   3, 40h,	 8, 77h,0FFh
							    ; Metal Gear room
DoorsRoom_119_w1:	    db	63h,   4, 40h,0F0h, 76h
		    db	6Bh,   1,   0, 24h,0E0h		    ; Big boss fight room
		    db 0FFh

DoorsRoom122_w1:	    db	4Ah,   1,   0, 64h, 39h,0FFh

DoorsRoom123_w1:	    db	83h,   2,0B8h,0A0h, 38h,0FFh

DoorsRoom125_w1:	    db	30h,   1,   0, 64h, 5Dh,0FFh

DoorsRoom126_w1:	    db	65h,   4, 40h,0D0h,   5,0FFh

DoorsRoom127_w1:	    db	6Dh,   4, 40h,0D0h,   5,0FFh

DoorsRoom128_w1:	    db	71h,   4, 40h,0D0h,   5,0FFh

DoorsRoom129_w1:	    db	  3,   2,0B8h, 60h,   6,0FFh

DoorsRoom130_w1:	    db	76h,   4, 40h,0D0h,   7,0FFh

DoorsRoom131_w1:	    db	77h,   4, 40h,0D0h,   7,0FFh

DoorsRoom132_w1:	    db	78h,   4, 40h,0D0h,   7,0FFh

DoorsRoom133_w1:	    db	  7,   2,0B8h, 60h, 0Ah,0FFh

DoorsRoom134_w1:	    db	0Ah,   4, 40h,0D0h, 0Eh,0FFh

DoorsRoom135_w1:	    db	74h,   4, 40h,0D0h,   9,0FFh

DoorsRoom136_w1:	    db	  8,   4, 40h,0D0h, 0Dh,0FFh

DoorsRoom137_w1:	    db	  9,   3, 40h, 28h, 0Dh,0FFh

DoorsRoom138_w1:	    db	  1,   2,0B8h, 60h,   8,0FFh

DoorsRoom139_w1:	    db	15h,   2,0B8h, 60h, 10h,0FFh

DoorsRoom140_w1:	    db	79h,   4, 40h,0D0h, 11h,0FFh

DoorsRoom141_w1:	    db	7Ah,   2,0B8h, 60h, 13h
		    db	7Bh,   4, 20h,0D0h, 8Eh
		    db 0FFh

DoorsRoom142_w1:	    db	18h,   4, 20h,0D0h, 17h
		    db	7Bh,   3, 20h, 28h, 8Dh
		    db	7Ch,   2,0B8h, 40h, 15h
		    db	7Dh,   2,0B8h,0A0h, 15h
		    db 0FFh

DoorsRoom143_w1:	    db	9Bh,   2,0B8h, 60h, 14h,0FFh

DoorsRoom144_w1:	    db	1Ah,   2,0B8h, 60h, 16h,0FFh

DoorsRoom145_w1:	    db	1Bh,   2,0B8h, 60h, 18h,0FFh

DoorsRoom146_w1:	    db	1Dh,   4, 40h,0D0h, 1Ch,0FFh

DoorsRoom147_w1:	    db	1Eh,   4, 40h,0D0h, 1Ch,0FFh

DoorsRoom148_w1:	    db	20h,   4, 40h,0D0h, 1Dh
		    db	66h,   1,   0, 64h, 95h
		    db 0FFh

DoorsRoom149_w1:	    db	66h,   2,0B8h, 60h, 94h
		    db	7Eh,   4, 40h,0D0h, 1Eh
		    db 0FFh

DoorsRoom150_w1:	    db	23h,   2,0B8h, 60h, 21h
		    db	24h,   4, 40h,0F0h, 97h
		    db 0FFh

DoorsRoom151_w1:	    db	24h,   3, 40h, 28h, 96h,0FFh

DoorsRoom152_w1:	    db	21h,   3, 40h, 28h, 1Eh,0FFh

DoorsRoom153_w1:	    db	80h,   4, 40h,0D0h, 20h
		    db	7Fh,   2,0B8h, 60h, 20h
		    db 0FFh

DoorsRoom154_w1:	    db	4Fh,   5,   0, 84h,0F6h
		    db	25h,   2,0B8h, 60h, 5Ch
		    db 0FFh

DoorsRoom156_w1:	    db	27h,   2,0B8h, 60h, 23h,0FFh

DoorsRoom157_w1:	    db	29h,   2,0B8h, 60h, 24h,0FFh

DoorsRoom158_w1:	    db	28h,   2,0B8h, 60h, 24h,0FFh

DoorsRoom159_w1:	    db	2Ah,   3, 40h, 28h, 26h,0FFh

DoorsRoom160_w1:	    db	2Ch,   2,0B8h, 60h, 28h,0FFh

DoorsRoom161_w1:	    db	2Dh,   3, 40h, 28h, 29h,0FFh

DoorsRoom162_w1:	    db	82h,   3, 40h, 24h, 2Ah,0FFh

DoorsRoom163_w1:	    db	2Eh,   2,0B8h, 60h, 33h,0FFh

DoorsRoom_164_w1:	    db	0Ch, 0Dh, 98h, 60h, 36h
		    db	67h, 0Fh, 20h,0D0h,0A5h
		    db 0FFh

DoorsRoom165_w1:	    db	67h, 0Eh, 20h, 20h,0A4h,0FFh

Door_166_w1:	    db	6Ah, 0Fh, 20h,0D0h,0A7h
		    db	0Eh,   2,0B8h, 60h, 37h
		    db 0FFh

Door_167_w1:	    db	6Ah, 0Eh, 20h, 20h,0A6h,0FFh

Door_168_w1:	    db	9Ah,   1,   0, 64h, 39h,0FFh

DoorsRoom169_w1:	    db	10h, 11h, 40h,0D0h, 3Bh,0FFh

DoorsRoom170_w1:	    db	13h,   4, 40h,0D0h, 3Eh,0FFh

DoorsRoom171_w1:	    db	11h,   1,   0, 64h, 3Ah,0FFh

DoorsRoom172_w1:	    db	12h, 0Ch,   0, 64h, 3Dh,0FFh

DoorsRoom173_w1:	    db	85h,   4, 40h,0D0h,   9,0FFh

DoorsRoom174_w1:	    db	84h,   4, 40h,0D0h, 40h,0FFh

DoorsRoom175_w1:	    db	86h,   4, 40h,0D0h, 41h,0FFh

DoorsRoom176_w1:	    db	34h,   2,0B8h, 60h, 46h,0FFh

DoorsRoom177_w1:	    db	32h,   2,0B8h, 60h, 46h,0FFh

DoorsRoom178_w1:	    db	37h,   4, 40h,0D0h, 4Ah,0FFh

DoorsRoom179_w1:	    db	39h,   3, 40h, 28h, 4Bh,0FFh

DoorsRoom180_w1:	    db	3Ch,   3, 40h, 28h, 4Eh,0FFh

DoorsRoom181_w1:	    db	87h,   2,0B8h, 60h, 4Fh,0FFh

DoorsRoom182_w1:	    db	3Dh,   2,0B8h, 60h, 51h,0FFh

DoorsRoom183_w1:	    db	47h,   2,0B8h, 60h, 57h,0FFh

DoorsRoom_184_w1:	    db	4Bh,   2,0B8h, 60h, 57h,0FFh

DoorsRoom185_w1:	    db	49h,   2,0B8h, 60h, 56h,0FFh

DoorsRoom186_w1:	    db	4Dh,   2,0B8h, 60h, 58h,0FFh

DoorsRoom187_w1:	    db	4Eh,   2,0B8h, 60h, 59h,0FFh

DoorsRoom188_w1:	    db	53h,   2,0B8h, 60h, 62h
		    db	99h,   4, 40h,0D0h,0BDh
		    db 0FFh

DoorsRoom189_w1:	    db	54h,   2,0B8h, 60h, 62h
		    db	99h,   3, 40h, 28h,0BCh
		    db 0FFh

DoorsRoom190_w1:	    db	89h,   2,0B8h, 60h, 65h,0FFh

DoorsRoom191_w1:	    db	8Ah,   2,0B8h, 60h, 65h,0FFh

DoorsRoom192_w1:	    db	8Bh,   2,0B8h, 60h, 6Eh,0FFh

DoorsRoom193_w1:	    db	5Ch,   2,0B8h, 60h, 6Eh,0FFh

DoorsRoom194_w1:	    db	5Eh,   3, 40h, 28h, 73h,0FFh

DoorsRoom195_w1:	    db	17h,   3, 40h, 28h, 11h,0FFh

DoorsRoom196_w1:	    db	88h,   2,0B8h, 60h, 5Dh,0FFh

DoorsRoom197_w1:	    db	50h,   2,0B8h, 60h, 5Eh,0FFh

DoorsRoom198_w1:	    db	46h,   2,0B8h, 60h, 56h,0FFh

DoorsRoom199_w1:	    db	75h,   4, 40h,0D0h,   5,0FFh

DoorsRoom200_w1:	    db	73h, 0Ch,   0, 60h, 73h,0FFh

DoorsRoom201_w1:	    db	9Ch,   4, 40h,0D0h, 6Ch,0FFh

DoorsRoom202_w1:	    db	72h,   2,0B8h, 60h, 52h,0FFh

DoorsRoom203_w1:	    db	56h,   2,0B8h, 60h, 63h,0FFh

DoorsRoom204_w1:	    db	91h,   2,   0, 80h, 75h
		    db	81h,   2,   0, 80h, 2Eh
		    db	5Bh,   2,   0, 80h, 2Dh
		    db 0FFh

DoorsRoom205_w1:	    db	48h,   2,0B8h, 60h, 55h
		    db	6Fh,   5,   0, 84h,0F5h
		    db 0FFh

DoorsRoom206_w1:	    db	3Bh,   2,0B8h, 60h, 4Ch
		    db	6Eh,   5,   0, 84h,0F5h
		    db 0FFh

DoorsRoom207_w1:	    db	57h,   2,0B8h, 60h, 63h
		    db	70h,   5,   0, 84h,0F5h
		    db 0FFh

DoorsRoom213_w1:	    db	92h,   4, 40h,0D0h,   9,0FFh

DoorsRoom214_w1:	    db	93h,   4, 40h,0D0h, 68h,0FFh

DoorsRoom215_w1:	    db	94h,   4, 40h,0D0h, 41h,0FFh

DoorsRoom216_w1:	    db	95h,   4, 40h,0D0h, 68h,0FFh

DoorsRoom217_w1:	    db	96h,   4, 40h,0D0h, 41h,0FFh

DoorsRoom218_w1:	    db	97h,   4, 40h,0D0h, 68h,0FFh

DoorsRoom219_w1:	    db	98h,   4, 40h,0D0h,   9,0FFh

DoorsRoom_224_w1:	    db	6Bh,   6, 80h,0E8h, 77h
		    db 0FFh

; Elevators

DoorsRoom240_w1:	    db	  2,   6, 98h,0E0h,   3
		    db	22h,   6, 18h,0E0h, 1Fh
		    db 0FFh

DoorsRoom241_w1:	    db	0Bh,   6, 58h,0E0h, 0Fh
		    db	14h,   6, 98h,0E0h, 3Fh
		    db	1Ch,   6, 18h,0E0h, 1Bh
		    db 0FFh

DoorsRoom242_w1:	    db	2Bh,   6, 98h,0E0h, 27h
		    db	2Fh,   6, 58h,0E0h, 35h
		    db 0FFh

DoorsRoom243_w1:	    db	36h,   6, 58h,0E0h, 48h
		    db	51h,   6, 98h,0E0h, 5Fh
		    db	3Eh,   6, 18h,0E0h, 51h
		    db 0FFh

DoorsRoom244_w1:	    db	4Ch,   6, 98h,0E0h, 58h,0FFh

DoorsRoom245_w1:	    db	6Eh,   6, 58h,0E0h,0CEh
		    db	6Fh,   6, 18h,0E0h,0CDh
		    db	70h,   6, 98h,0E0h,0CFh
		    db 0FFh

DoorsRoom246_w1:	    db	4Fh,   6, 98h,0E0h, 9Ah,0FFh

DoorsRoom247_w1:	    db	5Ah,   6, 18h,0E0h, 6Dh,0FFh

DoorsRoom250_w1:	    db	5Dh,   6, 98h,0E0h, 73h

; 63h 6Bh
NoDoorsRoom_w1:	    db 0FFh

;----------------------------------------------------------------------------
;
; Each door ID has its own data
;
; Bits 4-0:
; 1 = ChkElevatorDoor
; 2 = ChkCard1
; 3 = ChkCard2
; 4 = ChkCard3
; 5 = ChkCard4
; 6 = ChkCard5
; 7 = ChkCard6
; 8 = ChkCard7
; 9 = ChkCard8
; A = ChkPunchDoor
; B = ChkBasementWall63
; C = ChkDesertDoorBuild2
; D = ChkJenifferCompassDoor
; E = ChkBigBossDoor
; F = ChkPrisonWalls
;10 = ChkBasementWall
;
; Bits 7-6:
;    #80 = open
; others = closed
;
; Bit 5:
;      1 = No need to teleport the player (Broken wall inside a	room. Does not connect to other	room)
;----------------------------------------------------------------------------
IdDoorsLogic_w1:	    db	  2, 41h,   5,	 5,   5, 45h,	5, 42h,	  3, 43h, 41h, 2Fh,   7,   7,	4, 30h
		    db	  5, 30h,   4, 41h,   4,   5, 44h, 44h,	  4, 44h, 42h, 41h, 42h,   3, 42h, 42h
		    db	43h, 41h, 43h, 42h,   6,   3,	3,   3,	  2, 42h, 41h,	 4, 43h,   4, 41h,   7
		    db	4Ch,   5, 45h,	 7,   5, 41h,	3,   6,	  7, 48h,   6, 46h, 47h, 41h, 42h, 81h
		    db	42h, 42h, 43h, 46h, 46h, 44h,	7,   6,	  7,   3, 0Dh, 41h, 43h,   5, 41h, 46h
		    db	41h, 47h,   7,	 6, 46h, 46h,	6, 44h,	  8, 41h, 81h, 48h, 41h, 49h, 49h,   9
		    db	30h, 42h, 0Eh, 30h, 8Ah,   2, 2Fh, 10h,	0Bh, 30h, 0Eh, 81h, 8Bh, 41h, 41h, 41h
		    db	8Bh, 81h, 30h, 81h, 81h, 81h, 81h, 81h,	81h, 81h, 44h, 81h, 81h, 81h, 81h, 81h
		    db	81h, 81h, 42h, 81h, 81h, 81h, 81h, 81h,	42h, 81h,   2, 10h, 10h, 10h, 10h, 10h
		    db	81h, 81h, 81h, 81h, 81h, 81h, 81h, 81h,	81h, 0Ah,   2, 42h


TilesBasemWall60_w1:   db 6
		    db 4
		    db	19h, 19h, 19h, 19h
		    db	39h, 32h, 39h, 39h
		    db	37h, 39h, 39h, 37h
		    db	39h, 39h, 36h, 39h
		    db	39h, 38h, 39h, 39h
		    db	41h, 41h, 41h, 41h


TilesBasemWall61_w1:   db 1
		    db 4
		    db	19h, 19h, 19h, 19h


TilesBasemWall59_w1:   db 0Dh
		    db 3
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h
		    db	18h, 3Dh, 41h


TilesBasemWall58_w1:   db 0Dh
		    db 5
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h


TilesBasemWall63_w1:   db 0Ch
		    db 5
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h

;----------------------------------------------------------------------------
;
; Tiles	to hide	south exit in GreyFox cell
;
;----------------------------------------------------------------------------
TilesWallPrison2_w1:   db 1
		    db 4
		    db	17h, 17h, 17h, 17h

;----------------------------------------------------------------------------
;
; Tiles	breakable wall in Snake	cell
;
;----------------------------------------------------------------------------
TilesWallPrison1_w1:   db 0Dh
		    db 3
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h
		    db	14h, 33h, 35h


TilesWallPrison_w1:    db 0Ch
		    db 2
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h
		    db	32h, 13h


TilesWallBld3_108_w1:  db 0Ah
		    db 8
		    db	21h, 21h, 21h, 21h, 21h, 21h, 21h, 21h
		    db	1Ch, 49h, 49h, 49h, 49h, 49h, 49h, 1Dh
		    db	1Ch, 46h, 49h, 49h, 49h, 47h, 49h, 1Dh
		    db	1Ch, 49h, 49h, 47h, 49h, 49h, 49h, 1Dh
		    db	18h, 21h, 21h, 21h, 21h, 21h, 21h, 1Bh
		    db	49h, 49h, 49h, 47h, 47h, 49h, 49h, 49h
		    db	4Ah, 4Bh, 4Ah, 4Bh, 4Ah, 4Bh, 4Ah, 4Bh
		    db	49h, 46h, 49h, 49h, 43h, 49h, 47h, 49h
		    db	4Ah, 4Bh, 4Ah, 4Bh, 4Ah, 4Bh, 4Ah, 4Bh
		    db	61h, 61h, 61h, 61h, 61h, 61h, 61h, 61h


TilesBasemWall93_w1:   db 0Ch
		    db 2
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h
		    db	3Ah, 17h


TilesBasemWall100_w1:  db 0Ch
		    db 5
		    db	26h, 17h, 18h, 3Dh, 41h
		    db	27h, 17h, 18h, 3Dh, 41h
		    db	28h, 17h, 18h, 3Dh, 41h
		    db	29h, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 18h, 3Dh, 41h
		    db	3Ah, 17h, 19h, 19h, 19h
		    db	3Ah, 17h, 18h, 22h, 35h
		    db	3Ah, 17h, 18h, 23h, 39h
		    db	3Ah, 17h, 18h, 24h, 37h
		    db	3Ah, 17h, 18h, 25h, 39h


TilesBasemWall112_w1:  db 5
		    db 6
		    db	32h, 39h, 39h, 39h, 39h, 33h
		    db	39h, 39h, 37h, 39h, 32h, 39h
		    db	39h, 36h, 39h, 39h, 39h, 36h
		    db	38h, 39h, 39h, 39h, 37h, 39h
		    db	41h, 41h, 41h, 41h, 41h, 41h