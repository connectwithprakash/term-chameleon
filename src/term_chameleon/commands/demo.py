from __future__ import annotations

import time

from ..live_iterm import apply_preset_to_current_session
from ..presets import PRESETS

# Walk from the most transparent (dark backgrounds) to the most opaque /
# high-contrast (bright backgrounds), so a viewer sees the full adaptation range.
DEMO_SEQUENCE = ("dark-glass", "balanced", "bright-safe", "accessibility")

DEFAULT_HOLD_SECONDS = 2.5


def demo(
    *,
    presets: tuple[str, ...] = DEMO_SEQUENCE,
    hold: float = DEFAULT_HOLD_SECONDS,
    sleep=time.sleep,
) -> int:
    """Apply a representative range of readability presets to the live iTerm2 session
    in turn, holding between each so the recoloring is visible in the frontmost iTerm2
    window. (Runs the curated DEMO_SEQUENCE subset, not every preset.)

    This is a guided live walkthrough, not a screenshotter: macOS only lets a
    tool screenshot the active Space, so capturing the terminal reliably is the
    user's job (e.g. a QuickTime screen recording). Run this with the iTerm2
    window visible and watch the colors and transparency adapt; record it if you
    want a shareable clip.
    """
    unknown = [p for p in presets if p not in PRESETS]
    if unknown:
        raise ValueError(f"unknown preset(s): {', '.join(unknown)}")

    print("Watch your iTerm2 window. Applying a representative range of presets:")
    applied = 0
    for preset in presets:
        try:
            result = apply_preset_to_current_session(preset)
        except RuntimeError as exc:
            print(f"[fail] {preset}: {exc}")
            print("Need a live iTerm2 session (open iTerm2 and run this from it).")
            return 1
        applied += 1
        print(f"[ok] {preset}: {result.message}")
        if applied < len(presets):
            sleep(hold)

    print(f"Applied {applied} presets. The watcher picks between these automatically by")
    print("sampling the background; run `watch-live --yes` to see it adapt on its own.")
    return 0
