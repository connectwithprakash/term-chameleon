# Research: iTerm2 Integration

## Official surfaces

### Dynamic Profiles

Official docs: <https://iterm2.com/documentation-dynamic-profiles.html>

Dynamic Profiles are JSON/XML/plist profile files stored outside normal preferences:

```text
~/Library/Application Support/iTerm2/DynamicProfiles/
```

They require at least `Guid` and `Name`. They are appropriate for durable presets, dotfiles-friendly profile generation, and installable profile templates.

Uncertainty: the docs say runtime changes are picked up, but every setting's behavior on already-running sessions still needs hands-on verification.

### Python API

Docs:

- <https://iterm2.com/python-api/index.html>
- <https://iterm2.com/python-api/profile.html>
- <https://iterm2.com/python-api/color.html>
- <https://iterm2.com/python-api/tutorial/running.html>
- <https://iterm2.com/python-api/tutorial/daemons.html>

The Python API is the best candidate for live adaptive behavior. Official examples show session-local profile mutation via `LocalWriteOnlyProfile` and `session.async_set_profile_properties`, which avoids permanently rewriting user profiles.

Relevant examples:

- Set tab color: <https://iterm2.com/python-api/examples/settabcolor.html>
- Increase font size: <https://iterm2.com/python-api/examples/increase_font_size.html>
- Theme change color presets: <https://iterm2.com/python-api/examples/theme.html>
- Per-host colors: <https://iterm2.com/python-api/examples/colorhost.html>

### AutoLaunch scripts

Python AutoLaunch scripts live under:

```text
~/Library/Application Support/iTerm2/Scripts/AutoLaunch/
```

Long-running AutoLaunch daemons are officially supported by the Python API docs.

### AppleScript

Official docs: <https://iterm2.com/documentation-scripting.html>

Useful for window/tab/profile orchestration, but likely secondary to the Python API for adaptive behavior.

### Escape sequences / OSC

Official docs: <https://iterm2.com/documentation-escape-codes.html>

iTerm2 supports proprietary OSC `1337` commands and xterm-style color controls. OSC is useful as a fallback/live-session pathway but is fragmented across terminals and tmux.

## iTerm2 built-in contrast features

Official colors docs: <https://iterm2.com/documentation-preferences-profiles-colors.html>

iTerm2 includes `Minimum Contrast`, context-aware cursor color, bold color, ANSI colors, selection colors, and faint text opacity. Term Chameleon should supplement these rather than duplicate them blindly.

## Recommended iTerm2 architecture

1. Dynamic Profiles for durable presets.
2. Python AutoLaunch daemon for live iTerm2 integration.
3. Session-local mutations via `LocalWriteOnlyProfile` for dynamic behavior.
4. OSC as optional/fallback.
5. Avoid direct plist mutation as primary mechanism.

## Validation tasks

- Map Dynamic Profile keys to Python API setters.
- Verify which properties update live.
- Verify `Minimum Contrast`, transparency, blur, and ANSI color mutation through Python API.
- Verify interactions with existing sessions and Automatic Profile Switching.
