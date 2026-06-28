"""Backdrop capture backend selection.

The watcher samples "what is behind the glass terminal" to decide how readable text
will be. Two backends, chosen at runtime by capability, never by a hard dependency:

- ``screencapture`` (default, always available): the macOS CLI grab. It captures the
  already-composited screen, so the terminal's own pixels pollute the sample — a usable
  but imperfect proxy for the backdrop.
- ``screencapturekit`` (opt-in, when ``pyobjc-framework-ScreenCaptureKit`` is importable
  AND actually permitted): can capture everything *except* the terminal window via an
  exclude filter, recovering the true pre-composite backdrop and a more accurate global
  decision.

The tool ships zero runtime dependencies; SCK is an optional extra. This module decides
which backend is usable and falls back transparently, so the watcher works everywhere and
is simply more accurate where SCK is available. On macOS Tahoe (26.x) a non-bundled CLI
can be denied Screen Recording (TCC -3801); the capability probe treats that as "SCK
unavailable" and falls back rather than failing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackdropCapability:
    backend: str  # "screencapturekit" | "screencapture"
    sck_importable: bool
    reason: str


def _sck_importable() -> bool:
    try:
        import ScreenCaptureKit  # type: ignore[import-not-found]  # noqa: F401
    except Exception:
        return False
    return True


def detect_backdrop_capability() -> BackdropCapability:
    """Report which backdrop backend the watcher will use, and why.

    Does not capture; only inspects what is importable. The screencapturekit backend is
    selected only when its framework is importable. Actual permission (TCC) is verified at
    capture time, where a failure falls back to screencapture.
    """
    if _sck_importable():
        return BackdropCapability(
            backend="screencapturekit",
            sck_importable=True,
            reason=(
                "ScreenCaptureKit available; will capture the backdrop "
                "excluding the terminal window"
            ),
        )
    return BackdropCapability(
        backend="screencapture",
        sck_importable=False,
        reason=(
            "ScreenCaptureKit not importable (install the 'sck' extra for true-backdrop "
            "capture); using the screencapture composite grab"
        ),
    )
