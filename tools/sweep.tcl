proc shot {n} { screenshot -raw C:/DevMSX/mgshots/$n.png }
# boot sweep
after time 2  {shot s02}
after time 5  {shot s05}
after time 8  {shot s08}
after time 11 {shot s11}
after time 14 {shot s14}
# tap SPACE a few times to pass title
after time 15   {keymatrixdown 8 1}
after time 15.3 {keymatrixup 8 1}
after time 16   {keymatrixdown 8 1}
after time 16.3 {keymatrixup 8 1}
after time 18 {shot s18}
after time 22 {shot s22}
after time 26 {shot s26}
after time 27 {exit}
