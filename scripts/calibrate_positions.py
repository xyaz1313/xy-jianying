"""Usage: python calibrate_positions.py <out_dir>  (throwaway draft; keyword 月入十万？ around 9.5 s; frames at 11 s)
Glyph-box calibration with the text DESELECTED (no selection frame / rotate handle in the preview)."""
import json
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import jy_ui  # noqa: E402
import panel  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402

SC = sys.argv[1]
tl.layout()
tl.calibrate()
tl.seek(11.0)
EMPTY = ((panel.PLAYER[0] + panel.PLAYER[2]) / 2, panel.PLAYER[1] + 120)   # grey player area above the video


def frame_rect(a):
    # geometric 16:9 fit inside the player (pixel-based detection mis-crops dark footage)
    h, w = a.shape[:2]
    fh = round(w * 9 / 16)
    y0 = (h - fh) // 2
    return 0, y0, w, y0 + fh


def select():
    x, y = steps.find_segment("月入十万？")
    jy_ui.click(x, y)
    time.sleep(0.8)
    panel.tab("文本")


def shot():
    jy_ui.click(*EMPTY)          # deselect
    time.sleep(1.3)
    return np.asarray(jy_ui.grab(panel.PLAYER)).astype(int)


select()
steps.set_xy(9000, 9000)
base = shot()
res = []
for (X, Y, size) in [(0, 0, 14), (0, 0, 8), (0, 0, 11), (1500, 800, 14), (3018, 1608, 8)]:
    select()
    panel.set_value("字号", size)
    steps.set_xy(X, Y)
    a = shot()
    x0, y0, x1, y1 = frame_rect(a)
    d = np.abs(a - base).sum(axis=2)
    d[:, :x0] = 0; d[:, x1:] = 0; d[:y0] = 0; d[y1:] = 0
    ys, xs = np.nonzero(d > 90)
    W, H = x1 - x0, y1 - y0
    box = [(xs.min() - x0) / W, (ys.min() - y0) / H, (xs.max() + 1 - x0) / W, (ys.max() + 1 - y0) / H]
    m = {"X": X, "Y": Y, "size": size, "box": [round(v, 4) for v in box],
         "cx": round((box[0] + box[2]) / 2, 4), "cy": round((box[1] + box[3]) / 2, 4),
         "w": round(box[2] - box[0], 4), "h": round(box[3] - box[1], 4)}
    print(m)
    res.append(m)
    from PIL import Image
    Image.fromarray(a.astype("uint8")).save(f"{SC}/g_{X}_{Y}_{size}.png")
json.dump(res, open(f"{SC}/calib_glyph.json", "w"), indent=1)
