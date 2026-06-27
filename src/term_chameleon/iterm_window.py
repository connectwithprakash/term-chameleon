from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .images import Region
from .png import read_png
from .screenshot import capture_screen


@dataclass(frozen=True)
class WindowBoundsResult:
    available: bool
    region: Region | None
    message: str


def get_iterm_window_bounds() -> WindowBoundsResult:
    """Return front iTerm2 window bounds in full-screenshot pixel coordinates."""
    raw = _raw_iterm_window_bounds_points()
    if not raw.available or raw.region is None:
        return raw
    try:
        return WindowBoundsResult(
            True,
            _points_region_to_screenshot_pixels(raw.region),
            f"{raw.message}; converted to screenshot pixels",
        )
    except Exception as exc:
        return WindowBoundsResult(False, None, f"could not convert iTerm2 bounds to pixels: {exc}")


def _raw_iterm_window_bounds_points() -> WindowBoundsResult:
    script = r"""
tell application "iTerm2"
  if (count of windows) < 1 then
    return "ERROR|iTerm2 has no windows"
  end if
  set b to bounds of window 1
  set leftEdge to item 1 of b as integer
  set topEdge to item 2 of b as integer
  set rightEdge to item 3 of b as integer
  set bottomEdge to item 4 of b as integer
  set widthValue to rightEdge - leftEdge
  set heightValue to bottomEdge - topEdge
  return "OK|" & leftEdge & "," & topEdge & "," & widthValue & "," & heightValue
end tell
"""
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return WindowBoundsResult(False, None, "timed out reading iTerm2 window bounds")
    raw = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return WindowBoundsResult(
            available=False,
            region=None,
            message=raw or "could not read iTerm2 bounds; use --region x,y,width,height",
        )
    if raw.startswith("OK|"):
        try:
            region = Region.parse(raw.removeprefix("OK|"))
        except ValueError as exc:
            # AppleScript returns negative left/top when the iTerm2 window is on a
            # secondary monitor placed to the left of, or above, the main display.
            # Region rejects negative x/y, so we surface a clear message instead of
            # propagating an uncaught ValueError out of get_iterm_window_bounds().
            return WindowBoundsResult(
                False,
                None,
                (
                    f"iTerm2 window has a negative screen origin ({raw.removeprefix('OK|')}); "
                    "it is likely on a secondary monitor — use --region x,y,width,height to "
                    f"specify the capture area explicitly ({exc})"
                ),
            )
        return WindowBoundsResult(True, region, raw)
    if raw.startswith("ERROR|"):
        return WindowBoundsResult(False, None, raw.removeprefix("ERROR|"))
    return WindowBoundsResult(False, None, raw or "unexpected iTerm2 bounds response")


def _desktop_bounds_points() -> tuple[int, int, int, int]:
    completed = subprocess.run(
        ["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    raw = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(raw or "could not read desktop bounds")
    try:
        parts = [int(part.strip()) for part in raw.split(",")]
    except ValueError as exc:
        raise RuntimeError(f"could not parse desktop bounds from Finder: {raw!r}") from exc
    if len(parts) != 4:
        raise RuntimeError(f"unexpected desktop bounds: {raw}")
    return parts[0], parts[1], parts[2], parts[3]


def _screenshot_size_pixels() -> tuple[int, int]:
    with tempfile.TemporaryDirectory(prefix="term-chameleon-bounds-") as tmp:
        path = Path(tmp) / "screen.png"
        result = capture_screen(path)
        if not result.captured or result.output_path is None:
            raise RuntimeError(result.message)
        image = read_png(result.output_path)
        return image.width, image.height


def _points_region_to_screenshot_pixels(region: Region) -> Region:
    left, top, right, bottom = _desktop_bounds_points()
    screenshot_width, screenshot_height = _screenshot_size_pixels()
    point_width = right - left
    point_height = bottom - top
    if point_width <= 0 or point_height <= 0:
        raise RuntimeError(f"invalid desktop bounds: {left},{top},{right},{bottom}")
    # screencapture -x (no -D flag) captures only the main display, but Finder
    # 'bounds of window of desktop' returns the union of ALL displays on a multi-
    # monitor setup (left/top can be negative, width/height span every screen).
    # Dividing screenshot pixels by the full-desktop point size yields wrong scale
    # factors and can map iTerm2 window coordinates outside the captured image.
    # Detect the mismatch: if the desktop origin is not (0, 0) a secondary display
    # extends to the left or above the main display, making the denominators
    # inconsistent.  Fail early with a clear message so callers can ask the user
    # for an explicit --region instead of silently producing a mis-scaled crop.
    if left != 0 or top != 0:
        raise RuntimeError(
            "multi-monitor layout detected (Finder desktop origin is "
            f"{left},{top}): screencapture captures only the main display but "
            "Finder desktop bounds span all displays, so window-to-pixel scaling "
            "would be incorrect — use --region x,y,width,height to specify the "
            "capture area explicitly"
        )
    scale_x = screenshot_width / point_width
    scale_y = screenshot_height / point_height
    x = round((region.x - left) * scale_x)
    y = round((region.y - top) * scale_y)
    width = round(region.width * scale_x)
    height = round(region.height * scale_y)
    return Region(max(0, x), max(0, y), max(1, width), max(1, height))
