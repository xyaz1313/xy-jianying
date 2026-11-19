"""Export ONLY when the owner says so (rule 2). v1.2 — the flow done by hand on 剪映 11.8 (2026-11-20), now fixed.

python export_draft.py <draft_name> "<YYYY-MM-DD 标题>" [--covers 封面-横版16x9.png 封面-竖版3x4.png]

  editor title bar 「导出」 (teal, OCR can't read it -> found by colour) -> 标题 = "<YYYY-MM-DD 标题>" (read back)
  -> 导出至: folder icon -> Windows 「请选择导出路径」 -> 文件夹 = export_root (config.json) -> 选择文件夹 (read back)
  -> 分辨率 must read 原始 (3840×2160) or 4K, 帧率 30, 格式 MP4 (else STOP: change it by hand) -> 导出
  -> wait for the new mp4 (size stable) -> folder <export_root>/<YYYY-MM-DD 标题>/ with the mp4 + both covers
  -> ffprobe: 3840×2160, 30 fps, duration.
Never clicked: 「发布」 (export-complete window), 「开通 AI Ultra」, 「收起至首页」.
剪映 11.8 does NOT create the per-title sub-folder (house-style said it would) -> this script makes it and moves the mp4.
9:11 of 4K exported in ≈ 2–3 min on the owner's PC.
"""
import argparse
import glob
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import jy_ui  # noqa: E402
import steps  # noqa: E402
from config import CFG  # noqa: E402
from platform_env import FF, FFPROBE  # noqa: E402,F401
from steps import S, Pause, auto, norm  # noqa: E402


def teal_button(region):
    a = np.asarray(jy_ui.grab(region)).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g > 150) & (b > 150) & (r < 90)
    ys, xs = np.nonzero(m)
    if len(xs) < 50:
        return None
    return region[0] + int(np.median(xs)), region[1] + int(np.median(ys))


def find(label, region, tries=10):
    return steps.wait_for(lambda: jy_ui.find(label, region, exact=True) or jy_ui.find(label, region), tries,
                          what=f"「{label}」")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("title")
    ap.add_argument("--covers", nargs="*", default=[])
    a = ap.parse_args()
    root = CFG.get("export_root") or r"D:\视频成品"
    os.makedirs(root, exist_ok=True)
    if not steps.in_editor():
        steps.open_draft(a.draft)
    w = jy_ui.win()
    w.SetActive()
    time.sleep(0.8)
    r = w.BoundingRectangle
    btn = teal_button((r.right - S(500), r.top, r.right - S(90), r.top + S(40)))
    if not btn:
        raise Pause("标题栏右上角找不到青色的「导出」按钮")
    before = set(glob.glob(os.path.join(root, "**", "*.mp4"), recursive=True))
    jy_ui.click(*btn)
    time.sleep(2.5)
    whole = (r.left, r.top, r.right, r.bottom)
    lab = find("标题", whole)
    jy_ui.click(lab[1] + S(200), lab[2])
    time.sleep(0.4)
    jy_ui.keys("{Ctrl}a", wait=0.2)
    auto.SetClipboardText(a.title)
    jy_ui.keys("{Ctrl}v", wait=0.4)
    jy_ui.click(lab[1], lab[2] - S(40))                       # inert label above (「导出时间线」)
    time.sleep(0.6)
    got = "".join(h[0] for h in jy_ui.texts((lab[1] + S(60), lab[2] - S(15), lab[1] + S(400), lab[2] + S(15))))
    if norm(a.title).replace(" ", "")[:10] not in norm(got).replace(" ", ""):
        raise Pause(f"标题没填进去：读回「{got}」")
    to = find("导出至", whole)
    jy_ui.click(to[1] + S(233), to[2])                        # folder icon at the right end of the path field
    time.sleep(2.5)
    fl = find("文件夹:", whole)
    jy_ui.click(fl[1] + S(300), fl[2])
    time.sleep(0.4)
    jy_ui.keys("{Ctrl}a", wait=0.2)
    auto.SetClipboardText(root)
    jy_ui.keys("{Ctrl}v", wait=0.5)
    sel = find("选择文件夹", whole)
    jy_ui.click(sel[1], sel[2])
    time.sleep(2.0)
    path_txt = "".join(h[0] for h in jy_ui.texts((to[1] + S(60), to[2] - S(15), to[1] + S(400), to[2] + S(15))))
    if norm(root).replace("\\", "/").replace(":", "")[:6] not in norm(path_txt).replace("\\", "/").replace(":", ""):
        raise Pause(f"导出位置没改过来：读回「{path_txt}」")
    dlg = [norm(h[0]) for h in jy_ui.texts(whole)]
    ok_res = any(x in dlg for x in ("原始", "4K")) and "MP4" in dlg and "30" in dlg
    if not ok_res:
        raise Pause(f"分辨率 / 格式 / 帧率不是 原始(4K) / MP4 / 30：{[x for x in dlg if x in ('原始', '4K', '1080P', 'MP4', 'MOV', '30', '25', '60')]}")
    cancel = find("取消", whole)
    jy_ui.click(cancel[1] - S(82), cancel[2])                  # 「导出」 is the teal button left of 「取消」
    print("exporting …", flush=True)
    t0, new, last, stable = time.time(), [], -1, 0
    while time.time() - t0 < 1800:
        new = [f for f in glob.glob(os.path.join(root, "**", "*.mp4"), recursive=True) if f not in before]
        size = sum(os.path.getsize(f) for f in new) if new else -1
        stable = stable + 1 if size == last and size > 0 else 0
        last = size
        if stable >= 5:
            break
        time.sleep(2)
    if not new:
        raise Pause("等了 30 分钟没有新的 mp4")
    mp4 = max(new, key=os.path.getsize)
    dst_dir = os.path.join(root, a.title)
    os.makedirs(dst_dir, exist_ok=True)
    if os.path.dirname(os.path.abspath(mp4)) != os.path.abspath(dst_dir):
        shutil.move(mp4, os.path.join(dst_dir, os.path.basename(mp4)))
        mp4 = os.path.join(dst_dir, os.path.basename(mp4))
    for c in a.covers:
        shutil.copy2(c, os.path.join(dst_dir, os.path.basename(c)))
    pr = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height,r_frame_rate:format=duration", "-of", "json", mp4], capture_output=True, text=True)
    info = json.loads(pr.stdout or "{}")
    st = (info.get("streams") or [{}])[0]
    print(json.dumps({"mp4": mp4, "size_gb": round(os.path.getsize(mp4) / 1e9, 2), "w": st.get("width"), "h": st.get("height"),
                      "fps": st.get("r_frame_rate"), "duration": round(float(info.get("format", {}).get("duration", 0)), 2),
                      "folder": sorted(os.listdir(dst_dir))}, ensure_ascii=False))
    print("剪映导出完成窗口里的「发布」不要点 —— 小爷自己发。")


if __name__ == "__main__":
    main()
