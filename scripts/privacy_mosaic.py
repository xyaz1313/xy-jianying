"""Automatic privacy mosaic for screen-filmed footage.

Pass 1 (ocr):    sample frames, OCR them, decide which text boxes are private (small names, phone numbers, sidebars)
                 while keeping evidence text (large chat bubbles / burned-in captions / whitelisted words).
Pass 2 (render): decode the full-res video on the GPU, pixelate those boxes (union of neighbouring samples so
                 moving handheld footage stays covered), optionally bleep word ranges, re-encode with NVENC.

python privacy_mosaic.py ocr    <video> <boxes.json> [sample_fps=5]
python privacy_mosaic.py render <video> <boxes.json> <out.mp4> [--bleep 84.00-84.32 ...]
"""
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platform_env import FF, FFPROBE, ff_font, font as sys_font, hwaccel, venc  # noqa: E402,F401  (v1.1 cross-platform)
FP = FFPROBE
KEEP_WORDS = ["产品", "投入", "福利", "研究", "方法", "赚", "月入", "客户", "搞到爆", "会销", "线上", "适合",
              "好事", "主要是他", "可以教", "卖", "不用", "W", "万", "师傅", "跟进", "沟通", "名片", "加你"]
PHONE = re.compile(r"1[3-9]\d{9}")
# names that must always be hidden regardless of size (e.g. a chat window title); extend per video
ALWAYS_PRIVATE = ["丰谦", "丰谦"]
OCR_W = 1920  # OCR resolution (width)


def probe(v):
    out = subprocess.check_output([str(FP), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(v)])
    j = json.loads(out)
    s = j["streams"][0]
    n, d = map(int, s["r_frame_rate"].split("/"))
    return s["width"], s["height"], n / d, float(j["format"]["duration"])


