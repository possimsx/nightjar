# Per-world path index + checkpoint list test (docs/LIMITS-PLAN.md Phase D4).
# Requires the TEMPORARY world-1 test edits (see the D4 section of the plan):
#   data/world1/pathindex.asm   room 1 -> Paths_002 (world 0 uses Paths_000)
#   data/world1/checkpoints.asm extra pair [1,5] (not in the stock list)
# Flow: boot -> warp room 5 (w0) -> walk W into room 1 -> dump guards' path
# pointers (+17h/+18h) + saved-game room -> back E -> gateway to world 1 ->
# walk W into room 1 -> dump again -> back E -> gateway home -> walk W -> dump.
# PASS when: w1 pointers differ from w0 pointers (per-world index live), the
# save fires ONLY on the world-1 5->1 transition (GPB room becomes 1), and the
# final w0 re-entry shows stock pointers again.
set LOG "C:/DevMSX/mgshots/d4.txt"
file delete $LOG
proc lg {msg} { global LOG; set f [open $LOG a]; puts $f $msg; close $f }
proc dump {tag} {
  set ptrs ""
  for {set i 0} {$i<4} {incr i} {
    set base [expr {0xd000 + $i*0x80}]
    append ptrs " \[[debug read memory $base]:[debug read memory [expr {$base+0x17}]],[debug read memory [expr {$base+0x18}]]\]"
  }
  set gpb ""
  for {set a 0xc9fe} {$a <= 0xca06} {incr a} { append gpb " [debug read memory $a]" }
  lg "$tag room=[debug read memory 0xc130] ws=[debug read memory 0xf131] ptrs=$ptrs gpb=$gpb"
}
proc gate {} {
  for {set i 0} {$i < 8} {incr i} {
    set base [expr {0xc3d0 + $i*16}]
    if {[debug read memory $base] == 101} {
      debug write memory [expr {$base + 15}] 252
      debug write memory [expr {0xc450 + 101 - 1}] 0
      debug write memory 0xc4fc 101
      debug write memory 0xc133 0
      debug write memory 0xc151 1
      return
    }
  }
  lg "gate: door 101 NOT FOUND"
}
set throttle off
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
# warp: replay a room 4 -> N -> room 5 transition (wbtest recipe, conn cache poked)
after time 41.0 { debug write memory 0xc180 0; debug write memory 0xc4fc 0
  debug write memory 0xc184 128; debug write memory 0xc182 96
  debug write memory 0xf0fb 5; debug write memory 0xf0fc 255
  debug write memory 0xf0fd 0; debug write memory 0xf0fe 8
  debug write memory 0xc130 4; debug write memory 0xc133 1; debug write memory 0xc151 1 }
after time 43.0 { dump T43-w0-r5 }
after time 43.5 { debug write memory 0xc133 3; debug write memory 0xc151 1 }
after time 45.0 { dump T45-w0-r1 }
after time 45.5 { debug write memory 0xc133 4; debug write memory 0xc151 1 }
after time 47.0 { gate }
after time 48.5 { dump T48-w1-r5 }
after time 49.0 { debug write memory 0xc133 3; debug write memory 0xc151 1 }
after time 50.5 { dump T50-w1-r1 }
after time 51.0 { debug write memory 0xc133 4; debug write memory 0xc151 1 }
after time 52.5 { gate }
after time 54.0 { dump T54-w0-r5 }
after time 54.5 { debug write memory 0xc133 3; debug write memory 0xc151 1 }
after time 56.0 { dump T56-w0-r1; lg "DONE" }
after time 57.0 { exit }
