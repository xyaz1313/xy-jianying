"""Mode-B helpers: drive the 剪映 UI like a person, by *seeing* it.

Every action: screenshot -> OCR -> find the label -> click / type -> (optionally) tell the overlay.
Physical-pixel coordinates throughout (process is per-monitor DPI aware).

CLI (handy for rehearsals):
  python jy_ui.py shot <out.png> [x0 y0 x1 y1]       screenshot (whole screen or region)
  python jy_ui.py find <text> [x0 y0 x1 y1]           print matches of <text> on screen
  python jy_ui.py texts [x0 y0 x1 y1]                 print every OCR'd text with its centre
  python jy_ui.py click <x> <y>
  python jy_ui.py clicktext <text> [x0 y0 x1 y1]
  python jy_ui.py keys <uiautomation-keys>            e.g. "{Ctrl}b"
"""
import ctypes
import json
import sys
import time
import urllib.request

ctypes.windll.shcore.SetProcessDpiAwareness(2)
import numpy as np  # noqa: E402
import uiautomation as auto  # noqa: E402
from PIL import ImageGrab  # noqa: E402

_ocr = None
OVERLAY = "http://127.0.0.1:8790/event"


def ocr_engine():
    global _ocr
    if _ocr is None:
        import gpu_env  # noqa: F401  (CUDA DLLs for onnxruntime-gpu)
        import onnxruntime as ort
        ort.set_default_logger_severity(3)      # silence the harmless 'no plugin EP device' probe warning
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
    return _ocr


def win():
    return auto.WindowControl(searchDepth=1, Name="剪映专业版")


def activate():
    w = win()
    w.SetActive()
    time.sleep(0.4)
    return w


def _overlay_pid():
    import subprocess
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True).stdout.decode("mbcs", "ignore")
    for line in out.splitlines():
        if "127.0.0.1:8790" in line and "LISTENING" in line:
            return int(line.split()[-1])
    return None


def overlay_stop():
    """Stop OUR overlay process (the one listening on 127.0.0.1:8790)."""
    import subprocess
    pid = _overlay_pid()
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        for _ in range(20):
            if _overlay_pid() is None:
                break
            time.sleep(0.25)
    return pid


def overlay_start():
    """Start the overlay (scripts/overlay/overlay.py) if it is not running; wait until it answers."""
    import os
    import pathlib
    import subprocess
    if _overlay_pid():
        return True
    here = pathlib.Path(__file__).resolve().parent
    subprocess.Popen([sys.executable, "-X", "utf8", str(here / "overlay" / "overlay.py"), "--parent", str(os.getpid())],
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for _ in range(80):
        try:
            urllib.request.urlopen("http://127.0.0.1:8790/", timeout=0.5)
            time.sleep(1.5)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def overlay_restart():
    """The QWebEngine overlay loses its transparency (turns OPAQUE BLACK) after hide/show or over 剪映's home page.
    Restarting the process is the only reliable cure."""
    overlay_stop()
    return overlay_start()


def _overlay_hwnds():
    """Top-level windows of the overlay process (the one listening on 127.0.0.1:8790), INCLUDING hidden ones —
    UI Automation does not list hidden windows, so a hidden overlay could never be found again that way."""
    import ctypes
    import ctypes.wintypes as wt
    import subprocess
    pid = _overlay_pid()
    if pid is None:
        return []
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _):
        p = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            r = wt.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            ex = u.GetWindowLongW(h, -20) & 0xFFFFFFFF
            # ONLY the full-screen layered + click-through window; the process also owns hidden helper windows
            # (Chromium widget, Qt screen observer) that must never be shown
            if r.right - r.left > 1000 and r.bottom - r.top > 1000 and ex & 0x80000 and ex & 0x20:
                found.append(h)
        return True
    u.EnumWindows(cb, 0)
    return found


def overlay_show(on):
    """Hide the overlay while 剪映 is on its HOME page (home + overlay = black window); show it again in the editor."""
    import ctypes
    hs = _overlay_hwnds()
    for h in hs:
        ctypes.windll.user32.ShowWindow(h, 4 if on else 0)          # SW_SHOWNOACTIVATE / SW_HIDE
    time.sleep(0.5)
    return bool(hs)


def overlay_visible():
    import ctypes
    return any(ctypes.windll.user32.IsWindowVisible(h) for h in _overlay_hwnds())


