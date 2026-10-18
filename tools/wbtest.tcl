# WORLDBANK A/B verification (docs/LIMITS-PLAN.md Phase C1).
# Boots, climbs the dock ladder 121->0->1 and dumps room/actor/item RAM at
# fixed emu-times. Run once on the flag-OFF ROM and once on the flag-ON ROM;
# identical logs = the world-bank relocation is behaviour-neutral.
# Log file name comes from env MGLOG (default wb.txt).
set LOG "C:/DevMSX/mgshots/wb.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
file delete $LOG
proc lg {msg} { global LOG; set f [open $LOG a]; puts $f $msg; close $f }
proc dump {tag} {
  set ids ""
  for {set i 0} {$i<16} {incr i} { append ids " [debug read memory [expr {0xd000 + $i*0x80}]]" }
  set items ""
  for {set i 0} {$i<12} {incr i} { append items " [debug read memory [expr {0xc5d0 + $i}]]" }
  set radio "[debug read memory 0xc87f]:"
  for {set i 0} {$i<8} {incr i} { append radio " [debug read memory [expr {0xc880 + $i}]]" }
  set doors "[debug read memory 0xc4ff]:"
  for {set i 0} {$i<16} {incr i} { append doors " [debug read memory [expr {0xc500 + $i}]]" }
  set ck 0
  for {set i 0} {$i<0x500} {incr i} { set ck [expr {($ck + [debug read memory [expr {0xe000 + $i}]] * ($i+1)) & 0xFFFFFF}] }
  set shots ""
  for {set i 0} {$i<16} {incr i} { append shots " [debug read memory [expr {0xc860 + $i}]]" }
  lg "$tag room=[debug read memory 0xc130] map=$ck shots=$shots ids=$ids items=$items radio=$radio doors=$doors"
}
set throttle off
# title + intro radio call: mash SPACE/RETURN
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 40.0 { dump T40 }
# spatial replay (EMU_TCL 's' recipe): enter room 5 from room 4 heading N.
# Poking Room bypasses SetRoomPal, so also refresh the WORLDBANK CurRoomConns
# cache (0xF0FB, room 4 row N=5 S=255 W=0 E=8; harmless unused RAM when off).
after time 41.0 { debug write memory 0xc180 0; debug write memory 0xc4fc 0
  debug write memory 0xc184 128; debug write memory 0xc182 96
  debug write memory 0xf0fb 5; debug write memory 0xf0fc 255
  debug write memory 0xf0fd 0; debug write memory 0xf0fe 8
  debug write memory 0xc130 4; debug write memory 0xc133 1; debug write memory 0xc151 1 }
after time 43.0 { dump T43 }
# two walk-offs driven by the ENGINE-FILLED conn cache (no cache poke):
# room 5 --W(3)--> room 1 (3 guards), then room 1 --E(4)--> room 5
after time 43.5 { debug write memory 0xc133 3; debug write memory 0xc151 1 }
after time 45.0 { dump T45 }
after time 45.5 { debug write memory 0xc133 4; debug write memory 0xc151 1 }
after time 47.0 { dump T47 }
# door replay (EMU_TCL 'd' recipe): open + enter door 101 -> room 126 (ration)
after time 47.5 { debug write memory 0xc4b4 0
  debug write memory 0xc4fc 101; debug write memory 0xc133 0; debug write memory 0xc151 1 }
after time 49.5 { dump T49; lg "DONE" }
after time 50.5 { exit }
