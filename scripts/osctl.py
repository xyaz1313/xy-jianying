"""xy-jianying v1.1 — mouse / keyboard / window / clipboard / process control on Windows AND macOS.

Mode-B code used to call `uiautomation` and `ctypes.windll` directly. It now does `import osctl as auto` and gets
the same small API on both systems. Coordinates are ALWAYS screenshot pixels (physical pixels): on a Retina Mac
the screenshot is 2x the point size, so this module divides by the backing scale before posting events.

  Click(x, y, waitTime)   MoveTo(x, y)   SetCursorPos(x, y)   DoubleClick(x, y)
  DragDrop(x1, y1, x2, y2, moveSpeed, waitTime)   WheelUp(n)   WheelDown(n)
  SendKeys("{Ctrl}b")     (uiautomation syntax; on Mac {Ctrl} means ⌘ for shortcuts, see MAC_CMD)
  SetClipboardText(s)
  WindowControl(Name="剪映专业版") -> object with Exists(), BoundingRectangle, SetActive(), Control(...)
  restore(w)  maximise(w)  minimise(w)  is_minimised(w)
  dpi_aware()  pid_alive(pid)  kill(pid)  port_pid(port)  process_running(names)

macOS needs two permissions for the app that runs Python (Terminal / 豆包 / WorkBuddy …):
  System Settings → Privacy & Security → Accessibility (click / type)  and  Screen Recording (screenshots).
"""
import os
import subprocess
import sys
import time

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# 剪映 window titles / process names on each OS (Mac process name differs from the Windows exe)
JY_NAMES = ("剪映专业版", "剪映", "JianyingPro", "VideoFusion", "VideoFusion-macOS")


def dpi_aware():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


# ======================================================================== Windows: thin wrapper over uiautomation
if IS_WIN:
    dpi_aware()
    import ctypes
    import uiautomation as _u

    def primary_rect():
        """The MAIN screen in physical pixels (DPI-aware process): (0, 0, w, h). v1.1.1: everything happens here —
        the owner works on a vertical extended screen next to it and the AI must never act there."""
        u = ctypes.windll.user32
        return (0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1))

    def on_primary(x, y):
        r = primary_rect()
        return r[0] <= x < r[2] and r[1] <= y < r[3]

    def _chk(*pts):
        for x, y in pts:
            if not on_primary(x, y):
                raise RuntimeError(f"坐标 ({int(x)},{int(y)}) 不在主屏上：只在主屏（横屏）操作，绝不碰扩展屏")

    def Click(x, y, waitTime=0.5):
        _chk((x, y))
        return _u.Click(int(x), int(y), waitTime=waitTime)

    def MoveTo(x, y, moveSpeed=1, waitTime=0.5):
        _chk((x, y))
        return _u.MoveTo(int(x), int(y), moveSpeed=moveSpeed, waitTime=waitTime)

    def SetCursorPos(x, y):
        _chk((x, y))
        return _u.SetCursorPos(int(x), int(y))

    def DragDrop(x1, y1, x2, y2, moveSpeed=1, waitTime=0.5):
        _chk((x1, y1), (x2, y2))
        return _u.DragDrop(int(x1), int(y1), int(x2), int(y2), moveSpeed=moveSpeed, waitTime=waitTime)

    WheelUp = _u.WheelUp
    WheelDown = _u.WheelDown
    SendKeys = _u.SendKeys
    SetClipboardText = _u.SetClipboardText
    WindowControl = _u.WindowControl

    def ui_scale():
        """Physical pixels per logical point (1.5 at 150 % Windows scaling)."""
        try:
            return ctypes.windll.user32.GetDpiForSystem() / 96
        except Exception:
            return 1.5

    def DoubleClick(x, y, waitTime=0.2):
        _chk((x, y))
        _u.SetCursorPos(int(x), int(y))
        for _ in range(2):
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
            time.sleep(0.05)
        time.sleep(waitTime)

    def _show(w, cmd):
        ctypes.windll.user32.ShowWindow(w.NativeWindowHandle, cmd)

    def restore(w):
        _show(w, 9)
        to_primary(w)

    def window_on_primary(w):
        r = w.BoundingRectangle
        return on_primary((r.left + r.right) / 2, (r.top + r.bottom) / 2)

    def to_primary(w):
        """Move 剪映 onto the main screen if it is on another one (it reopens where it was last closed)."""
        if window_on_primary(w):
            return False
        h = w.NativeWindowHandle
        ctypes.windll.user32.ShowWindow(h, 9)                       # restore (a maximised window cannot move)
        time.sleep(0.4)
        ctypes.windll.user32.SetWindowPos(h, 0, 60, 60, 0, 0, 0x0001 | 0x0004)   # SWP_NOSIZE | SWP_NOZORDER
        time.sleep(0.6)
        return True

    def maximise(w):
        to_primary(w)
        _show(w, 3)

    def minimise(w):
        _show(w, 6)

    def is_minimised(w):
        return bool(ctypes.windll.user32.IsIconic(w.NativeWindowHandle))

    def redraw(w):
        ctypes.windll.user32.RedrawWindow(w.NativeWindowHandle, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)

    def pid_alive(pid):
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259

    def kill(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)

    def port_pid(port):
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True).stdout.decode("mbcs", "ignore")
        for line in out.splitlines():
            if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                return int(line.split()[-1])
        return None

    def process_running(names=("JianyingPro.exe",)):
        out = subprocess.run(["tasklist"], capture_output=True).stdout.decode("mbcs", "ignore")
        return any(n.lower() in out.lower() for n in names)


