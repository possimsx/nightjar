# Power-switch A/B: warp to room 116 (electric floor + switch, tileset 1 -> color slot 5),
# let the switch pulse the floor, and sample VDP palette slots 5 and 9 over time.
# OLD (room cp) vs NEW (per-tileset table) must produce identical sequences.
set LOG "C:/DevMSX/mgshots/ps.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
file delete $LOG
proc lg {m} { global LOG; set f [open $LOG a]; puts $f $m; close $f }
proc pal {n} { return [format "%02x%02x" [debug read {VDP palette} [expr {$n*2}]] [debug read {VDP palette} [expr {$n*2+1}]]] }
proc samp {tag} { lg "$tag room=[debug read memory 0xc130] slot5=[pal 5] slot9=[pal 9] pswOn=[debug read memory 0xc4a0]" }
set throttle off
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 40.0 {
  debug write memory 0xc182 96
  debug write memory 0xc184 128
  debug write memory 0xc130 116
  debug write memory 0xc133 0
  debug write memory 0xc151 1
}
set s 41.0
for {set i 0} {$i < 8} {incr i} { after time $s "samp T$i"; set s [expr {$s+0.35}] }
after time 44.5 { lg DONE; exit }
