"""Transcript repair helpers (v1.2, problem log #17 #19 #25 #27).

python retx.py suspects <tx.json>                      -> words whose average char lasts > 0.45 s (a stutter, cough,
                                                          half-sentence restart or a pause is hidden inside them)
python retx.py window <clip16k.wav> a-b [a-b ...]      -> each window transcribed ALONE (no context) + energy strip
python retx.py fragment <clip16k.wav> a-b [a-b ...]    -> plain text of short fragments (is this 0.4 s 「嗯」? 「第三」?)

Sample run facts: 「统」 was tagged 2.9 s long and held 「当我在完成整个自媒体的，[cough] 当我在…」; one 「哪怕」 was really
「哪怕你用 [0.8 s] 哪怕你用 WorkBuddy」; the sign-off 「Respect」 came out as 「就是被」 and 「阿们」 was invented in silence.
Always pass the hotwords as the prompt (style.json subtitle.hotwords + this episode's words).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import asr  # noqa: E402
import cut_points  # noqa: E402
from style import ST  # noqa: E402

PROMPT = ", ".join(ST["subtitle"]["hotwords"]) + "。"


def suspects(tx):
    for s in json.load(open(tx, encoding="utf-8"))["segments"]:
        for w in s["words"]:
            t = w["w"].strip()
            n = len(t) if not t.isascii() else max(1, len(t) / 3)
            if t and (w["e"] - w["s"]) / n > 0.45:
                print(f"{w['s']:8.2f}-{w['e']:8.2f}  {w['e'] - w['s']:4.2f}s  「{t}」")


def main():
    cmd = sys.argv[1]
    if cmd == "suspects":
        return suspects(sys.argv[2])
    x = asr.load_wav(sys.argv[2])
    lvl = cut_points.load(sys.argv[2]) if cmd == "window" else None
    for arg in sys.argv[3:]:
        a, b = map(float, arg.split("-"))
        seg = x[int(a * asr.SR):int(b * asr.SR)]
        if cmd == "fragment":
            print(f"{a:.2f}-{b:.2f}  「{asr.text(seg, PROMPT)}」")
            continue
        ws = [(a + w["s"], a + w["e"], w["w"]) for s in asr.transcribe(seg, PROMPT) for w in s["words"]]
        print(f"\n== {a}-{b}: " + " ".join(f"{t}({s:.2f}-{e:.2f})" for s, e, t in ws))
        env = "".join(" .:-=+*#%@"[min(9, int(lvl[k] * 5))] for k in range(int(a / 0.02), min(len(lvl), int(b / 0.02))))
        for k in range(0, len(env), 100):
            print(f"   {a + k * 0.02:8.2f} {env[k:k + 100]}")


if __name__ == "__main__":
    main()
