"""GPU transcription with word timestamps (faster-whisper large-v3 on CUDA).
Usage: python transcribe.py <out_dir> <audio1> [audio2 ...] [--vad]
Writes <name>.json (segments + words) and <name>.txt next to out_dir.
--vad: Silero VAD. Tested on a 17-min process demo: WORSE (prompt leaked, real lines lost) -> default off
       everywhere; rely on the suspect flag instead.
v0.8: every segment gets no_speech / logprob and a "suspect" flag (whisper invents text on silence, e.g.
「请不吝点赞 订阅 转发 打赏支持明镜与点点栏目」 over 27 s of keyboard noise); suspect lines are marked "?" in the .txt."""
import json
import os
import pathlib
import site
import sys
import time

# make pip-installed NVIDIA DLLs (cuBLAS / cuDNN) visible on Windows
for base in site.getsitepackages() + [site.getusersitepackages()]:
    nv = pathlib.Path(base) / "nvidia"
    if nv.exists():
        for b in nv.glob("*/bin"):
            os.add_dll_directory(str(b))
            os.environ["PATH"] = str(b) + os.pathsep + os.environ["PATH"]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gpu_env  # noqa: E402,F401
from faster_whisper import WhisperModel  # noqa: E402

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
print(f"model loaded in {time.time() - t0:.1f}s", flush=True)

VAD = "--vad" in sys.argv
HALLU = ("点赞", "订阅", "打赏", "明镜", "by ", "谢谢观看", "简体中文", "标点符号")


def suspect(s):
    dur = s.end - s.start
    n = len(s.text.strip())
    return bool((s.no_speech_prob > 0.6 and s.avg_logprob < -0.8) or any(h in s.text for h in HALLU)
                or (dur > 12 and n / dur < 1.0))


for a in [x for x in sys.argv[2:] if not x.startswith("--")]:
    a = pathlib.Path(a)
    t1 = time.time()
    # read 16 kHz mono WAV ourselves (newer PyAV breaks faster-whisper's decoder); extract with ffmpeg first
    import wave
    import numpy as np
    with wave.open(str(a)) as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1, "need 16 kHz mono wav"
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, info = model.transcribe(
        audio, language="zh", beam_size=5, word_timestamps=True, vad_filter=VAD,
        initial_prompt="以下是普通话口播，使用简体中文和标点符号。",
        condition_on_previous_text=False)
    data = {"file": a.name, "duration": info.duration, "segments": []}
    lines = []
    for s in segs:
        sus = suspect(s)
        data["segments"].append({"start": s.start, "end": s.end, "text": s.text, "suspect": sus,
                                 "no_speech": round(s.no_speech_prob, 3), "logprob": round(s.avg_logprob, 3),
                                 "words": [{"s": w.start, "e": w.end, "w": w.word, "p": w.probability} for w in (s.words or [])]})
        lines.append(f"{'?' if sus else ' '}[{s.start:6.2f}-{s.end:6.2f}] {s.text}")
    (out / f"{a.stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{a.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{a.name}: {info.duration:.1f}s audio in {time.time() - t1:.1f}s", flush=True)
