"""Process / demo video mapper (v0.8, new mode "process-demo").

A filmed AI-edit run (camera pointed at the monitor) is mostly silent. To cut it we need to know, for every moment:
which live_run step was on screen, what the overlay said, how much was moving, and whether the owner was speaking.

python process_map.py <video.mp4> <transcript.json> <out_dir> [--every 2]
  - decodes with NVDEC (h264/hevc_cuvid) at 1920 px, one frame every --every seconds
  - OCR (rapidocr on CUDA) on the whole frame: the overlay status line 「AI EDIT // 0N …」 (top-left), the stats line
    「已剪掉 … 用时 mm:ss」 (top-right), banners
  - activity = mean abs difference to the previous sample (camera shake included, so it is relative)
Writes out_dir/process_map.json and out_dir/thumbs/NNNN.jpg (640 px, for contact sheets / previews).
"""
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gpu_env  # noqa: E402,F401
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import jy_ui  # noqa: E402

FF = next(pathlib.Path.home().joinpath("AppData/Local/Microsoft/WinGet/Packages").rglob("ffmpeg.exe"))
STEP_RE = re.compile(r"(?:AI\s*EDIT)?\W*0?([1-7])\s*(.{0,40})")


def main():
    video, tx_p, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 2.0
    (out / "thumbs").mkdir(parents=True, exist_ok=True)
    W, H = 1920, 1080
    cmd = [str(FF), "-hide_banner", "-loglevel", "error", "-hwaccel", "cuda", "-i", video,
           "-vf", f"fps=1/{every},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    eng = jy_ui.ocr_engine()
    tx = json.load(open(tx_p, encoding="utf-8"))
    speech = [(s["start"], s["end"], s["text"]) for s in tx["segments"] if not s.get("suspect")]
    rows, prev, i = [], None, 0
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        t = i * every
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        small = img[::8, ::8].astype(np.int16)
        act = float(np.abs(small - prev).mean()) if prev is not None else 0.0
        prev = small
        res, _ = eng(img[:, :, ::-1])
        lines = [(r[1], (r[0][0][0] + r[0][2][0]) / 2 / W, (r[0][0][1] + r[0][2][1]) / 2 / H) for r in (res or [])]
        status = next((tx_ for tx_, x, y in lines if "EDIT" in tx_.upper() or "暂停" in tx_), "")
        stats = next((tx_ for tx_, x, y in lines if "用时" in tx_ or "已剪" in tx_ or "成片" in tx_), "")
        step = None
        if status:
            m = STEP_RE.search(status.upper().split("EDIT")[-1] if "EDIT" in status.upper() else status)
            step = int(m.group(1)) if m else None
        clock = re.search(r"(\d{1,2}):(\d{2})\s*$", stats)
        said = " ".join(s[2] for s in speech if s[0] < t + every and s[1] > t)
        rows.append({"t": t, "step": step, "status": status, "stats": stats,
                     "clock": int(clock.group(1)) * 60 + int(clock.group(2)) if clock else None,
                     "activity": round(act, 2), "speech": said,
                     "texts": [l[0] for l in lines if len(l[0]) >= 2][:40]})
        Image.fromarray(img).resize((640, 360)).save(out / "thumbs" / f"{i:04d}.jpg", quality=80)
        if i % 30 == 0:
            print(f"{int(t // 60):02d}:{t % 60:04.1f}  step {step}  {status[:40]!r}  {stats[:30]!r}  act {act:.1f}",
                  flush=True)
        i += 1
    p.wait()
    json.dump({"video": video, "every": every, "rows": rows}, open(out / "process_map.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("samples", len(rows))


if __name__ == "__main__":
    main()
