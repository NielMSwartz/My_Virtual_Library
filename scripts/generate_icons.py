"""Generate the Bookshelf PWA icons using only the Python standard library.

Run with: python scripts/generate_icons.py

The icons are checked into app/static/images/icons, so this script is only
needed if you want to change the artwork.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "images" / "icons"

SAGE = (120, 145, 123)  # #78917B
SAGE_DARK = (95, 122, 99)
CREAM = (247, 241, 230)
SAND = (217, 201, 180)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_rect_sd(px: float, py: float, cx: float, cy: float,
                   half_w: float, half_h: float, radius: float) -> float:
    """Signed distance to a rounded rectangle (negative inside)."""
    qx = abs(px - cx) - (half_w - radius)
    qy = abs(py - cy) - (half_h - radius)
    return ((max(qx, 0.0) ** 2 + max(qy, 0.0) ** 2) ** 0.5
            + min(max(qx, qy), 0.0) - radius)


def _coverage(signed_distance: float, antialias: float = 1.15) -> float:
    return _clamp(0.5 - signed_distance / antialias)


def _blend(dst: tuple[int, int, int, int], color: tuple[int, int, int],
           alpha: float) -> tuple[int, int, int, int]:
    alpha = _clamp(alpha)
    if alpha <= 0:
        return dst
    rgb = tuple(round(dst[i] * (1 - alpha) + color[i] * alpha) for i in range(3))
    return (rgb[0], rgb[1], rgb[2], round(255 * alpha + dst[3] * (1 - alpha)))


def _scaled_rect(x0: float, y0: float, x1: float, y1: float,
                 size: int, scale: float) -> tuple[float, float, float, float]:
    """Map a 0-1 design rectangle into pixel coordinates around the centre."""
    def map_axis(value: float) -> float:
        return size * (0.5 + (value - 0.5) * scale)

    return map_axis(x0), map_axis(y0), map_axis(x1), map_axis(y1)


def _pixel(x: float, y: float, size: int, scale: float,
           full_bleed: bool) -> tuple[int, int, int, int]:
    centre = size / 2
    pixel: tuple[int, int, int, int] = (0, 0, 0, 0)

    # Background tile.
    if full_bleed:
        pixel = _blend(pixel, SAGE, 1.0)
    else:
        bg_sd = _round_rect_sd(x, y, centre, centre, centre, centre, size * 0.22)
        pixel = _blend(pixel, SAGE, _coverage(bg_sd))

    # Open book pages.
    for x0, x1 in ((0.205, 0.486), (0.514, 0.795)):
        rx0, ry0, rx1, ry1 = _scaled_rect(x0, 0.29, x1, 0.715, size, scale)
        sd = _round_rect_sd(
            x, y, (rx0 + rx1) / 2, (ry0 + ry1) / 2,
            (rx1 - rx0) / 2, (ry1 - ry0) / 2, size * 0.018 * scale,
        )
        pixel = _blend(pixel, CREAM, _coverage(sd))

    # Spine shadow between the pages.
    sx0, sy0, sx1, sy1 = _scaled_rect(0.486, 0.29, 0.514, 0.715, size, scale)
    sd = _round_rect_sd(
        x, y, (sx0 + sx1) / 2, (sy0 + sy1) / 2,
        (sx1 - sx0) / 2, (sy1 - sy0) / 2, size * 0.006 * scale,
    )
    pixel = _blend(pixel, SAGE_DARK, _coverage(sd) * 0.85)

    # Faint page lines.
    for line_y in (0.415, 0.515, 0.615):
        for line_x0, line_x1 in ((0.265, 0.44), (0.56, 0.735)):
            lx0, ly0, lx1, ly1 = _scaled_rect(
                line_x0, line_y, line_x1, line_y + 0.012, size, scale
            )
            sd = _round_rect_sd(
                x, y, (lx0 + lx1) / 2, (ly0 + ly1) / 2,
                (lx1 - lx0) / 2, (ly1 - ly0) / 2, size * 0.006 * scale,
            )
            pixel = _blend(pixel, SAND, _coverage(sd) * 0.9)

    # Bookmark ribbon.
    bx0, by0, bx1, by1 = _scaled_rect(0.60, 0.29, 0.66, 0.545, size, scale)
    sd = _round_rect_sd(
        x, y, (bx0 + bx1) / 2, (by0 + by1) / 2,
        (bx1 - bx0) / 2, (by1 - by0) / 2, size * 0.008 * scale,
    )
    pixel = _blend(pixel, SAND, _coverage(sd))

    return pixel


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path: Path, size: int, scale: float, full_bleed: bool) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # PNG filter: none
        for x in range(size):
            raw.extend(_pixel(x + 0.5, y + 0.5, size, scale, full_bleed))

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    path.write_bytes(png)
    print(f"wrote {path.relative_to(OUT_DIR.parent.parent.parent)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_png(OUT_DIR / "icon-192.png", 192, 1.0, False)
    write_png(OUT_DIR / "icon-512.png", 512, 1.0, False)
    write_png(OUT_DIR / "icon-maskable-512.png", 512, 0.78, True)
    write_png(OUT_DIR / "apple-touch-icon.png", 180, 0.86, True)
    write_png(OUT_DIR / "favicon-64.png", 64, 1.0, False)


if __name__ == "__main__":
    main()
