"""Render an edit decision list (EDL) to a quick review MP4: any order, any source ranges, pauses removed.

edl.json: {"files": [...], "speed": 1.1, "volume_db": 6, "pauses": {"2": [[a,b],...], ...},
           "edl": [{"clip": 3, "a": 9.84, "b": 19.22, "part": "HOOK", "note": "..."}, ...]}
python render_edl.py <edl.json> <out.mp4>
Prints the final timeline (start time of each part) so the plan can reference real times.
"""
import json
import pathlib
import subprocess
import sys

FF = next(pathlib.Path.home().joinpath("AppData/Local/Microsoft/WinGet/Packages").rglob("ffmpeg.exe"))

E = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
sp = E.get("speed", 1.0)
pauses = {int(k): v for k, v in E.get("pauses", {}).items()}


def minus_pauses(clip, a, b):
    ranges = [(a, b)]
    for p0, p1 in sorted(pauses.get(clip, [])):
        nxt = []
        for r0, r1 in ranges:
            if p1 <= r0 or p0 >= r1:
                nxt.append((r0, r1))
            else:
                if p0 > r0:
                    nxt.append((r0, p0))
                if p1 < r1:
                    nxt.append((p1, r1))
        ranges = nxt
    return [(r0, r1) for r0, r1 in ranges if r1 - r0 > 0.05]


parts, fc, n, t = [], [], 0, 0.0
for item in E["edl"]:
    start = t
    for a, b in minus_pauses(item["clip"], item["a"], item["b"]):
        i = item["clip"] - 1
        fc.append(f"[{i}:v]trim={a}:{b},setpts=PTS-STARTPTS,scale=1920:1080,fps=30[v{n}];"
                  f"[{i}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=48000[a{n}]")
        n += 1
        t += (b - a) / sp
    parts.append((round(start, 2), item.get("part", ""), item.get("note", "")))
fc.append("".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append(f"[cv]setpts=PTS/{sp}[v];[ca]atempo={sp},volume={E.get('volume_db', 0)}dB,alimiter=limit=0.95[a]")
script = pathlib.Path(out).with_suffix(".filter.txt")
script.write_text(";".join(fc), encoding="utf-8")
cmd = [str(FF), "-hide_banner", "-loglevel", "error", "-y"]
for f in E["files"]:
    cmd += ["-hwaccel", "cuda", "-i", f]
cmd += ["-/filter_complex", str(script), "-map", "[v]", "-map", "[a]", "-c:v", "h264_nvenc", "-preset", "p5",
        "-b:v", "8M", "-c:a", "aac", "-b:a", "192k", out]
subprocess.run(cmd, check=True)
for s, p, note in parts:
    print(f"{int(s // 60)}:{s % 60:05.2f}  {p:10s} {note}")
print(f"total {int(t // 60)}:{t % 60:05.2f}")
