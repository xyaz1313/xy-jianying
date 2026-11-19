"""成片回听 (v1.2, problem log #21): transcribe the rendered preview and diff it against what the EDL should say.

python listen_back.py <edl.json> <src_tx.json> <preview.mp4|preview16k.wav> [--prompt "热词…"]
Prints every place where the preview says LESS (swallowed tail: 货 / 模块 / 里 / 看) or MORE (stutter / cough /
「第三 第三」) than the script, with the preview time and whether it sits on a seam.

Caveats learned on the sample run — read before trusting it:
  * whisper MERGES repeats («跟我说 | 跟我说» heard once) and DROPS half-cut syllables at clip edges, and in a full-file
    pass it can also HALLUCINATE a repeat («第一 第一» was really 「嗯」). So a flag here is a lead, not a verdict:
    confirm each one by transcribing the 0.3–1 s fragment ALONE (retx.py --window) and by the energy strip.
  * expected text comes from the source transcript, whose word times are ±0.4 s off -> many harmless 1-char hits
    near seams; look at the ones with whole words.
"""
import difflib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import asr  # noqa: E402
from platform_env import FF  # noqa: E402

PUNCT = r"[\s，。！？,.!?、；;：:]"


def kept(E, a, b):
    r = [(a, b)]
    for p0, p1 in E["pauses"].get("1", []):
        n = []
        for r0, r1 in r:
            if p1 <= r0 or p0 >= r1:
                n.append((r0, r1))
            else:
                if p0 > r0:
                    n.append((r0, p0))
                if p1 < r1:
                    n.append((p1, r1))
        r = n
    return r


def main():
    E = json.load(open(sys.argv[1], encoding="utf-8"))
    src = [w for s in json.load(open(sys.argv[2], encoding="utf-8"))["segments"] for w in s["words"]]
    prev = pathlib.Path(sys.argv[3])
    prompt = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else None
    wav = prev
    if prev.suffix.lower() != ".wav":
        wav = prev.with_suffix(".16k.wav")
        subprocess.run([str(FF), "-v", "error", "-y", "-i", str(prev), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    sp = E["speed"]
    exp, seams, t = [], [], 0.0
    for s in E["edl"]:
        for a, b in kept(E, s["a"], s["b"]):
            for w in src:
                m = (w["s"] + w["e"]) / 2
                if a <= m < b:
                    for c in re.sub(PUNCT, "", w["w"]):
                        exp.append((t + (m - a) / sp, c))
            t += (b - a) / sp
            seams.append(t)
    got = [(w["s"], c) for s in asr.transcribe(asr.load_wav(wav), prompt) for w in s["words"]
           for c in re.sub(PUNCT, "", w["w"])]
    A, B = "".join(c for _, c in exp), "".join(c for _, c in got)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    print(f"expected {len(A)} chars · heard {len(B)} · similarity {sm.ratio():.3f}")
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        tt = got[j1][0] if j1 < len(got) else exp[min(i1, len(exp) - 1)][0]
        seam = min(seams, key=lambda x: abs(x - tt))
        flag = "SEAM" if abs(seam - tt) < 1.0 else "    "
        ctx = B[max(0, j1 - 6):j1] + "【" + B[j1:j2] + "】" + B[j2:j2 + 6]
        print(f"{int(tt // 60)}:{tt % 60:04.1f} {flag} {op:7s} should「{A[i1:i2]}」 heard「{B[j1:j2]}」  …{ctx}…")


if __name__ == "__main__":
    main()
