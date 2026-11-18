"""Visual + layout directors for a process-demo video (v0.8).

python process_visual.py <visual_spec_demo.json> <timeline.json> <preview.mp4> <out_dir>

Layers (owner-approved house rules + process-demo rules):
  big text  = keywords from the spec: 仓耳榜黑, mood colour + white second line, owner layout (字号 13, lines touching,
              edge-aligned; director.plan_one dodges every face found on the REAL preview frames, incl. the small
              face inside the filmed 剪映 player; no face -> the EMPTIER side, never centred - owner rule)
  step chip = 「STEP n · …」 small white text on a black pill, bottom-left, for the whole step
  speed     = 「»» 加速 ×N」 yellow on black, top-right, on every sped-up segment (already burnt into the preview)
Writes out_dir/visual_plan_demo.json (out-times + 剪映 X/Y/字号/colour/entrance per keyword, step chips, badges),
out_dir/preview_visual.mp4 (preview with keywords + chips composited, real font; entrance animations not simulated)
and out_dir/visual_sheet.jpg (one frame per keyword).
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import director  # noqa: E402
from visual_director import ANIMS, COLORS  # noqa: E402

FF = director.FF
VW, VH = 1280, 720
CHIP_FONT = "C:/Windows/Fonts/msyhbd.ttc"


def frame(mp4, t):
    out = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(mp4),
                          "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)


def kw_layer(p, red, white, color):
    """RGBA 1280x720 with the two keyword lines drawn at the planned boxes in the real font."""
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    for (x0, y0, x1, y1), txt, c in zip(p["boxes"], [red, white], [col, (255, 255, 255)]):
        if not txt:
            continue
        fs = 120
        while fs > 10:
            f = ImageFont.truetype(director.KW_FONT, fs)
            if f.getlength(txt) <= (x1 - x0) * VW * 0.92:
                break
            fs -= 1
        d.text(((x0 + x1) / 2 * VW, (y0 + y1) / 2 * VH), txt, font=f, fill=c, anchor="mm",
               stroke_width=max(3, fs // 7), stroke_fill=(0, 0, 0))
    return im


def chip_layer(text):
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(CHIP_FONT, 26)
    w = f.getlength(text)
    x, y = 26, VH - 26 - 44
    d.rounded_rectangle([x, y, x + w + 36, y + 44], 10, fill=(0, 0, 0, 170))
    d.rectangle([x, y, x + 8, y + 44], fill=(255, 40, 127, 255))
    d.text((x + 22, y + 22), text, font=f, fill=(255, 255, 255), anchor="lm")
    return im


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    import compliance
    bad = compliance.check_keywords(spec["keywords"])
    if bad:                                            # owner rule 2026-11-18: no 导流 words in big text, ever
        raise SystemExit("大字里有导流词（平台会判导流），先改词：" + "; ".join(f"{t} → {h}" for t, h in bad))
    T = json.load(open(sys.argv[2], encoding="utf-8"))
    mp4, out = sys.argv[3], pathlib.Path(sys.argv[4])
    lay = out / "layers"; lay.mkdir(parents=True, exist_ok=True)
    segs = T["segments"]
    plan = {"total": T["total"], "keywords": [], "steps": [], "badges": []}
    layers = []                                         # (png, t0, t1)
    tiles = []
    for n, k in enumerate(spec["keywords"]):
        s = segs[k["seg"]]
        t0 = s["out_start"] + k["off"]
        dur = k.get("dur", director.DUR)
        t1 = min(t0 + dur, T["total"] - 0.05)
        fb, imgs = [], []
        for dt in (0.1, 1.0, 2.0, dur - 0.2):
            img = frame(mp4, min(t0 + dt, t1 - 0.05))
            if img is None:
                continue
            fb += director.faces(img)
            imgs.append(img)
        p = director.plan_one(k["top"], k.get("bottom") or "", fb, imgs)
        p.update({"t": round(t0, 2), "end": round(t1, 2), "red": k["top"], "white": k.get("bottom"),
                  "mood": k["mood"], "color": COLORS[k["mood"]], "anim": k.get("anim") or ANIMS[k["mood"]],
                  "why": k.get("why", ""), "faces": [[round(v, 3) for v in b] for b in fb]})
        plan["keywords"].append(p)
        png = lay / f"kw_{n:02d}.png"
        kw_layer(p, k["top"], k.get("bottom"), COLORS[k["mood"]]).save(png)
        layers.append((png, t0, t1))
    # step chips: from the first to the last segment of each step
    # owner rule 2026-11-18: STEP chips are engineering labels -> never in the delivered video (planned only with --labels)
    for st, label in (spec.get("steps", {}) if "--labels" in sys.argv else {}).items():
        ss = [s for s in segs if str(s.get("step")) == st]
        if not ss:
            continue
        t0, t1 = ss[0]["out_start"], ss[-1]["out_end"]
        plan["steps"].append({"step": int(st), "text": label, "t": t0, "end": t1})
        png = lay / f"step_{st}.png"
        chip_layer(label).save(png)
        layers.append((png, t0, t1))
    for s in segs:
        sp = s.get("speed")
        if sp and sp > 1.15:
            plan["badges"].append({"text": f"»» 加速 ×{sp:g}", "t": s["out_start"], "end": s["out_end"]})
    json.dump(plan, open(out / "visual_plan_demo.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # composite preview
    args, fc, last = [str(FF), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4)], [], "[0:v]"
    for i, (png, a, b) in enumerate(layers, 1):
        args += ["-loop", "1", "-t", f"{T['total']:.2f}", "-i", str(png)]
        fc.append(f"{last}[{i}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{i}]")
        last = f"[v{i}]"
    args += ["-filter_complex", ";".join(fc), "-map", last, "-map", "0:a", "-t", f"{T['total']:.2f}",
             "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "25", "-pix_fmt", "yuv420p", "-c:a", "copy",
             str(out / "preview_visual.mp4")]
    subprocess.run(args, check=True)
    # contact sheet: one frame per keyword (1.4 s in, after the entrance)
    f = ImageFont.truetype(CHIP_FONT, 18)
    for p in plan["keywords"]:
        img = frame(out / "preview_visual.mp4", p["t"] + 1.4)
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((640, 360))
        d = ImageDraw.Draw(pil)
        for b in p["faces"]:
            d.rectangle([b[0] * 640, b[1] * 360, b[2] * 640, b[3] * 360], outline=(0, 255, 255), width=2)
        tile = Image.new("RGB", (640, 390)); tile.paste(pil, (0, 30))
        ImageDraw.Draw(tile).text((8, 5), f"{int(p['t'] // 60)}:{p['t'] % 60:04.1f}  {p['anim']} · {p['reason']}",
                                  font=f, fill=(255, 80, 80) if p["covers_face"] else (255, 255, 255))
        tiles.append(tile)
    cols = 2
    sheet = Image.new("RGB", (640 * cols, 390 * ((len(tiles) + cols - 1) // cols)), (20, 20, 20))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 640, (i // cols) * 390))
    sheet.save(out / "visual_sheet.jpg", quality=88)
    for p in plan["keywords"]:
        print(f"{int(p['t'] // 60)}:{p['t'] % 60:04.1f} [{p['mood']}] {p['anim']} {p['red']} / {p['white']} → {p['reason']}"
              f"  X{p['x']}/{p['x_white']} Y{p['y_red']}/{p['y_white']} 字号{p['size']}")
    print(len(plan["steps"]), "step chips,", len(plan["badges"]), "speed badges")


if __name__ == "__main__":
    main()
