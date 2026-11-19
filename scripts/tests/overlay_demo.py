"""Light-overlay demo over the 剪映 window — no clicks, only effects. For a human to look at (Mac & Windows).

  python scripts/tests/overlay_demo.py          (Mac: bash run.sh tests/overlay_demo.py)

Open 剪映 first (any page). For ~15 s you should see: an AI cursor gliding to the four corners and the centre,
click bursts, a flying light trail, a status label and a banner — all ON TOP of 剪映, background transparent,
and your mouse still works on 剪映 underneath (click-through). Then the overlay closes by itself.
Answer the 5 questions printed at the end.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import jy_ui  # noqa: E402

w = jy_ui.win()
if not w.Exists(3, 0.5):
    sys.exit("先打开剪映（首页或者任意草稿都行），再运行。")
w.SetActive()
r = w.BoundingRectangle
print("剪映窗口:", (r.left, r.top, r.right, r.bottom))
if not jy_ui.overlay_start():
    sys.exit("✗ 光效层没起来（看上面的报错；Mac 上可能是 PySide6 / QtWebEngine 没装好）")
cx, cy = (r.left + r.right) / 2, (r.top + r.bottom) / 2
pts = [(r.left + 200, r.top + 200), (r.right - 200, r.top + 200), (r.right - 200, r.bottom - 200),
       (r.left + 200, r.bottom - 200), (cx, cy)]
jy_ui.fx({"type": "status", "text": f"{jy_ui.AGENT} · 光效层测试"})
for x, y in pts:
    jy_ui.fx({"type": "cursor", "agent": jy_ui.AGENT, "to": [x, y]})
    time.sleep(1.2)
    jy_ui.fx({"type": "click", "at": [x, y]})
    time.sleep(0.6)
jy_ui.fx({"type": "fly", "from": [r.left + 300, r.bottom - 300], "to": [r.right - 300, r.top + 300], "text": "飞线"})
time.sleep(2)
jy_ui.fx({"type": "banner", "text": "光效层 OK", "sub": "xy-jianying v1.1", "hold": 3})
time.sleep(4)
jy_ui.overlay_stop()
print("""
光效层已关闭。请回答：
1. 光标、点击光圈、飞线、横幅都看到了吗？位置是不是正好在剪映窗口里（四个角 + 正中间）？
2. 背景是透明的吗（能看清剪映），有没有变成黑屏 / 白屏？
3. 测试时你用鼠标点剪映，剪映有反应吗（点击穿透）？
4. 现在光效层是不是已经完全消失了？
5. 再跑一次，中途按 ⌃⌥F12（笔记本 fn+⌃⌥F12），光效层会不会马上关掉？
""")
