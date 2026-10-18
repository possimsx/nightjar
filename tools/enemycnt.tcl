# Forced-call verification of SetSpecialEnemyCnt (0x55E2, seg0). Sentinel the two
# counters (0xEE), set Room, force-call, read counters. Expected:
#   room 83 -> ArnoldsCnt=2 (Guard untouched), 150 -> GuardSilencerCnt=4 (Arnold
#   untouched), other -> both untouched.
set LOG "C:/DevMSX/mgshots/enemycnt.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set R 83
if {[info exists ::env(MGR)]} { set R $::env(MGR) }
file delete $LOG
proc report {} {
  global LOG R
  set f [open $LOG a]
  puts $f "room=$R ArnoldsCnt=[debug read memory 0xc626] GuardSilencerCnt=[debug read memory 0xc638]"
  close $f; exit
}
set throttle off
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 {
  global R
  debug write memory 0xc626 0xEE
  debug write memory 0xc638 0xEE
  debug write memory 0xc130 $R
  debug set_bp 0xe100 {} { report }
  set sp [expr {[reg SP] - 2}]; reg SP $sp
  debug write memory $sp 0x00
  debug write memory [expr {$sp+1}] 0xe1
  reg PC 0x55e2
}
after time 44.0 { global LOG R; set f [open $LOG a]; puts $f "room=$R TIMEOUT"; close $f; exit }
