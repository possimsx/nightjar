# Gateway round-trip test (docs/LIMITS-PLAN.md Phase D2).
# Boot -> warp to room 5 (world 0) -> poke the first door's DESTINATION byte
# in DoorsList RAM to the gateway sentinel 252 -> enter it. GatewayTable maps
# (room 5, 252) -> world 1 room 5, whose layout carries a marker byte, so the
# map checksum must CHANGE while the room number stays 5 and CurWorldSeg
# becomes WORLD_SEG+3. World 1's table maps (5,252) back to world 0 -> repeat
# the poke and return. Expected: ws 16 -> 19 -> 16, checksums A -> B -> A.
set LOG "C:/DevMSX/mgshots/gw.txt"
file delete $LOG
proc lg {msg} { global LOG; set f [open $LOG a]; puts $f $msg; close $f }
proc dump {tag} {
  set ck 0
  for {set i 0} {$i<0x500} {incr i} { set ck [expr {($ck + [debug read memory [expr {0xe000 + $i}]] * ($i+1)) & 0xFFFFFF}] }
  lg "$tag room=[debug read memory 0xc130] ws=[debug read memory 0xf131] map=$ck doors=[debug read memory 0xc4ff]"
}
proc gate {} {
  # find door id 101 in DoorsList (16B records; +0 ID, +15 dest) and poke its dest
  for {set i 0} {$i < 8} {incr i} {
    set base [expr {0xc3d0 + $i*16}]
    set id [debug read memory $base]
    if {$id == 101} {
      lg "gate: slot $i id $id dest[expr {$base+15}]"
      debug write memory [expr {$base + 15}] 252
      debug write memory [expr {0xc450 + $id - 1}] 0
      debug write memory 0xc4fc $id
      debug write memory 0xc133 0
      debug write memory 0xc151 1
      return
    }
  }
  lg "gate: door 101 NOT FOUND in DoorsList"
}
set ::hn 0
debug set_bp 0x9357 {} { if {[incr ::hn] <= 8} {
  lg "HOOK a=[reg A] room=[debug read memory 0xc130] c50f=[debug read memory 0xc50f]" } }
set throttle off
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 41.0 { debug write memory 0xc180 0; debug write memory 0xc4fc 0
  debug write memory 0xc184 128; debug write memory 0xc182 96
  debug write memory 0xf0fb 5; debug write memory 0xf0fc 255
  debug write memory 0xf0fd 0; debug write memory 0xf0fe 8
  debug write memory 0xc130 4; debug write memory 0xc133 1; debug write memory 0xc151 1 }
after time 43.0 { dump T43-w0 }
after time 43.5 { gate }
after time 45.5 { dump T45-w1 }
after time 46.0 { gate }
after time 48.0 { dump T48-w0; lg "DONE" }
after time 49.0 { exit }
