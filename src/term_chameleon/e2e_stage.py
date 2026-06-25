from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .background_html import write_background_html
from .screenshot_test import run_screenshot_test
from .terminal_pattern import write_pattern_bundle
from .visual import write_visual_report


@dataclass(frozen=True)
class E2EStageReport:
    output_dir: Path
    background_files: list[str]
    pattern_files: list[str]
    visual_report_json: str
    visual_report_md: str
    screenshot_report_json: str
    screenshot_report_md: str
    screenshot_captured: bool | None


def run_e2e_stage(
    profile_path: str | Path,
    output_dir: str | Path,
    *,
    capture: bool = False,
    width: int = 640,
    height: int = 360,
) -> E2EStageReport:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    backgrounds = write_background_html(out / "background-html")
    pattern, script = write_pattern_bundle(out / "pattern")
    visual_json, visual_md, _checks = write_visual_report(profile_path, out / "visual-test")
    screenshot_report = run_screenshot_test(
        out / "screenshot-test",
        capture=capture,
        width=width,
        height=height,
    )

    report = E2EStageReport(
        output_dir=out,
        background_files=[str(artifact.path) for artifact in backgrounds],
        pattern_files=[str(pattern), str(script)],
        visual_report_json=str(visual_json),
        visual_report_md=str(visual_md),
        screenshot_report_json=str(screenshot_report.output_dir / "report.json"),
        screenshot_report_md=str(screenshot_report.output_dir / "report.md"),
        screenshot_captured=screenshot_report.screenshot.captured
        if screenshot_report.screenshot is not None
        else None,
    )
    write_e2e_report(report)
    return report


def write_e2e_report(report: E2EStageReport) -> tuple[Path, Path]:
    json_path = report.output_dir / "e2e-stage-report.json"
    md_path = report.output_dir / "e2e-stage-report.md"
    json_path.write_text(json.dumps(asdict(report), indent=2, default=str) + "\n", encoding="utf-8")
    visual_rel = Path(report.visual_report_json).relative_to(report.output_dir)
    screenshot_rel = Path(report.screenshot_report_json).relative_to(report.output_dir)
    rows = [
        "# Term Chameleon E2E Stage Report",
        "",
        "This stage bundles deterministic visual checks, controlled background artifacts, "
        "ANSI pattern artifacts, and optional screenshot capture. It is the permission-light "
        "staging layer before live GUI staging.",
        "",
        f"- background files: `{len(report.background_files)}`",
        f"- pattern files: `{len(report.pattern_files)}`",
        f"- visual report: `{visual_rel}`",
        f"- screenshot report: `{screenshot_rel}`",
        f"- screenshot captured: `{report.screenshot_captured}`",
        "",
        "## Live GUI stage",
        "",
        "For controlled Safari+iTerm2 orchestration, run `term-chameleon live-stage --dry-run` "
        "to preview scripts or `term-chameleon live-stage --yes --capture` after granting "
        "macOS permissions.",
    ]
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path
