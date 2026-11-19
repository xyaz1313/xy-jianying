"""Local settings for xy-jianying (v1.0.0). Personal paths live in <skill>/config.json, never in code.

  from config import CFG, jianying_exe
  CFG["export_root"]  ->  e.g. D:\\视频成品   (default when config.json is missing)
  jianying_exe()      ->  path of JianyingPro.exe: config -> env JIANYING_EXE -> running process -> common install dirs
"""
import glob
import json
import os
import pathlib
import subprocess
import sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
IS_MAC = sys.platform == "darwin"
_EXPORT = r"D:\视频成品" if sys.platform == "win32" else str(pathlib.Path.home() / "Movies" / "视频成品")
DEFAULTS = {"jianying_exe": "", "drafts_root": "", "export_root": _EXPORT, "inbox_dir": "", "mirror_dir": "",
            "bgm": {"name": "", "file": "", "volume_db": -6.3}}


def _load():
    cfg = dict(DEFAULTS)
    p = SKILL / "config.json"
    if p.exists():
        try:
            cfg.update({k: v for k, v in json.load(open(p, encoding="utf-8")).items() if not k.startswith("_") and v != ""})   # "" = use the per-OS default
        except Exception:                               # a broken config must not stop an edit: fall back
            pass
    return cfg


CFG = _load()


def jianying_exe():
    """Windows: JianyingPro.exe (newest version wins). Mac: the 剪映专业版 .app bundle. Linux: None (no 剪映)."""
    for cand in (CFG.get("jianying_exe"), os.environ.get("JIANYING_EXE")):
        if cand and os.path.exists(cand):
            return cand
    if IS_MAC:
        hits = []
        for root in ("/Applications", str(pathlib.Path.home() / "Applications")):
            hits += glob.glob(os.path.join(root, "*剪映*.app")) + glob.glob(os.path.join(root, "VideoFusion*.app"))
            hits += glob.glob(os.path.join(root, "JianyingPro*.app"))
        return sorted(hits)[0] if hits else None
    if sys.platform != "win32":
        return None
    try:                                                # a running 剪映 tells us exactly where it lives
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process JianyingPro -ErrorAction SilentlyContinue | Select-Object -First 1).Path"],
                             capture_output=True, encoding="mbcs", errors="replace", timeout=10).stdout.strip()
        if out and os.path.exists(out):
            return out
    except Exception:
        pass
    roots = [os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""),
             os.environ.get("ProgramFiles(x86)", "")] + [f"{d}:\\" for d in "CDEF"]
    hits = []
    for r in roots:
        if r:
            hits += glob.glob(os.path.join(r, "*剪映*", "JianyingPro", "*", "JianyingPro.exe"))
            hits += glob.glob(os.path.join(r, "JianyingPro", "Apps", "*", "JianyingPro.exe"))
            hits += glob.glob(os.path.join(r, "JianyingPro", "*", "JianyingPro.exe"))
    hits = sorted(set(hits), key=lambda p: [int(x) if x.isdigit() else 0 for x in pathlib.Path(p).parent.name.split(".")])
    return hits[-1] if hits else None


if __name__ == "__main__":
    print("config:", {k: v for k, v in CFG.items()})
    print("JianyingPro.exe:", jianying_exe())
