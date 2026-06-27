from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

from .color import Color
from .contrast import contrast_ratio
from .images import RasterImage, Region, crop_image
from .screenshot_test import read_image_file


class TextContrastUnavailable(ValueError):
    """Raised when text-row contrast cannot be inferred from an image."""


@dataclass(frozen=True)
class TextRowBand:
    y: int
    height: int
    score: float
    glyph_pixels: int

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class TextContrastEstimate:
    image_path: str
    region: str | None
    bands: list[TextRowBand]
    foreground_color: str
    background_color: str
    foreground_luminance: float
    background_luminance: float
    contrast: float
    threshold: float
    passed: bool
    glyph_pixels: int
    background_pixels: int


def _mean_color(colors: list[Color]) -> Color:
    if not colors:
        raise ValueError("cannot average an empty color set")
    return Color(
        r=sum(color.r for color in colors) / len(colors),
        g=sum(color.g for color in colors) / len(colors),
        b=sum(color.b for color in colors) / len(colors),
    )


def _row_pixels(image: RasterImage, y: int) -> tuple[Color, ...]:
    start = y * image.width
    return image.pixels[start : start + image.width]


def _row_score(image: RasterImage, y: int) -> float:
    values = [pixel.relative_luminance() for pixel in _row_pixels(image, y)]
    return max(values) - min(values)


def _otsu_threshold(values: list[float]) -> float:
    """Compute Otsu's threshold for a list of luminance values."""
    if not values:
        return 0.5
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-6:
        return lo
    bins = 256
    hist = [0] * bins
    span = hi - lo
    for v in values:
        idx = min(bins - 1, int((v - lo) / span * bins))
        hist[idx] += 1
    total = len(values)
    best_var = -1.0
    best_t = lo
    w0 = 0
    sum0 = 0.0
    sum_all = sum(lo + (i + 0.5) / bins * span for i, c in enumerate(hist) for _ in range(c))
    for i in range(bins):
        w0 += hist[i]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        t_i = lo + (i + 0.5) / bins * span
        sum0 += t_i * hist[i]
        mean0 = sum0 / w0
        mean1 = (sum_all - sum0) / w1
        var_between = w0 * w1 * (mean0 - mean1) ** 2
        if var_between > best_var:
            best_var = var_between
            best_t = (mean0 + mean1) / 2
    return best_t


def detect_text_row_bands(
    image: RasterImage,
    *,
    min_row_delta: float = 0.12,
    merge_gap: int = 1,
    min_height: int = 1,
) -> list[TextRowBand]:
    if min_row_delta <= 0:
        raise ValueError("min_row_delta must be positive")
    active_rows = [(y, _row_score(image, y)) for y in range(image.height)]
    active_rows = [(y, score) for y, score in active_rows if score >= min_row_delta]
    if not active_rows:
        return []

    bands: list[TextRowBand] = []
    start = active_rows[0][0]
    last = start
    scores = [active_rows[0][1]]
    for y, score in active_rows[1:]:
        if y - last <= merge_gap + 1:
            last = y
            scores.append(score)
            continue
        if last - start + 1 >= min_height:
            bands.append(TextRowBand(start, last - start + 1, max(scores), 0))
        start = last = y
        scores = [score]
    if last - start + 1 >= min_height:
        bands.append(TextRowBand(start, last - start + 1, max(scores), 0))
    return bands


def estimate_text_contrast(
    image_path: str | Path,
    *,
    region: Region | None = None,
    threshold: float = 4.5,
    min_row_delta: float = 0.12,
    glyph_delta: float = 0.08,
) -> TextContrastEstimate:
    source = Path(image_path)
    image = read_image_file(source)
    if region is not None:
        image = crop_image(image, region)
    return estimate_raster_text_contrast(
        image,
        image_path=str(source),
        region=region,
        threshold=threshold,
        min_row_delta=min_row_delta,
        glyph_delta=glyph_delta,
    )