# ======================================================================== macOS: Quartz events + AppleScript
elif IS_MAC:
    import Quartz  # pyobjc-framework-Quartz

    MAC_CMD = True          # {Ctrl}x in shared code means the app shortcut -> ⌘ on Mac

    def _scale():
        """Screenshot pixels per point on the main display (2.0 on Retina)."""
        try:
            d = Quartz.CGMainDisplayID()
            mode = Quartz.CGDisplayCopyDisplayMode(d)
            px = Quartz.CGDisplayModeGetPixelWidth(mode)
            pt = Quartz.CGDisplayModeGetWidth(mode)
            return px / pt if pt else 1.0
        except Exception:
            return 2.0

    SCALE = _scale()

    def main_display_bounds():
        """主屏 bounds（Quartz points，原点通常是 0,0）。"""
        b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        return (b.origin.x, b.origin.y, b.origin.x + b.size.width, b.origin.y + b.size.height)

    def on_main_display(raw_b):
        """raw_b 是 Quartz 的 points 字典（含负原点）。判断窗口是否整体落在主屏内（允许 10% 越界）。

        多屏（延展桌面）时截屏只抓得到主屏，坐标又是「全局 points × 主屏 scale」，
        剪映跑到副屏必然错位、会点到别处 —— 所以宁可先拦住，也不要在副屏上瞎点。
        """
        try:
            m = main_display_bounds()
            x, y = float(raw_b.get("X", 0)), float(raw_b.get("Y", 0))
            w, h = float(raw_b.get("Width", 0)), float(raw_b.get("Height", 0))
            tol = 0.1 * max(w, h)
            return (x >= m[0] - tol and y >= m[1] - tol
                    and x + w <= m[2] + tol and y + h <= m[3] + tol)
        except Exception:
            return True

    def ui_scale():
        return SCALE

    def _pt(x, y):
        """像素坐标 -> 全局 points，并且绝不越出主屏（多屏时防止点到副屏）。"""
        px, py = float(x) / SCALE, float(y) / SCALE
        try:
            m = main_display_bounds()
            bad = not (m[0] <= px <= m[2] and m[1] <= py <= m[3])
        except Exception:
            bad = False
        if bad:      # v1.1.1: never act on another display (clamping would click something else)
            raise RuntimeError(f"坐标 ({px:.0f},{py:.0f}) 不在主屏上：只在主屏操作，绝不碰扩展屏")
        return Quartz.CGPointMake(px, py)

    def _post(ev):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _mouse(kind, x, y, button=Quartz.kCGMouseButtonLeft, clicks=1):
        ev = Quartz.CGEventCreateMouseEvent(None, kind, _pt(x, y), button)
        if clicks > 1:
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, clicks)
        _post(ev)

    def MoveTo(x, y, moveSpeed=1, waitTime=0.05):
        _mouse(Quartz.kCGEventMouseMoved, x, y)
        time.sleep(waitTime)

    SetCursorPos = MoveTo

    def Click(x, y, waitTime=0.3):
        MoveTo(x, y, waitTime=0.03)
        _mouse(Quartz.kCGEventLeftMouseDown, x, y)
        time.sleep(0.03)
        _mouse(Quartz.kCGEventLeftMouseUp, x, y)
        time.sleep(waitTime)

    def DoubleClick(x, y, waitTime=0.2):
        MoveTo(x, y, waitTime=0.03)
        for n in (1, 2):
            _mouse(Quartz.kCGEventLeftMouseDown, x, y, clicks=n)
            _mouse(Quartz.kCGEventLeftMouseUp, x, y, clicks=n)
            time.sleep(0.05)
        time.sleep(waitTime)

    def DragDrop(x1, y1, x2, y2, moveSpeed=1, waitTime=0.5):
        MoveTo(x1, y1, waitTime=0.1)
        _mouse(Quartz.kCGEventLeftMouseDown, x1, y1)
        time.sleep(0.15)
        steps = max(8, int(abs(x2 - x1) / 6 / max(moveSpeed, 0.1)))
        for i in range(1, steps + 1):
            _mouse(Quartz.kCGEventLeftMouseDragged, x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
            time.sleep(0.01)
        time.sleep(0.15)
        _mouse(Quartz.kCGEventLeftMouseUp, x2, y2)
        time.sleep(waitTime)

    def _wheel(n, waitTime=0.05):
        ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, int(n) * 3)
        _post(ev)
        time.sleep(waitTime)

    def WheelUp(wheelTimes=1, waitTime=0.05):
        for _ in range(int(wheelTimes)):
            _wheel(1, waitTime)

    def WheelDown(wheelTimes=1, waitTime=0.05):
        for _ in range(int(wheelTimes)):
            _wheel(-1, waitTime)

    # --- keyboard: translate uiautomation syntax -> macOS virtual key codes
    _VK = {"enter": 36, "return": 36, "tab": 48, "space": 49, "delete": 117, "back": 51, "backspace": 51,
           "esc": 53, "escape": 53, "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119,
           "pageup": 116, "pagedown": 121, "f12": 111}
    _CH = {c: k for k, c in enumerate("asdfhgzxcv")}
    _CH.update({"b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
                "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34,
                "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46, ".": 47})
    _MODS = {"ctrl": Quartz.kCGEventFlagMaskCommand, "cmd": Quartz.kCGEventFlagMaskCommand,
             "realctrl": Quartz.kCGEventFlagMaskControl, "alt": Quartz.kCGEventFlagMaskAlternate,
             "shift": Quartz.kCGEventFlagMaskShift, "win": Quartz.kCGEventFlagMaskCommand}

    def _key(code, flags=0):
        for down in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, code, down)
            if flags:
                Quartz.CGEventSetFlags(ev, flags)
            _post(ev)
            time.sleep(0.01)

    def _type_text(s):
        for ch in s:
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
            _post(ev)
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
            _post(ev)
            time.sleep(0.008)

    def SendKeys(keys, interval=0.06, waitTime=0.3):
        # v1.1.1: 剪映 Mac drops keys sent faster than ~50 ms apart ("{Right}"*3 moved one frame) -> 60 ms per key
        """Supports what xy-jianying uses: {Ctrl}b {Ctrl}v {Enter} {Delete} {Left}{Right}… and plain text."""
        i, flags = 0, 0
        while i < len(keys):
            if keys[i] == "{":
                j = keys.index("}", i)
                tok = keys[i + 1:j].lower()
                i = j + 1
                if tok in _MODS:
                    flags |= _MODS[tok]
                    continue
                if tok in _VK:
                    _key(_VK[tok], flags)
                elif len(tok) == 1:
                    _key(_CH.get(tok, 0), flags)
                flags = 0
            else:
                ch = keys[i]
                i += 1
                if flags and ch.lower() in _CH:
                    _key(_CH[ch.lower()], flags)
                else:
                    _type_text(ch)
                flags = 0
            time.sleep(interval)
        time.sleep(waitTime)

    def SetClipboardText(s):
        subprocess.run(["pbcopy"], input=s.encode("utf-8"), env={**os.environ, "LANG": "en_US.UTF-8"})

    # --- windows via Quartz window list (read) + AppleScript / System Events (activate, resize)
    class _Rect:
        def __init__(self, l, t, r, b):
            self.left, self.top, self.right, self.bottom = int(l), int(t), int(r), int(b)

        def width(self):
            return self.right - self.left

        def height(self):
            return self.bottom - self.top

    class _Missing:
        def Exists(self, *a, **k):
            return False

    def _jy_windows():
        # macOS：剪映常被放成独立全屏 Space，只用 OnScreenOnly 会把它漏掉（"先判断窗口再激活"直接失败）。
        # 但纯用 All 又会把「隐藏的旧窗口 / 别的 Space 的窗口」当主体，坐标会错（实测会选到 3420×2214 的幽灵窗口）。
        # 正解：优先当前屏幕上的窗口，一个都没有（剪映在别的桌面）才退回全部窗口。
        opts = Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements
        on_screen, others = [], []
        for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
            owner = str(w.get("kCGWindowOwnerName", ""))
            if w.get("kCGWindowLayer", 1) != 0 or not any(n.lower() in owner.lower() for n in JY_NAMES):
                continue
            b = w.get("kCGWindowBounds", {})
            if b.get("Width", 0) < 400:
                continue
            item = (b["Width"] * b["Height"], owner, int(w.get("kCGWindowOwnerPID", 0)), b)
            (on_screen if w.get("kCGWindowIsOnscreen") else others).append(item)
        return sorted(on_screen or others, reverse=True)

    class WindowControl:
        """The biggest on-screen 剪映 window. searchDepth / Name are accepted for API compatibility."""

        def __init__(self, searchDepth=1, Name="剪映专业版", **_):
            self.Name = Name

        def _info(self):
            ws = _jy_windows()
            return ws[0] if ws else None

        def Exists(self, maxSearchSeconds=0, searchIntervalSeconds=0.5):
            t0 = time.time()
            while True:
                if self._info():
                    return True
                if time.time() - t0 >= maxSearchSeconds:
                    return False
                time.sleep(max(0.1, searchIntervalSeconds or 0.5))

        @property
        def owner(self):
            i = self._info()
            return i[1] if i else None

        @property
        def ProcessId(self):
            i = self._info()
            return i[2] if i else None

        @property
        def NativeWindowHandle(self):
            return self.ProcessId

        @property
        def BoundingRectangle(self):
            i = self._info()
            if not i:
                return _Rect(0, 0, 0, 0)
            b = i[3]
            s = SCALE
            return _Rect(b["X"] * s, b["Y"] * s, (b["X"] + b["Width"]) * s, (b["Y"] + b["Height"]) * s)

        def SetActive(self, waitTime=0.3):
            """把剪映激活到前台。

            Mac 实测：AppleScript 的 `set frontmost` 对剪映**不切桌面**（剪映在别的 Space 时，
            前台看着变了，画面还停在原桌面，浮层就画在了桌面上）。必须走 NSRunningApplication.activate，
            它才会把那个 Space 一起带过来。
            """
            pid = self.ProcessId
            if pid:
                if IS_MAC:
                    try:
                        from AppKit import (NSRunningApplication, NSApplicationActivateAllWindows,
                                            NSApplicationActivateIgnoringOtherApps)
                        a = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
                        if a:
                            a.activateWithOptions_(NSApplicationActivateAllWindows
                                                   | NSApplicationActivateIgnoringOtherApps)
                    except Exception:
                        _osa(f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true')
                else:
                    _osa(f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true')
            time.sleep(waitTime)
            return True

        def Control(self, *a, **k):
            return _Missing()          # no UI Automation tree on Mac: callers fall back to OCR

    def _osa(script):
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()

    def _proc_ref(w):
        return f"(first process whose unix id is {w.ProcessId})"

    def restore(w):
        if w.ProcessId:
            _osa(f'tell application "System Events" to set visible of {_proc_ref(w)} to true')
        w.SetActive()

    def maximise(w):
        """Fill the visible screen (not macOS full-screen space, which hides the menu bar and breaks the overlay)."""
        if not w.ProcessId:
            return
        # v1.1.1: the MAIN display only (Finder's desktop bounds span every screen -> the window spilled over)
        m = main_display_bounds()
        sw, sh = int(m[2] - m[0]), int(m[3] - m[1])
        _osa(f'tell application "System Events" to tell {_proc_ref(w)} to tell window 1 \n'
             f'set position to {{0, 25}}\nset size to {{{sw}, {sh - 25}}}\nend tell')

    def minimise(w):
        if w.ProcessId:
            _osa(f'tell application "System Events" to set visible of {_proc_ref(w)} to false')

    def is_minimised(w):
        return not w.Exists(0, 0)

    def redraw(w):
        pass

    def pid_alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def kill(pid):
        try:
            os.kill(pid, 15)
        except Exception:
            pass

    def port_pid(port):
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], capture_output=True,
                             text=True).stdout.split()
        return int(out[0]) if out else None

    def process_running(names=JY_NAMES):
        out = subprocess.run(["ps", "-axo", "comm"], capture_output=True, text=True).stdout
        # 剪映 ⌘Q 后仍会留下托盘/崩溃处理等辅助进程（VideoFusion-macOSTrayHelper 等），别把它们当"剪映还开着"
        lines = [l for l in out.splitlines()
                 if not any(k in l.rsplit("/", 1)[-1].lower() for k in ("helper", "tray", "crash"))]
        return any(n.lower() in "\n".join(lines).lower() for n in names)

    def accessibility_ok():
        try:
            from ApplicationServices import AXIsProcessTrusted
            return bool(AXIsProcessTrusted())
        except Exception:
            return None

    def screen_recording_ok():
        try:
            return bool(Quartz.CGPreflightScreenCaptureAccess())
        except Exception:
            return None

else:
    raise ImportError("osctl: live control of 剪映 needs Windows or macOS (剪映 has no Linux version)")
