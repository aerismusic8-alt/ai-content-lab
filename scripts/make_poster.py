"""Cinematic poster / title-card generator.

Turns a free photo into a movie-poster-style background card: heavy vignette,
teal-orange grade, letterbox bars, and a Thai display title with an English
subtitle. Layouts are indexed so consecutive cards never look the same.

Usage:
    python make_poster.py <image> <out.jpg> --title "..." --subtitle "..." \
        --layout 3 --text "chapter line"
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

# 1920x1080 keeps the encode fast; the poster look comes from grading + layout,
# not from resolution.
W, H = 1920, 1080
BAR = 108  # letterbox bar height, poster "cinema" cue


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS, name)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return ImageFont.truetype(path, size)


def cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale-and-crop to exactly w x h (like CSS object-fit: cover)."""
    r = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * r)), max(h, int(im.height * r))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = int((im.height - h) * 0.42)  # bias slightly above centre
    return im.crop((left, top, left + w, top + h))


def grade(im: Image.Image) -> Image.Image:
    """Teal-orange cinematic grade: cool the shadows, warm the highlights.

    Saturation is raised (not lowered) because the vignette and the shadow
    crush both drain colour; reference posters sit around 0.30-0.60.
    """
    im = ImageEnhance.Color(im).enhance(1.35)
    im = ImageEnhance.Contrast(im).enhance(1.10)
    px = im.load()
    for y in range(0, im.height, 2):               # step 2 for speed
        for x in range(0, im.width, 2):
            r, g, b = px[x, y]
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            # shadows -> teal, highlights -> orange
            r = int(max(0, min(255, r + (lum - 0.5) * 22)))
            b = int(max(0, min(255, b - (lum - 0.5) * 22)))
            g = int(max(0, min(255, g + (lum - 0.5) * 3)))
            px[x, y] = (r, g, b)
    return im


def vignette(im: Image.Image, strength: float = 0.85) -> Image.Image:
    """Radial darkening, built once per size and reused as a mask."""
    mask = Image.new("L", (im.width, im.height), 0)
    d = ImageDraw.Draw(mask)
    cx, cy = im.width / 2, im.height / 2
    maxd = math.hypot(cx, cy)
    step = 6
    for y in range(0, im.height, step):
        for x in range(0, im.width, step):
            dist = math.hypot(x - cx, y - cy) / maxd
            v = int(255 * min(1.0, max(0.0, (dist - 0.30) / 0.70)) * strength)
            d.rectangle([x, y, x + step, y + step], fill=v)
    mask = mask.filter(ImageFilter.GaussianBlur(60))
    dark = Image.new("RGB", im.size, (0, 0, 0))
    return Image.composite(dark, im, mask)


def draw_text(d: ImageDraw.ImageDraw, xy, text, f, fill, anchor="la",
              shadow=True, shadow_off=(3, 3), stroke=0, stroke_fill=None):
    x, y = xy
    if shadow:
        d.text((x + shadow_off[0], y + shadow_off[1]), text, font=f,
               fill=(0, 0, 0), anchor=anchor,
               stroke_width=stroke, stroke_fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=fill, anchor=anchor,
           stroke_width=stroke, stroke_fill=stroke_fill)


# Layouts: (title anchor, title size, subtitle size, rule y, block side)
LAYOUTS = [
    ("mm", 132, 44, 0.62, "center"),
    ("lm", 118, 40, 0.58, "left"),
    ("rm", 118, 40, 0.58, "right"),
    ("mm", 156, 50, 0.70, "center"),
    ("lm", 104, 36, 0.52, "left"),
    ("rm", 104, 36, 0.52, "right"),
    ("mm", 176, 54, 0.50, "center"),
    ("lm", 128, 42, 0.72, "left"),
]


def build(image_path: str, out: str, title: str, subtitle: str,
          layout: int, chapter: str = "", index: str = "") -> None:
    im = cover(Image.open(image_path).convert("RGB"), W, H)
    im = grade(im)
    im = vignette(im)
    d = ImageDraw.Draw(im, "RGBA")

    anchor, tsize, ssize, rule_y, side = LAYOUTS[layout % len(LAYOUTS)]
    f_title = font("Kanit-Bold.ttf", tsize)
    f_sub = font("Prompt-Regular.ttf", ssize)
    f_small = font("Kanit-Regular.ttf", 30)
    f_idx = font("Kanit-Bold.ttf", 34)

    # letterbox bars
    d.rectangle([0, 0, W, BAR], fill=(0, 0, 0))
    d.rectangle([0, H - BAR, W, H], fill=(0, 0, 0))

    y = int(H * rule_y)
    if side == "center":
        x = W // 2
    elif side == "left":
        x = 130
    else:
        x = W - 130

    # short rule above the title
    if side == "center":
        d.line([(x - 90, y - 52), (x + 90, y - 52)], fill=(212, 175, 95, 220), width=3)
    elif side == "left":
        d.line([(x, y - 52), (x + 180, y - 52)], fill=(212, 175, 95, 220), width=3)
    else:
        d.line([(x - 180, y - 52), (x, y - 52)], fill=(212, 175, 95, 220), width=3)

    draw_text(d, (x, y), title, f_title, (247, 243, 236), anchor=anchor,
              stroke=2, stroke_fill=(10, 8, 6))
    draw_text(d, (x, y + tsize + 16), subtitle, f_sub, (198, 190, 178), anchor=anchor)

    if chapter:
        draw_text(d, (x, H - BAR - 44), chapter, f_small, (170, 164, 154), anchor=anchor)

    if index:
        d.text((W - 60, 34), index, font=f_idx, fill=(212, 175, 95), anchor="ra")

    # subtle film grain so flat photos do not look like plain slides
    noise = Image.effect_noise((W, H), 12).convert("L")
    im = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), im,
                         noise.point(lambda v: 18 if v > 200 else 0))

    im.save(out, quality=92, subsampling=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--chapter", default="")
    ap.add_argument("--index", default="")
    ap.add_argument("--layout", type=int, default=0)
    a = ap.parse_args()
    build(a.image, a.out, a.title, a.subtitle, a.layout, a.chapter, a.index)
    print(f"poster -> {a.out}")


if __name__ == "__main__":
    main()
