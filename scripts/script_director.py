"""Build the script director's dossier: every phrase with clip/time/duration, a contact sheet per clip,
pause statistics and repeated phrases, so the agent can plan hook / structure / cuts (see SCRIPT_DIRECTOR.md).

python script_director.py <out_dir> <clip1.mp4> <clip1_tx.json> [<clip2.mp4> <clip2_tx.json> ...]
"""
from style import ST  # noqa: E402  (v1.1.1)
import difflib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platform_env import FF, FFPROBE, ff_font, font as sys_font, hwaccel, venc  # noqa: E402,F401  (v1.1 cross-platform)
PUNCT = "，。！？,.!?"


def phrases(tx):
    d = json.load(open(tx, encoding="utf-8"))
    words = [w for s in d["segments"] for w in s["words"]]
    out, cur, st = [], "", None
    for w in words:
        st = w["s"] if st is None else st
        cur += w["w"]
        if any(p in w["w"] for p in PUNCT) or len(cur) >= 16:
            out.append((st, w["e"], cur.strip()))
            cur, st = "", None
    if cur:
        out.append((st, words[-1]["e"], cur.strip()))
    gaps = [b["s"] - a["e"] for a, b in zip(words, words[1:]) if b["s"] - a["e"] >= ST["rhythm"]["pause_min_s"]]
    return d["duration"], out, gaps


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    pairs = list(zip(sys.argv[2::2], sys.argv[3::2]))
    lines = ["# Script director dossier", ""]
    allp = []
    for i, (vid, tx) in enumerate(pairs, 1):
        dur, ph, gaps = phrases(tx)
        sheet = out / f"clip{i}_sheet.jpg"
        subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-y", *hwaccel(), "-i", vid, "-vf",
                        f"fps={8 / max(dur, 1)},scale=360:-1,tile=8x1", "-frames:v", "1", str(sheet)])
        lines += [f"## Clip {i} — `{pathlib.Path(vid).name}` · {dur:.1f}s",
                  f"![[{sheet.name}]]", "",
                  f"Pauses ≥{ST['rhythm']['pause_min_s']} s: {len(gaps)} (total {sum(gaps):.1f}s)", "",
                  "| # | start | end | dur | line |", "|---|---|---|---|---|"]
        for k, (a, b, t) in enumerate(ph, 1):
            lines.append(f"| {i}.{k} | {a:.2f} | {b:.2f} | {b - a:.1f} | {t} |")
            allp.append((i, a, t))
        lines.append("")
    # repeated claims across the whole footage (candidates to drop one of them)
    lines += ["## Possible repeats", ""]
    for x in range(len(allp)):
        for y in range(x + 1, len(allp)):
            s = difflib.SequenceMatcher(None, allp[x][2], allp[y][2]).ratio()
            if s > 0.6 and len(allp[x][2]) > 4:
                lines.append(f"- clip{allp[x][0]}@{allp[x][1]:.1f}s「{allp[x][2]}」≈ clip{allp[y][0]}@{allp[y][1]:.1f}s「{allp[y][2]}」({s:.0%})")
    (out / "dossier.md").write_text("\n".join(lines), encoding="utf-8")
    print("dossier:", out / "dossier.md")


if __name__ == "__main__":
    main()
