"""Usage: python keyword_anim_check.py <visual_plan.json> <report.json>  (applies + verifies every keyword's entrance animation)
Read back the entrance animation of every keyword clip: 动画 → 入场, find the card with the teal selection border."""
import difflib
import json
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import jy_ui  # noqa: E402
import panel  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402

plan = json.load(open(sys.argv[1], encoding="utf-8"))["keywords"]
tl.layout()
tl.calibrate()
out = []


def selected_anim():
    R = (panel.PANEL[0], 200, panel.PANEL[2], 1450)
    a = np.asarray(jy_ui.grab(R)).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    teal = (g > 150) & (b > 150) & (r < 90)
    ys, xs = np.nonzero(teal)
    labels = [h for h in jy_ui.texts(R) if not h[0].startswith("ABC") and len(h[0]) >= 2]
    if not len(xs):
        return None
    # the teal border surrounds the card; its label sits just below the card
    cx, cy = R[0] + np.median(xs), R[1] + ys.max()
    near = [h for h in labels if abs(h[1] - cx) < 60 and 0 < h[2] - cy < 70]
    return near[0][0] if near else f"? ({int(cx)},{int(cy)})"


for k in plan:
    for line in (k["red"], k.get("white")):
        if not line:
            continue
        r = tl.L["tl"]
        xc = tl.x_of(k["t"] + 0.6)
        cands = jy_ui.texts((int(xc) - 140, r[1] + 60, int(xc) + 140, tl.L["track_y"] - 45))
        best = max(cands, key=lambda h: difflib.SequenceMatcher(None, line[:4], h[0].replace(" ", "")[:4]).ratio())
        jy_ui.click(best[1], best[2])
        time.sleep(0.8)
        panel.tab("文本")
        content = "".join(x[0] for x in jy_ui.texts((panel.P(20), 180, panel.PANEL[2], 280)))
        if difflib.SequenceMatcher(None, line, content.replace("?", "？").replace("!", "！")).ratio() < 0.6:
            out.append((k["t"], line, k["anim"], f"wrong clip selected: {content}", "SKIP"))
            print(out[-1], flush=True)
            continue
        try:
            steps.set_anim(k["anim"])
            got, ok = k["anim"], True
        except steps.Pause as e:
            got, ok = str(e), False
        out.append((k["t"], line, k["anim"], got, "OK" if ok else "CHECK"))
        print(out[-1], flush=True)
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
