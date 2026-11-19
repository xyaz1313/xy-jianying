"""Subtitles = transcribe the RENDERED CUT itself (v1.2, problem log #49).

python subs_from_cut.py <preview.mp4|cut16k.wav> <subs.json> [subs.srt] [--hotwords 投喂,复用,...]
Why from the cut and not from the source transcript: the cut's timeline IS the draft's timeline (no mapping), and the
removed retakes / coughs are simply not in it. The source-transcript route produced 「他不就大概 / 大概半个小时」 and lost
「为什么」 / 「哪怕」 at piece edges.
Hotwords: style.json subtitle.hotwords + --hotwords (this episode). Word fixes: style.json subtitle.fixes.
Lines: ≤ 14 chars, break at punctuation / pauses > 0.6 s, 1–2 char lines folded into the previous one, no punctuation.
CHECK the result: grep the hook line, the sign-off (Respect) and every hotword before building the draft.
"""
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import asr  # noqa: E402
from platform_env import FF  # noqa: E402
from style import ST  # noqa: E402

PUNCT = "，。！？,.!?、；;：:"
TRAD = str.maketrans("們當為麼個這說話時頭會實來對還歡體關點樣場經過萬憑像門東發後問題習書車長開間見覺訊認識讓",
                     "们当为么个这说话时头会实来对还欢体关点样场经过万凭像门东发后问题习书车长开间见觉讯认识让")


def ts(v):
    return f"{int(v // 3600):02d}:{int(v % 3600 // 60):02d}:{int(v % 60):02d},{int(round(v % 1 * 1000)) % 1000:03d}"


def main():
    src = pathlib.Path(sys.argv[1])
    out_json = sys.argv[2]
    out_srt = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
    extra = sys.argv[sys.argv.index("--hotwords") + 1].split(",") if "--hotwords" in sys.argv else []
    words = list(dict.fromkeys(ST["subtitle"]["hotwords"] + [w for w in extra if w]))
    fixes = ST["subtitle"].get("fixes", [])
    wav = src
    if src.suffix.lower() != ".wav":
        wav = src.with_suffix(".16k.wav")
        subprocess.run([str(FF), "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    segs = asr.transcribe(asr.load_wav(wav), ", ".join(words) + "。")
    lines = []
    for s in segs:
        cur = None
        for w in s["words"]:
            t = w["w"].strip()
            if not t:
                continue
            if cur and (len(cur["text"]) >= 14 or w["s"] - cur["t1"] > 0.6):
                lines.append(cur)
                cur = None
            if cur is None:
                cur = {"t0": w["s"], "t1": w["e"], "text": ""}
            ascii_join = cur["text"][-1:].isascii() and cur["text"][-1:].isalnum() and t[:1].isascii() and t[:1].isalnum()
            cur["text"] += (" " if cur["text"] and ascii_join else "") + t
            cur["t1"] = w["e"]
            if t[-1:] in PUNCT:
                lines.append(cur)
                cur = None
        if cur:
            lines.append(cur)
    merged = []
    for L in lines:
        if merged and len(L["text"].strip(PUNCT + " ")) <= 2 and L["t0"] - merged[-1]["t1"] < 0.5 \
                and len(merged[-1]["text"]) + len(L["text"]) <= 16:
            merged[-1]["text"] += L["text"]
            merged[-1]["t1"] = L["t1"]
        else:
            merged.append(L)
    out = []
    for i, L in enumerate(merged):
        t = L["text"].translate(TRAD)
        for a, b in fixes:
            t = t.replace(a, b)
        t = re.sub(r"\s+", " ", re.sub(f"[{PUNCT}]", " ", t)).strip()
        if not t:
            continue
        nxt = merged[i + 1]["t0"] if i + 1 < len(merged) else L["t1"] + 0.3
        out.append({"t0": round(L["t0"], 3), "t1": round(max(min(nxt, L["t1"] + 0.6), L["t0"] + 0.3), 3), "text": t})
    json.dump(out, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    if out_srt:
        with open(out_srt, "w", encoding="utf-8") as f:
            for i, s in enumerate(out, 1):
                f.write(f"{i}\n{ts(s['t0'])} --> {ts(s['t1'])}\n{s['text']}\n\n")
    print(f"{len(out)} subtitle lines · first: {out[0]['text'] if out else ''} · last: {out[-1]['text'] if out else ''}")


if __name__ == "__main__":
    main()