def ocr(video, boxes_json, sample_fps=5.0):
    import numpy as np
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import gpu_env  # noqa: F401
    from rapidocr_onnxruntime import RapidOCR
    W, H, fps, dur = probe(video)
    oh = round(H * OCR_W / W)
    import platform_env
    eng = platform_env.ocr_engine()
    p = subprocess.Popen([str(FF), "-hide_banner", "-loglevel", "error", *hwaccel(), "-i", str(video),
                          "-vf", f"fps={sample_fps},scale={OCR_W}:{oh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    samples, i, sz = [], 0, OCR_W * oh * 3
    while True:
        buf = p.stdout.read(sz)
        if len(buf) < sz:
            break
        img = np.frombuffer(buf, np.uint8).reshape(oh, OCR_W, 3)
        res, _ = eng(img)
        res = res or []

        def glyph_h(b):  # skew-robust text height: mean length of the quad's left and right edges
            return (np.hypot(b[3][0] - b[0][0], b[3][1] - b[0][1]) + np.hypot(b[2][0] - b[1][0], b[2][1] - b[1][1])) / 2

        hmax = max([glyph_h(b) for b, _, _ in res] or [1])
        priv = []
        for b, txt, sc in res:
            xs, ys = [q[0] for q in b], [q[1] for q in b]
            h = glyph_h(b)
            keep_word = any(k in txt for k in KEEP_WORDS) and h >= 0.4 * hmax
            small = h < 0.6 * hmax
            if PHONE.search(txt.replace(" ", "")) or any(n in txt for n in ALWAYS_PRIVATE) or (small and not keep_word):
                s = W / OCR_W
                priv.append([round(min(xs) * s), round(min(ys) * s), round(max(xs) * s), round(max(ys) * s)])
        samples.append({"t": i / sample_fps, "boxes": priv})
        if i % 25 == 0:
            print(f"ocr t={i / sample_fps:.1f}s boxes={len(priv)}", flush=True)
        i += 1
    pathlib.Path(boxes_json).write_text(json.dumps({"W": W, "H": H, "fps": fps, "samples": samples}), encoding="utf-8")
    print("ocr done", len(samples), "samples")


def render(video, boxes_json, out, bleeps):
    import cv2
    import numpy as np
    meta = json.loads(pathlib.Path(boxes_json).read_text(encoding="utf-8"))
    W, H, fps = meta["W"], meta["H"], meta["fps"]
    S = meta["samples"]
    dt = S[1]["t"] - S[0]["t"] if len(S) > 1 else 1
    pad = int(W * 0.016)
    dec = subprocess.Popen([str(FF), "-hide_banner", "-loglevel", "error", *hwaccel(), "-i", str(video),
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    af = []
    for b in bleeps:  # mute the word and lay a 1 kHz beep on top
        a, z = map(float, b.split("-"))
        af.append(f"volume=enable='between(t,{a},{z})':volume=0")
    abeep = ""
    if bleeps:
        parts = [f"sine=f=1000:sample_rate=48000:d={float(b.split('-')[1]) - float(b.split('-')[0])},volume=0.25,"
                 f"adelay={int(float(b.split('-')[0]) * 1000)}|{int(float(b.split('-')[0]) * 1000)},apad" for b in bleeps]
        abeep = ";".join(f"{p}[b{k}]" for k, p in enumerate(parts))
    fc = f"[1:a]{','.join(af) if af else 'anull'}[m]" + (f";{abeep};[m]" + "".join(f"[b{k}]" for k in range(len(bleeps)))
                                                       + f"amix=inputs={len(bleeps) + 1}:duration=first:normalize=0[a]"
                                                       if bleeps else ";[m]anull[a]")
    enc = subprocess.Popen([str(FF), "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-i", str(video), "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                            *venc(18, "slow", hevc=True),
                            "-c:a", "aac", "-b:a", "256k", str(out)], stdin=subprocess.PIPE)
    sz, n = W * H * 3, 0
    while True:
        buf = dec.stdout.read(sz)
        if len(buf) < sz:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        orig = img.copy()
        t = n / fps
        k = int(t / dt)
        # 1) bright list panels (white app pages filmed off a screen): pixelate the whole panel,
        #    then restore burned-in yellow captions (evidence) on top.
        sm = cv2.resize(orig, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
        bright = cv2.morphologyEx((gray > 175).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cnt, lab, st, _ = cv2.connectedComponentsWithStats(bright)
        panel_mask = np.zeros((H, W), np.uint8)
        for c in range(1, cnt):
            x, y, w_, h_, area = st[c]
            if area > 0.03 * sm.shape[0] * sm.shape[1] and h_ > 0.35 * sm.shape[0] and area > 0.45 * w_ * h_:
                x0, y0, x1, y1 = x * 8, y * 8, min(W, (x + w_) * 8), min(H, (y + h_) * 8)
                roi = img[y0:y1, x0:x1]
                cell = 28
                small = cv2.resize(roi, (max(1, (x1 - x0) // cell), max(1, (y1 - y0) // cell)), interpolation=cv2.INTER_AREA)
                img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
                panel_mask[y0:y1, x0:x1] = 1
        if panel_mask.any():
            hsv = cv2.cvtColor(orig, cv2.COLOR_BGR2HSV)
            yellow = ((hsv[..., 0] >= 15) & (hsv[..., 0] <= 38) & (hsv[..., 1] > 110) & (hsv[..., 2] > 140)).astype(np.uint8)
            yellow = cv2.morphologyEx(yellow, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            # keep only big yellow blobs (captions), grow them to include the black outline
            cy, ly, sy, _ = cv2.connectedComponentsWithStats(yellow)
            keep = np.zeros_like(yellow)
            for c in range(1, cy):
                if sy[c][4] > 2500:
                    keep[ly == c] = 1
            keep = cv2.dilate(keep, np.ones((31, 31), np.uint8)) & panel_mask
            img[keep == 1] = orig[keep == 1]
        for j in range(k - 5, k + 6):  # ±1 s of OCR samples: covers handheld motion and OCR misses
            if 0 <= j < len(S):
                for x0, y0, x1, y1 in S[j]["boxes"]:
                    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
                    if x1 - x0 < 4 or y1 - y0 < 4:
                        continue
                    roi = img[y0:y1, x0:x1]
                    cell = max(12, (y1 - y0) // 3)
                    small = cv2.resize(roi, (max(1, (x1 - x0) // cell), max(1, (y1 - y0) // cell)), interpolation=cv2.INTER_LINEAR)
                    img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        enc.stdin.write(img.tobytes())
        n += 1
        if n % 300 == 0:
            print(f"render {t:.1f}s", flush=True)
    enc.stdin.close(); enc.wait()
    print("render done", out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ocr":
        ocr(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 5.0)
    else:
        bl = sys.argv[sys.argv.index("--bleep") + 1:] if "--bleep" in sys.argv else []
        render(sys.argv[2], sys.argv[3], sys.argv[4], bl)
