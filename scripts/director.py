"""Layout director: decide where each big keyword goes so it NEVER covers a face.

For every keyword it samples frames across the keyword's on-screen window, detects faces (OpenCV Haar, frontal +
profile, mirrored), then picks a placement:
  person on screen -> top-left or top-right corner, on the side away from the face
  no person        -> top centre
It checks the chosen text boxes against the face boxes (shrinks the text if needed) and renders a preview sheet.

python director.py <job.json> <layout.json> <out_dir>
Writes out_dir/director_plan.json (per keyword: x, y_red, y_white, size, reason) and out_dir/director_preview.jpg
"""
import json
import pathlib
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platform_env import FF, FFPROBE, ff_font, font as sys_font, hwaccel, venc  # noqa: E402,F401  (v1.1 cross-platform)
W, H = 3840, 2160
# 剪映 position units -> canvas pixels. v0.6 CALIBRATED in 剪映 11.8 (draft 校准一号, 4K canvas, text deselected,
# difference image vs. text moved off-canvas): X 1500 -> +0.1983 W, Y 800 -> -0.1854 H  =>  ~2 units per pixel.
# (v0.4 estimates were UX 0.414 / UY 0.52 / CHAR_W 0.072 / LINE_H 0.11 -> corner text ran off the frame.)
UX, UY = 0.500, 0.501     # first fit said UX 0.508; its video-rect detector cut 13 px off a dark left edge (1132 vs
                          # 1150 px wide) -> corrected to 0.500 = exactly 2 units per pixel. v06 plan used 0.508 (<0.5% W).
# ink box of 仓耳榜黑 with stroke 90 at 字号 14, fraction of frame width per char / frame height per line
# (measured: 5 chars = 0.4117 W, one line = 0.190 H; linear in 字号: size 8 -> 0.235 W / 0.108 H)
CHAR_W, LINE_H = 0.081, 0.190      # CHAR_W corrected for the same 1.6 % width bias (0.0823 raw)
DUR = 3.0
FONT = sys_font()          # labels on the preview sheet only
import platform_env  # noqa: E402
from style import ST  # noqa: E402  (v1.1.1)
KW_FONT = platform_env.jianying_font(ST["keyword"]["font"]) or FONT             # the real 剪映 keyword font, so previews look like the edit

fr_cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
pr_cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def frame_at(path, t):
    out = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path),
                          "-frames:v", "1", "-vf", "scale=960:-1", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)


def faces(img):
    g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    h, w = g.shape
    boxes = []
    for cas, flip in ((fr_cas, False), (pr_cas, False), (pr_cas, True)):
        src = cv2.flip(g, 1) if flip else g
        for (x, y, bw, bh) in cas.detectMultiScale(src, 1.1, 6, minSize=(int(w * 0.08), int(w * 0.08))):
            if flip:
                x = w - x - bw
            boxes.append((x / w, y / h, (x + bw) / w, (y + bh) / h))
    return boxes


def src_of(layout, t):
    for s in layout["segments"]:
        if s["start"] <= t < s["end"]:
            return s["clip"], s["src"][0] + (t - s["start"]) * 1.1
    s = layout["segments"][-1]
    return s["clip"], s["src"][1] - 0.05


# v0.7 OWNER STYLE (reference: owner hand-tuned 「彩排五号」 keyword 9.1 s, 2026-11-18):
#   red  「AI创业兄弟」 字号 8 · 缩放 160% · X 2186 · Y 1761      white 「千万别上当」 字号 8 · 缩放 157% · X 2331 · Y 1125
#   => effective 字号 ≈ 12.8 (字号 8 × 缩放 1.6 == 字号 12.8, both linear); both lines RIGHT-aligned to the same edge
#      (61 px = 1.6 % W from the right), red line's box 1.7 % H from the top, the two lines TOUCH (centre-to-centre
#      0.148 H at 12.8 → 0.01165 H per 字号) — "上排和下排永远靠在一起".
KW_SIZE = ST["keyword"]["size"]            # default 字号 for big text (owner reference ≈ 12.8); screen footage (no person) uses 14
KW_SIZE_CENTRE = ST["keyword"]["size_no_person"]
PITCH_PER = 0.148 / 12.7          # line pitch (= line box height, lines touch) per 字号, fraction of H
CHAR_PER = CHAR_W / 14            # one CJK char per 字号, fraction of W
ASCII_W = 0.7                     # a latin letter/digit ≈ 0.7 CJK char in 仓耳榜黑 (fits 「AI创业兄弟」 X 2186)
MARGIN_X, MARGIN_T = 0.016, 0.017


