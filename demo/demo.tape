# Term Chameleon CLI demo — rendered with VHS (https://github.com/charmbracelet/vhs)
# Regenerate:  vhs demo/demo.tape   (from the repo root)

Output demo/demo.gif
Output demo/demo.mp4

Require term-chameleon

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 20
Set Width 1200
Set Height 760
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms
Set Margin 16
Set BorderRadius 10

# --- Hidden setup: clean prompt, no shell noise ---
Hide
Type "export PS1='$ ' && clear"
Enter
Sleep 500ms
Show

# --- 1. What terminal am I in? ---
Type "term-chameleon terminal-info"
Sleep 400ms
Enter
Sleep 2s

# --- 2. Diagnose a profile whose ANSI-black text vanishes ---
Type "term-chameleon doctor tests/fixtures/iterm/bad-ansi-black.json"
Sleep 400ms
Enter
Sleep 2.5s

# --- 3. Apply readable colors to this terminal, live, over OSC ---
Type "term-chameleon osc apply dark-glass --write"
Sleep 400ms
Enter
Sleep 1.5s

# --- 4. The dynamic engine: watch it pick a mode as the background changes ---
Type "# dark -> bright -> dark background:"
Enter
Type "term-chameleon watch-sim --stable 1 0.10 0.90 0.10"
Sleep 400ms
Enter
Sleep 3s

Type "# bright background -> bright-safe, dark -> dark-glass. Automatically."
Sleep 2.5s
Enter
