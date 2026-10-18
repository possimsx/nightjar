proc shot {n} { screenshot -raw C:/DevMSX/mgshots/$n.png }
after time 15   {keymatrixdown 8 1}
after time 15.4 {keymatrixup 8 1}
set t 18
for {set i 0} {$i < 16} {incr i} {
  after time $t "shot r[format %02d $i]"
  set t [expr {$t + 1.6}]
}
after time 46 {exit}
