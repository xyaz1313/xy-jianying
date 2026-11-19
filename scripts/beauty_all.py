"""Beauty for the WHOLE main track in one go (v1.2 — the owner's method, 2026-11-20).

python beauty_all.py <draft_name> [--restart] [--expect-frames N]
  --restart        quit 剪映 first (a running 剪映 does not list a draft written while it runs), then open the draft
  --expect-frames  total length at 30 fps (build_full.py prints it); any change -> stop

In 剪映 11.8 Shift+click and Ctrl+click do NOT multi-select clips (they just re-select). What works:
  lock every track ABOVE the main track (text / subtitles / filter) -> click the main track -> Ctrl+A (= all clips on
  unlocked tracks) -> 画面 -> 美颜美体 (switches to 多人脸模式 by itself) -> 美颜预设 -> style.json beauty.preset -> unlock.
Checks: after Ctrl+A the panel must be the VIDEO multi-select panel (画面 present, 文本 absent); total length never
changes; afterwards 3 clips (10 / 50 / 90 %) read back beauty.check (磨皮 23). ≈ 2 min for a 9-minute video,
versus ~1 hour clip by clip (and one stray click there dragged a clip: +4.8 s, problem log #51).
"""
import argparse
import sys
import time

import numpy as np

import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import jy_ui  # noqa: E402
import panel  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402
from steps import S, Pause, auto  # noqa: E402
from style import ST  # noqa: E402


def lock_icons():
    """y of each lock icon in the track-header column above the main track (white icon pixels, clustered)."""
    # offsets in this skill's base units (4K / 150 %: S(v) == v px there). Measured 2026-11-20: lock icons at
    # tl.left + 73; first track row ~315 below tl.top. Stay below the timeline tabs + toolbar (~ +110), which hold
    # other small white icons (the first scripted run clicked the 「时间线」 tab row there and found 1 "track").
    r = tl.L["tl"]
    x0, x1 = int(r[0] + S(62)), int(r[0] + S(86))
    top, bottom = int(r[1] + S(130)), int(tl.L["track_y"] - S(25))
    a = np.asarray(jy_ui.grab((x0, top, x1, bottom))).astype(int)
    bright = (a.min(axis=2) > 170).sum(axis=1) >= 2
    rows, run = [], []
    for i, b in enumerate(bright):
        if b:
            run.append(i)
        elif run:
            if len(run) >= 3:
                rows.append(top + (run[0] + run[-1]) / 2)
            run = []
    if run and len(run) >= 3:
        rows.append(top + (run[0] + run[-1]) / 2)
    return (x0 + x1) / 2, rows


def frames():
    f = tl.total_frames()
    if f is None:
        raise Pause("读不到总长（剪映被别的窗口挡住了？）——停下，什么都不按")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--expect-frames", type=int)
    a = ap.parse_args()
    if a.restart:
        steps.quit_jianying()
    steps.open_draft(a.draft)
    time.sleep(2)
    panel.geom(); tl.layout(); tl.calibrate()
    f0 = frames()
    if a.expect_frames and abs(f0 - a.expect_frames) > 2:
        raise Pause(f"打开的草稿总长 {f0} 帧 ≠ {a.expect_frames}")
    x, rows = lock_icons()
    if not rows:
        raise Pause("主轨上面找不到轨道的锁头图标")
    print(f"tracks above main: {len(rows)} (lock x={x:.0f}, y={[round(y) for y in rows]})", flush=True)
    for y in rows:
        jy_ui.click(x, y)
        time.sleep(0.4)
    try:
        jy_ui.click(tl.x_of(1.0), tl.L["track_y"])
        time.sleep(0.6)
        jy_ui.keys("{Ctrl}a", wait=1.0)
        tabs = steps.panel_tabs()
        if "画面" not in tabs or "文本" in tabs:
            raise Pause(f"全选后不是「只有视频片段」的面板：{tabs}")
        if frames() != f0:
            raise Pause("全选后总长变了")
        panel.tab("画面")
        panel.tab("美颜美体", sub=True)
        time.sleep(1.0)
        panel.scroll(15, down=False)
        time.sleep(0.6)
        jy_ui.click_text("美颜预设", panel.PANEL)
        time.sleep(1.5)
        preset = ST["beauty"]["preset"]
        h = steps.wait_for(lambda: jy_ui.find(preset, panel.PANEL, exact=True) or jy_ui.find(preset, panel.PANEL), 10,
                           what=f"美颜预设「{preset}」")
        jy_ui.click(h[0][1], h[0][2] - S(60))
        time.sleep(3.0)
        if frames() != f0:
            raise Pause("套美颜后总长变了")
    finally:
        for y in rows:                       # always unlock, also after a stop
            jy_ui.click(x, y)
            time.sleep(0.4)
    check = ST["beauty"].get("check") or {}
    key = next(iter(check), "磨皮")
    total = f0 / tl.FPS
    for frac in (0.1, 0.5, 0.9):
        for dt in (0.0, 0.7, -0.7, 1.4):                 # a click on a seam selects nothing: nudge
            jy_ui.click(tl.x_of(total * frac + dt), tl.L["track_y"])
            time.sleep(0.9)
            if "画面" in steps.panel_tabs():
                break
        else:
            raise Pause(f"抽查 {total * frac:.0f}s：选不中视频片段")
        panel.tab("画面"); panel.tab("美颜美体", sub=True)
        time.sleep(1.0)
        panel.scroll(15, down=False)
        try:
            jy_ui.click_text("美颜", (panel.PANEL[0], panel.PANEL[1], panel.PANEL[2], panel.PANEL[1] + S(270)), exact=True)
            time.sleep(0.8)
        except LookupError:
            pass
        v = panel._num(str(panel.get_value(key)))
        ok = (abs(v - float(check[key])) < 0.51) if check else (v or 0) > 0
        print(f"check {total * frac:6.1f}s  {key} = {v}  {'✓' if ok else '✗'}", flush=True)
        if not ok:
            raise Pause(f"{total * frac:.0f}s 的美颜没套上（{key} {v}）")
    if frames() != f0:
        raise Pause("最后总长变了")
    print(f"beauty OK on all clips · total {f0} frames unchanged")


if __name__ == "__main__":
    main()
