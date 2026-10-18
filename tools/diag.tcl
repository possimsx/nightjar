set f [open C:/DevMSX/mgshots/diag.txt w]
catch {puts $f "DEVICES: [machine_info device]"} e; puts $f "  err=$e"
after time 5 {
  foreach dev [machine_info device] {
    catch {puts $f "DEV \[$dev\]: [machine_info device $dev]"}
  }
  catch {puts $f "screen mode: [get_screen_mode]"} e2; puts $f "  smerr=$e2"
  flush $f; close $f; exit
}
