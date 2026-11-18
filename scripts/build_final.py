"""Mode A for a real edit: put only the KEPT ranges of each clip on the main track (frame-exact cuts from the
transcript plan), at the given speed and volume, as a NEW 剪映 draft. Writes a layout JSON for the live runner
(segment positions, seams = where each cut happened, cut descriptions).

python build_final.py <plan.json> <draft_name> <layout_out.json> --files f1 f2 f3 [--volume-db 6]
"""
import argparse
import json
import os
import sys

SKILL = os.path.expanduser(r"~\.claude\skills\jianying-editor-reliable")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(SKILL, "scripts", "vendor"))
from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("name"); ap.add_argument("out")
ap.add_argument("--files", nargs="+", required=True)
ap.add_argument("--volume-db", type=float, default=0.0)
a = ap.parse_args()

P = json.load(open(a.plan, encoding="utf-8"))
sp = P["speed"]
vol = 10 ** (a.volume_db / 20)
p = JyProject(project_name=a.name)
p._ensure_track(draft.TrackType.video, "Main")
t_us, segs, cuts = 0, [], []


def words_of(tx):
    d = json.load(open(tx, encoding="utf-8"))
    return [w for s in d["segments"] for w in s["words"]]


for ci, (c, f) in enumerate(zip(P["clips"], a.files)):
    mat = draft.VideoMaterial(p._stage_local_asset(f))
    if not p._first_video_resolved:
        p.script.width, p.script.height = mat.width, mat.height
        p._first_video_resolved = True
    dur = min(c["dur"], mat.duration / 1e6)
    rem = sorted(c["remove"])
    keep, cur = [], 0.0
    for r0, r1 in rem:
        if r0 > cur:
            keep.append((cur, r0))
        cur = max(cur, r1)
    if cur < dur:
        keep.append((cur, dur))
    W = words_of(c["tx"])
    for r0, r1 in rem:  # describe each cut with its spoken context
        before = "".join(w["w"] for w in W if r0 - 2.0 < w["e"] <= r0 + 0.05)[-9:].strip("，。,.!?！？ ")
        after = "".join(w["w"] for w in W if r1 - 0.05 <= w["s"] < r1 + 2.0)[:9].strip("，。,.!?！？ ")
        kind = "开头空拍" if r0 <= 0.001 else ("结尾空拍" if r1 >= dur - 0.01 else ("骗子原声" if r1 - r0 > 5 else "气口"))
        cuts.append({"clip": ci + 1, "src": [r0, r1], "len": round(r1 - r0, 2), "kind": kind,
                     "before": before, "after": after})
    for k0, k1 in keep:
        src = trange(round(k0 * 1e6), round((k1 - k0) * 1e6))
        tl_len = round((k1 - k0) * 1e6 / sp)
        seg = draft.VideoSegment(mat, trange(t_us, tl_len), source_timerange=src, speed=sp, volume=vol)
        p.script.add_segment(seg, "Main")
        segs.append({"clip": ci + 1, "src": [k0, k1], "start": t_us / 1e6, "end": (t_us + tl_len) / 1e6})
        t_us += tl_len

# seam (timeline time) for each cut: the end of the kept segment that precedes it in the same clip
for cut in cuts:
    prev = [s for s in segs if s["clip"] == cut["clip"] and s["src"][1] <= cut["src"][0] + 1e-6]
    nxt = [s for s in segs if s["clip"] == cut["clip"] and s["src"][0] >= cut["src"][1] - 1e-6]
    cut["seam"] = prev[-1]["end"] if prev else (nxt[0]["start"] if nxt else None)
res = p.save()
json.dump({"save": res, "total": t_us / 1e6, "segments": segs, "cuts": cuts}, open(a.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({"save": res, "total": t_us / 1e6, "segments": len(segs), "cuts": len(cuts)}, ensure_ascii=False))
