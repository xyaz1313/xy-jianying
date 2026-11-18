"""Safety tests for the v0.7 overlay: parent watchdog, emergency hotkey, /quit, 剪映-missing rule."""
import ctypes
import pathlib
import subprocess
import sys
import time

SK = pathlib.Path(__file__).resolve().parent.parent   # the skill's scripts/ (works wherever it is installed)
sys.path.insert(0, str(SK))
import jy_ui  # noqa: E402

PY = sys.executable
jy = jy_ui.win().Exists(0, 0)
print("剪映 running:", jy)


def wait_gone(sec):
    t0 = time.time()
    while time.time() - t0 < sec:
        if jy_ui._overlay_pid() is None:
            return round(time.time() - t0, 1)
        time.sleep(0.25)
    return None


jy_ui.overlay_stop()
res = {}

# 1 parent watchdog: a child script starts the overlay, then exits
child = subprocess.Popen([PY, "-c", f"import sys; sys.path.insert(0, r'{SK}'); import jy_ui, time; "
                                    "print(jy_ui.overlay_start()); time.sleep(3)"])
child.wait()
up = jy_ui._overlay_pid() is not None
res["1 parent exits -> overlay quits"] = (up or "not up (剪映 missing rule may already have closed it)", wait_gone(10))

# 2 emergency hotkey Ctrl+Alt+F12 (overlay with no parent)
subprocess.Popen([PY, "-X", "utf8", str(SK / "overlay/overlay.py")], creationflags=subprocess.CREATE_NO_WINDOW)
for _ in range(60):
    if jy_ui._overlay_pid():
        break
    time.sleep(0.25)
time.sleep(2)
up = jy_ui._overlay_pid() is not None
u = ctypes.windll.user32
for vk in (0x11, 0x12, 0x7B):
    u.keybd_event(vk, 0, 0, 0)
for vk in (0x7B, 0x12, 0x11):
    u.keybd_event(vk, 0, 2, 0)
res["2 Ctrl+Alt+F12 -> overlay quits"] = (up, wait_gone(6))

# 3 /quit + overlay_stop (what live_run's finally does)
if jy:
    jy_ui.overlay_start()
    up = jy_ui._overlay_pid() is not None
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8790/quit", data=b"", method="POST"), timeout=2)
    except Exception:
        pass
    res["3 POST /quit -> overlay quits"] = (up, wait_gone(6))
else:
    # 4 剪映 missing: overlay must quit by itself within ~3 s instead of covering the screen
    subprocess.Popen([PY, "-X", "utf8", str(SK / "overlay/overlay.py")], creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1)
    res["4 剪映 not running -> overlay quits (no fullscreen fallback)"] = ("started", wait_gone(15))
jy_ui.overlay_stop()
for k, v in res.items():
    print(k, "| was up:", v[0], "| gone after s:", v[1])
