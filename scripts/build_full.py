"""v1.2 MAIN ROUTE — the whole edit as ONE new 剪映 draft, written as a file (no screenshots, no clicking).

python build_full.py <edl.json> <visual_plan.json> <subs.json> <draft_name>
  cuts + speed + volume (EDL) · filter over 0 → end (style.json filter) · subtitles (subs_from_cut.py, style.json
  subtitle look) · every keyword: two lines, own colour / position / 字号 / 描边 / entrance animation / duration
Then in 剪映 only: beauty_all.py (select-all, one preset) -> look -> export_draft.py when the owner says so.

Sample run 2026-11-19: 2.4 s for a 9:11 video, 418 subtitle lines, 25 keywords — versus 2+ hours of OCR clicking that
never finished. Facts that shaped this file:
  * 剪映 ENCRYPTS draft_content.json as soon as it saves a draft -> never patch an opened draft; build a NEW one
    (a fresh name; 剪映 must be restarted to list it).
  * Position units: 剪映 UI X/Y = 2 per pixel on the 4K canvas -> draft transform = X / 3840, Y / 2160 (half canvas).
  * 字号 / 描边宽度 are the same numbers as in the UI. Two subtitle lines may not overlap on one track.
  * Beauty (美颜美体 preset) is NOT in the draft library -> beauty_all.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import platform_env  # noqa: E402
SKILL = platform_env.dependency_skill("jianying-editor-reliable")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(SKILL, "scripts", "vendor"))
from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402
from pyJianYingDraft import trange  # noqa: E402
from style import ST  # noqa: E402

W_UI, H_UI = 3840.0, 2160.0
ANIM = {"打字机I": "打字机_I", "打字机II": "打字机_II", "打字机III": "打字机_III"}


def minus(pauses, clip, s0, s1):
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


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def main():
    edl_p, plan_p, subs_p, name = sys.argv[1:5]
    if len(name) > 5:
        raise SystemExit(f"草稿名「{name}」太长：5 个字以内（剪映首页会截断）")
    E = json.load(open(edl_p, encoding="utf-8"))
    V = json.load(open(plan_p, encoding="utf-8"))
    SUBS = sorted(json.load(open(subs_p, encoding="utf-8")), key=lambda s: s["t0"])
    sp, vol = E.get("speed", 1.0), 10 ** (E.get("volume_db", 0) / 20)
    pauses = {int(k): v for k, v in E.get("pauses", {}).items()}

    p = JyProject(project_name=name)
    S = p.script
    p._ensure_track(draft.TrackType.video, "Main")
    mats, t_us = {}, 0
    for it in E["edl"]:
        c = it["clip"]
        if c not in mats:
            mats[c] = draft.VideoMaterial(p._stage_local_asset(E["files"][c - 1]))
            if not p._first_video_resolved:
                S.width, S.height = mats[c].width, mats[c].height
                p._first_video_resolved = True
        for s0, s1 in minus(pauses, c, it["a"], it["b"]):
            n = round((s1 - s0) * 1e6 / sp)
            S.add_segment(draft.VideoSegment(mats[c], trange(t_us, n), source_timerange=trange(round(s0 * 1e6), round((s1 - s0) * 1e6)),
                                             speed=sp, volume=vol), "Main")
            t_us += n
    total = t_us

    F = ST["filter"]
    S.add_track(draft.TrackType.filter, "Filter")
    S.add_filter(getattr(draft.FilterType, F["name"]), trange(0, total), track_name="Filter", intensity=F["strength"])

    sub = ST["subtitle"]
    S.add_track(draft.TrackType.text, "Sub")
    n_sub, prev_end = 0, 0
    for i, s in enumerate(SUBS):
        nxt = round(SUBS[i + 1]["t0"] * 1e6) if i + 1 < len(SUBS) else total
        a = max(round(s["t0"] * 1e6), prev_end)
        b = min(round(s["t1"] * 1e6), nxt, total)
        if b - a < 100000:
            continue
        prev_end = b
        S.add_segment(draft.TextSegment(
            s["text"], trange(a, b - a), font=getattr(draft.FontType, sub["font"]),
            style=draft.TextStyle(size=sub["size"], color=rgb(sub["color"]), align=1),
            border=draft.TextBorder(color=(0, 0, 0), width=sub["stroke"]),
            clip_settings=draft.ClipSettings(transform_y=sub["y"] / H_UI)), "Sub")
        n_sub += 1

    K = ST["keyword"]
    tracks = {}

    def put(line, kw, text, color, x, y):
        a = round(kw["t"] * 1e6)
        d = round(min(kw.get("dur", 3.0), total / 1e6 - kw["t"]) * 1e6)
        seg = draft.TextSegment(
            text, trange(a, d), font=getattr(draft.FontType, K["font"]),
            style=draft.TextStyle(size=kw["size"], color=rgb(color), align=1),
            border=draft.TextBorder(color=(0, 0, 0), width=K["stroke"]),
            clip_settings=draft.ClipSettings(transform_x=x / W_UI, transform_y=y / H_UI))
        seg.add_animation(getattr(draft.TextIntro, ANIM.get(kw["anim"], kw["anim"])))
        for i in range(6):                                   # first track of this line that is free at [a, a+d)
            tn = f"KW_{line}_{i}"
            if tn not in tracks:
                S.add_track(draft.TrackType.text, tn, relative_index=10 + (2 * i + (line == "w")))
                tracks[tn] = []
            if all(a >= e or a + d <= s0 for s0, e in tracks[tn]):
                S.add_segment(seg, tn)
                tracks[tn].append((a, a + d))
                return
        raise SystemExit(f"no free track for {text}")

    for kw in V["keywords"]:
        put("c", kw, kw["red"], kw["color"], kw["x"], kw["y_red"])
        if kw.get("white"):
            put("w", kw, kw["white"], K["second_line_color"], kw.get("x_white", kw["x"]), kw["y_white"])

    res = p.save()
    print(json.dumps({"save": res.get("status"), "draft": name, "total": round(total / 1e6, 2), "total_frames_30": round(total / 1e6 * 30),
                      "subtitles": n_sub, "keywords": len(V["keywords"]), "keyword_tracks": len(tracks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
