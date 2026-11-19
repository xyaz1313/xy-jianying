"""xy-jianying overlay (formerly jianying-live-fx).

A transparent, always-on-top, click-through window that sits exactly over the JianYing (剪映) window
and plays live "AI edit" effects (flying light trails, agent cursors, click bursts, labels).

Agents send events with HTTP POST to http://127.0.0.1:8790/event (JSON body, see overlay.html for types).
Coordinates are PHYSICAL screen pixels (what UI Automation reports); the overlay converts them.

Run:  python overlay.py [--parent PID]   (follows the 剪映 window ONLY - never covers the whole screen)
Stop: POST /quit, global hotkey Ctrl+Alt+F12 (Mac: ⌃⌥F12, laptop keyboards fn+⌃⌥F12), or automatically.
v1.1: runs on Windows AND macOS (window lookup / process checks via scripts/osctl.py). POST /hide, /show too.

SAFETY (v0.7, after the owner's PC was locked behind a black always-on-top overlay after every run):
  the overlay quits by itself when
  - the parent process (live_run.py / any script that started it) has exited      (--parent PID)
  - no event has arrived for IDLE_QUIT seconds
  - the 剪映 window is gone or minimised for 3 s (it used to fall back to covering the whole primary screen)
  - the owner presses Ctrl+Alt+F12 (global hotkey; works even when the overlay is black and nothing else reacts)
"""
import ctypes  # Windows hotkey hook only
import os as _os
# v1.1.3: stop Qt from turning this script into a foreground app on Mac (it activates itself on launch)
_os.environ.setdefault("QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM", "1")
import os
import json
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

PORT = 8790
IDLE_QUIT = 15 * 60          # seconds without any event -> quit
# Ctrl+Alt+F12 (fallback Ctrl+Alt+Shift+F12). NOT Ctrl+Alt+Q: that is 剪映's own 「返回草稿页」 shortcut and
# 剪映 warned about the conflict (2026-11-18)
HOTKEYS = ((0x0001 | 0x0002, 0x7B), (0x0001 | 0x0002 | 0x0004, 0x7B))
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import osctl  # noqa: E402


def jianying_rect():
    """Physical-pixel rect (left, top, right, bottom) of the main 剪映 window, or None."""
    try:
        w = osctl.WindowControl(searchDepth=1, Name="剪映专业版")
        if w.Exists(0, 0):
            if osctl.is_minimised(w):
                return None
            r = w.BoundingRectangle
            if r.right - r.left < 200 or r.left <= -30000:
                return None
            return (r.left, r.top, r.right, r.bottom)
    except Exception:
        pass
    return None


def alive(pid):
    """True while process pid is running."""
    return osctl.pid_alive(pid)


def hotkey_thread_mac(bridge):
    """Mac emergency hotkey ⌃⌥F12 via pynput (needs Input Monitoring permission for the app running Python).
    If the permission is missing, the other safety exits still apply (parent exit / idle / 剪映 gone) and
    ⌘⌥Esc → force-quit Python always works."""
    try:
        from pynput import keyboard
    except Exception:
        print("emergency hotkey: pynput missing (pip install pynput) — use ⌘⌥Esc → Python", flush=True)
        return
    try:
        with keyboard.GlobalHotKeys({"<ctrl>+<alt>+<f12>": bridge.quit.emit}) as h:
            print("emergency hotkey: ⌃⌥F12", flush=True)
            h.join()
    except Exception as e:
        print("emergency hotkey FAILED:", e, flush=True)


