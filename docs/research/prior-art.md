# Research: Prior Art and Novelty

## Existing terminal contrast features

### iTerm2 Minimum Contrast

Docs: <https://iterm2.com/documentation-preferences-profiles-colors.html>

iTerm2 shifts text colors closer to black or white when text and background colors are too similar. It does not modify background colors.

### macOS Terminal automatic contrast tweaking

Discussion: <https://apple.stackexchange.com/questions/29487/is-it-possible-to-disable-terminals-automatic-tweaking-of-colors-in-lion>

Apple Terminal has historically applied automatic minimum contrast behavior to ANSI colors.

### Ghostty minimum contrast

Discussion: <https://github.com/ghostty-org/ghostty/discussions/3869>

Modern terminal emulators continue to add contrast correction.

## Transparency / blur prior art

- WezTerm macOS blur: <https://wezterm.org/config/lua/config/macos_window_background_blur.html>
- Warp opacity/readability request: <https://github.com/warpdotdev/Warp/issues/5335>
- Kitty opacity issue: <https://github.com/kovidgoyal/kitty/issues/6815>
- Alacritty transparent background colors issue: <https://github.com/alacritty/alacritty/issues/8031>
- Hyper dynamic transparency plugin: <https://github.com/magus/hyper-transparent-dynamic>

These validate the pain: users like translucent terminal aesthetics, but readability and color compositing can break.

## Web/UI contrast prior art

- Text over images: <https://www.nngroup.com/articles/text-over-images/>
- CSS backdrop-filter: <https://web.dev/articles/backdrop-filter>
- CSS contrasting text methods: <https://css-tricks.com/methods-contrasting-text-backgrounds>
- CSS contrast-color: <https://una.im/contrast-color>
- WCAG contrast minimum: <https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html>
- APCA/SAPC: <https://github.com/Myndex/SAPC-APCA>

Adaptive contrast is not new as a general UI idea.

## Novelty assessment

Not novel:

- Transparent terminals.
- Static opacity/blur settings.
- Minimum contrast sliders.
- Automatic black/white foreground selection.
- WCAG/APCA contrast algorithms.
- Text-over-image UI techniques.

Potentially novel and worth pursuing:

> A live background-aware contrast daemon for translucent terminal windows that samples or infers the actual visual environment behind the terminal and adapts palette, opacity, blur, and contrast with hysteresis.

The product should position itself as a contrast controller for translucent terminals, not as merely another terminal theme.
