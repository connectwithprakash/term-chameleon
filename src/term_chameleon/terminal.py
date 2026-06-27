"""Terminal detection for cross-terminal support.

Detects which terminal emulator is running so Term Chameleon can use the
appropriate color-setting mechanism (OSC sequences work universally; live
session mutation is iTerm2-specific).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from .osc import reset_sequences, sequences_for_preset


@dataclass(frozen=True)
class TerminalInfo:
    name: str
    is_iterm2: bool
    is_kitty: bool
    is_ghostty: bool
    is_alacritty: bool
    is_supported: bool

    @property
    def supports_osc(self) -> bool:
        """All detected terminals support OSC color sequences."""
        return self.is_supported

    @property
    def supports_live_session(self) -> bool:
        """Only iTerm2 supports live session-local profile mutation."""
        return self.is_iterm2


def detect_terminal() -> TerminalInfo:
    """Detect the current terminal emulator from environment variables."""
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    term = os.environ.get("TERM", "").lower()
    ghostty_environ = os.environ.get("GHOSTTY_RESOURCES_DIR") is not None

    is_iterm2 = term_program == "iterm.app" or term_program == "iterm2"
    is_kitty = term_program == "kitty" or term == "xterm-kitty" or term.startswith("xterm-kitty-")
    is_ghostty = ghostty_environ or term_program == "ghostty"
    is_alacritty = term_program == "alacritty"

    name = "unknown"
    if is_iterm2:
        name = "iterm2"
    elif is_kitty:
        name = "kitty"
    elif is_ghostty:
        name = "ghostty"
    elif is_alacritty:
        name = "alacritty"

    is_supported = is_iterm2 or is_kitty or is_ghostty or is_alacritty

    return TerminalInfo(
        name=name,
        is_iterm2=is_iterm2,
        is_kitty=is_kitty,
        is_ghostty=is_ghostty,
        is_alacritty=is_alacritty,
        is_supported=is_supported,
    )


def apply_osc_to_terminal(preset_name: str, *, reset: bool = False) -> bool:
    """Apply OSC color sequences to the current terminal.

    This works universally across iTerm2, Kitty, Ghostty, and Alacritty.
    Returns True if sequences were written to stdout.
    Raises OSError if output to stdout fails.
    """
    seqs = reset_sequences() if reset else sequences_for_preset(preset_name)

    # Write raw escape sequences directly to stdout.
    payload = "".join(s.sequence for s in seqs)

    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
    except OSError as e:
        raise OSError(f"Failed to write OSC sequences to terminal: {e}") from e
    return True
