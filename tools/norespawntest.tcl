# Forced-call unit test for IsNoRespawnRoom (logic/norespawn.asm).
# Sets A = room, traps the routine's `ret`, reads the Z flag it returns.
# Expected with the stock table {216}:  A=216 -> Z=1 (no-respawn);  all else Z=0.
# Proves the shipped ASM interpreter matches tools/mgnorespawn.py's Phase-1 proof.
set LOG "C:/DevMSX/mgshots/nr.txt"
file delete $LOG
proc lg {m} { global LOG; set f [open $LOG a]; puts $f $m; close $f }
set throttle off

set ADDR 0x7d38                                 ;# IsNoRespawnRoom
set SENT 0xe010                                 ;# unused RAM to land on
set tests {216 215 217 100 0 240 214 218}
set idx 0
set bpid ""

proc setup_call {} {
  global ADDR SENT tests idx bpid
  set a [lindex $tests $idx]
  set sp [expr {[reg SP] - 2}] ; reg SP $sp      ;# push sentinel return (LE)
  debug write memory $sp [expr {$SENT & 0xff}]
  debug write memory [expr {$sp+1}] [expr {($SENT >> 8) & 0xff}]
  reg A $a
  set bpid [debug set_bp $SENT {} { report }]
  reg PC $ADDR
}

proc report {} {
  global tests idx bpid
  set a [lindex $tests $idx]
  set z [expr {([reg F] & 0x40) ? 1 : 0}]
  set exp [expr {$a == 216 ? 1 : 0}]
  lg [format "A=%3d  Z=%d  expect=%d  %s" $a $z $exp [expr {$z==$exp ? "OK" : "FAIL"}]]
  debug remove_bp $bpid
  incr idx
  if {$idx < [llength $tests]} { setup_call } else { lg DONE ; after realtime 0.3 exit }
}

after time 10 {
  set found -1
  for {set s 0} {$s < 16} {incr s} {
    debug write memory 0x6000 $s
    if {[debug read memory 0x7d38] == 229} { set found $s ; break }   ;# 229 = E5 push hl
  }
  lg "seg for 0x7d38 = $found  opcode=[debug read memory 0x7d38]"
  if {$found >= 0} { setup_call } else { lg "ROUTINE NOT MAPPED" ; after realtime 0.3 exit }
}
after time 25 { lg TIMEOUT ; exit }
