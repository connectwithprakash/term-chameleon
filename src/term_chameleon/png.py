from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .color import Color
from .images import RasterImage

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png(path: str | Path) -> RasterImage:
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    chunks = _chunks(data[len(PNG_SIGNATURE) :])
    width = height = color_type = bit_depth = interlace = None
    idat_parts: list[bytes] = []
    for chunk_type, payload in chunks:
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
        elif chunk_type == b"IDAT":
            idat_parts.append(payload)
        elif chunk_type == b"IEND":
            break
    if (
        width is None
        or height is None
        or color_type is None
        or bit_depth is None
        or interlace is None
    ):
        raise ValueError("PNG missing IHDR")
    if bit_depth != 8:
        raise ValueError(f"only 8-bit PNG files are supported, got bit depth {bit_depth}")
    if interlace != 0:
        raise ValueError("interlaced PNG files are not supported")
    channels = _channels_for_color_type(color_type)
    raw = zlib.decompress(b"".join(idat_parts))
    stride = width * channels
    rows = _unfilter_rows(raw, width=width, height=height, channels=channels)
    if len(rows) != height * stride:
        raise ValueError("decoded PNG has unexpected size")
    pixels = []
    for i in range(0, len(rows), channels):
        if color_type == 0:
            gray = rows[i]
            pixels.append(Color(gray / 255, gray / 255, gray / 255))
        elif color_type == 2:
            pixels.append(Color(rows[i] / 255, rows[i + 1] / 255, rows[i + 2] / 255))
        elif color_type == 4:
            gray = rows[i]
            pixels.append(Color(gray / 255, gray / 255, gray / 255, rows[i + 1] / 255))
        elif color_type == 6:
            pixels.append(
                Color(rows[i] / 255, rows[i + 1] / 255, rows[i + 2] / 255, rows[i + 3] / 255)
            )
    return RasterImage(width, height, tuple(pixels))


def _chunks(data: bytes):
    offset = 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        crc_end = end + 4
        if crc_end > len(data):
            raise ValueError("truncated PNG chunk")
        yield chunk_type, data[start:end]
        offset = crc_end


def _channels_for_color_type(color_type: int) -> int:
    if color_type == 0:
        return 1
    if color_type == 2:
        return 3
    if color_type == 4:
        return 2
    if color_type == 6:
        return 4
    raise ValueError(f"unsupported PNG color type {color_type}")


def _unfilter_rows(raw: bytes, *, width: int, height: int, channels: int) -> bytes:
    stride = width * channels
    result = bytearray()
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        if offset >= len(raw):
            raise ValueError("truncated PNG scanline")
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + stride])
        offset += stride
        if len(row) != stride:
            raise ValueError("truncated PNG row")
        _unfilter_row(row, prev, filter_type, channels)
        result.extend(row)
        prev = row
    return bytes(result)


def _unfilter_row(row: bytearray, prev: bytearray, filter_type: int, bpp: int) -> None:
    for i, value in enumerate(row):
        left = row[i - bpp] if i >= bpp else 0
        up = prev[i]
        up_left = prev[i - bpp] if i >= bpp else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = _paeth(left, up, up_left)
        else:
            raise ValueError(f"unsupported PNG filter type {filter_type}")
        row[i] = (value + predictor) & 0xFF


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c
