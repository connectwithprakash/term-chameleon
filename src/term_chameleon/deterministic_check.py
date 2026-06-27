from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .color import Color
from .diagnostics import diagnose
from .e2e_stage import run_e2e_stage
from .images import RasterImage, write_ppm
from .install import profile_document
from .iterm_profile import dumps_document, load_profile
from .pixel_contrast import write_contrast_report
from .text_contrast import write_text_contrast_report
from .watch import ModeSelector, Sample


@dataclass(frozen=True)
class CheckStep:
    name: str
    passed: bool
    detail: str
    artifacts: list[str]


@dataclass(frozen=True)
class DeterministicCheckReport:
    output_dir: Path
    steps: list[CheckStep]

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


def run_deterministic_check(
    output_dir: str | Path, *, width: int = 96, height: int = 48
) -> DeterministicCheckReport:
    """Run permission-free Term Chameleon checks useful after package install."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    steps: list[CheckStep] = []

    profile_path = out / "generated-balanced-profile.json"
    profile_path.write_text(
        dumps_document(profile_document(name="Self-Test Adaptive Glass")), encoding="utf-8"
    )
    profile = load_profile(profile_path)
    diagnostics = diagnose(profile)
    failing = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "fail"]
    steps.append(
        CheckStep(
            name="generated-profile-doctor",
            passed=not failing,
            detail="generated balanced profile passes failure-level diagnostics"
            if not failing
            else ", ".join(diagnostic.code for diagnostic in failing),
            artifacts=[str(profile_path)],
        )
    )

    e2e = run_e2e_stage(profile_path, out / "e2e-stage", capture=False, width=width, height=height)
    e2e_artifacts = [
        str(e2e.output_dir / "e2e-stage-report.json"),
        str(e2e.output_dir / "e2e-stage-report.md"),
        e2e.visual_report_json,
        e2e.screenshot_report_json,
    ]
    steps.append(
        CheckStep(
            name="deterministic-e2e-stage",
            passed=e2e.passed,
            detail="background, ANSI pattern, visual, and screenshot-test artifacts generated"
            if e2e.passed
            else f"{e2e.visual_checks_failed} visual contrast check(s) failed",
            artifacts=e2e_artifacts,
        )
    )

    contrast_image = out / "contrast-fixture.ppm"
    _write_text_like_fixture(contrast_image)
    _pixel_json, _pixel_md, pixel = write_contrast_report(
        contrast_image,
        out / "screenshot-contrast",
        threshold=4.5,
    )
    steps.append(
        CheckStep(
            name="pixel-contrast",
            passed=pixel.passed,
            detail=f"estimated contrast {pixel.contrast:.2f}:1",
            artifacts=[str(_pixel_json), str(_pixel_md), str(contrast_image)],
        )
    )

    _text_json, _text_md, text = write_text_contrast_report(
        contrast_image,
        out / "screenshot-text-contrast",
        threshold=4.5,
        min_row_delta=0.2,
        glyph_delta=0.2,
    )
    steps.append(
        CheckStep(
            name="text-row-contrast",
            passed=text.passed and bool(text.bands),
            detail=f"detected {len(text.bands)} row band(s), contrast {text.contrast:.2f}:1",
            artifacts=[str(_text_json), str(_text_md)],
        )
    )

    selector = ModeSelector(stable_samples_required=2)
    sequence = [Sample(0.2, 0.0), Sample(0.2, 0.0), Sample(0.82, 0.0), Sample(0.82, 0.0)]
    observations = [selector.observe(sample) for sample in sequence]
    modes = [mode for mode, _classification, _switched in observations]
    switched_flags = [switched for _mode, _classification, switched in observations]
    expected_modes = ["balanced", "dark-glass", "dark-glass", "bright-safe"]
    expected_switches = [False, True, False, True]
    steps.append(
        CheckStep(
            name="watch-hysteresis",
            passed=modes == expected_modes and switched_flags == expected_switches,
            detail=(
                "modes "
                + " -> ".join(modes)
                + "; switches "
                + ",".join("yes" if switched else "no" for switched in switched_flags)
            ),
            artifacts=[],
        )
    )

    report = DeterministicCheckReport(output_dir=out, steps=steps)
    write_deterministic_check_report(report)
    return report


def write_deterministic_check_report(report: DeterministicCheckReport) -> tuple[Path, Path]:
    json_path = report.output_dir / "deterministic-check-report.json"
    md_path = report.output_dir / "deterministic-check-report.md"
    payload = {
        "output_dir": str(report.output_dir),
        "passed": report.passed,
        "steps": [asdict(step) for step in report.steps],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    rows = [
        "# Term Chameleon Deterministic Check",
        "",
        f"Overall passed: `{report.passed}`",
        "",
        "| Step | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for step in report.steps:
        rows.append(f"| `{step.name}` | {'pass' if step.passed else 'fail'} | {step.detail} |")
    rows.extend(
        [
            "",
            "## Artifacts",
            "",
        ]
    )
    for step in report.steps:
        if not step.artifacts:
            continue
        rows.append(f"### {step.name}")
        rows.append("")
        for artifact in step.artifacts:
            rows.append(f"- `{artifact}`")
        rows.append("")
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path


def _write_text_like_fixture(path: Path) -> None:
    bg = Color.from_hex("#000000")
    fg = Color.from_hex("#FFFFFF")
    pixels: list[Color] = []
    for y in range(24):
        for x in range(96):
            if 8 <= y <= 15 and 8 <= x <= 72 and (x % 8 in {1, 2, 3, 4, 5}):
                pixels.append(fg)
            else:
                pixels.append(bg)
    write_ppm(path, RasterImage(width=96, height=24, pixels=tuple(pixels)))
