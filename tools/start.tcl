proc lr {tag} { set f [open C:/DevMSX/mgshots/rooms.txt a]; puts $f "$tag room=[debug read memory 0xc130]"; close $f }
proc shot {n} { screenshot -raw C:/DevMSX/mgshots/$n.png }
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 {shot dock_corners}
# centre + climb to verify 121->0->1 still works
after time 40.0 {debug write memory 0xc183 0; debug write memory 0xc184 128}
after time 40.3 {keymatrixdown 8 32}
set s 41.5
for {set i 0} {$i < 6} {incr i} { after time $s "lr u$i"; set s [expr {$s+1.1}] }
after time 48.5 {keymatrixup 8 32}
after time 49 {exit}
