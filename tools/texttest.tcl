# Text->flag gate verification (docs/CODEC-GATE-PLAN.md Phase 2, Table A).
# Boots, then does a forced subroutine call to SetTextGateFlag (0x5EF4, NEW ROM)
# with A = TextId, and reads the four story flags back. Proves the table-driven
# routine sets exactly the mapped flag: 117->JeniRocketF, 118->JeniOpenDoorF,
# 138->SchneiderCaptured, anything else -> none.
# Env: MGLOG (log name), MGTID (TextId to feed).
set LOG "C:/DevMSX/mgshots/txt.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set TID 100
if {[info exists ::env(MGTID)]} { set TID $::env(MGTID) }
set XADDR 0xc617
if {[info exists ::env(MGXADDR)]} { set XADDR $::env(MGXADDR) }
file delete $LOG
proc report {} {
  global TID LOG
  set f [open $LOG a]
  puts $f "tid=$TID jrock=[debug read memory 0xc661] jopen=[debug read memory 0xc663] schn=[debug read memory 0xc662] b2=[debug read memory 0xc62c] pool0=[debug read memory $::XADDR]"
  close $f
  exit
}
set throttle off
# boot: mash SPACE/RETURN through title + intro
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 {
  global TID
  # clear the four story flags this system can set
  debug write memory 0xc661 0
  debug write memory 0xc662 0
  debug write memory 0xc663 0
  debug write memory 0xc62c 0
  # forced call: SetTextGateFlag(A=TID), returning to sentinel 0xE010
  debug set_bp 0xe010 {} { report }
  reg A $TID
  set sp [expr {[reg SP] - 2}]
  reg SP $sp
  debug write memory $sp 0x10
  debug write memory [expr {$sp+1}] 0xe0
  reg PC 0x5ef4
}
after time 45.0 { global TID LOG; set f [open $LOG a]; puts $f "tid=$TID TIMEOUT"; close $f; exit }
