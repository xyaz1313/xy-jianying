"""Mode A for a process-demo video (v0.8): the approved cut + its visual plan -> a NEW 剪映 draft.

python build_demo.py <edl_demo.json> <timeline.json> <visual_plan_demo.json> <voice.json> <draft_name> <layout_out.json>

voice.json = {"p": "<denoised 48k wav of source p>", "i": "..."}  (highpass 80 Hz + afftdn, same as the preview)

Tracks written (everything that must be frame-exact goes in here; the filmed live run adds the rest):
  Main   video  every segment of timeline.json: source range (sentence-snapped a/b), its speed, MUTED
  Voice  audio  the speech of every 1.1x segment and every borrowed line (audio_from), from the denoised wav, same
                speed as its picture -> denoise is baked in (owner: 「降噪一下」)
  BGM    audio  visual_plan["bgm"]: 「22 22」 at -6.3 dB, 0 -> end, no fades (owner rules 2026-11-18)
  Steps  text   (empty unless --labels) 「STEP n · …」 chips — engineering labels, never in a delivered video
  Speed  text   「»» 加速 ×N」 on every segment faster than 1.15x, top-right, yellow on black
Layout JSON (for live_run): segments with clip 1 = p (screen footage) / 2 = i (talking head), seams for step 2.
"""
import json
import os
import sys

SKILL = os.path.expanduser(r"~\.claude\skills\jianying-editor-reliable")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(SKILL, "scripts", "vendor"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402

import director  # noqa: E402

E = json.load(open(sys.argv[1], encoding="utf-8"))
T = json.load(open(sys.argv[2], encoding="utf-8"))
P = json.load(open(sys.argv[3], encoding="utf-8"))
VOICE = json.load(open(sys.argv[4], encoding="utf-8"))
NAME, OUT = sys.argv[5], sys.argv[6]
CLIP = {"p": 1, "i": 2}
us = lambda s: round(s * 1e6)  # noqa: E731

p = JyProject(project_name=NAME)
sc = p.script
p._ensure_track(draft.TrackType.video, "Main")
for name, kind in (("Voice", draft.TrackType.audio), ("BGM", draft.TrackType.audio),
                   ("Steps", draft.TrackType.text), ("Speed", draft.TrackType.text)):
    sc.add_track(kind, name)

vmat, amat = {}, {}
for key, path in E["sources"].items():
    vmat[key] = draft.VideoMaterial(p._stage_local_asset(path))
    if not p._first_video_resolved:
        sc.width, sc.height = vmat[key].width, vmat[key].height
        p._first_video_resolved = True
for key, path in VOICE.items():
    amat[key] = draft.AudioMaterial(p._stage_local_asset(path))

segs_out, t_us = [], 0
for s in T["segments"]:
    a, b = s.get("a_snapped", s["a"]), s.get("b_snapped", s["b"])
    tl_len = us(s["out_end"]) - us(s["out_start"])
    # picture: speed so that the source range fills exactly the approved output length
    speed = (b - a) / (tl_len / 1e6)
    seg = draft.VideoSegment(vmat[s["src"]], trange(t_us, tl_len), source_timerange=trange(us(a), us(b - a)),
                             speed=speed, volume=0.0)
    sc.add_segment(seg, "Main")
    # voice
    if "audio_from" in s:
        k, aa, ab = s["audio_from"]
        snap = s.get("snap", "")
        if "->" in snap:                                     # borrowed audio was snapped too
            aa, ab = [float(x) for x in snap.split("->")[1].strip().split("-")]
        asp = (ab - aa) / (tl_len / 1e6)
        sc.add_segment(draft.AudioSegment(amat[k], trange(t_us, tl_len), source_timerange=trange(us(aa), us(ab - aa)),
                                          speed=asp, volume=1.0), "Voice")
    elif s.get("audio") and s.get("speed", 1) < 2:
        sc.add_segment(draft.AudioSegment(amat[s["src"]], trange(t_us, tl_len), source_timerange=trange(us(a), us(b - a)),
                                          speed=speed, volume=1.0), "Voice")
    # speed badge
    if s.get("speed") and s["speed"] > 1.15:
        txt = f"»» 加速 ×{s['speed']:g}"
        size = 6.0
        w = director.line_w(txt, size)
        cx, cy = 1 - 0.022 - w / 2, 0.065
        sc.add_segment(draft.TextSegment(
            txt, trange(t_us, tl_len),
            style=draft.TextStyle(size=size, bold=True, color=(1.0, 0.902, 0.0), align=1),
            background=draft.TextBackground(color="#000000", alpha=0.62, round_radius=0.3, height=0.3, width=0.2),
            clip_settings=draft.ClipSettings(transform_x=(cx - 0.5) * 2, transform_y=(0.5 - cy) * 2)), "Speed")
    segs_out.append({"clip": CLIP[s["src"]], "src": [a, b], "start": t_us / 1e6, "end": (t_us + tl_len) / 1e6,
                     "part": s.get("label", "")[:20], "speed": round(speed, 3), "step": s.get("step")})
    t_us += tl_len
total = t_us / 1e6

# step chips — owner rule 2026-11-18: engineering labels never go into the delivered draft (only with --labels)
for st in (P.get("steps", []) if "--labels" in sys.argv else []):
    a0, a1 = us(st["t"]), min(us(st["end"]), t_us)
    size = 5.0
    w = director.line_w(st["text"], size)
    cx, cy = 0.024 + w / 2, 0.935
    sc.add_segment(draft.TextSegment(
        st["text"], trange(a0, a1 - a0),
        style=draft.TextStyle(size=size, bold=True, color=(1.0, 1.0, 1.0), align=1),
        background=draft.TextBackground(color="#000000", alpha=0.65, round_radius=0.3, height=0.3, width=0.2),
        clip_settings=draft.ClipSettings(transform_x=(cx - 0.5) * 2, transform_y=(0.5 - cy) * 2)), "Steps")

# BGM
bg = P["bgm"]
bmat = draft.AudioMaterial(p._stage_local_asset(bg["file"]))
blen = min(t_us, bmat.duration)
sc.add_segment(draft.AudioSegment(bmat, trange(0, blen), source_timerange=trange(0, blen),
                                  volume=10 ** (bg["volume_db"] / 20)), "BGM")

# seams for the live run's step 2 (light trail at every cut)
cuts = []
for x, y in zip(segs_out, segs_out[1:]):
    if x["clip"] != y["clip"] or y["src"][0] < x["src"][1] - 0.05:
        kind, ln = "换序", 0.0
    elif y["src"][0] - x["src"][1] > 0.05:
        kind, ln = "删段", y["src"][0] - x["src"][1]
    else:
        kind, ln = "变速", 0.0
    cuts.append({"kind": kind, "len": round(ln, 2), "seam": x["end"],
                 "before": f"×{x['speed']:g}", "after": f"×{y['speed']:g}"})
res = p.save()
json.dump({"save": res, "total": total, "segments": segs_out, "cuts": cuts}, open(OUT, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({"save": res["status"], "total": round(total, 2), "segments": len(segs_out),
                  "badges": sum(1 for s in T["segments"] if s.get("speed") and s["speed"] > 1.15),
                  "steps": len(P["steps"])}, ensure_ascii=False))
