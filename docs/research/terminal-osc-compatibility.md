# Research: Terminal OSC Compatibility

## Portable baseline

Primary reference: xterm control sequences, <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html>

Important OSC sequences:

```text
OSC 4    set/query indexed palette colors
OSC 10   set/query default foreground
OSC 11   set/query default background
OSC 12   set/query cursor color
OSC 104  reset palette colors
OSC 110  reset foreground
OSC 111  reset background
OSC 112  reset cursor
```

Examples:

```bash
printf '\033]10;#E5EBF5\033\\'
printf '\033]11;#090C16\033\\'
printf '\033]4;0;#6B7280\033\\'
printf '\033]4;8;#9CA3AF\033\\'
```

## Terminal notes

### Ghostty

Docs:

- <https://ghostty.org/docs/vt/osc/4>
- <https://ghostty.org/docs/vt/osc/1x>
- <https://ghostty.org/docs/vt/osc/104>
- <https://ghostty.org/docs/vt/osc/11x>

Ghostty documents core support for OSC 4 and OSC 10/11/12 plus resets.

### Alacritty

Escape support: <https://alacritty.org/misc-alacritty-escapes.html>

Alacritty documents implemented support for OSC 4, 10, 11, 12, 104, 110, 111, and 112.

### Kitty

Docs:

- <https://sw.kovidgoyal.net/kitty/color-stack>
- <https://sw.kovidgoyal.net/kitty/remote-control/>

Kitty has xterm-style color controls, a Kitty-specific color stack, and remote control through `kitten @`.

### WezTerm

Docs:

- <https://wezterm.org/escape-sequences.html>
- <https://wezterm.org/config/lua/window/set_config_overrides.html>

WezTerm has escape-sequence support and rich Lua/runtime configuration overrides.

### tmux

Docs:

- <https://man7.org/linux/man-pages/man1/tmux.1.html>
- <https://github.com/tmux/tmux/wiki/FAQ>

Modern tmux supports passthrough with:

```tmux
set -g allow-passthrough on
```

tmux can swallow OSC sequences and query replies. Term Chameleon must detect `$TMUX`, wrap passthrough where possible, and avoid claiming live updates succeeded unless verified.

## Limitations

- OSC changes are runtime/session state, not persistent profile config.
- Truecolor application output is not recolored by palette changes.
- Query replies require robust timeout handling.
- tmux/screen/IDE terminals may block or filter sequences.
- Terminal-specific richer integrations should be adapter-based.