def line_w(txt, size):
    n = sum(ASCII_W if ord(c) < 128 else 1.0 for c in (txt or "").replace(" ", ""))
    return CHAR_PER * size * n


def layout(red, white, side, size, top=MARGIN_T):
    """Owner style: lines stacked touching; aligned to the outer edge (right/left) or centred ('top')."""
    pitch = PITCH_PER * size
    out = []
    for i, txt in enumerate((red, white)):
        if not txt:
            continue
        w = line_w(txt, size)
        cx = 1 - MARGIN_X - w / 2 if side == "right" else MARGIN_X + w / 2 if side == "left" else 0.5
        cy = top + pitch / 2 + i * pitch
        out.append((cx - w / 2, cy - pitch / 2, cx + w / 2, cy + pitch / 2, txt, cx, cy))
    return out


def overlaps(a, b, pad=0.012):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def core(b):
    """Haar boxes include hair, ears and a margin (owner's reference text sat right beside such a box and was fine)
    -> keep the face core: 12 % in from each side, 15 % down from the top."""
    w, h = b[2] - b[0], b[3] - b[1]
    return (b[0] + 0.12 * w, b[1] + 0.15 * h, b[2] - 0.12 * w, b[3])


def busyness(imgs, boxes):
    """How much is going on under the text boxes (mean edge density + texture over the given BGR frames).
    Low = plain wall / dark area = where the owner wants the big text."""
    if not imgs:
        return 0.0
    vals = []
    for img in imgs:
        if img is None:
            continue
        h, w = img.shape[:2]
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(g, 60, 160)
        for b in boxes:
            x0, y0, x1, y1 = (max(0, int(b[0] * w)), max(0, int(b[1] * h)), min(w, int(b[2] * w)), min(h, int(b[3] * h)))
            if x1 > x0 and y1 > y0:
                vals.append(edges[y0:y1, x0:x1].mean() / 255 + g[y0:y1, x0:x1].std() / 255)
    return float(np.mean(vals)) if vals else 0.0


