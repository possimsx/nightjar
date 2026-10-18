# Checkpoint terminator-scanner verification (docs/LIMITS-PLAN.md Phase A).
# Boots the game, walks the dock ladder 121->0 and back 0->121, and logs every
# ChkSaveGameStatus entry (SCAN) and save trigger (SAVE) via breakpoints.
# Pair [0,121] is #32 in the list - beyond the old fixed-31 loop - so a SAVE on
# 121->0 proves the 0FFh-terminator rework; the SAVE on 0->121 (stock pair
# [121,0]) proves stock behaviour is intact.
set LOG "C:/DevMSX/mgshots/cptest.txt"
file delete $LOG
proc lg {msg} { set f [open C:/DevMSX/mgshots/cptest.txt a]; puts $f $msg; close $f }
proc st {tag} { lg "$tag room=[debug read memory 0xc130] gs=[debug read memory 0xc000]/[debug read memory 0xc001] pcm=[debug read memory 0xc180] y=[debug read memory 0xc182] x=[debug read memory 0xc184]" }
# only trust the bp when segment 6 is mapped at #A000 (scanner signature bytes)
proc seg6ok {} { expr {[debug read memory 0xBE08]==0x7E && [debug read memory 0xBE09]==0xFE && [debug read memory 0xBE0A]==0xFF} }
debug set_bp 0xBDF8 {} { if {[seg6ok]} { lg "SCAN room=[debug read memory 0xc130] prev=[debug read memory 0xc136]" } }
debug set_bp 0xBE20 {} { if {[seg6ok]} { lg "SAVE room=[debug read memory 0xc130] prev=[debug read memory 0xc136]" } }
set throttle off
# title + intro radio call: mash SPACE/RETURN (start.tcl pattern)
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
# centre on the dock ladder, climb up 121->0 (NEW pair 32 [0,121]),
# then climb back down 0->121 (stock pair [121,0])
after time 40.0 { st T40; debug write memory 0xc183 0; debug write memory 0xc184 128 }
after time 40.3 {keymatrixdown 8 32}
after time 44.5 {keymatrixup 8 32}
after time 45   { st T45; screenshot -raw C:/DevMSX/mgshots/cp45.png }
after time 45.5 {keymatrixdown 8 64}
after time 52.5 {keymatrixup 8 64}
after time 53   { st T53; lg "DONE" }
after time 54   { exit }
