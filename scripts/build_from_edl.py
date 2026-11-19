"""Mode A from an approved EDL (script director output): any order, pauses removed, speed + volume, as a NEW
剪映 draft. Writes a layout JSON for the live runner: segments (clip/src/start/end) and 'cuts' = every seam with
what happened there (气口 removed / 删段 / 换序 = moved), with the spoken words on both sides for the overlay.

python build_from_edl.py <edl.json> <draft_name> <layout_out.json> --tx 1=tx1.json 2=tx2.json ...
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import platform_env  # noqa: E402  (v1.1: finds the draft library in any agent's skills folder)
SKILL = platform_env.dependency_skill("jianying-editor-reliable")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(SKILL, "scripts", "vendor"))
from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("edl"); ap.add_argument("name"); ap.add_argument("out")
ap.add_argument("--tx", nargs="*", default=[])
a = ap.parse_args()
E = json.load(open(a.edl, encoding="utf-8"))
sp, vol = E.get("speed", 1.0), 10 ** (E.get("volume_db", 0) / 20)
pauses = {int(k): v for k, v in E.get("pauses", {}).items()}
TX = {int(k): v for k, v in (x.split("=", 1) for x in a.tx)}
words = {c: [w for s in json.load(open(p, encoding="utf-8"))["segments"] for w in s["words"]] for c, p in TX.items()}


def minus(clip, s0, s1):
    rs = [(s0, s1)]
    for p0, p1 in sorted(pauses.get(clip, [])):
        nx = []
        for r0, r1 in rs:
            if p1 <= r0 or p0 >= r1:
                nx.append((r0, r1))
            else:
                if p0 > r0:
                    nx.append((r0, p0))
                if p1 < r1:
                    nx.append((p1, r1))
        rs = nx
    return [r for r in rs if r[1] - r[0] > 0.05]


def said(clip, t0, t1, n=9, tail=False):
    s = "".join(w["w"] for w in words.get(clip, []) if t0 <= w["s"] < t1).strip("，。,.!?！？ ")
    return s[-n:] if tail else s[:n]


p = JyProject(project_name=a.name)
p._ensure_track(draft.TrackType.video, "Main")
mats, segs, t_us = {}, [], 0
for it in E["edl"]:
    c = it["clip"]
    if c not in mats:
        mats[c] = draft.VideoMaterial(p._stage_local_asset(E["files"][c - 1]))
        if not p._first_video_resolved:
            p.script.width, p.script.height = mats[c].width, mats[c].height
            p._first_video_resolved = True
    for s0, s1 in minus(c, it["a"], it["b"]):
        tl_len = round((s1 - s0) * 1e6 / sp)
        seg = draft.VideoSegment(mats[c], trange(t_us, tl_len), source_timerange=trange(round(s0 * 1e6), round((s1 - s0) * 1e6)),
                                 speed=sp, volume=vol)
        p.script.add_segment(seg, "Main")
        segs.append({"clip": c, "src": [s0, s1], "start": t_us / 1e6, "end": (t_us + tl_len) / 1e6, "part": it.get("part", "")})
        t_us += tl_len

cuts = []
for x, y in zip(segs, segs[1:]):
    if x["clip"] == y["clip"] and 0 <= y["src"][0] - x["src"][1] < 1.5:
        kind, ln = "气口", y["src"][0] - x["src"][1]
    elif x["clip"] == y["clip"] and y["src"][0] > x["src"][1]:
        kind, ln = "删段", y["src"][0] - x["src"][1]
    else:
        kind, ln = ("钩子提前" if x.get("part") == "HOOK" else "换序"), 0.0
    if ln < 0.05 and kind == "气口":
        continue
    cuts.append({"kind": kind, "len": round(ln, 2), "seam": x["end"],
                 "before": said(x["clip"], x["src"][1] - 2.5, x["src"][1] + 0.05, tail=True),
                 "after": said(y["clip"], y["src"][0] - 0.05, y["src"][0] + 2.5)})
res = p.save()
json.dump({"save": res, "total": t_us / 1e6, "segments": segs, "cuts": cuts}, open(a.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({"save": res["status"], "total": round(t_us / 1e6, 2), "segments": len(segs), "cuts": len(cuts)}))