def hotkey_thread(bridge):
    """Global emergency hotkey: Ctrl+Alt+F12 -> quit the overlay.
    Two layers (v1.0, 2026-11-18): RegisterHotKey alone did NOT fire while 剪映 had the focus (剪映 swallows the
    key combo), which is exactly when the owner needs it. So a low-level keyboard hook (WH_KEYBOARD_LL) watches
    for Ctrl+Alt+F12 too — the overlay starts after 剪映, so its hook sits first in the chain."""
    from ctypes import wintypes
    u = ctypes.windll.user32
    for i, (mod, vk) in enumerate(HOTKEYS, 1):
        if u.RegisterHotKey(None, i, mod | 0x4000, vk):   # MOD_NOREPEAT
            print("emergency hotkey: " + ("Ctrl+Alt+F12" if i == 1 else "Ctrl+Alt+Shift+F12"), flush=True)
            break

    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class KBD(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    u.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    u.CallNextHookEx.restype = LRESULT

    def down(vk):
        return bool(u.GetAsyncKeyState(vk) & 0x8000)

    @HOOKPROC
    def proc(n, wparam, lparam):
        if n == 0 and wparam in (0x0100, 0x0104):          # WM_KEYDOWN / WM_SYSKEYDOWN
            k = ctypes.cast(lparam, ctypes.POINTER(KBD)).contents
            if k.vkCode == 0x7B and down(0x11) and down(0x12):   # F12 with Ctrl + Alt held
                print("emergency hotkey (keyboard hook) -> quit", flush=True)
                bridge.quit.emit()
        return u.CallNextHookEx(None, n, wparam, lparam)

    hook = u.SetWindowsHookExW(13, proc, None, 0)           # WH_KEYBOARD_LL
    print("keyboard hook:", "on" if hook else "FAILED", flush=True)
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312:                          # WM_HOTKEY
            bridge.quit.emit()


class Bridge(QObject):
    event = Signal(str)
    quit = Signal()
    visible = Signal(bool)


def raise_overlay(overlay):
    if not osctl.IS_MAC:
        overlay.raise_()


class Overlay(QWebEngineView):
    def __init__(self, bridge: Bridge, parent_pid=None):
        super().__init__()
        self.parent_pid, self.last_event, self.missing = parent_pid, time.time(), 0
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        if osctl.IS_MAC:
            # a Qt.Tool window is an NSPanel that HIDES when its app is inactive — the overlay is never active
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            # 剪映常被放成独立全屏 Space；不设这个，浮层只会留在自己的那个桌面（看着"画在桌面上"）
            QTimer.singleShot(400, self._mac_join_all_spaces)
        self.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        self.load(QUrl.fromLocalFile(str(HERE / "overlay.html")))
        self.origin = (0, 0)
        bridge.event.connect(self.push)
        bridge.quit.connect(QApplication.quit)
        bridge.visible.connect(self.set_shown)
        self.hidden_by_cmd = False
        self.follow()
        self.timer = QTimer(self, interval=1000, timeout=self.follow)
        self.timer.start()

    def _mac_join_all_spaces(self):
        """Mac 上给浮层窗口设 collection behavior。

        两条实测教训：
        1) 加 CanJoinAllSpaces 后，**每块显示器都会各画一份**（外接屏也被铺满，用户以为 AI 跑到副屏乱画）；
        2) 但剪映若停在自己的全屏 Space，不加它就是"浮层画在桌面上、不盖剪映"。
        所以：**只有单屏时**才允许跨 Space（此时不会跑到别的屏），多屏一律老实待在自己那块屏。
        """
        try:
            from AppKit import (NSApp, NSWindowCollectionBehaviorStationary,
                                NSWindowCollectionBehaviorCanJoinAllSpaces,
                                NSWindowCollectionBehaviorFullScreenAuxiliary)
            from Quartz import (CGWindowLevelForKey, kCGScreenSaverWindowLevelKey,
                                CGGetActiveDisplayList, kCGNullDirectDisplay)
            ndisp = len(CGGetActiveDisplayList(64, None, None)[1])
            wid = int(self.winId())
            beh = NSWindowCollectionBehaviorStationary
            if ndisp <= 1:
                beh |= NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
            for w in NSApp.windows():
                if w.windowNumber() == wid:
                    w.setCollectionBehavior_(beh)
                    w.setLevel_(CGWindowLevelForKey(kCGScreenSaverWindowLevelKey))
            print(f"mac: overlay behavior set (screens={ndisp}, join_all_spaces={ndisp <= 1})", flush=True)
        except Exception as e:
            print("mac: overlay behavior failed:", e, flush=True)

    def set_shown(self, on):
        self.hidden_by_cmd = not on
        self.show() if on else self.hide()

    def follow(self):
        # safety: never outlive the run, never cover the screen without 剪映 under it
        if self.parent_pid and not alive(self.parent_pid):
            print("parent exited -> quit", flush=True)
            QApplication.quit()
            return
        if time.time() - self.last_event > IDLE_QUIT:
            print("idle -> quit", flush=True)
            QApplication.quit()
            return
        r = jianying_rect()
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        if r is None:
            self.missing += 1
            if self.missing >= 3:
                print("剪映 window gone/minimised -> quit", flush=True)
                QApplication.quit()
            return
        self.missing = 0
        # v1.1.1: the main screen only — never draw on an extended screen (the owner works there)
        g = QGuiApplication.primaryScreen().geometry()
        cx, cy = (r[0] + r[2]) / 2 / dpr, (r[1] + r[3]) / 2 / dpr
        if not (g.left() <= cx <= g.right() and g.top() <= cy <= g.bottom()):
            if self.isVisible():
                print("剪映 is not on the main screen -> overlay hidden", flush=True)
                self.hide()
            return
        if r[:2] != self.origin or not self.isVisible():
            self.origin = r[:2]
        self.setGeometry(int(r[0] / dpr), int(r[1] / dpr), int((r[2] - r[0]) / dpr), int((r[3] - r[1]) / dpr))
        if self.hidden_by_cmd:
            return
        if not self.isVisible():
            self.show()
        raise_overlay(self)
        if osctl.IS_MAC:
            try:                                    # v1.1.3: if we ever became the active app, hand it back
                from AppKit import NSApp
                if NSApp.isActive():
                    NSApp.deactivate()
                    print('mac: overlay was the active app -> deactivated', flush=True)
            except Exception:
                pass

    def push(self, payload: str):
        self.last_event = time.time()
        e = json.loads(payload)
        # make every coordinate relative to the overlay window
        ox, oy = self.origin
        for k in ("from", "to", "at"):
            if k in e:
                e[k] = [e[k][0] - ox, e[k][1] - oy]
        if "box" in e:
            e["box"] = [e["box"][0] - ox, e["box"][1] - oy, e["box"][2], e["box"][3]]
        self.page().runJavaScript(f"window.onEvent({json.dumps(e, ensure_ascii=False)})")


def serve(bridge: Bridge):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
            if self.path == "/quit":
                bridge.quit.emit()
            elif self.path in ("/hide", "/show"):
                bridge.visible.emit(self.path == "/show")
            else:
                for line in body.splitlines() or [body]:
                    if line.strip():
                        json.loads(line)  # validate
                        bridge.event.emit(line)
            self.send_response(204); self.end_headers()

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"xy-jianying overlay ok")

        def log_message(self, *a):
            pass

    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    osctl.dpi_aware()
    app = QApplication(sys.argv)
    if osctl.IS_MAC:
        # v1.1.2: an accessory app never becomes the frontmost app, so it can never steal 剪映's keyboard focus
        # (v1.1.1 Mac test: menu bar said 'Python' -> every ← → Home went to the overlay, the playhead never moved)
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().setActivationPolicy_(1)   # NSApplicationActivationPolicyAccessory
        except Exception as e:
            print('mac: activation policy failed:', e, flush=True)
    bridge = Bridge()
    ppid = int(sys.argv[sys.argv.index("--parent") + 1]) if "--parent" in sys.argv else None
    ov = Overlay(bridge, ppid)
    threading.Thread(target=serve, args=(bridge,), daemon=True).start()
    threading.Thread(target=hotkey_thread if osctl.IS_WIN else hotkey_thread_mac, args=(bridge,), daemon=True).start()
    print(f"overlay listening on http://127.0.0.1:{PORT}", flush=True)
    code = app.exec()
    os._exit(code)          # also ends the HTTP / hotkey threads and QtWebEngine children
