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
    """Report whether the true-backdrop (ScreenCaptureKit) path is available.

    Does not capture; only inspects what is importable. NOTE: the watcher currently always
    uses the screencapture composite grab — the SCK exclude-terminal capture is a planned
    upgrade gated by the 'sck' extra (see docs/design-adaptive-readability.md). This reports
    readiness for that path, not that it is in use yet.
    """
    if _sck_importable():
        return BackdropCapability(
            backend="screencapture",
            sck_importable=True,
            reason=(
                "ScreenCaptureKit is importable; true-backdrop capture is not yet wired, so "
                "the watcher still uses the screencapture composite grab"
            ),
        )
    return BackdropCapability(
        backend="screencapture",
        sck_importable=False,
        reason=(
            "ScreenCaptureKit not importable (install the 'sck' extra to enable the planned "
            "true-backdrop capture); using the screencapture composite grab"
        ),
    )
