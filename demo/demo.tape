# Term Chameleon CLI demo — rendered with VHS (https://github.com/charmbracelet/vhs)
# Regenerate:  vhs demo/demo.tape   (from the repo root, with term-chameleon on PATH)

Output demo/demo.gif
Output demo/demo.mp4

Require term-chameleon

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 20
Set Width 1200
Set Height 820
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms
Set Margin 16
Set BorderRadius 10

Hide
Type "export PS1='$ ' && clear"
Enter
Sleep 500ms
Show

# 1. Diagnose a profile whose ANSI-black text vanishes on glass
Type "term-chameleon doctor tests/fixtures/iterm/bad-ansi-black.json"
Sleep 400ms
Enter
Sleep 2.5s

# 2. Apply readable colors to this terminal, live, over OSC
Type "term-chameleon osc apply dark-glass --write"
Sleep 400ms
Enter
Sleep 1.2s

# 3. The dynamic engine: it picks a mode as the background changes
Type "# background dark -> bright -> dark, the watcher decides automatically:"
Enter
Type "term-chameleon watch-sim --stable 1 0.10 0.90 0.10"
Sleep 400ms
Enter
Sleep 2.8s

# 4. How it samples the backdrop (true-backdrop capture is an optional upgrade)
Type "term-chameleon backdrop-info"
Sleep 400ms
Enter
Sleep 2.2s
