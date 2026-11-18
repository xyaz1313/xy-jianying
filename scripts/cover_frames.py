"""Cover module, step 1 — pick the owner's best-looking frames (v0.9 draft, 2026-11-18).

python cover_frames.py <out_dir> <clip.mp4> [<clip2.mp4> …] [--every 0.25] [--top 8]

Scores every sampled frame of the talking-head clips (NVDEC decode):
  face   big, frontal, roughly centred (Haar frontal face)          — the cover is about the person
  eyes   two open eyes found inside the face (Haar eye)              — no blinks / half-closed, droopy eyes
         (owner 2026-11-18: 「眼睛是含着的、表情七七八八的不能用」 — frames with < 2 eyes found are dropped)
  sharp  variance of the Laplacian on the face                      — no motion blur
  mouth  low motion vs the previous sample                          — mid-word mouth shapes look odd
  teeth  bright, low-saturation pixels in the mouth area            — owner rule 2026-11-18: NO visible teeth
         (author's preference); frames showing teeth are dropped, not just ranked lower
Writes out_dir/cover_candidates.jpg (numbered contact sheet) + out_dir/cand_NN.png (full-res) + candidates.json.
The OWNER picks the frame ("抽一帧我帅的") — never auto-publish a choice.
"""
import json
import pathlib
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FF = next(pathlib.Path.home().joinpath("AppData/Local/Microsoft/WinGet/Packages").rglob("ffmpeg.exe"))
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml")


def frames(path, every):
    W, H = 1920, 1080
    p = subprocess.Popen([str(FF), "-hide_banner", "-loglevel", "error", "-hwaccel", "cuda", "-i", str(path),
                          "-vf", f"fps=1/{every},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield i * every, np.frombuffer(b, np.uint8).reshape(H, W, 3).copy()
        i += 1


def score(img, prev):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (960, 540))
    fs = FACE.detectMultiScale(cv2.equalizeHist(small), 1.08, 4, minSize=(80, 80))
    if len(fs) == 0:
        return None
    x, y, w, h = max(fs, key=lambda f: f[2] * f[3])
    x, y, w, h = x * 2, y * 2, w * 2, h * 2
    face = g[y:y + h, x:x + w]
    eyes = EYE.detectMultiScale(face[: h // 2], 1.1, 5, minSize=(w // 10, w // 10))
    sharp = cv2.Laplacian(face, cv2.CV_64F).var()
    # teeth: centre of the lower face (mouth), bright + low saturation (teeth are light even when yellowish)
    mx0, mx1, my0, my1 = x + int(w * 0.3), x + int(w * 0.7), y + int(h * 0.68), y + int(h * 0.92)
    hsv = cv2.cvtColor(img[my0:my1, mx0:mx1], cv2.COLOR_BGR2HSV)
    # teeth = light AND yellowish (hue 12–40, some saturation); the grey mic windscreen in front of the mouth
    # is light too but has ~no saturation, so it no longer counts (it wrongly sank the owner's favourite frame)
    H_, S_, V_ = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    teeth = float(((V_ > 150) & (H_ >= 12) & (H_ <= 40) & (S_ >= 30) & (S_ <= 120)).mean()) if hsv.size else 0.0
    size = (w * h) / (1920 * 1080)
    centred = 1 - abs((x + w / 2) / 1920 - 0.5) * 2
    motion = float(np.abs(small.astype(int) - prev.astype(int)).mean()) if prev is not None else 10.0
    s = (min(size / 0.06, 1.5) * 2 + min(len(eyes), 2) * 1.2 + min(sharp / 300, 1.5) + centred - motion / 12)
    if len(eyes) < 2:
        s -= 50                                        # half-closed / droopy eyes: owner rejects these
    if teeth > 0.012:                                  # tuned on the owner's picks: #4 0.001 ok, #2 0.020 = teeth
        s -= 100                                       # dropped: teeth visible
    return {"score": round(float(s), 3), "teeth": round(teeth, 3), "face": [int(x), int(y), int(w), int(h)], "eyes": int(len(eyes)),
            "sharp": round(float(sharp), 1), "motion": round(motion, 2)}, small


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 0.25
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 8
    clips = [a for a in sys.argv[2:] if a.endswith((".mp4", ".MP4", ".mov", ".MOV"))]
    cands = []
    for c in clips:
        prev = None
        for t, img in frames(c, every):
            r = score(img, prev)
            if r is None:
                prev = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (960, 540))
                continue
            info, prev = r
            cands.append((info["score"], c, t, img, info))
    cands.sort(key=lambda x: -x[0])
    picked = []
    cands = [x for x in cands if x[4].get("teeth", 0) <= 0.012 and x[4].get("eyes", 0) >= 2] + [x for x in cands if x[4].get("teeth", 0) > 0.012][:0]
    for sc, c, t, img, info in cands:                  # spread out: at least 0.75 s apart
        if all(c != p[1] or abs(t - p[2]) >= 0.75 for p in picked):
            picked.append((sc, c, t, img, info))
        if len(picked) >= top:
            break
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 30)
    tiles, meta = [], []
    for n, (sc, c, t, img, info) in enumerate(picked, 1):
        # OUTPUT seeking (-ss after -i) = frame-accurate; input seeking gave a different frame than the tile
        full = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-i", c, "-ss", f"{t:.3f}",
                               "-frames:v", "1", str(out / f"cand_{n:02d}.png"), "-y"])
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((640, 360))
        d = ImageDraw.Draw(pil)
        d.rectangle([0, 0, 120, 44], fill=(0, 0, 0))
        d.text((10, 4), f"#{n}", font=font, fill=(255, 230, 0))
        tiles.append(pil)
        meta.append({"n": n, "clip": c, "t": round(t, 2), **info, "png": f"cand_{n:02d}.png"})
    cols = 4
    sheet = Image.new("RGB", (640 * cols, 360 * ((len(tiles) + cols - 1) // cols)), (20, 20, 20))
    for i, tl_ in enumerate(tiles):
        sheet.paste(tl_, ((i % cols) * 640, (i // cols) * 360))
    sheet.save(out / "cover_candidates.jpg", quality=90)
    json.dump(meta, open(out / "candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for m in meta:
        print(m)


if __name__ == "__main__":
    main()
