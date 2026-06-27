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
