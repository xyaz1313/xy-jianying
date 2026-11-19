"""xy-jianying v1.1 — one place that knows which machine we are on and which backend to use.

Every other script imports from here instead of hard-coding CUDA / NVENC / C:\\Windows\\Fonts.

  from platform_env import FF, OS, hwaccel, venc, font, whisper_cfg, ocr_cuda, tier

Backends (chosen automatically, cached in <skill>/.cache/backend.json, re-probed by `doctor.py`):
  OS     win | mac | linux
  GPU    nvidia  (CUDA decode, NVENC encode, faster-whisper CUDA, OCR CUDA)
         apple   (Apple Silicon: VideoToolbox decode/encode, mlx-whisper on Metal if installed, OCR on CPU)
         amd     (integrated / discrete Radeon: AMF encode, whisper + OCR on CPU)
         intel   (QSV encode, whisper + OCR on CPU)
         cpu     (libx264, everything on CPU)
Override for testing:  XY_BACKEND=cpu | amd | intel | apple | nvidia     (e.g. "pretend there is no NVIDIA card")
"""
import glob
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
CACHE = SKILL / ".cache"
OS = "win" if sys.platform == "win32" else "mac" if sys.platform == "darwin" else "linux"


# ---------------------------------------------------------------- ffmpeg
def _find_ffmpeg():
    exe = "ffmpeg.exe" if OS == "win" else "ffmpeg"
    for env in ("XY_FFMPEG", "FFMPEG"):
        p = os.environ.get(env)
        if p and os.path.exists(p):
            return pathlib.Path(p)
    cands = []
    if OS == "mac":
        # v1.1.1 (Mac test): Homebrew's plain `ffmpeg` has no drawtext (Chinese captions / speed badges) and its
        # ffprobe crashed on a missing libx265 dylib -> prefer the keg-only `ffmpeg-full` that install.sh installs
        cands += ["/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg"]
    for c in cands:
        if os.path.exists(c):
            return pathlib.Path(c)
    p = shutil.which("ffmpeg")
    if p:
        return pathlib.Path(p)
    cands = []
    if OS == "win":
        cands += glob.glob(str(pathlib.Path.home() / "AppData/Local/Microsoft/WinGet/Packages/**/ffmpeg.exe"),
                           recursive=True)
        cands += glob.glob(r"C:\ffmpeg\bin\ffmpeg.exe") + glob.glob(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe")
    else:
        cands += ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for c in cands:
        if os.path.exists(c):
            return pathlib.Path(c)
    return pathlib.Path(exe)          # let the call fail with a clear "ffmpeg not found" from the OS


FF = _find_ffmpeg()
FFPROBE = FF.with_name("ffprobe.exe" if OS == "win" else "ffprobe")


# ---------------------------------------------------------------- GPU / encoder probe
def _ff_ok(args, timeout=25):
    """Run a tiny ffmpeg job; True if it worked (an encoder can be *listed* but still fail on this machine)."""
    try:
        r = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-y", *args],
                           capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def _probe_encoder(name):
    return _ff_ok(["-f", "lavfi", "-i", "color=c=gray:s=640x360:d=0.5", "-frames:v", "8", "-c:v", name,
                   "-f", "null", "-"])


def _has_nvidia():
    if OS == "mac":
        return False
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True,
                           text=True, errors="replace", timeout=10)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def probe(force=False):
    """Detect the backend once and cache it. Returns dict(gpu=..., encoder=..., h265=..., gpu_names=[...])."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / "backend.json"
    if f.exists() and not force:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("ffmpeg") == str(FF) and d.get("os") == OS:
                return d
        except Exception:
            pass
    d = {"os": OS, "ffmpeg": str(FF), "machine": platform.machine(), "gpu": "cpu",
         "encoder": "libx264", "h265": "libx265", "hwaccel": []}
    if OS == "mac":
        if platform.machine() == "arm64":
            d["gpu"] = "apple"
        if _probe_encoder("h264_videotoolbox"):
            d.update(encoder="h264_videotoolbox", h265="hevc_videotoolbox", hwaccel=["-hwaccel", "videotoolbox"])
    else:
        if _has_nvidia() and _probe_encoder("h264_nvenc"):
            d.update(gpu="nvidia", encoder="h264_nvenc", h265="hevc_nvenc", hwaccel=["-hwaccel", "cuda"])
        elif _probe_encoder("h264_amf"):
            d.update(gpu="amd", encoder="h264_amf", h265="hevc_amf")
        elif _probe_encoder("h264_qsv"):
            d.update(gpu="intel", encoder="h264_qsv", h265="hevc_qsv")
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def _backend():
    d = dict(probe())
    o = os.environ.get("XY_BACKEND", "").lower()
    if o:                                         # forced (tests): only switch to what this machine can really do
        table = {"cpu": ("cpu", "libx264", "libx265", []),
                 "amd": ("amd", "h264_amf", "hevc_amf", []),
                 "intel": ("intel", "h264_qsv", "hevc_qsv", []),
                 "apple": ("apple", "h264_videotoolbox", "hevc_videotoolbox", ["-hwaccel", "videotoolbox"]),
                 "nvidia": ("nvidia", "h264_nvenc", "hevc_nvenc", ["-hwaccel", "cuda"])}
        if o in table:
            g, e, h, hw = table[o]
            d.update(gpu=g, encoder=e, h265=h, hwaccel=hw, forced=o)
    return d


B = _backend()
GPU = B["gpu"]


def hwaccel():
    """Decoder args to put BEFORE -i. NVIDIA: cuda, Mac: videotoolbox, everyone else: plain CPU decode."""
    return list(B["hwaccel"])


def venc(q=23, preset="medium", hevc=False):
    """Encoder args for a preview / intermediate file at roughly constant quality q (lower = better, ~18–28)."""
    e = B["h265"] if hevc else B["encoder"]
    if e.endswith("_nvenc"):
        p = {"fast": "p3", "medium": "p4", "slow": "p6"}.get(preset, "p4")
        return ["-c:v", e, "-preset", p, "-rc", "vbr", "-cq", str(q), "-b:v", "0"]
    if e.endswith("_videotoolbox"):
        # VideoToolbox has no CQ; -q:v 1..100 (higher = better). Map q 18..28 -> ~75..50
        return ["-c:v", e, "-q:v", str(max(35, min(85, int(120 - 2.5 * q)))), "-allow_sw", "1"]
    if e.endswith("_amf"):
        return ["-c:v", e, "-quality", "balanced", "-rc", "cqp", "-qp_i", str(q), "-qp_p", str(q + 2)]
    if e.endswith("_qsv"):
        return ["-c:v", e, "-global_quality", str(q), "-preset", preset]
    return ["-c:v", "libx265" if hevc else "libx264", "-preset", "veryfast" if preset == "fast" else preset,
            "-crf", str(q)]


# ---------------------------------------------------------------- transcription / OCR
def whisper_cfg():
    """(engine, device, compute_type). engine: 'faster-whisper' or 'mlx' (Apple Silicon, much faster on M chips)."""
    if GPU == "nvidia":
        return "faster-whisper", "cuda", "float16"
    if GPU == "apple":
        try:
            import mlx_whisper  # noqa: F401
            return "mlx", "metal", "float16"
        except Exception:
            pass
    return "faster-whisper", "cpu", "int8"


def whisper_model_name():
    """large-v3 everywhere it is fast enough; on plain CPU use 'large-v3-turbo' unless XY_WHISPER_MODEL says otherwise."""
    m = os.environ.get("XY_WHISPER_MODEL")
    if m:
        return m
    eng, dev, _ = whisper_cfg()
    if eng == "mlx":
        return "mlx-community/whisper-large-v3-turbo"
    return "large-v3" if dev == "cuda" else "large-v3-turbo"


def ocr_cuda():
    return GPU == "nvidia"


def ocr_engine():
    """RapidOCR on CUDA (NVIDIA) or CPU (everyone else — fast enough for UI text)."""
    if ocr_cuda():
        import gpu_env  # noqa: F401
    import onnxruntime as ort
    ort.set_default_logger_severity(3)
    from rapidocr_onnxruntime import RapidOCR
    c = ocr_cuda()
    return RapidOCR(det_use_cuda=c, cls_use_cuda=c, rec_use_cuda=c)


# ---------------------------------------------------------------- fonts
_FONTS = {
    "win": ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"],
    "mac": ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc", "/Library/Fonts/Arial Unicode.ttf"],
    "linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
}


def font():
    """A bold CJK system font for preview labels (NOT the video's own fonts — those come from 剪映)."""
    for f in _FONTS[OS]:
        if os.path.exists(f):
            return f
    hits = glob.glob("/usr/share/fonts/**/*CJK*.tt*", recursive=True) + glob.glob("/usr/share/fonts/**/wqy*.tt*",
                                                                                   recursive=True)
    return hits[0] if hits else _FONTS[OS][0]


def ff_font():
    """font() escaped for an ffmpeg drawtext filter (the Windows drive colon must be escaped)."""
    return font().replace("\\", "/").replace(":", "\\:")


# ---------------------------------------------------------------- 剪映 locations
def jianying_data_dirs():
    """Candidate '…/JianyingPro/User Data' folders (fonts / effects cache, drafts)."""
    home = pathlib.Path.home()
    if OS == "win":
        la = os.environ.get("LOCALAPPDATA", "")
        return [pathlib.Path(la, "JianyingPro", "User Data")] if la else []
    if OS == "mac":
        return [home / "Movies" / "JianyingPro" / "User Data",
                home / "Library" / "Containers" / "com.lemon.lvpro" / "Data" / "Movies" / "JianyingPro" / "User Data"]
    return []


def jianying_font(name):
    """Path of a 剪映 cloud font (e.g. 仓耳榜黑.ttf) once 剪映 has downloaded it, else None."""
    for d in jianying_data_dirs():
        hits = glob.glob(str(d / "Cache" / "effect" / "**" / f"{name}.tt*"), recursive=True)
        if hits:
            return hits[0]
    return None


def drafts_root():
    """剪映 draft folder (…/com.lveditor.draft). config.json 'drafts_root' wins."""
    try:
        from config import CFG
        if CFG.get("drafts_root") and os.path.isdir(CFG["drafts_root"]):
            return CFG["drafts_root"]
    except Exception:
        pass
    home = pathlib.Path.home()
    cands = [d / "Projects" / "com.lveditor.draft" for d in jianying_data_dirs()]
    if OS == "mac":
        cands.append(home / "Movies" / "JianyingPro Drafts")
    for c in cands:
        if c.is_dir():
            return str(c)
    return str(cands[0]) if cands else None


def dependency_skill(name):
    """Sibling skill folder (e.g. jianying-editor-reliable) in any agent's skills dir."""
    home = pathlib.Path.home()
    here = SKILL.parent / name
    cands = [here] + [home / h / "skills" / name for h in (".claude", ".agents", ".codex", ".workbuddy", ".cursor",
                                                            ".kimi-code", ".kimi", ".trae", ".doubao")]
    for c in cands:
        if c.is_dir():
            return str(c)
    return str(here)


def tier():
    """What this machine can do. Returned to doctor / SKILL so the agent tells the user up front."""
    try:
        from config import jianying_exe
        jy = bool(jianying_exe())
    except Exception:
        jy = False
    if OS == "linux" or not jy:
        return "director-only"
    if OS == "mac":
        return "mac"
    return "full" if GPU == "nvidia" else "standard"


TIER_TEXT = {
    "full": "满配：Windows + NVIDIA，全部功能（显卡转写 / 渲染 / OCR）",
    "standard": "标准：Windows 无 N 卡，全部功能；转写走 CPU（慢几倍），编码走核显或 CPU",
    "mac": "Mac：全部功能（导演层 + 生成剪映草稿 + 实时操作剪映 + 光效层）；转写走苹果芯片",
    "director-only": "仅导演：没找到剪映（或 Linux）——转写 / 去气口 / 脚本 / 样片 / 字幕 / 封面能做，剪映那一步跳过",
}

if __name__ == "__main__":
    d = probe(force="--probe" in sys.argv)
    print(json.dumps({**B, "tier": tier(), "font": font(), "whisper": whisper_cfg(),
                      "whisper_model": whisper_model_name(), "drafts_root": drafts_root()},
                     ensure_ascii=False, indent=1))
