"""Cover module, step 2 — render the owner's cover style (v0.9 draft, 2026-11-18).

python cover_render.py <out_dir> <top_line> <bottom_line> <frame_h.png> [<frame_v_top.png> <frame_v_bottom.png>]

Owner's style (reference covers 「CLAUDE / 不能用了又如何」):
  - font 仓耳榜黑, top line #FF287F, bottom line white, thick black stroke, the two lines touching, CENTRED
    (the cover is the one place where centred text is the style)
  - horizontal 16:9 (in-video cover): text in the lower middle and inside the central 4:3 area (platforms show
    the 16:9 cover cropped to 4:3), top line ≈ 60 % of the width
  - vertical 3:4: two frames stacked (top half / bottom half, each centre-cropped), the text sits across the seam
Writes out_dir/cover_16x9.png (3840x2160) and out_dir/cover_3x4.png (1620x2160).
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import director  # noqa: E402  (KW_FONT = 仓耳榜黑 from the 剪映 cache)

from style import ST  # noqa: E402  (v1.1.1: cover colours + layout from style.json)
_C = ST["cover"]
PINK, WHITE = (tuple(int(_C[k][i:i + 2], 16) for i in (0, 2, 4)) for k in ("top_color", "bottom_color"))


# Owner layout, MEASURED on his reference covers 「CLAUDE / 不能用了又如何」 (2026-11-18):
#   16:9  both lines the SAME fill width = 0.575 W (≈ 77 % of the central 4:3), block centre at 0.726 H
#   3:4   both lines the SAME fill width = 0.86 W (stroke almost touches the sides), block centre at the seam
#   the two lines' strokes touch (fill gap ≈ 2 × stroke) — 「上下排得很紧，字放大，霸气」
H_FILL_W, H_CENTRE = _C["landscape_fill_width"], _C["landscape_centre_y"]
V_FILL_W, V_CENTRE = _C["portrait_fill_width"], _C["portrait_centre_y"]


def font_for_width(text, target_w):
    """Font whose FILL (no stroke) width of `text` is target_w."""
    lo, hi = 20, 1200
    while hi - lo > 2:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(director.KW_FONT, mid)
        x0, _, x1, _ = f.getbbox(text)
        lo, hi = (mid, hi) if x1 - x0 <= target_w else (lo, mid)
    return ImageFont.truetype(director.KW_FONT, lo)


def block(img, top, bottom, cx, cy, fill_w):
    """Two lines, same fill width, strokes touching, centred on (cx, cy)."""
    d = ImageDraw.Draw(img)
    f1, f2 = font_for_width(top, fill_w), font_for_width(bottom, fill_w)
    sw1, sw2 = max(6, f1.size // 7), max(6, f2.size // 7)
    b1, b2 = f1.getbbox(top), f2.getbbox(bottom)
    h1, h2 = b1[3] - b1[1], b2[3] - b2[1]
    gap = 0.9 * (sw1 + sw2)                             # strokes touch
    total = h1 + gap + h2
    y1 = cy - total / 2                                 # top of line-1 fill
    y2 = y1 + h1 + gap
    for txt, f, sw, bb, ytop, col in ((top, f1, sw1, b1, y1, PINK), (bottom, f2, sw2, b2, y2, WHITE)):
        w = bb[2] - bb[0]
        d.text((cx - w / 2 - bb[0], ytop - bb[1]), txt, font=f, fill=col, stroke_width=sw, stroke_fill=(0, 0, 0))


def cover_h(frame, top, bottom, out):
    W, H = 3840, 2160
    img = Image.open(frame).convert("RGB").resize((W, H))
    block(img, top, bottom, W / 2, H * H_CENTRE, W * H_FILL_W)
    img.save(out)


def cover_v(frame_a, frame_b, top, bottom, out):
    W, H = 1620, 2160
    canvas = Image.new("RGB", (W, H))
    for i, fr in enumerate((frame_a, frame_b)):
        im = Image.open(fr).convert("RGB")
        tw, th = W, H // 2                              # centre-crop each frame to W x H/2
        s_ = max(tw / im.width, th / im.height)
        im = im.resize((round(im.width * s_), round(im.height * s_)))
        x0, y0 = (im.width - tw) // 2, max(0, int((im.height - th) * 0.25))
        canvas.paste(im.crop((x0, y0, x0 + tw, y0 + th)), (0, i * th))
    block(canvas, top, bottom, W / 2, H * V_CENTRE, W * V_FILL_W)
    canvas.save(out)


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    top, bottom, fh = sys.argv[2], sys.argv[3], sys.argv[4]
    cover_h(fh, top, bottom, out / "cover_16x9.png")
    if len(sys.argv) >= 7:
        cover_v(sys.argv[5], sys.argv[6], top, bottom, out / "cover_3x4.png")
    print("ok", out)


if __name__ == "__main__":
    main()
