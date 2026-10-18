set throttle off
puts "NIGHTJAR verify script running"
after time 3  {screenshot -raw C:/DevMSX/mgshots/t03.png}
after time 6  {screenshot -raw C:/DevMSX/mgshots/t06.png}
after time 9  {screenshot -raw C:/DevMSX/mgshots/t09.png}
after time 12 {screenshot -raw C:/DevMSX/mgshots/t12.png}
after time 13 {exit}
