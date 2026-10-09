"""Generates app.ico and the installer images (run by build.bat)."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

NAVY, BLUE, ORANGE, WHITE = (15, 23, 42), (37, 99, 235), (245, 158, 11), (255, 255, 255)
UPPER = (0.35, 0.7, 1.0, 0.55, 0.85, 0.45, 0.65)   # waveform bar heights
LOWER = (0.4, 0.65, 0.95, 0.6, 0.8, 0.5, 0.6)       # a similar waveform: "the same voice"


def gradient(size: int) -> Image.Image:
    base = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(base)
    for y in range(size):
        t = y / (size - 1)
        draw.line((0, y, size, y), fill=tuple(int(NAVY[i] + (BLUE[i] - NAVY[i]) * t) for i in range(3)))
    return base


def logo(size: int = 256) -> Image.Image:
    """Rounded tile with two waveforms that line up."""
    tile = gradient(size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), size // 5, fill=255)
    tile.putalpha(mask)
    draw = ImageDraw.Draw(tile)
    bar, gap = size * 0.075, size * 0.05
    total = len(UPPER) * bar + (len(UPPER) - 1) * gap
    left = (size - total) / 2
    for row, (heights, colour, centre) in enumerate(((UPPER, WHITE, size * 0.33), (LOWER, ORANGE, size * 0.68))):
        for index, height in enumerate(heights):
            x = left + index * (bar + gap)
            half = size * 0.17 * height
            draw.rounded_rectangle((x, centre - half, x + bar, centre + half), bar / 2, fill=colour)
    return tile


def font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sidebar(width: int = 328, height: int = 628) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / (height - 1) * 0.8
        draw.line((0, y, width, y), fill=tuple(int(NAVY[i] + (BLUE[i] - NAVY[i]) * t) for i in range(3)))
    mark = logo(160)
    img.paste(mark, ((width - 160) // 2, 110), mark)
    draw.text((width / 2, 316), "VoxCompare", font=font(36), fill="white", anchor="mm")
    draw.text((width / 2, 360), "Hangazonosító", font=font(24), fill=(190, 205, 235), anchor="mm")
    draw.text((width / 2, height - 40), "Vadóc Gábor · 2026", font=font(20), fill=(190, 205, 235), anchor="mm")
    return img


def main() -> None:
    logo(256).save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    sidebar().save("installer_side.bmp")
    small = Image.new("RGB", (110, 110), "white")
    mark = logo(86)
    small.paste(mark, (12, 12), mark)
    small.save("installer_small.bmp")


if __name__ == "__main__":
    main()
