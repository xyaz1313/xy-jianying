"""Mode-B helpers: drive the 剪映 UI like a person, by *seeing* it.

Every action: screenshot -> OCR -> find the label -> click / type -> (optionally) tell the overlay.
Physical-pixel coordinates throughout (Windows: per-monitor DPI aware; Mac: Retina screenshot pixels, osctl converts).

CLI (handy for rehearsals):
  python jy_ui.py shot <out.png> [x0 y0 x1 y1]       screenshot (whole screen or region)
  python jy_ui.py find <text> [x0 y0 x1 y1]           print matches of <text> on screen
  python jy_ui.py texts [x0 y0 x1 y1]                 print every OCR'd text with its centre
  python jy_ui.py click <x> <y>
  python jy_ui.py clicktext <text> [x0 y0 x1 y1]
  python jy_ui.py keys <uiautomation-keys>            e.g. "{Ctrl}b"   (on Mac {Ctrl} = ⌘)
"""
import json
import sys
import time
import urllib.request

import osctl as auto  # noqa: E402  (v1.1: Windows = uiautomation, Mac = Quartz; same API)
import numpy as np  # noqa: E402
from PIL import ImageGrab  # noqa: E402

IS_MAC = auto.IS_MAC

_ocr = None
OVERLAY = "http://127.0.0.1:8790/event"


def ocr_engine():
    global _ocr
    if _ocr is None:
        import platform_env           # CUDA on NVIDIA, CPU everywhere else (UI text is small: CPU is fine)
        _ocr = platform_env.ocr_engine()
    return _ocr


def win():
    """The 剪映 window, always on the MAIN screen: if it opened on an extended screen it is moved over first.
    v1.1.1 (owner works on a vertical extended screen next to the main one): never act on another screen."""
    w = auto.WindowControl(searchDepth=1, Name="剪映专业版")
    if auto.IS_MAC:
        i = w._info()
        if i and not auto.on_main_display(i[3]):
            auto.maximise(w)                         # moves it to the main display
            time.sleep(0.8)
            i = w._info()
            if i and not auto.on_main_display(i[3]):
                raise RuntimeError("剪映在扩展屏上、挪不回主屏：请把剪映窗口拖回主屏再跑")
    elif w.Exists(0, 0) and not auto.window_on_primary(w):
        auto.to_primary(w)
        if not auto.window_on_primary(w):
            raise RuntimeError("剪映在扩展屏上、挪不回主屏：请把剪映窗口拖回主屏再跑")
    return w


def activate():
    w = win()
    w.SetActive()
    time.sleep(0.4)
    return w


def _overlay_pid():
    return auto.port_pid(8790)


def _overlay_cmd(path):
    """POST /hide, /show, /quit to the overlay itself (used on Mac; works on Windows too)."""
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8790" + path, data=b"", method="POST"),
                               timeout=1)
        return True
    except Exception:
        return False


def overlay_stop():
    """Stop OUR overlay process (the one listening on 127.0.0.1:8790)."""
    import subprocess
    pid = _overlay_pid()
    if pid:
        if IS_MAC:
            _overlay_cmd("/quit")
            time.sleep(0.8)
        if _overlay_pid():
            auto.kill(pid)
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
    if IS_MAC:
        ok = _overlay_cmd("/show" if on else "/hide")
        time.sleep(0.5)
        return ok
    import ctypes
    hs = _overlay_hwnds()
    for h in hs:
        ctypes.windll.user32.ShowWindow(h, 4 if on else 0)          # SW_SHOWNOACTIVATE / SW_HIDE
    time.sleep(0.5)
    return bool(hs)


def overlay_visible():
    if IS_MAC:
        return _overlay_pid() is not None
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
    w = w or win()

    def ok():
        r = w.BoundingRectangle
        a = np.asarray(_screen().crop((r.left + 20, r.top + 140, r.right - 20, r.bottom - 20))
                       .resize((96, 54)))
        return a.std() > 12
    for k in range(3):
        if ok():
            return True
        if k == 0:
            auto.redraw(w)
        elif k == 1:
            unblack()
        else:
            auto.minimise(w)
            time.sleep(0.8)
            auto.restore(w)
            w.SetActive()
        time.sleep(1.2)
    return ok()


def _is_black(im):
    a = np.asarray(im.resize((96, 54)))
    return a.mean() < 12 and np.median(a) < 2


def _quartz_screen():
    import Quartz
    from PIL import Image
    cg = Quartz.CGWindowListCreateImage(
        Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()),
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if cg is None:
        raise RuntimeError("Quartz 抓屏失败：请检查屏幕录制权限")
    w, h = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg))
    return Image.frombytes("RGBA", (w, h), bytes(data), "raw", "BGRA",
                           Quartz.CGImageGetBytesPerRow(cg), 1).convert("RGB")


def _screen():
    """Whole screen in physical pixels. Mac uses Quartz directly, without spawning screencapture."""
    if IS_MAC:
        return _quartz_screen()
    return ImageGrab.grab()


def grab(region=None):
    im = _screen()
    if _is_black(im.crop((0, 120, im.width, im.height - 120))) and unblack():
        im = _screen()
    return im.crop(region) if region else im


def texts(region=None, upscale=1):
    """[(text, cx, cy, (x0,y0,x1,y1), score)] in physical screen pixels. upscale=2 helps small / grey text."""
    im = grab(region)
    ox, oy = (region[0], region[1]) if region else (0, 0)
    if upscale != 1:
        im = im.resize((im.width * upscale, im.height * upscale))
    res, _ = ocr_engine()(np.array(im)[:, :, ::-1])
    out = []
    for b, t, s in res or []:
        xs, ys = [p[0] / upscale for p in b], [p[1] / upscale for p in b]
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


AGENT = __import__("os").environ.get("XY_AGENT", "Claude")     # name on the overlay cursor (豆包 / WorkBuddy …)


def click(x, y, agent=None, label=None, wait=0.35):
    agent = agent or AGENT
    fx({"type": "cursor", "agent": agent, "to": [x, y]})
    time.sleep(0.15)
    auto.Click(int(x), int(y), waitTime=wait)
    fx({"type": "click", "at": [x, y]})
    if label:
        fx({"type": "status", "text": label})


def click_text(text, region=None, exact=False, nth=0, **kw):
    if IS_MAC:
        import panel
        native = panel._native_tab_hit(text)
        if native:
            click(native[1], native[2], **kw)
            return native
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