def plan_one(red, white, face_boxes, imgs=None):
    """v0.8 owner rule (2026-11-18): big text is NEVER centred — always the left or right corner, so the middle
    of the picture stays free. With a face: the side away from it. Without a face: the EMPTIER side (plain wall,
    dark area), judged on the real frames `imgs` (BGR); right if no frames are given."""
    white = white or ""
    face_boxes = [core(b) for b in face_boxes]
    if face_boxes:
        fx = np.mean([(b[0] + b[2]) / 2 for b in face_boxes])
        sides = ["right", "left"] if fx < 0.5 else ["left", "right"]
        tries = []
        # keep the owner's size as long as possible: far side first, then near side, then step down the corner,
        # and only then shrink one 字号 at a time (never below 9)
        for size in range(KW_SIZE, 8, -1):
            for side in sides:
                for top in (MARGIN_T, MARGIN_T + 0.12, MARGIN_T + 0.24):
                    bx = layout(red, white, side, size, top)
                    hit = any(overlaps(b, f) for b in bx for f in face_boxes)
                    tries.append((hit, side, top, size, bx))
        clear = [c for c in tries if not c[0]]
        hit, side, top, size, bx = clear[0] if clear else tries[0]
        pos = ("右" if side == "right" else "左") + ("上角" if top < 0.05 else "侧偏上")
        reason = f"有人（脸在{'左' if fx < 0.5 else '右'}侧）→ {pos}，字号{size}" + ("  ⚠ 仍碰到脸" if hit else "")
    else:
        size, hit = KW_SIZE, False
        cand = {sd: layout(red, white, sd, size) for sd in ("right", "left")}
        busy = {sd: busyness(imgs, [b[:4] for b in bx]) for sd, bx in cand.items()}
        side = min(busy, key=busy.get) if imgs else "right"
        bx = cand[side]
        reason = (f"没有人 → {'右' if side == 'right' else '左'}上角（这边更空 {busy[side]:.2f} vs "
                  f"{busy['left' if side == 'right' else 'right']:.2f}），字号{size}" if imgs else
                  f"没有人 → 右上角，字号{size}")
    r = bx[0]
    wl = bx[1] if len(bx) > 1 else None
    to_x = lambda cx: round((cx - 0.5) * W / UX)  # noqa: E731
    to_y = lambda cy: round((0.5 - cy) * H / UY)  # noqa: E731
    return {"x": to_x(r[5]), "y_red": to_y(r[6]),
            "x_white": to_x(wl[5]) if wl else to_x(r[5]),
            "y_white": to_y(wl[6]) if wl else to_y(r[6] + PITCH_PER * size),
            "size": size, "side": side, "reason": reason, "covers_face": hit, "boxes": [b[:4] for b in bx]}


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    layout = json.load(open(sys.argv[2], encoding="utf-8"))
    out = pathlib.Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    ep = json.load(open(job["edit_plan"], encoding="utf-8"))
    times = [k["t"] for k in ep["keywords"]]
    plan, tiles = [], []
    font = ImageFont.truetype(KW_FONT, 38)
    for t, pair in zip(times, job["keywords"]):
        if not pair:
            plan.append(None)
            continue
        red, white = pair
        t = max(t, 0.05)
        fb, shown = [], None
        for dt in (0.2, 1.2, 2.4):
            clip, st = src_of(layout, t + dt)
            img = frame_at(job["files"][clip - 1], st)
            if img is None:
                continue
            f = faces(img)
            fb += f
            if shown is None or (dt == 1.2):
                shown = (img, f)
        p = plan_one(red, white or "", fb)
        p.update({"t": round(t, 2), "red": red, "white": white})
        plan.append(p)
        # preview tile
        img, _ = shown
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((640, 360))
        d = ImageDraw.Draw(pil)
        for b in fb:
            d.rectangle([b[0] * 640, b[1] * 360, b[2] * 640, b[3] * 360], outline=(0, 255, 255), width=3)
        for (x0, y0, x1, y1), txt, col in zip(p["boxes"], [red, white], [(255, 40, 127), (255, 255, 255)]):
            d.rectangle([x0 * 640, y0 * 360, x1 * 640, y1 * 360], outline=col, width=2)
            d.text(((x0 + x1) / 2 * 640, (y0 + y1) / 2 * 360), txt, font=font, fill=col, anchor="mm",
                   stroke_width=6, stroke_fill=(0, 0, 0))
        d.rectangle([0, 0, 640, 30], fill=(0, 0, 0))
        d.text((8, 4), f"{t:5.1f}s  {p['reason']}", font=ImageFont.truetype(FONT, 18),
               fill=(255, 80, 80) if p["covers_face"] else (255, 255, 255))
        tiles.append(pil)
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (640 * cols, 360 * rows), (20, 20, 20))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 640, (i // cols) * 360))
    sheet.save(out / "director_preview.jpg", quality=90)
    json.dump(plan, open(out / "director_plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p in plan:
        if p:
            print(f"{p['t']:6.1f}s  {p['red']} / {p['white']}  → {p['reason']}  X{p['x']} Y{p['y_red']}/{p['y_white']} 字号{p['size']}")


if __name__ == "__main__":
    main()
