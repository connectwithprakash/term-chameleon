from __future__ import annotations

from pathlib import Path

from ..iterm_api import (
    live_adapter_script,
    live_adapter_setters,
    write_live_adapter_script,
)
from ..osc import reset_sequences, sequences_for_preset, shell_printf


def osc(action: str, preset: str, *, tmux: bool, shell: bool, write: bool = False) -> int:
    if write:
        from ..terminal import apply_osc_to_terminal

        apply_osc_to_terminal(preset, reset=(action == "reset"))
        return 0
    sequences = reset_sequences() if action == "reset" else sequences_for_preset(preset)
    if shell:
        print(shell_printf(sequences, tmux=tmux))
    else:
        for seq in sequences:
            rendered = seq.sequence
            if tmux:
                from ..osc import tmux_wrap

                rendered = tmux_wrap(rendered)
            print(f"# {seq.description}")
            print(rendered.encode("unicode_escape").decode("ascii"))
    return 0


def terminal_info(*, json_output: bool = False) -> int:
    from ..terminal import detect_terminal

    info = detect_terminal()
    if json_output:
        import json

        payload = {
            "name": info.name,
            "is_iterm2": info.is_iterm2,
            "is_kitty": info.is_kitty,
            "is_ghostty": info.is_ghostty,
            "is_alacritty": info.is_alacritty,
            "is_supported": info.is_supported,
            "supports_osc": info.supports_osc,
            "supports_live_session": info.supports_live_session,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Terminal: {info.name}")
        print(f"Supported: {info.is_supported}")
        print(f"OSC sequences: {info.supports_osc}")
        print(f"Live session mutation: {info.supports_live_session}")
        if info.is_iterm2:
            print("  Use: term-chameleon watch-live --yes")
        elif info.is_supported:
            print("  Use: term-chameleon osc apply --write")
    return 0


def backdrop_info(*, json_output: bool = False) -> int:
    """Report which backdrop-capture backend the watcher will use.

    screencapturekit (when the optional 'sck' extra is installed) captures the true
    backdrop behind the terminal; otherwise the built-in screencapture composite grab.
    """
    from ..backdrop import detect_backdrop_capability

    cap = detect_backdrop_capability()
    if json_output:
        import json

        print(
            json.dumps(
                {
                    "backend": cap.backend,
                    "sck_importable": cap.sck_importable,
                    "reason": cap.reason,
                },
                indent=2,
            )
        )
    else:
        print(f"Backdrop backend: {cap.backend}")
        print(f"ScreenCaptureKit available: {cap.sck_importable}")
        print(f"Reason: {cap.reason}")
        if not cap.sck_importable:
            print("  For true-backdrop capture: pip install 'term-chameleon[sck]'")
    return 0


def iterm_api_check() -> int:
    from .. import cli

    env = cli.check_environment()
    print(f"iTerm2 app installed: {'yes' if env.app_installed else 'no'}")
    print(f"iTerm2 Python package available: {'yes' if env.python_package_available else 'no'}")
    print(f"Python executable: {env.python_executable}")
    print("app paths checked:")
    for path in env.app_paths_checked:
        print(f"- {path}")
    print("required LocalWriteOnlyProfile setters:")
    for setter in live_adapter_setters():
        if not env.python_package_available:
            status = "skipped"
        else:
            status = "missing" if setter in env.missing_setters else "ok"
        print(f"- {setter}: {status}")
    if env.ready_for_live_probe:
        print("[ok] ready for live iTerm2 API probe")
        return 0
    if not env.python_package_available:
        print("[hint] install iTerm support with: uv sync --extra iterm")
    if env.missing_setters:
        print("[warn] installed iterm2 package is missing required setter(s)")
    print("[warn] live iTerm2 API probe is not ready on this Python environment")
    return 1


def iterm_live_script(preset: str, *, output: Path | None) -> int:
    content = live_adapter_script(preset_name=preset)
    compile(content, str(output or "<term-chameleon-iterm-live-script>"), "exec")
    if output is None:
        print(content)
    else:
        target = write_live_adapter_script(output, preset_name=preset)
        print(f"Wrote: {target}")
    print("[ok] generated iTerm2 live adapter script compiles")
    return 0


def iterm_connect_probe() -> int:
    from .. import cli

    result = cli.probe_iterm_connection()
    print(result.message)
    if result.connected:
        print("[ok] connected to live iTerm2 Python API")
        return 0
    print("[warn] could not connect to live iTerm2 Python API")
    print("[hint] start iTerm2 and enable Preferences > General > Magic > Python API")
    return 1


def iterm_window_bounds() -> int:
    from .. import cli

    result = cli.get_iterm_window_bounds()
    if result.available and result.region is not None:
        print(str(result.region))
        print("[ok] read iTerm2 window bounds")
        return 0
    print(result.message)
    print("[warn] could not read iTerm2 window bounds")
    print("[hint] grant Accessibility permission or pass --region x,y,width,height")
    return 1
