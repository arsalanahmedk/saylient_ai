#!/usr/bin/env python3
"""Generate the SaylientAI extension icons (16/48/128 PNG), stdlib only.

No Pillow, no external assets: pixels are computed in pure Python and
the PNG is encoded by hand (zlib + struct). The design is a Glacier
Blue (#9CBDE0) rounded square with a white chat bubble and a small
Safety Orange (#FF5F00) dot — the approved 60/30/10 palette, no text
(the mark must stay legible at 16 px).

Usage: python3 tools/make_icons.py   (run from apps/extension/)
Outputs: icons/icon16.png, icons/icon48.png, icons/icon128.png
"""

from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

GLACIER = (0x9C, 0xBD, 0xE0, 255)
WHITE = (255, 255, 255, 255)
ORANGE = (0xFF, 0x5F, 0x00, 255)
TRANSPARENT = (0, 0, 0, 0)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    chunk = struct.pack(">I", len(data)) + chunk_type + data
    chunk += struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return chunk


def write_png(path: Path, size: int, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for r, g, b, a in row:
            raw.extend((r, g, b, a))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _rounded_rect_mask(size: int, radius: int) -> list[list[bool]]:
    mask: list[list[bool]] = []
    for y in range(size):
        row: list[bool] = []
        for x in range(size):
            # Distance to the nearest corner centre; inside if within
            # the rounded-rectangle outline.
            cx = min(max(x, radius), size - 1 - radius)
            cy = min(max(y, radius), size - 1 - radius)
            row.append((x - cx) ** 2 + (y - cy) ** 2 <= radius * radius)
        mask.append(row)
    return mask


def _disc(mask: list[list[bool]], size: int, cx: float, cy: float, radius: float) -> list[list[bool]]:
    out = [row[:] for row in mask]
    for y in range(size):
        for x in range(size):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= radius * radius:
                out[y][x] = True
    return out


def render_icon(size: int) -> list[list[tuple[int, int, int, int]]]:
    radius = max(2, round(size * 0.24))
    outer = _rounded_rect_mask(size, radius)
    # White chat bubble: rounded rect inset, with a small tail.
    pad = size * 0.26
    bubble_r = max(1, round(size * 0.10))
    bubble_top, bubble_left = pad, pad
    bubble_bottom, bubble_right = size - pad - size * 0.06, size - pad
    bubble: list[list[bool]] = []
    for y in range(size):
        row = []
        for x in range(size):
            cx = min(max(x, bubble_left + bubble_r), bubble_right - bubble_r)
            cy = min(max(y, bubble_top + bubble_r), bubble_bottom - bubble_r)
            inside = (x - cx) ** 2 + (y - cy) ** 2 <= bubble_r * bubble_r
            inside = inside and bubble_left <= x <= bubble_right and bubble_top <= y <= bubble_bottom
            row.append(inside)
        bubble.append(row)
    # Tail: small triangle under the bubble's left side.
    tail_h = size * 0.10
    for y in range(size):
        if bubble_bottom <= y <= bubble_bottom + tail_h:
            t = (y - bubble_bottom) / max(tail_h, 1)
            x0 = bubble_left + size * 0.08
            x1 = x0 + size * 0.22 * (1 - t)
            for x in range(size):
                if x0 <= x <= x1:
                    bubble[y][x] = True
    # Orange dot at the bubble's lower right.
    dot_cx = bubble_right - size * 0.10
    dot_cy = bubble_bottom - size * 0.06
    dot = _disc(
        [[False] * size for _ in range(size)], size, dot_cx, dot_cy, max(1.0, size * 0.055)
    )

    pixels: list[list[tuple[int, int, int, int]]] = []
    for y in range(size):
        row = []
        for x in range(size):
            if dot[y][x]:
                row.append(ORANGE)
            elif bubble[y][x]:
                row.append(WHITE)
            elif outer[y][x]:
                row.append(GLACIER)
            else:
                row.append(TRANSPARENT)
        pixels.append(row)
    return pixels


def main() -> int:
    here = Path(__file__).resolve().parent.parent  # apps/extension/
    icons_dir = here / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        out = icons_dir / f"icon{size}.png"
        write_png(out, size, render_icon(size))
        print(f"wrote {out} ({size}x{size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
