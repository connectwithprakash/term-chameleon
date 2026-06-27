import struct
import zlib

import pytest

from term_chameleon.png import read_png


def _chunk(kind: bytes, payload: bytes) -> bytes:
    import zlib as _zlib

    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", _zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(width: int, height: int, color_type: int, rows: list[bytes]) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def test_read_png_truecolor(tmp_path):
    path = tmp_path / "two.png"
    path.write_bytes(_png(2, 1, 2, [bytes([0, 0, 0, 255, 255, 255])]))
    image = read_png(path)
    assert image.width == 2
    assert image.height == 1
    assert image.pixels[0].to_hex() == "#000000"
    assert image.pixels[1].to_hex() == "#FFFFFF"


def test_read_png_rgba(tmp_path):
    path = tmp_path / "rgba.png"
    path.write_bytes(_png(1, 1, 6, [bytes([255, 0, 0, 128])]))
    image = read_png(path)
    assert image.pixels[0].to_hex() == "#FF0000"
    assert round(image.pixels[0].a, 2) == 0.5


def test_read_png_truncated_ihdr_raises_value_error(tmp_path):
    """A PNG whose IHDR chunk length is not 13 must raise ValueError, not struct.error."""
    path = tmp_path / "short_ihdr.png"
    # Build a PNG with an IHDR whose declared payload is only 5 bytes (not 13).
    short_payload = b"\x00" * 5
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", short_payload))
    with pytest.raises(ValueError, match="IHDR"):
        read_png(path)


def test_read_png_truncated_ihdr_is_not_struct_error(tmp_path):
    """Confirm the raised exception is ValueError, not struct.error (regression guard)."""
    import struct as _struct

    path = tmp_path / "short_ihdr2.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", b"\x00" * 5))
    exc = None
    try:
        read_png(path)
    except Exception as e:
        exc = e
    assert exc is not None
    assert isinstance(exc, ValueError), f"expected ValueError, got {type(exc)}"
    assert not isinstance(exc, _struct.error), "must not propagate raw struct.error"


def test_read_png_corrupt_idat_raises_value_error(tmp_path):
    """A PNG with corrupt IDAT data must raise ValueError, not zlib.error."""
    path = tmp_path / "corrupt_idat.png"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    # IDAT payload is not valid zlib-compressed data.
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", b"not valid zlib data here")
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(ValueError, match="corrupt PNG image data"):
        read_png(path)


def test_read_png_corrupt_idat_is_not_zlib_error(tmp_path):
    """Confirm the raised exception is ValueError, not zlib.error (regression guard)."""
    path = tmp_path / "corrupt_idat2.png"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", b"not valid zlib data here")
        + _chunk(b"IEND", b"")
    )
    exc = None
    try:
        read_png(path)
    except Exception as e:
        exc = e
    assert exc is not None
    assert isinstance(exc, ValueError), f"expected ValueError, got {type(exc)}"
    assert not isinstance(exc, zlib.error), "must not propagate raw zlib.error"


# --- Dimension cap / decompression-bomb guard tests ---


def test_read_png_rejects_oversized_dimensions(tmp_path):
    """read_png raises ValueError when width*height exceeds MAX_PIXELS."""
    from term_chameleon.png import MAX_PIXELS

    # Build an IHDR whose declared dimensions would overflow MAX_PIXELS.
    # We never produce IDAT because the check fires before decompression.
    over_side = int(MAX_PIXELS**0.5) + 1  # e.g. 2001 for MAX_PIXELS=4_000_000
    ihdr = struct.pack(">IIBBBBB", over_side, over_side, 8, 2, 0, 0, 0)
    path = tmp_path / "bomb.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"\x00"))
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(ValueError, match="exceed"):
        read_png(path)


def test_read_png_dimension_cap_is_value_error_not_memory_error(tmp_path):
    """The dimension-cap rejection must surface as ValueError, not MemoryError."""
    from term_chameleon.png import MAX_PIXELS

    over_side = int(MAX_PIXELS**0.5) + 1
    ihdr = struct.pack(">IIBBBBB", over_side, over_side, 8, 2, 0, 0, 0)
    path = tmp_path / "bomb2.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"\x00"))
        + _chunk(b"IEND", b"")
    )
    exc = None
    try:
        read_png(path)
    except Exception as e:
        exc = e
    assert exc is not None
    assert isinstance(exc, ValueError), f"expected ValueError, got {type(exc)}"


def test_read_png_accepts_image_at_max_pixels_boundary(tmp_path):
    """An image exactly at MAX_PIXELS is accepted (boundary condition)."""
    from term_chameleon.png import MAX_PIXELS

    # Use a 1-row image whose width exactly equals MAX_PIXELS to hit the
    # boundary without over-allocating.  Truecolor (3 bytes/pixel).
    width = MAX_PIXELS
    height = 1
    row = bytes([0, 0, 0] * width)  # all-black
    path = tmp_path / "boundary.png"
    path.write_bytes(_png(width, height, 2, [row]))
    image = read_png(path)
    assert image.width == width
    assert image.height == height
    assert len(image.pixels) == MAX_PIXELS


def test_read_png_decompression_bomb_rejected_even_below_pixel_cap(tmp_path):
    """Decompression output exceeding the expected raw size is rejected."""
    # Build a 1×1 truecolor PNG whose IDAT decompresses to far more bytes than
    # the expected 1*(1+1*3)=4 raw bytes by padding the uncompressed stream.
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    # Oversized uncompressed payload: correct scanline + lots of extra zeros
    oversized = b"\x00\x00\x00\x00" + b"\x00" * 1000
    path = tmp_path / "oversize_idat.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(oversized))
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(ValueError, match="decompressed PNG data"):
        read_png(path)
