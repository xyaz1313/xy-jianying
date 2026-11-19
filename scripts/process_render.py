"""Render a PREVIEW of a process-demo EDL (v0.8, mode "process-demo") for the owner's script approval.

python process_render.py <edl_demo.json> <out_dir> [--hook A|B|C] [--first SECONDS]
  each segment -> 1280x720 30 fps clip (NVDEC decode, NVENC encode), then concat (no re-encode)
  speed >= 2 : picture sped up, muted, speed badge 「×N」 top-right
  audio_from : picture plays at whatever speed fits the borrowed audio's length
v0.8 owner rules (review of preview v1, 2026-11-18):
  - SPEECH IS NEVER CUT MID-SENTENCE (snap_cut, needs E["tx"][src] = [transcript.json, 16k.wav]): a cut inside a
    whisper phrase moves to the phrase edge, short tag phrases right after it (对吧 / 啊, <= 1 s, gap < 0.15 s) are
    kept, then the cut moves to the quietest 20 ms within 0.45 s (whisper word ends are early: 「这才是重点」 lost 重点).
  - EVERY sped-up part is labelled 「»» 加速 ×N」 (⏩ is not in 微软雅黑 -> tofu box) (pill, top-right): anything faster than the house 1.1x.
  - Speech audio is denoised (highpass 80 Hz + afftdn); in 剪映 the same is 音频降噪 on every clip.
Writes out_dir/preview_<hook>.mp4 and out_dir/timeline_<hook>.json (output time of every segment, used later for
the visual director and the 剪映 build).
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platform_env import FF, FFPROBE, ff_font, font as sys_font, hwaccel, venc  # noqa: E402,F401  (v1.1 cross-platform)
FONT = ff_font()
DENOISE = "highpass=f=80,afftdn=nr=14:nf=-32"
_TX = {}


def _load_tx(E, key):
    """(phrases, samples) for source key from E['tx'][key] = [transcript.json, audio16k.wav]; None if not given."""
    if key in _TX:
        return _TX[key]
    v = None
    if key in E.get("tx", {}):
        import wave
        import numpy as np
        jp, wp = E["tx"][key]
        segs = [x for x in json.load(open(jp, encoding="utf-8"))["segments"] if not x.get("suspect")]
        with wave.open(wp) as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)
        v = (segs, pcm)
    _TX[key] = v
    return v


def snap_cut(E, key, a, b):
    """Sentence-safe cut — the shared rule in speech_cuts.py (same rule for every video type)."""
    t = _load_tx(E, key)
    if not t:
        return a, b, ""
    import speech_cuts
    return speech_cuts.snap_cut(t[0], t[1], a, b)


def badge(speed):
    """v0.8 owner rule: every sped-up part is labelled (anything faster than the house 1.1x)."""
    if speed <= 1.15:
        return ""
    return (f",drawtext=fontfile='{FONT}':text='»» 加速 ×{speed:g}':fontsize=46:fontcolor=0xFFE600:"
            "box=1:boxcolor=black@0.6:boxborderw=16:x=w-tw-44:y=36")


def segs_for(E, hook):
    out = list(E["hooks"][hook]["segs"]) if hook else []
    for s in E["body"]:
        if s.get("skip_with_hook") == hook:
            continue
        out.append(s)
    return out


def render_seg(E, s, path):
    src = E["sources"][s["src"]]
    a, b = s["a"], s["b"]
    vf = "scale=1280:720,fps=30"
    s["snap"] = ""
    if s.get("audio") and s.get("speed", 1.0) < 2:
        a, b, s["snap"] = snap_cut(E, s["src"], a, b)
        s["a_snapped"], s["b_snapped"] = round(a, 3), round(b, 3)
    if "audio_from" in s:
        asrc, aa, ab = s["audio_from"]
        aa, ab, s["snap"] = snap_cut(E, asrc, aa, ab)
        dur = ab - aa
        speed = (b - a) / dur
        args = ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", *hwaccel(), "-i", src,
                "-ss", f"{aa:.3f}", "-t", f"{dur:.3f}", "-i", E["sources"][asrc]]
        fc = (f"[0:v]setpts=(PTS-STARTPTS)/{speed:.5f},{vf}{badge(speed) if speed > 1.6 else ''}[v];"
              f"[1:a]asetpts=PTS-STARTPTS,{DENOISE},aresample=48000[a]")
    else:
        speed = s.get("speed", 1.0)
        dur = (b - a) / speed
        args = ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", *hwaccel(), "-i", src,
                "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        v = f"[0:v]setpts=(PTS-STARTPTS)/{speed:.5f},{vf}{badge(speed)}[v]"
        if s.get("audio") and speed < 2:
            t = []
            sp = speed
            while sp > 2.0:
                t.append("atempo=2.0"); sp /= 2.0
            t.append(f"atempo={sp:.5f}")
            fc = v + f";[0:a]asetpts=PTS-STARTPTS,{','.join(t)},{DENOISE},aresample=48000[a]"
        else:
            fc = v + ";[1:a]anull[a]"
    cmd = [str(FF), "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *venc(26),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ac", "2", str(path)]
    subprocess.run(cmd, check=True)
    return dur


def main():
    E = json.load(open(sys.argv[1], encoding="utf-8"))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    hook = sys.argv[sys.argv.index("--hook") + 1] if "--hook" in sys.argv else "C"
    first = float(sys.argv[sys.argv.index("--first") + 1]) if "--first" in sys.argv else None
    tmp = out / f"_segs_{hook}"; tmp.mkdir(exist_ok=True)
    t, tl, files = 0.0, [], []
    for i, s in enumerate(segs_for(E, hook)):
        if first is not None and t >= first:
            break
        p = tmp / f"{i:03d}.mp4"
        d = render_seg(E, s, p)
        if s.get("snap"):
            print(f"  seg {i}: {s['snap']}  ({s['label'][:30]})")
        tl.append({"i": i, "out_start": round(t, 2), "out_end": round(t + d, 2), **s})
        t += d
        files.append(p)
    (tmp / "list.txt").write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    name = f"preview_{hook}" + ("_hook15s" if first else "")
    tl_name = f"timeline_{hook}" + ("_hook15s" if first else "")
    subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i",
                    str(tmp / "list.txt"), "-c", "copy", str(out / f"{name}.mp4")], check=True)
    json.dump({"hook": hook, "total": round(t, 2), "segments": tl}, open(out / f"{tl_name}.json", "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{name}: {len(files)} segments, {int(t // 60)}:{t % 60:04.1f}")


if __name__ == "__main__":
    main()
