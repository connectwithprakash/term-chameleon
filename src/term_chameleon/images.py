from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from .color import Color


@dataclass(frozen=True)
class RasterImage:
    width: int
    height: int
    pixels: tuple[Color, ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.pixels) != self.width * self.height:
            raise ValueError(f"expected {self.width * self.height} pixels, got {len(self.pixels)}")


@dataclass(frozen=True)
class ImageStats:
    average_luminance: float
    luminance_variance: float
    min_luminance: float
    max_luminance: float


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("region x/y must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("region width/height must be positive")

    @classmethod
    def parse(cls, raw: str) -> Region:
        parts = raw.split(",")
        if len(parts) != 4:
            raise ValueError("region must be x,y,width,height")
        try:
            x, y, width, height = (int(part.strip()) for part in parts)
        except ValueError as exc:
            raise ValueError("region values must be integers") from exc
        return cls(x, y, width, height)

    def clamp_to(self, image: RasterImage) -> Region:
        if self.x >= image.width or self.y >= image.height:
            raise ValueError(
                f"region origin {self.x},{self.y} is outside image {image.width}x{image.height}"
            )
        width = min(self.width, image.width - self.x)
        height = min(self.height, image.height - self.y)
        return Region(self.x, self.y, width, height)

    def __str__(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


def solid_image(width: int, height: int, color: Color) -> RasterImage:
    return RasterImage(width, height, tuple(color for _ in range(width * height)))


def checkerboard_image(
    width: int,
    height: int,
    *,
    color_a: Color,
    color_b: Color,
    cell_size: int = 32,
) -> RasterImage:
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    pixels = []
    for y in range(height):
        for x in range(width):
            use_a = ((x // cell_size) + (y // cell_size)) % 2 == 0
            pixels.append(color_a if use_a else color_b)
    return RasterImage(width, height, tuple(pixels))


def horizontal_gradient_image(width: int, height: int, *, left: Color, right: Color) -> RasterImage:
    pixels = []
    denom = max(1, width - 1)
    for _y in range(height):
        for x in range(width):
            t = x / denom
            pixels.append(
                Color(
                    left.r * (1 - t) + right.r * t,
                    left.g * (1 - t) + right.g * t,
                    left.b * (1 - t) + right.b * t,
                )
            )
    return RasterImage(width, height, tuple(pixels))


def image_stats(image: RasterImage, *, max_pixels: int | None = None) -> ImageStats:
    pixels = image.pixels
    if max_pixels is not None:
        if max_pixels <= 0:
            raise ValueError("max_pixels must be positive")
        if len(pixels) > max_pixels:
            sample_side = max(1, math.floor(math.sqrt(max_pixels)))
            step_x = max(1, math.ceil(image.width / sample_side))
            step_y = max(1, math.ceil(image.height / sample_side))
            pixels = tuple(
                image.pixels[y * image.width + x]
                for y in range(0, image.height, step_y)
                for x in range(0, image.width, step_x)
            )
    values = [pixel.relative_luminance() for pixel in pixels]
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return ImageStats(
        average_luminance=avg,
        luminance_variance=variance,
        min_luminance=min(values),
        max_luminance=max(values),
    )


def crop_image(image: RasterImage, region: Region) -> RasterImage:
    clamped = region.clamp_to(image)
    pixels = []
    for y in range(clamped.y, clamped.y + clamped.height):
        start = y * image.width + clamped.x
        end = start + clamped.width
        pixels.extend(image.pixels[start:end])
    return RasterImage(clamped.width, clamped.height, tuple(pixels))


def write_ppm(path: str | Path, image: RasterImage) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = f"P6\n{image.width} {image.height}\n255\n".encode("ascii")
    payload = bytearray()
    for pixel in image.pixels:
        payload.extend(_rgb_bytes(pixel))
    target.write_bytes(header + bytes(payload))
    return target


def read_ppm(path: str | Path) -> RasterImage:
    data = Path(path).read_bytes()
    tokens, offset = _read_ppm_header(data)
    if tokens[0] != b"P6":
        raise ValueError("only binary P6 PPM files are supported")
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if max_value != 255:
        raise ValueError("only 8-bit PPM files are supported")
    payload = data[offset:]
    expected = width * height * 3
    if len(payload) != expected:
        raise ValueError(f"expected {expected} bytes of image data, got {len(payload)}")
    pixels = []
    for i in range(0, len(payload), 3):
        pixels.append(Color(payload[i] / 255, payload[i + 1] / 255, payload[i + 2] / 255))
    return RasterImage(width, height, tuple(pixels))


def _rgb_bytes(color: Color) -> bytes:
    return bytes(
        (
            _clamp_byte(color.r),
            _clamp_byte(color.g),
            _clamp_byte(color.b),
        )
    )


def _clamp_byte(value: float) -> int:
    return max(0, min(255, math.floor(value * 255 + 0.5)))


def _read_ppm_header(data: bytes) -> tuple[list[bytes], int]:
    tokens: list[bytes] = []
    i = 0
    while len(tokens) < 4:
        while i < len(data) and data[i] in b" \t\r\n":
            i += 1
        if i >= len(data):
            raise ValueError("incomplete PPM header")
        if data[i] == ord("#"):
            while i < len(data) and data[i] not in b"\r\n":
                i += 1
            continue
        start = i
        while i < len(data) and data[i] not in b" \t\r\n":
            i += 1
        tokens.append(data[start:i])
    while i < len(data) and data[i] in b" \t\r\n":
        i += 1
    return tokens, i
