# RoomFlags / RoomFlags2 verification (docs/HAZARD-FLAGS-PLAN.md).
# Boots, then warps Room to each key room and reads the two cached flag bytes
# CurRoomFlags (0xF0FA) and CurRoomFlags2 (0xC0F7), refilled by CacheRoomFlags on
# each room load. Checks the four laser/capture bits the engine gates on:
#   CurRoomFlags  bit5 = moving lasers   bit6 = laser-beam room   bit7 = short camera lasers
#   CurRoomFlags2 bit0 = capture trap
# Expected: 72 -> moving+laser; 24 -> laser; 111 -> short cam; 8 -> capture; 47 -> none.
set LOG "C:/DevMSX/mgshots/laser.txt"
file delete $LOG
proc lg {m} { global LOG; set f [open $LOG a]; puts $f $m; close $f }
proc bit {v n} { return [expr {($v & (1 << $n)) ? 1 : 0}] }
proc snap {tag mov las shc cap} {
  set room [debug read memory 0xc130]
  set crf  [debug read memory 0xf0fa]
  set crf2 [debug read memory 0xc0f7]
  set m [bit $crf 5]; set l [bit $crf 6]; set s [bit $crf 7]; set c [bit $crf2 0]
  set ok [expr {$m==$mov && $l==$las && $s==$shc && $c==$cap}]
  lg [format "%-5s room=%3d crf=0x%02x crf2=0x%02x  mov=%d/%d laser=%d/%d short=%d/%d cap=%d/%d  %s" \
      $tag $room $crf $crf2 $m $mov $l $las $s $shc $c $cap [expr {$ok ? "OK" : "FAIL"}]]
}
set throttle off
# --- boot: mash SPACE/RETURN through title + intro radio call ---
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 { snap BOOT 0 0 0 0 }
proc warp {r} {
  debug write memory 0xc182 96
  debug write memory 0xc184 128
  debug write memory 0xc130 $r
  debug write memory 0xc133 0
  debug write memory 0xc151 1
}
#                                    mov las shc cap
after time 40.0 { warp 72 }
after time 40.8 { snap R72  1 1 0 0 }
after time 41.2 { warp 24 }
after time 42.0 { snap R24  0 1 0 0 }
after time 42.4 { warp 47 }
after time 43.2 { snap R47  0 0 0 0 }
after time 43.6 { warp 111 }
after time 44.4 { snap R111 0 0 1 0 }
after time 44.8 { warp 8 }
after time 45.6 { snap R8   0 0 0 1 }
after time 46.0 { lg DONE; exit }
