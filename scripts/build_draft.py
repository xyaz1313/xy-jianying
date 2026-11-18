"""Mode A: assemble clips on the main track in order at a given speed, as a NEW 剪映 draft (never touches
existing/encrypted drafts). Bypasses the skill's H.264 re-encode: 剪映 reads HEVC natively.

python build_draft.py <draft_name> <speed> <clip1> [clip2 ...]
Prints JSON with each clip's timeline start/end (seconds) for the live-edit planner.
"""
import json
import os
import sys

SKILL = os.path.expanduser(r"~\.claude\skills\jianying-editor-reliable")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(SKILL, "scripts", "vendor"))
from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402

name, speed, clips = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
p = JyProject(project_name=name)
track = "Main"
p._ensure_track(draft.TrackType.video, track)
t, layout = 0, []
for c in clips:
    staged = p._stage_local_asset(c)          # copy into the draft folder so it is self-contained
    mat = draft.VideoMaterial(staged)
    if not p._first_video_resolved:
        p.script.width, p.script.height = mat.width, mat.height
        p._first_video_resolved = True
    src = mat.duration
    seg = draft.VideoSegment(mat, trange(t, round(src / speed)), source_timerange=trange(0, src), speed=speed)
    p.script.add_segment(seg, track)
    layout.append({"clip": os.path.basename(c), "start": t / 1e6, "end": (t + round(src / speed)) / 1e6, "src_dur": src / 1e6})
    t += round(src / speed)
print(json.dumps({"save": p.save(), "layout": layout}, ensure_ascii=False))
