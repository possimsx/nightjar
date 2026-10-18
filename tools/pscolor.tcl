# Forced-call verification of the per-tileset ElectricColorSlot lookup.
# Craft a fake POWER_SWITCH actor (ANIM_CNT=0, BRIGHT=4, BRIGHT_DELTA=1), set
# CurrentTileSet, page seg3 (PowerSwitchLogic) into 0xA000, and force-call
# PowerSwitchLogic (0xA244). It should SetPaletteColor on slot = ElectricColorSlot
# [tileset]: tileset 0 -> slot 9, tileset 1/2 -> slot 5. We pre-zero slots 5 & 9
# and see which one the routine writes.
set LOG "C:/DevMSX/mgshots/pscolor.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set TS 1
if {[info exists ::env(MGTS)]} { set TS $::env(MGTS) }
file delete $LOG
proc pal {n} { return [format "%02x%02x" [debug read {VDP palette} [expr {$n*2}]] [debug read {VDP palette} [expr {$n*2+1}]]] }
proc report {} {
  global LOG TS
  set f [open $LOG a]
  puts $f "TS=$TS slot5=[pal 5] slot9=[pal 9] BRIGHT=[debug read memory 0xe013] (expect: TS0->slot9 set, TS1/2->slot5 set)"
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
  global TS
  # sentinel: zero palette slots 5 and 9
  foreach b {10 11 18 19} { debug write {VDP palette} $b 0 }
  # fake actor @0xe000: ANIM_CNT(+12)=0, BRIGHT(+19)=4, BRIGHT_DELTA(+20)=1
  debug write memory 0xe00c 0
  debug write memory 0xe013 4
  debug write memory 0xe014 1
  debug write memory 0xc157 $TS            ;# CurrentTileSet
  debug write memory 0xa000 3              ;# page seg3 into 0xA000 (PowerSwitchLogic)
  debug set_bp 0xe100 {} { report }
  reg IX 0xe000
  set sp [expr {[reg SP] - 2}]; reg SP $sp
  debug write memory $sp 0x00
  debug write memory [expr {$sp+1}] 0xe1
  reg PC 0xa244
}
after time 44.0 { global LOG TS; set f [open $LOG a]; puts $f "TS=$TS TIMEOUT"; close $f; exit }
