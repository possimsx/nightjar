# Per-room antenna decoupling verification (docs/CODEC-GATE-PLAN.md).
# Forced call to SetRadioArea (0x4376) with Room=MGROOM, then reads MapZone
# (music, 0xC161) and RoomNeedsAntenna (0xC15A). Stock init has the antenna
# table = (zone>=5), so RoomNeedsAntenna should equal (MapZone>=5) for every
# room. After an editor edit they can diverge (that's the whole point).
# Env: MGLOG, MGROOM.
set LOG "C:/DevMSX/mgshots/ant.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set ROOM 0
if {[info exists ::env(MGROOM)]} { set ROOM $::env(MGROOM) }
file delete $LOG
proc report {} {
  global ROOM LOG
  set mz [debug read memory 0xc161]
  set rna [debug read memory 0xc15a]
  set exp [expr {$mz >= 5 ? 1 : 0}]
  set f [open $LOG a]
  puts $f "room=$ROOM mapzone=$mz rna=$rna expect(zone>=5)=$exp [expr {($rna!=0)==$exp ? {OK} : {MISMATCH}}]"
  close $f
  exit
}
set throttle off
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 {
  global ROOM
  debug write memory 0xc130 $ROOM
  debug write memory 0xc15a 238            ;# poison RoomNeedsAntenna so we see it get written
  debug set_bp 0xe010 {} { report }
  set sp [expr {[reg SP] - 2}] ; reg SP $sp
  debug write memory $sp 0x10 ; debug write memory [expr {$sp+1}] 0xe0
  reg PC 0x4376
}
after time 45.0 { global ROOM LOG; set f [open $LOG a]; puts $f "room=$ROOM TIMEOUT"; close $f; exit }
