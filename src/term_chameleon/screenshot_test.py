from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .color import Color
from .images import (
    ImageStats,
    Region,
    checkerboard_image,
    crop_image,
    horizontal_gradient_image,
    image_stats,
    solid_image,
    write_ppm,
)
from .png import read_png
from .screenshot import ScreenshotResult, capture_screen, screencapture_path
from .watch import RISK_TO_MODE, Sample, classify_sample


@dataclass(frozen=True)
class BackgroundArtifact:
    name: str
    path: Path
    stats: ImageStats
    risk: str
    suggested_mode: str
    reason: str


@dataclass(frozen=True)
class ScreenshotTestReport:
    output_dir: Path
    backgrounds: list[BackgroundArtifact]
    screenshot: ScreenshotResult | None
    screenshot_stats: ImageStats | None = None


def generate_background_artifacts(
    output_dir: str | Path, *, width: int = 640, height: int = 360
) -> list[BackgroundArtifact]:
    out = Path(output_dir)
    background_dir = out / "backgrounds"
    specs = {
        "solid-dark": solid_image(width, height, Color.from_hex("#050814")),
        "solid-light": solid_image(width, height, Color.from_hex("#F8FAFC")),
        "mid-gray": solid_image(width, height, Color.from_hex("#808080")),
        "checkerboard": checkerboard_image(
            width,
            height,
            color_a=Color.from_hex("#050814"),
            color_b=Color.from_hex("#F8FAFC"),
            cell_size=32,
        ),
        "gradient": horizontal_gradient_image(
            width,
            height,
            left=Color.from_hex("#050814"),
            right=Color.from_hex("#F8FAFC"),
        ),
    }
    artifacts: list[BackgroundArtifact] = []
    for name, image in specs.items():
        path = write_ppm(background_dir / f"{name}.ppm", image)
        stats = image_stats(image)
        classification = classify_sample(Sample(stats.average_luminance, stats.luminance_variance))
        artifacts.append(
            BackgroundArtifact(
                name=name,
                path=path,
                stats=stats,
                risk=classification.risk,
                suggested_mode=RISK_TO_MODE[classification.risk],
                reason=classification.reason,
            )
        )
    return artifacts


def run_screenshot_test(
    output_dir: str | Path,
    *,
    capture: bool = False,
    width: int = 640,
    height: int = 360,
) -> ScreenshotTestReport:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = generate_background_artifacts(out, width=width, height=height)
    screenshot: ScreenshotResult | None = None
    screenshot_stats: ImageStats | None = None
    if capture:
        screenshot = capture_screen(out / "screen.png")
        if screenshot.captured and screenshot.output_path is not None:
            screenshot_stats = analyze_image_file(screenshot.output_path)
    report = ScreenshotTestReport(
        output_dir=out,
        backgrounds=artifacts,
        screenshot=screenshot,
        screenshot_stats=screenshot_stats,
    )
    write_report(report)
    return report


def analyze_image_file(
    path: str | Path, region: Region | None = None, *, max_pixels: int | None = None
) -> ImageStats:
    image = read_image_file(path)
    if region is not None:
        image = crop_image(image, region)
    return image_stats(image, max_pixels=max_pixels)


def read_image_file(path: str | Path):
    source = Path(path)
    if source.suffix.lower() == ".ppm":
        from .images import read_ppm

        return read_ppm(source)
    if source.suffix.lower() == ".png":
        return read_png(source)
    raise ValueError(f"unsupported image format for analysis: {source.suffix}")


def write_report(report: ScreenshotTestReport) -> tuple[Path, Path]:
    json_path = report.output_dir / "report.json"
    md_path = report.output_dir / "report.md"
    json_path.write_text(
        json.dumps(
            {
                "backgrounds": [
                    {
                        "name": artifact.name,
                        "path": str(artifact.path),
                        "stats": asdict(artifact.stats),
                        "risk": artifact.risk,
                        "suggested_mode": artifact.suggested_mode,
                        "reason": artifact.reason,
                    }
                    for artifact in report.backgrounds
                ],
                "screenshot": _screenshot_json(report.screenshot),
                "screenshot_stats": asdict(report.screenshot_stats)
                if report.screenshot_stats is not None
                else None,
                "screencapture_available": screencapture_path() is not None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [
        "# Term Chameleon Screenshot Test Foundation Report",
        "",
        "This report currently verifies controlled background artifact generation, "
        "luminance/variance classification, and optional macOS screenshot capture. "
        "It does not yet open iTerm2 or measure rendered text pixels.",
        "",
        "| Background | Avg lum | Variance | Risk | Suggested mode | Artifact |",
        "|---|---:|---:|---|---|---|",
    ]
    for artifact in report.backgrounds:
        rows.append(
            f"| {artifact.name} | {artifact.stats.average_luminance:.3f} | "
            f"{artifact.stats.luminance_variance:.3f} | {artifact.risk} | "
            f"{artifact.suggested_mode} | `{artifact.path.relative_to(report.output_dir)}` |"
        )
    if report.screenshot is not None:
        rows.extend(
            [
                "",
                "## Screenshot capture",
                "",
                f"- captured: `{report.screenshot.captured}`",
                f"- message: {report.screenshot.message}",
            ]
        )
        if report.screenshot_stats is not None:
            rows.extend(
                [
                    f"- average luminance: `{report.screenshot_stats.average_luminance:.3f}`",
                    f"- luminance variance: `{report.screenshot_stats.luminance_variance:.3f}`",
                    f"- min luminance: `{report.screenshot_stats.min_luminance:.3f}`",
                    f"- max luminance: `{report.screenshot_stats.max_luminance:.3f}`",
                ]
            )
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path


def _screenshot_json(result: ScreenshotResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "available": result.available,
        "captured": result.captured,
        "output_path": str(result.output_path) if result.output_path else None,
        "message": result.message,
        "returncode": result.returncode,
    }
