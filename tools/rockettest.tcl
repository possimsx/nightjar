# Rocket item-gate A/B verification (docs/CODEC-GATE-PLAN.md Phase 2, Table B).
# Boots, warps to the rocket-launcher room 185 (spatial 83->E->86, then door 73),
# and dumps ItemsInTheRoom. Run with JeniRocketF forced 0 and 1, on the OLD and
# NEW ROMs. Expected: flag 0 => no rocket (id 4); flag 1 => rocket present; and
# OLD == NEW for both (the cp-ROCKET_LAUNCHER -> GateItems refactor is neutral).
# Env: MGLOG (log file name), MGFLAG (JeniRocketF value 0/1).
set LOG "C:/DevMSX/mgshots/rk.txt"
if {[info exists ::env(MGLOG)]} { set LOG "C:/DevMSX/mgshots/$::env(MGLOG)" }
set FLAG 0
if {[info exists ::env(MGFLAG)]} { set FLAG $::env(MGFLAG) }
set FLAGADDR 0xc661
if {[info exists ::env(MGFLAGADDR)]} { set FLAGADDR $::env(MGFLAGADDR) }
file delete $LOG
proc lg {m} { global LOG; set f [open $LOG a]; puts $f $m; close $f }
proc items {} {
  set s ""
  for {set i 0} {$i < 3} {incr i} {
    set b [expr {0xc5d0 + $i*0x10}]
    append s [format " \[id%d y%d x%d\]" [debug read memory $b] \
      [debug read memory [expr {$b+2}]] [debug read memory [expr {$b+3}]]]
  }
  return $s
}
proc snap {tag} { lg "$tag room=[debug read memory 0xc130] gm=[debug read memory 0xc151] jeni=[debug read memory $::FLAGADDR] items:[items]" }
set throttle off
# --- boot: mash SPACE/RETURN through title + intro radio call ---
set t 13.5
for {set i 0} {$i < 38} {incr i} {
  after time $t "keymatrixdown 8 1"; after time [expr {$t+0.15}] "keymatrixup 8 1"
  after time [expr {$t+0.3}] "keymatrixdown 7 128"; after time [expr {$t+0.45}] "keymatrixup 7 128"
  set t [expr {$t + 0.65}]
}
after time 39.5 { snap BOOT }
after time 39.6 { global FLAG FLAGADDR; debug write memory $FLAGADDR $FLAG }
# --- stage 1: spatial warp 83 --E(4)--> 86 ---
after time 40.0 {
  debug write memory 0xc182 96
  debug write memory 0xc184 128
  debug write memory 0xc130 83
  debug write memory 0xc133 4
  debug write memory 0xc151 1
}
# --- stage 2: in room 86, open door 73 and enter it -> room 185 (poll + refire) ---
proc stage2 {} {
  global FLAG FLAGADDR
  set r [debug read memory 0xc130]
  if {$r == 86} {
    debug write memory $FLAGADDR $FLAG
    debug write memory 0xc498 0
    debug write memory 0xc4fc 73
    debug write memory 0xc133 0
    debug write memory 0xc151 1
  }
  if {$r != 185} { after realtime 0.3 stage2 }
}
after time 41.0 stage2
after time 44.0 { snap MID }
after time 47.0 { snap RESULT; lg DONE }
after time 48.0 { exit }
