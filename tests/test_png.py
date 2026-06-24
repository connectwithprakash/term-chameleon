import struct
import zlib

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