def estimate_raster_text_contrast(
    image: RasterImage,
    *,
    image_path: str = "<raster>",
    region: Region | None = None,
    threshold: float = 4.5,
    min_row_delta: float = 0.12,
    glyph_delta: float = 0.08,
    adaptive: bool = True,
) -> TextContrastEstimate:
    if glyph_delta <= 0:
        raise ValueError("glyph_delta must be positive")
    bands = detect_text_row_bands(image, min_row_delta=min_row_delta)
    if not bands:
        raise TextContrastUnavailable(
            "no text-like rows found; lower --min-row-delta or provide a tighter --region"
        )

    # Collect all band luminances for adaptive thresholding.
    band_pixel_lists: list[list[Color]] = []
    all_band_luminances: list[float] = []
    for band in bands:
        bp: list[Color] = []
        for y in range(band.y, band.bottom):
            bp.extend(_row_pixels(image, y))
        band_pixel_lists.append(bp)
        all_band_luminances.extend(p.relative_luminance() for p in bp)

    # Use Otsu adaptive threshold when available; fall back to fixed glyph_delta.
    if adaptive and all_band_luminances:
        adaptive_t = _otsu_threshold(all_band_luminances)

        # Split band pixels into dark and light clusters using the inter-class boundary,
        # with a glyph_delta margin that excludes uncertain transition pixels.
        # The minority cluster is the glyph (text); the majority is background.
        # Ties default to dark-as-glyph (dark text on light background).
        dark_count = sum(
            1
            for bp in band_pixel_lists
            for pixel in bp
            if pixel.relative_luminance() < adaptive_t - glyph_delta
        )
        light_count = sum(
            1
            for bp in band_pixel_lists
            for pixel in bp
            if pixel.relative_luminance() > adaptive_t + glyph_delta
        )
        if dark_count <= light_count:
            is_glyph: object = lambda lum: lum < adaptive_t - glyph_delta  # noqa: E731
        else:
            is_glyph = lambda lum: lum > adaptive_t + glyph_delta  # noqa: E731

        glyph_pixels: list[Color] = []
        background_pixels: list[Color] = []
        bands_with_counts: list[TextRowBand] = []
        for band, bp in zip(bands, band_pixel_lists, strict=True):
            glyph_count = 0
            for pixel in bp:
                lum = pixel.relative_luminance()
                if is_glyph(lum):
                    glyph_pixels.append(pixel)
                    glyph_count += 1
                else:
                    background_pixels.append(pixel)
            bands_with_counts.append(TextRowBand(band.y, band.height, band.score, glyph_count))
    else:
        bg_median = median(all_band_luminances) if all_band_luminances else 0.5

        def split_fn(lum: float) -> bool:
            return abs(lum - bg_median) >= glyph_delta

        glyph_pixels = []
        background_pixels = []
        bands_with_counts = []
        for band, bp in zip(bands, band_pixel_lists, strict=True):
            luminances = [pixel.relative_luminance() for pixel in bp]
            glyph_count = 0
            for pixel, lum in zip(bp, luminances, strict=True):
                if split_fn(lum):
                    glyph_pixels.append(pixel)
                    glyph_count += 1
                else:
                    background_pixels.append(pixel)
            bands_with_counts.append(TextRowBand(band.y, band.height, band.score, glyph_count))

    if not glyph_pixels:
        raise TextContrastUnavailable(
            "text-like rows were found, but no glyph pixels passed glyph_delta"
        )
    if not background_pixels:
        glyph_set = set(glyph_pixels)
        background_pixels = [pixel for pixel in image.pixels if pixel not in glyph_set]
    if not background_pixels:
        raise TextContrastUnavailable("could not identify background pixels")

    foreground = _mean_color(glyph_pixels)
    background = _mean_color(background_pixels)
    contrast = contrast_ratio(foreground, background)
    return TextContrastEstimate(
        image_path=image_path,
        region=str(region) if region is not None else None,
        bands=bands_with_counts,
        foreground_color=foreground.to_hex(),
        background_color=background.to_hex(),
        foreground_luminance=foreground.relative_luminance(),
        background_luminance=background.relative_luminance(),
        contrast=contrast,
        threshold=threshold,
        passed=contrast >= threshold,
        glyph_pixels=len(glyph_pixels),
        background_pixels=len(background_pixels),
    )


def write_text_contrast_report(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    region: Region | None = None,
    threshold: float = 4.5,
    min_row_delta: float = 0.12,
    glyph_delta: float = 0.08,
) -> tuple[Path, Path, TextContrastEstimate]:
    estimate = estimate_text_contrast(
        image_path,
        region=region,
        threshold=threshold,
        min_row_delta=min_row_delta,
        glyph_delta=glyph_delta,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "text-contrast-report.json"
    md_path = out / "text-contrast-report.md"
    json_path.write_text(json.dumps(asdict(estimate), indent=2) + "\n", encoding="utf-8")
    rows = [
        "# Term Chameleon Text Row Contrast Estimate",
        "",
        f"Image: `{estimate.image_path}`",
        f"Region: `{estimate.region or 'full image'}`",
        f"Detected row bands: `{len(estimate.bands)}`",
        (
            f"Foreground estimate: `{estimate.foreground_color}` "
            f"luminance={estimate.foreground_luminance:.3f}"
        ),
        (
            f"Background estimate: `{estimate.background_color}` "
            f"luminance={estimate.background_luminance:.3f}"
        ),
        f"Estimated contrast: {estimate.contrast:.2f}:1",
        f"Threshold: {estimate.threshold:.1f}:1",
        f"Result: {'PASS' if estimate.passed else 'FAIL'}",
        "",
        "| y | height | score | glyph pixels |",
        "|---:|---:|---:|---:|",
    ]
    for band in estimate.bands:
        rows.append(f"| {band.y} | {band.height} | {band.score:.3f} | {band.glyph_pixels} |")
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path, estimate
