"""Turn transcripts + a removal list into a frame-exact live-edit plan for 剪映.

Input  plan.json: {"speed":1.1, "clips":[{"name","dur","tx":"<transcript.json>","remove":[[a,b],...]}...],
                   "fix":{"wrong":"right",...}, "keywords":[{"text","src_clip","src_t","dur"}...]}
Output: edit_plan.json (timeline-time removals, processed back-to-front), subs.srt, keywords.srt
"""
import json
import pathlib
import sys

P = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
sp = P["speed"]
PUNCT = "，。！？,.!?、；;：:"


def final_map(ci, offsets_final, clip):
    rem = sorted(clip["remove"])

    def f(t):  # source time -> final timeline time (None if removed)
        cut = 0.0
        for a, b in rem:
            if t >= b:
                cut += b - a
            elif t > a:
                return None
        return offsets_final[ci] + (t - cut) / sp
    return f


# timeline offsets before cutting (all clips at speed) and after cutting
off0, off1, acc0, acc1 = [], [], 0.0, 0.0
for c in P["clips"]:
    off0.append(acc0); off1.append(acc1)
    acc0 += c["dur"] / sp
    acc1 += (c["dur"] - sum(b - a for a, b in c["remove"])) / sp

# removals in timeline time, back to front so earlier positions never move
removals = []
for ci, c in enumerate(P["clips"]):
    for a, b in c["remove"]:
        removals.append({"clip": ci + 1, "src": [a, b], "tl": [off0[ci] + a / sp, off0[ci] + min(b, c["dur"]) / sp]})
removals.sort(key=lambda r: -r["tl"][0])

# subtitles: words -> lines broken at punctuation / 14 chars, mapped to the final timeline
def fix(s):
    for k, v in P.get("fix", {}).items():
        s = s.replace(k, v)
    return s


lines = []
for ci, c in enumerate(P["clips"]):
    fm = final_map(ci, off1, c)
    tx = json.loads(pathlib.Path(c["tx"]).read_text(encoding="utf-8"))
    words = [w for s in tx["segments"] for w in s["words"]]
    cur, cs, ce = "", None, None
    for w in words:
        a, b = fm(w["s"]), fm(w["e"])
        if a is None or b is None:
            continue
        txt = w["w"].strip()
        end_here = any(p in txt for p in PUNCT)
        clean = "".join(ch for ch in txt if ch not in PUNCT)
        if cs is None:
            cs = a
        cur += clean
        ce = b
        if end_here or len(cur) >= 14:
            if cur:
                lines.append((cs, ce, fix(cur)))
            cur, cs = "", None
    if cur:
        lines.append((cs, ce, fix(cur)))
# make lines contiguous-ish (no flicker): extend each to next start if gap < 0.3s
for i in range(len(lines) - 1):
    s, e, t = lines[i]
    if lines[i + 1][0] - e < 0.3:
        lines[i] = (s, lines[i + 1][0] - 0.01, t)


def ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(items):
    return "\n".join(f"{i + 1}\n{ts(s)} --> {ts(e)}\n{t}\n" for i, (s, e, t) in enumerate(items))


(out / "subs.srt").write_text(srt(lines), encoding="utf-8")
kws = []
for k in P.get("keywords", []):
    c = P["clips"][k["src_clip"] - 1]
    t = final_map(k["src_clip"] - 1, off1, c)(k["src_t"])
    if t is not None:
        kws.append((t, t + k.get("dur", 1.6), k["text"]))
(out / "keywords.srt").write_text(srt(sorted(kws)), encoding="utf-8")
plan = {"speed": sp, "timeline_before": acc0, "timeline_after": acc1, "removals": removals,
        "subtitle_lines": len(lines), "keywords": [{"t": a, "text": t} for a, _, t in sorted(kws)]}
(out / "edit_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in plan.items() if k != "removals"}, ensure_ascii=False, indent=1))
print("removals:", len(removals))
