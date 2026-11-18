"""Mode B smoke test: drive 剪映 like a human (click ruler, Ctrl+B split, Ctrl+Z undo) while the overlay
visualises each step. Only run on a TEST draft. Usage: python mode_b_split_test.py <out_dir>"""
import ctypes
import json
import pathlib
import sys
import time
import urllib.request

ctypes.windll.shcore.SetProcessDpiAwareness(2)
import uiautomation as auto  # noqa: E402
from PIL import ImageGrab  # noqa: E402

OUT = pathlib.Path(sys.argv[1])


def send(e):
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8790/event",
                                                  data=json.dumps(e, ensure_ascii=False).encode(), method="POST"))


def shot(name):
    ImageGrab.grab(all_screens=True).crop((540, 1150, 3840, 1750)).resize((1650, 300)).save(OUT / name)


w = auto.WindowControl(searchDepth=1, Name="剪映专业版")
w.SetActive()
time.sleep(0.8)
shot("b0_before.png")

# calibration measured from the ruler: 00:00 at x=804, 170 physical px per second at the current zoom
X0, PX = 804, 170
T = 3.0
x, y_ruler, y_video = int(X0 + PX * T), 1220, 1656

send({"type": "status", "text": "B 模式 · 实时操作 · 在 3.0s 处分割"})
send({"type": "cursor", "agent": "Claude", "agentIndex": 0, "to": [x, y_ruler]})
time.sleep(0.9)
auto.Click(x, y_ruler, waitTime=0.3)
send({"type": "click", "at": [x, y_ruler], "agentIndex": 0})
time.sleep(0.5)
auto.SendKeys("{Ctrl}b", waitTime=0.6)
send({"type": "fly", "from": [x, y_ruler], "to": [x, y_video], "label": "分割 · at=3.0s (Ctrl+B)",
      "agent": "Claude", "agentIndex": 0, "dur": 0.7, "hold": 3})
time.sleep(1.2)
shot("b1_split.png")
auto.SendKeys("{Ctrl}z", waitTime=0.6)
send({"type": "status", "text": "B 模式 · 已撤销测试操作"})
time.sleep(0.8)
shot("b2_undo.png")
print("done")
