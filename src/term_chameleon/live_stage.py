from __future__ import annotations

import json
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

from .adapt import decide_from_screen
from .background_html import BACKGROUND_CSS, write_background_html
from .images import Region
from .iterm_window import get_iterm_window_bounds
from .pixel_contrast import write_contrast_report
from .screenshot import capture_screen
from .terminal_pattern import write_pattern_bundle

DEFAULT_BROWSER_BOUNDS = "0,0,1470,956"
DEFAULT_ITERM_BOUNDS = "80,90,980,760"


@dataclass(frozen=True)
class LiveStageReport:
    output_dir: Path
    background: str
    background_file: str
    pattern_script: str
    dry_run: bool
    browser_script: str
    iterm_script: str
    browser_returncode: int | None
    browser_message: str | None
    iterm_returncode: int | None
    iterm_message: str | None
    screenshot_path: str | None
    screenshot_captured: bool | None
    iterm_region: str | None
    suggested_mode: str | None
    estimated_contrast: float | None
    contrast_passed: bool | None
    settle_delay: float


def _parse_bounds(bounds: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in bounds.split(",")]
    if len(parts) != 4:
        raise ValueError("bounds must be x,y,width,height")
    x, y, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("bounds width and height must be positive")
    return x, y, width, height


def _applescript_bounds(bounds: str) -> str:
    x, y, width, height = _parse_bounds(bounds)
    return f"{{{x}, {y}, {x + width}, {y + height}}}"


def _file_url(path: Path) -> str:
    return "file://" + quote(str(path.resolve()))


def browser_stage_script(
    background_file: str | Path, *, bounds: str = DEFAULT_BROWSER_BOUNDS
) -> str:
    url = _file_url(Path(background_file))
    return f'''tell application "Safari"
  activate
  open location "{url}"
  delay 0.5
  set bounds of front window to {_applescript_bounds(bounds)}
end tell
'''


def iterm_stage_script(pattern_script: str | Path, *, bounds: str = DEFAULT_ITERM_BOUNDS) -> str:
    command = f"TERM_CHAMELEON_PATTERN_WAIT=0 {shlex.quote(str(Path(pattern_script).resolve()))}"
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    return f'''tell application "iTerm2"
  activate
  set newWindow to (create window with default profile)
  delay 0.5
  set bounds of newWindow to {_applescript_bounds(bounds)}
  tell current session of newWindow
    write text "{escaped}"
  end tell
end tell
'''


def run_osascript(script: str, *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def run_live_stage(
    output_dir: str | Path,
    *,
    background: str = "solid-light",
    browser_bounds: str = DEFAULT_BROWSER_BOUNDS,
    iterm_bounds: str = DEFAULT_ITERM_BOUNDS,
    dry_run: bool = True,
    capture: bool = False,
    threshold: float = 4.5,
    settle_delay: float = 1.0,
) -> LiveStageReport:
    if background not in BACKGROUND_CSS:
        raise ValueError(
            f"unknown background {background!r}; choose one of {', '.join(BACKGROUND_CSS)}"
        )
    if settle_delay < 0:
        raise ValueError("settle_delay must be >= 0")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    backgrounds = write_background_html(out / "background-html")
    background_file = next(artifact.path for artifact in backgrounds if artifact.name == background)
    _pattern, pattern_script = write_pattern_bundle(out / "pattern")
    browser_script = browser_stage_script(background_file, bounds=browser_bounds)
    iterm_script = iterm_stage_script(pattern_script, bounds=iterm_bounds)

    browser_result: subprocess.CompletedProcess[str] | None = None
    iterm_result: subprocess.CompletedProcess[str] | None = None
    if not dry_run:
        browser_result = run_osascript(browser_script)
        if browser_result.returncode == 0:
            iterm_result = run_osascript(iterm_script)
            if iterm_result.returncode == 0 and capture and settle_delay > 0:
                time.sleep(settle_delay)

    screenshot_path: Path | None = None
    screenshot_captured: bool | None = None
    iterm_region: Region | None = None
    suggested_mode: str | None = None
    estimated_contrast: float | None = None
    contrast_passed: bool | None = None
    if capture:
        screenshot_path = out / "live-stage-screen.png"
        screenshot = capture_screen(screenshot_path)
        screenshot_captured = screenshot.captured
        if screenshot.captured:
            bounds_result = get_iterm_window_bounds()
            if bounds_result.available:
                iterm_region = bounds_result.region
            decision = decide_from_screen(screenshot_path, region=iterm_region)
            suggested_mode = decision.suggested_mode
            _json_path, _md_path, estimate = write_contrast_report(
                screenshot_path,
                out / "contrast",
                region=iterm_region,
                threshold=threshold,
            )
            estimated_contrast = estimate.contrast
            contrast_passed = estimate.passed

    report = LiveStageReport(
        output_dir=out,
        background=background,
        background_file=str(background_file),
        pattern_script=str(pattern_script),
        dry_run=dry_run,
        browser_script=browser_script,
        iterm_script=iterm_script,
        browser_returncode=browser_result.returncode if browser_result is not None else None,
        browser_message=_completed_message(browser_result),
        iterm_returncode=iterm_result.returncode if iterm_result is not None else None,
        iterm_message=_completed_message(iterm_result),
        screenshot_path=str(screenshot_path) if screenshot_path is not None else None,
        screenshot_captured=screenshot_captured,
        iterm_region=str(iterm_region) if iterm_region is not None else None,
        suggested_mode=suggested_mode,
        estimated_contrast=estimated_contrast,
        contrast_passed=contrast_passed,
        settle_delay=settle_delay,
    )
    write_live_stage_report(report)
    return report


def _completed_message(completed: subprocess.CompletedProcess[str] | None) -> str | None:
    if completed is None:
        return None
    return (completed.stderr or completed.stdout or "").strip()


def write_live_stage_report(report: LiveStageReport) -> tuple[Path, Path]:
    json_path = report.output_dir / "live-stage-report.json"
    md_path = report.output_dir / "live-stage-report.md"
    json_path.write_text(json.dumps(asdict(report), indent=2, default=str) + "\n", encoding="utf-8")
    rows = [
        "# Term Chameleon Live Stage Report",
        "",
        f"- background: `{report.background}`",
        f"- dry run: `{report.dry_run}`",
        f"- browser return code: `{report.browser_returncode}`",
        f"- iTerm2 return code: `{report.iterm_returncode}`",
        f"- screenshot captured: `{report.screenshot_captured}`",
        f"- iTerm2 region: `{report.iterm_region}`",
        f"- suggested mode: `{report.suggested_mode}`",
        f"- estimated contrast: `{report.estimated_contrast}`",
        f"- contrast passed: `{report.contrast_passed}`",
        f"- settle delay: `{report.settle_delay}`",
        "",
        "## Browser AppleScript",
        "",
        "```applescript",
        report.browser_script.strip(),
        "```",
        "",
        "## iTerm2 AppleScript",
        "",
        "```applescript",
        report.iterm_script.strip(),
        "```",
    ]
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path
