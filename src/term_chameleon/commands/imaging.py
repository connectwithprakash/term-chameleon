from __future__ import annotations

import sys
from pathlib import Path

from ..background_html import open_file, write_background_html
from ..images import Region
from ..pixel_contrast import write_contrast_report
from ..screenshot import probe_screenshot
from ..screenshot_test import run_screenshot_test
from ..terminal_pattern import write_pattern_bundle
from ..text_contrast import write_text_contrast_report
from ..visual import write_visual_report


def visual_test(profile: Path, output_dir: Path) -> int:
    json_path, md_path, checks = write_visual_report(profile, output_dir)
    failed = [c for c in checks if not c.passed]
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Checks: {len(checks)} total, {len(failed)} failed")
    if failed:
        for c in failed[:10]:
            print(f"[fail] {c.background}/{c.style}: {c.contrast:.2f}:1 < {c.threshold:.1f}:1")
        return 1
    print("[ok] visual contrast simulation passed")
    return 0


def screenshot_probe(*, capture: bool, output: Path) -> int:
    result = probe_screenshot(output, capture=capture)
    print(result.message)
    if result.output_path is not None:
        print(f"output: {result.output_path}")
    if not result.available:
        return 1
    if capture and not result.captured:
        return 1
    return 0


def screenshot_test(*, output_dir: Path, capture: bool, width: int, height: int) -> int:
    report = run_screenshot_test(output_dir, capture=capture, width=width, height=height)
    print(f"Wrote: {report.output_dir / 'report.json'}")
    print(f"Wrote: {report.output_dir / 'report.md'}")
    print(f"Backgrounds: {len(report.backgrounds)}")
    for artifact in report.backgrounds:
        print(
            f"- {artifact.name}: lum={artifact.stats.average_luminance:.3f} "
            f"var={artifact.stats.luminance_variance:.3f} "
            f"risk={artifact.risk} mode={artifact.suggested_mode}"
        )
    if report.screenshot is not None:
        print(report.screenshot.message)
        if report.screenshot_stats is not None:
            print(
                f"Screenshot stats: lum={report.screenshot_stats.average_luminance:.3f} "
                f"var={report.screenshot_stats.luminance_variance:.3f}"
            )
        if not report.screenshot.captured:
            return 1
    print("[ok] screenshot-test foundation passed")
    return 0


def screenshot_contrast(
    *, image: Path, output_dir: Path, region: str | None, threshold: float, percentile: float
) -> int:
    json_path, md_path, estimate = write_contrast_report(
        image,
        output_dir,
        region=Region.parse(region) if region else None,
        threshold=threshold,
        percentile=percentile,
    )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Dark cluster: {estimate.dark_color}")
    print(f"Light cluster: {estimate.light_color}")
    print(f"Estimated contrast: {estimate.contrast:.2f}:1")
    print("[ok] screenshot contrast estimate passed" if estimate.passed else "[fail] low contrast")
    return 0 if estimate.passed else 1


def screenshot_text_contrast(
    *,
    image: Path,
    output_dir: Path,
    region: str | None,
    threshold: float,
    min_row_delta: float,
    glyph_delta: float,
) -> int:
    json_path, md_path, estimate = write_text_contrast_report(
        image,
        output_dir,
        region=Region.parse(region) if region else None,
        threshold=threshold,
        min_row_delta=min_row_delta,
        glyph_delta=glyph_delta,
    )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Detected row bands: {len(estimate.bands)}")
    print(f"Foreground estimate: {estimate.foreground_color}")
    print(f"Background estimate: {estimate.background_color}")
    print(f"Estimated contrast: {estimate.contrast:.2f}:1")
    print("[ok] text contrast estimate passed" if estimate.passed else "[fail] low text contrast")
    return 0 if estimate.passed else 1


def background_html(*, output_dir: Path, open_browser: bool) -> int:
    artifacts = write_background_html(output_dir)
    for artifact in artifacts:
        print(f"Wrote: {artifact.path}")
    if open_browser:
        index = next(artifact.path for artifact in artifacts if artifact.name == "index")
        completed = open_file(index)
        if completed.returncode != 0:
            message = completed.stderr or completed.stdout or "open failed"
            print(f"error: {message.strip()}", file=sys.stderr)
            return 1
        print(f"Opened: {index}")
    print("[ok] generated controlled HTML backgrounds")
    return 0


def pattern_script(*, output_dir: Path) -> int:
    pattern, script = write_pattern_bundle(output_dir)
    print(f"Wrote: {pattern}")
    print(f"Wrote: {script}")
    print("[ok] generated ANSI terminal pattern artifacts")
    return 0
