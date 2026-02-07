Output route_demo_light.gif
Set Theme "Gruvbox Light"
Set FontFamily "IosevkaTerm Nerd Font Mono"

Set Padding 16
Set BorderRadius 12
Set Margin 4
Set MarginFill "#FFFFFF"
Set WindowBar RingsRight

Set LetterSpacing 2
Set FontSize 18
Set Width 1100
Set Height 600

Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full"
Enter

Sleep 1.3s

Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple"
Enter

Sleep 2.3s

Type "metro config set preferences.route.compact true"
Enter
Sleep 300ms

Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full"
Enter

Sleep 1.3s

Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple"
Enter

Sleep 10s
