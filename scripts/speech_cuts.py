"""Sentence-safe cuts — ONE rule for every video type (v0.8, owner 2026-11-18: "话要一段一段讲完").

Why: whisper's word end times are early and its phrases are short, so a cut placed "at the end of the line" can
eat the last syllable (「这才是重点」 lost 「重点」) or stop mid-sentence (「我可以弄很多线，同时就很帅啊」).
The fix is not one-off EDL edits but a rule every cut passes through:

  snap_cut(segs, pcm, a, b)
    1. a cut inside a whisper phrase moves OUT to the phrase edge (keep the whole phrase)
    2. short tag phrases glued right after it (对吧 / 啊 / 嘛, <= 1 s, gap < 0.15 s) are kept
    3. each cut moves to the quietest 20 ms nearby (end: [b-0.05, b+0.45], start: [a-0.4, a+0.05])

  check(segs, pcm, t, side) -> "✗ …" (speech chopped) / "⚠ …" (too tight) / ""   — word level

CLI (run on EVERY EDL before showing the owner a preview, and again before the 剪映 build):
  python speech_cuts.py check <edl.json> [--tx 1=tx1.json 2=tx2.json ...]
    - process-demo EDL (sources / tx / hooks / body)  or  talking-head EDL (files / edl / pauses, needs --tx)
    - prints every cut that would chop speech, exit code 1 if any
"""
import json
import pathlib
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platform_env import FF, FFPROBE, ff_font, font as sys_font, hwaccel, venc  # noqa: E402,F401  (v1.1 cross-platform)
SR = 16000


def load(tx_json, media=None, wav=None):
    """(phrases without whisper's suspect ones, 16 kHz float pcm) — from a wav, or decoded from the media file."""
    segs = [x for x in json.load(open(tx_json, encoding="utf-8"))["segments"] if not x.get("suspect")]
    if wav:
        import wave
        with wave.open(str(wav)) as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)
    else:
        raw = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-i", str(media), "-vn", "-ac", "1",
                              "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return segs, pcm


def quiet(pcm, lo, hi):
    a, b = max(0, int(lo * SR)), min(len(pcm), int(hi * SR))
    if b - a < 640:
        return (lo + hi) / 2
    e = np.convolve(pcm[a:b] ** 2, np.ones(320), "valid")
    return (a + int(np.argmin(e)) + 160) / SR


def snap_cut(segs, pcm, a, b):
    a0, b0 = a, b
    for x in segs:
        if x["start"] < a < x["end"] - 0.05:
            a = x["start"]
        if x["start"] + 0.05 < b < x["end"]:
            b = x["end"]
    for x in segs:
        if 0 <= x["start"] - b < 0.15 and x["end"] - x["start"] <= 1.0:
            b = x["end"]
    a = quiet(pcm, a - 0.4, a + 0.05)
    b = quiet(pcm, b - 0.05, b + 0.45)
    note = f"snap {a0:.2f}-{b0:.2f} -> {a:.2f}-{b:.2f}" if abs(a - a0) > 0.1 or abs(b - b0) > 0.1 else ""
    return a, b, note


def _words(segs):
    return sorted(((w["s"], w["e"], w["w"].strip()) for x in segs for w in x.get("words", [])), key=lambda w: w[0])


def check(segs, pcm, t, side="end"):
    """Word-level judgement of one cut. side='end': the kept part ends at t; side='start': it starts at t.
    ✗ = speech is chopped (cut inside a word, or the sentence continues within 0.3 s);
    ⚠ = too tight (whisper ends words early — the last syllable's tail may be lost)."""
    ws = _words(segs)
    for s0, e0, w in ws:
        if s0 + 0.03 < t < e0 - 0.03:
            return f"✗ inside the word 「{w}」 ({s0:.2f}-{e0:.2f})"
    if side == "end":
        nxt = next((w for w in ws if w[0] >= t), None)
        prev = next((w for w in reversed(ws) if w[1] <= t), None)
        if nxt and nxt[0] - t < 0.3 and prev and t - prev[1] < 0.3:
            return f"✗ sentence goes on: 「{prev[2]}」|「{nxt[2]}」 (next word {nxt[0] - t:.2f} s later)"
        if prev and t - prev[1] < 0.12:
            return f"⚠ tight after 「{prev[2]}」 ({t - prev[1]:.2f} s) — tail may be cut"
    else:
        prev = next((w for w in reversed(ws) if w[1] <= t), None)
        nxt = next((w for w in ws if w[0] >= t), None)
        if prev and t - prev[1] < 0.3 and nxt and nxt[0] - t < 0.3:
            return f"✗ starts mid-sentence: 「{prev[2]}」|「{nxt[2]}」"
        if nxt and nxt[0] - t < 0.06:
            return f"⚠ tight before 「{nxt[2]}」 ({nxt[0] - t:.2f} s) — onset may be cut"
    return ""


def _cuts_demo(E):
    out = []
    for part in [*(h["segs"] for h in E.get("hooks", {}).values()), E["body"]]:
        for s in part:
            if "audio_from" in s:
                out.append((s["audio_from"][0], s["audio_from"][1], s["audio_from"][2], s["label"]))
            elif s.get("audio") and s.get("speed", 1) < 2:
                out.append((s["src"], s.get("a_snapped", s["a"]), s.get("b_snapped", s["b"]), s["label"]))
    return out


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "check":
        print(__doc__)
        sys.exit(2)
    E = json.load(open(sys.argv[2], encoding="utf-8"))
    bad = 0
    if "body" in E:                                    # process-demo EDL
        cache = {}
        for key, a, b, label in _cuts_demo(E):
            if key not in cache:
                jp, wp = E["tx"][key]
                cache[key] = load(jp, wav=wp)
            segs, pcm = cache[key]
            sa, sb, _ = snap_cut(segs, pcm, a, b)
            for side, t, st in (("start", a, sa), ("end", b, sb)):
                p = check(segs, pcm, t, side)
                if p:
                    bad += p.startswith("✗")
                    print(f"{label[:34]:34s} {side:5s} {t:8.2f}: {p}  → snap_cut moves it to {st:.2f}")
    else:                                              # talking-head EDL (build_from_edl format)
        tx = dict(x.split("=", 1) for x in sys.argv[sys.argv.index("--tx") + 1:]) if "--tx" in sys.argv else {}
        cache = {}
        for seg in E["edl"]:
            c = str(seg["clip"])
            if c not in tx:
                continue
            if c not in cache:
                cache[c] = load(tx[c], media=E["files"][int(c) - 1])
            segs, pcm = cache[c]
            cuts = [("start", seg["a"]), ("end", seg["b"])]
            cuts += [("end", p0) for p0, p1 in E.get("pauses", {}).get(c, []) if seg["a"] < p0 < seg["b"]]
            cuts += [("start", p1) for p0, p1 in E.get("pauses", {}).get(c, []) if seg["a"] < p1 < seg["b"]]
            for side, t in cuts:
                p = check(segs, pcm, t, side)
                if p:
                    bad += p.startswith("✗")
                    print(f"clip {c} {seg.get('note', '')[:28]:28s} {side:5s} {t:8.2f}: {p}")
    print(f"{bad} cut(s) would chop speech" if bad else "✓ every cut is between sentences")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
