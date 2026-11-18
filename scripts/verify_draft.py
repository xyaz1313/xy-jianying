"""Usage: python verify_draft.py <visual_plan.json> <frames_dir> <sheet.jpg>
Step D verification on the finished draft: preview frame at every keyword (+1.5 s, after the entrance) and at
5 other points; face check with the director's detector on the real 剪映 preview; contact sheet for the vault."""
import json
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import director  # noqa: E402
import jy_ui  # noqa: E402
import panel  # noqa: E402
import timeline as tl  # noqa: E402

plan_p, out_dir, sheet_p = sys.argv[1], sys.argv[2], sys.argv[3]
__import__("os").makedirs(out_dir, exist_ok=True)  # v0.7: create the frames dir
kws = json.load(open(plan_p, encoding="utf-8"))["keywords"]
tl.layout()
tl.calibrate()
total = tl.total_frames() / tl.FPS
pts = [(k["t"] + 1.5, f"{k['red']} / {k.get('white') or ''}") for k in kws]
pts += [(0.6, "开头"), (15.0, "证据段"), (30.0, "证据段"), (57.0, "收尾前"), (total - 0.4, "结尾")]
tiles, report = [], []
font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 20)


def frame_rect(a):
    # geometric 16:9 fit inside the player (pixel-based detection mis-crops dark footage)
    h, w = a.shape[:2]
    fh = round(w * 9 / 16)
    y0 = (h - fh) // 2
    return 0, y0, w, y0 + fh


for i, (t, label) in enumerate(pts):
    tl.seek(t)
    jy_ui.click((panel.PLAYER[0] + panel.PLAYER[2]) / 2, panel.PLAYER[1] + 120)   # deselect (grey player area)
    time.sleep(1.2)
    im = jy_ui.grab(panel.PLAYER)
    a = np.asarray(im)
    x0, y0, x1, y1 = frame_rect(a)
    fr = im.crop((x0, y0, x1, y1))
    fr.save(f"{out_dir}/frame_{i:02d}_{t:05.1f}.png")
    bgr = cv2.cvtColor(np.asarray(fr.resize((960, 540))), cv2.COLOR_RGB2BGR)
    faces = director.faces(bgr)
    tile = fr.resize((640, 360))
    d = ImageDraw.Draw(tile)
    for b in faces:
        d.rectangle([b[0] * 640, b[1] * 360, b[2] * 640, b[3] * 360], outline=(0, 255, 255), width=2)
    # v0.7: label strip ABOVE the frame (it hid the top keyword line, which now sits 1.7 % from the top)
    lab = Image.new("RGB", (640, 388), (0, 0, 0))
    lab.paste(tile, (0, 28))
    tile, d = lab, ImageDraw.Draw(lab)
    d.text((6, 3), f"{int(t // 60)}:{t % 60:04.1f}  {label}", font=font, fill=(255, 255, 255))
    tiles.append(tile)
    report.append({"t": round(t, 2), "label": label, "faces": [[round(v, 3) for v in b] for b in faces]})
    print(f"{t:6.2f}s {label}  faces={len(faces)}")
cols = 4
sheet = Image.new("RGB", (640 * cols, 388 * ((len(tiles) + cols - 1) // cols)), (20, 20, 20))
for i, tile in enumerate(tiles):
    sheet.paste(tile, ((i % cols) * 640, (i // cols) * 388))
sheet.save(sheet_p, quality=88)
json.dump({"total": total, "frames": report}, open(f"{out_dir}/verify.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total", total)
