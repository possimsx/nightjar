# One-shot flag-door verification (docs/CODEC-GATE-PLAN.md Phase 2, Table B doors).
# Forced call to ChkGateDoor (0x79C0) with A = door logic type, reading the carry
# result (CY=1 unlocked / 0 locked, via DoorUnlocked scf / DoorLocked and-a) and
# whether the one-shot story flag was cleared. Proves both table entries:
# type 13 -> JeniOpenDoorF (compass, room 87), type 14 -> OpenBigBossDoor.
# Env: MGLOG, MGTYPE (13/14), MGFV (flag value 0/1 before the call).
set LOG "C:/DevMSX/mgshots/door.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set TYPE 13
if {[info exists ::env(MGTYPE)]} { set TYPE $::env(MGTYPE) }
set FV 1
if {[info exists ::env(MGFV)]} { set FV $::env(MGFV) }
file delete $LOG
proc report {} {
  global TYPE FV LOG
  set f [open $LOG a]
  puts $f "type=$TYPE fv=$FV carry=[expr {[reg F] & 1}] jopen=[debug read memory 0xc663] bigboss=[debug read memory 0xc610]"
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
  global TYPE FV
  debug write memory 0xc663 0
  debug write memory 0xc610 0
  if {$TYPE == 13} { debug write memory 0xc663 $FV }
  if {$TYPE == 14} { debug write memory 0xc610 $FV }
  debug write memory 0x6000 1			;# page opendoor's segment into 0x6000-0x7FFF
  debug set_bp 0xe010 {} { report }
  reg A $TYPE
  reg BC 0xc000
  set sp [expr {[reg SP] - 2}]
  reg SP $sp
  debug write memory $sp 0x10
  debug write memory [expr {$sp+1}] 0xe0
  reg PC 0x79c0
}
after time 45.0 { global TYPE FV LOG; set f [open $LOG a]; puts $f "type=$TYPE fv=$FV TIMEOUT"; close $f; exit }
