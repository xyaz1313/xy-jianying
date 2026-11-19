"""Shared speech recognition for the v1.2 tools (retx / subs_from_cut / listen_back / seam checks).

One loaded model per process; NVIDIA -> faster-whisper CUDA, Apple Silicon -> mlx-whisper, else CPU (platform_env).
  load_wav(path)                      -> float32 mono 16 kHz array (ffmpeg extracts it first: `-ac 1 -ar 16000`)
  transcribe(audio, prompt=None)      -> [{"start","end","text","words":[{"s","e","w"}]}]   (word timestamps)
  text(audio, prompt=None)            -> plain text (no timestamps, for quick "what is said here" checks)
Audio is passed as an array, never a path (newer PyAV breaks faster-whisper's own decoder: 「metadata_errors」).
"""
import pathlib
import sys
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import platform_env  # noqa: E402

SR = 16000
ENGINE, DEVICE, CTYPE = platform_env.whisper_cfg()
MODEL = platform_env.whisper_model_name()
_model = None


def load_wav(path):
    with wave.open(str(path)) as wf:
        assert wf.getframerate() == SR and wf.getnchannels() == 1, "need 16 kHz mono wav (ffmpeg -ac 1 -ar 16000)"
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def _fw():
    global _model
    if _model is None:
        if DEVICE == "cuda":
            import gpu_env  # noqa: F401
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL, device=DEVICE, compute_type=CTYPE)
    return _model


def transcribe(audio, prompt=None, words=True):
    prompt = prompt or "以下是普通话口播，使用简体中文和标点符号。"
    out = []
    if ENGINE == "mlx":
        import mlx_whisper
        r = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, language="zh", word_timestamps=words,
                                   initial_prompt=prompt, condition_on_previous_text=False)
        for g in r.get("segments", []):
            out.append({"start": g["start"], "end": g["end"], "text": g["text"],
                        "words": [{"s": w["start"], "e": w["end"], "w": w["word"]} for w in g.get("words", [])]})
        return out
    segs, _ = _fw().transcribe(audio, language="zh", beam_size=5, word_timestamps=words, initial_prompt=prompt,
                               condition_on_previous_text=False)
    for s in segs:
        out.append({"start": s.start, "end": s.end, "text": s.text,
                    "words": [{"s": w.start, "e": w.end, "w": w.word} for w in (s.words or [])]})
    return out


def text(audio, prompt=None):
    return "".join(s["text"] for s in transcribe(audio, prompt, words=False)).strip()