def unblack():
    """The light-trail overlay sometimes turns OPAQUE BLACK: restart it (hide/show does NOT fix it)."""
    if _overlay_pid() is None:
        return False
    return overlay_restart()


def repaint(w=None):
    """剪映's home page sometimes stays black (never repainted) after leaving the editor. Escalate until it draws:
    RedrawWindow -> overlay hide/show -> minimise/restore. Returns True when the window shows content."""
    import ctypes
    w = w or win()
    h = w.NativeWindowHandle

    def ok():
        r = w.BoundingRectangle
        a = np.asarray(ImageGrab.grab(all_screens=True).crop((r.left + 20, r.top + 140, r.right - 20, r.bottom - 20))
                       .resize((96, 54)))
        return a.std() > 12
    for k in range(3):
        if ok():
            return True
        if k == 0:
            ctypes.windll.user32.RedrawWindow(h, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)
        elif k == 1:
            unblack()
        else:
            ctypes.windll.user32.ShowWindow(h, 6)       # minimise
            time.sleep(0.8)
            ctypes.windll.user32.ShowWindow(h, 9)       # restore
            w.SetActive()
        time.sleep(1.2)
    return ok()


def _is_black(im):
    a = np.asarray(im.resize((96, 54)))
    return a.mean() < 12 and np.median(a) < 2


def grab(region=None):
    im = ImageGrab.grab(all_screens=True)
    if _is_black(im.crop((0, 120, im.width, im.height - 120))) and unblack():
        im = ImageGrab.grab(all_screens=True)
    return im.crop(region) if region else im


def texts(region=None):
    """[(text, cx, cy, (x0,y0,x1,y1), score)] in physical screen pixels."""
    im = grab(region)
    ox, oy = (region[0], region[1]) if region else (0, 0)
    res, _ = ocr_engine()(np.array(im)[:, :, ::-1])
    out = []
    for b, t, s in res or []:
        xs, ys = [p[0] for p in b], [p[1] for p in b]
        x0, y0, x1, y1 = min(xs) + ox, min(ys) + oy, max(xs) + ox, max(ys) + oy
        out.append((t, (x0 + x1) / 2, (y0 + y1) / 2, (x0, y0, x1, y1), s))
    return out


def find(text, region=None, exact=False):
    hits = [h for h in texts(region) if (h[0] == text if exact else text in h[0])]
    return sorted(hits, key=lambda h: (h[2], h[1]))


def fx(e):
    try:
        urllib.request.urlopen(urllib.request.Request(OVERLAY, data=json.dumps(e, ensure_ascii=False).encode(),
                                                      method="POST"), timeout=0.5)
    except Exception:
        pass


def click(x, y, agent="Claude", label=None, wait=0.35):
    fx({"type": "cursor", "agent": agent, "to": [x, y]})
    time.sleep(0.15)
    auto.Click(int(x), int(y), waitTime=wait)
    fx({"type": "click", "at": [x, y]})
    if label:
        fx({"type": "status", "text": label})


def click_text(text, region=None, exact=False, nth=0, **kw):
    hits = find(text, region, exact)
    if len(hits) <= nth:
        raise LookupError(f"'{text}' not found on screen")
    h = hits[nth]
    x = h[1]
    if not exact and len(h[0]) > len(text):
        # OCR merged neighbouring labels ("智能包装滤镜"): aim at the sub-string's own centre
        i = h[0].index(text)
        x0, x1 = h[3][0], h[3][2]
        x = x0 + (x1 - x0) * (i + len(text) / 2) / len(h[0])
    click(x, h[2], **kw)
    return (h[0], x, h[2], h[3], h[4])


def keys(k, wait=0.3):
    auto.SendKeys(k, waitTime=wait)


if __name__ == "__main__":
    c, a = sys.argv[1], sys.argv[2:]
    reg = lambda xs: tuple(map(int, xs)) if len(xs) == 4 else None  # noqa: E731
    if c == "shot":
        grab(reg(a[1:5])).save(a[0]); print("saved", a[0])
    elif c == "find":
        for h in find(a[0], reg(a[1:5])): print(h[0], int(h[1]), int(h[2]))
    elif c == "texts":
        for h in texts(reg(a[0:4])): print(f"{int(h[1])},{int(h[2])}\t{h[0]}")
    elif c == "click":
        click(float(a[0]), float(a[1]))
    elif c == "clicktext":
        print(click_text(a[0], reg(a[1:5]))[:3])
    elif c == "keys":
        keys(a[0])
