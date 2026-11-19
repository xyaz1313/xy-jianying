"""Cut points + pause removal by AUDIO ENERGY (v1.2, sample run 2026-11-19: problem log #5 #6 #14 #15 #16 #24).

python cut_points.py plan.json edl.json [--strips]
plan.json: {"file": "clip.mp4", "tx": "tx.json", "wav": "clip16k.wav",
            "parts": [{"part": "HOOK", "a": 176.24, "b": 179.02, "note": "...", "exact": false}, ...]}
  a / b  = the word edges you chose from the transcript (whisper is ±0.4 s off in BOTH directions)
  exact  = true -> use a / b as given (cut points verified by hand: energy strip + the fragment transcribed alone)

Rules (each one is a defect the owner heard in v1):
  OUT (b): walk forward from b to real silence and keep a short tail INSIDE the silence; if a NEW syllable starts first
           (energy rises again after a dip) stop at that dip. Never earlier than b - 0.02 (moving earlier ate 货/模块/里).
  IN  (a): the same backwards (never later than a + 0.02).
  Pauses : every run of energy-silence >= pause_min inside a kept range is cut, keeping 0.08 s after the speech and
           0.04 s before the next (silences hidden inside one long whisper word are found too: 「这个 … 恋爱」).
  No "glue the short tag phrase" rule here (it kept the first 「第三」 of 「第三 第三」).
After rendering the preview ALWAYS run listen_back.py (it hears swallowed / doubled words) — this file only places cuts.
"""
import json
import pathlib
import sys
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from style import ST  # noqa: E402

FR = 0.02
SIL = 0.15                      # silence = RMS below 15 % of the speaker's median speech level


def load(wav):
    w = wave.open(str(wav))
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    fr = x[:len(x) // 320 * 320].reshape(-1, 320)
    rms = np.sqrt((fr ** 2).mean(1))
    med = np.median(rms[rms > np.percentile(rms, 40)])
    return np.convolve(rms / med, np.ones(2) / 2, "same")


def strip(lvl, t, n=10):
    i = int(round(t / FR))
    s = "".join(" .:-=+*#%@"[min(9, int(lvl[k] * 5))] for k in range(max(0, i - n), min(len(lvl), i + n)))
    return s[:n] + "^" + s[n:]


def _walk(lvl, start, stop, step, tail):
    """walk from frame start towards stop; return (frame, kind)."""
    silent = lvl < SIL
    lo, k = lvl[start], start
    best_k = start
    dipped = False
    while (k < stop) if step > 0 else (k > stop):
        if silent[k] and silent[min(max(k + step, 0), len(lvl) - 1)]:
            j = k
            while 0 <= j + step < len(lvl) and silent[j + step] and abs(j + step - k) * FR < tail:
                j += step
            return j, "silence"
        if lvl[k] < lo:
            lo, best_k = lvl[k], k
            dipped = True
        elif dipped and lvl[k] > max(2.5 * lo, lo + 0.25):        # a new syllable starts: stay in the valley
            return best_k, "valley"
        k += step
    return best_k, "valley"


def out_point(lvl, b):
    k, kind = _walk(lvl, int(round((b - 0.02) / FR)), min(len(lvl) - 1, int(round((b + 0.45) / FR))), +1, 0.06)
    return k * FR, kind


def in_point(lvl, a):
    k, kind = _walk(lvl, int(round((a + 0.02) / FR)), max(0, int(round((a - 0.6) / FR))), -1, 0.03)
    return k * FR, kind


def main():
    P = json.load(open(sys.argv[1], encoding="utf-8"))
    lvl = load(P["wav"])
    pmin = ST["rhythm"]["pause_min_s"]
    edl, pauses = [], []
    for p in P["parts"]:
        if p.get("exact"):
            a, ka, b, kb = p["a"], "exact", p["b"], "exact"
        else:
            a, ka = in_point(lvl, p["a"])
            b, kb = out_point(lvl, p["b"])
        edl.append({"clip": p.get("clip", 1), "a": round(a, 3), "b": round(b, 3), "part": p["part"], "note": p.get("note", "")})
        print(f'{p["part"]:8s} in {p["a"]:8.2f}->{a:8.2f} ({ka:7s}) |{strip(lvl, a)}|   '
              f'out {p["b"]:8.2f}->{b:8.2f} ({kb:7s}) |{strip(lvl, b)}|')
        k, i1 = int(round(a / FR)), int(round(b / FR))
        while k < i1:
            if lvl[k] < SIL:
                j = k
                while j < i1 and lvl[j] < SIL:
                    j += 1
                s0, s1 = k * FR, j * FR
                if s1 - s0 >= pmin and s0 > a + 0.05 and s1 < b - 0.05:
                    pauses.append([round(s0 + 0.08, 3), round(s1 - 0.04, 3)])
                k = j
            else:
                k += 1
    E = {"files": [P["file"]], "speed": ST["rhythm"]["speed"], "volume_db": ST["rhythm"]["voice_db"],
         "pauses": {"1": sorted(pauses)}, "edl": edl}
    json.dump(E, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    src = sum(e["b"] - e["a"] for e in edl)
    cut = sum(q - p for p, q in pauses)
    print(f"{len(edl)} parts · {len(pauses)} pauses ({cut:.1f}s) · final ≈ {(src - cut) / E['speed']:.1f}s")
    print("strip: 20 ms per char, ' ' silence … '@' loud, ^ = the cut. A cut on '#%@' is inside speech: check it.")


if __name__ == "__main__":
    main()
