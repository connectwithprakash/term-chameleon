from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .color import Color
from .contrast import contrast_ratio
from .images import RasterImage, Region, crop_image
from .screenshot_test import read_image_file


@dataclass(frozen=True)
class ContrastEstimate:
    image_path: str
    region: str | None
    dark_color: str
    light_color: str
    dark_luminance: float
    light_luminance: float
    contrast: float
    threshold: float
    passed: bool
    sampled_pixels: int


def _mean_color(colors: list[Color]) -> Color:
    if not colors:
        raise ValueError("cannot average an empty color set")
    return Color(
        r=sum(color.r for color in colors) / len(colors),
        g=sum(color.g for color in colors) / len(colors),
        b=sum(color.b for color in colors) / len(colors),
    )


def estimate_image_contrast(
    image_path: str | Path,
    *,
    region: Region | None = None,
    threshold: float = 4.5,
    percentile: float = 0.10,
) -> ContrastEstimate:
    if not 0 < percentile <= 0.5:
        raise ValueError("percentile must be > 0 and <= 0.5")
    source = Path(image_path)
    image = read_image_file(source)
    if region is not None:
        image = crop_image(image, region)
    return estimate_raster_contrast(
        image,
        image_path=str(source),
        region=region,
        threshold=threshold,
        percentile=percentile,
    )


def estimate_raster_contrast(
    image: RasterImage,
    *,
    image_path: str = "<raster>",
    region: Region | None = None,
    threshold: float = 4.5,
    percentile: float = 0.10,
) -> ContrastEstimate:
    pixels = sorted(image.pixels, key=lambda color: color.relative_luminance())
    if len(pixels) < 2:
        raise ValueError("contrast estimation needs at least two pixels")
    sample_size = max(1, min(round(len(pixels) * percentile), len(pixels) // 2))
    dark = _mean_color(pixels[:sample_size])
    light = _mean_color(pixels[-sample_size:])
    contrast = contrast_ratio(light, dark)
    return ContrastEstimate(
        image_path=image_path,
        region=str(region) if region is not None else None,
        dark_color=dark.to_hex(),
        light_color=light.to_hex(),
        dark_luminance=dark.relative_luminance(),
        light_luminance=light.relative_luminance(),
        contrast=contrast,
        threshold=threshold,
        passed=contrast >= threshold,
        sampled_pixels=len(pixels),
    )


def write_contrast_report(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    region: Region | None = None,
    threshold: float = 4.5,
    percentile: float = 0.10,
) -> tuple[Path, Path, ContrastEstimate]:
    estimate = estimate_image_contrast(
        image_path,
        region=region,
        threshold=threshold,
        percentile=percentile,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "contrast-report.json"
    md_path = out / "contrast-report.md"
    json_path.write_text(json.dumps(asdict(estimate), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Term Chameleon Screenshot Contrast Estimate",
                "",
                f"Image: `{estimate.image_path}`",
                f"Region: `{estimate.region or 'full image'}`",
                f"Dark cluster: `{estimate.dark_color}` luminance={estimate.dark_luminance:.3f}",
                f"Light cluster: `{estimate.light_color}` luminance={estimate.light_luminance:.3f}",
                f"Estimated contrast: {estimate.contrast:.2f}:1",
                f"Threshold: {estimate.threshold:.1f}:1",
                f"Result: {'PASS' if estimate.passed else 'FAIL'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, md_path, estimate
