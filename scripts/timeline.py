"""Frame-accurate playhead control on the 剪映 timeline (mode B). Layout-independent: everything is located
live from the window / UIA timeline rect + OCR, so it survives window moves, resizes and zoom changes.

layout():    maximise 剪映, find timeline rect, ruler strip, timecode readout, main-track row.
calibrate(): OCR ruler labels (mm:ss) -> linear map time->x.
seek(t):     click ruler near t, read player timecode, nudge ←/→ (1 frame each) until exact.
split_at(t): seek + Ctrl+B.
"""
import re
import time

import jy_ui


def S(v):
    import panel
    return panel.S(v)

FPS = 30
L = {}       # layout cache
_cal = None
TC_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}):(\d{2})")


def maximise():
    import steps, subprocess
    w = steps.uia_retry(lambda: jy_ui.win())
    jy_ui.auto.maximise(w)
    w.SetActive()
    time.sleep(0.8)
    if jy_ui.IS_MAC:
        # v1.1.4(mac 实测 2026-11-19): 「把窗口拉满」≠「macOS 全屏 Space」。
        # 真全屏后窗口变成 (0,68,3380,2090) 铺满整屏、没有菜单栏和窗口边缘干扰，
        # seek 0/2/5/10 两轮 8/8 全中。这里主动切进全屏。
        try:
            import AppKit
            f = AppKit.NSScreen.mainScreen().frame().size
            r = w.BoundingRectangle
            if (r.right - r.left) < f.width * 0.98 or (r.bottom - r.top) < f.height * 0.88:
                subprocess.run(["osascript", "-e",
                    'tell application "System Events" to tell process "VideoFusion-macOS" '
                    'to keystroke "f" using {control down, command down}'], timeout=8)
                # 全屏 Space 切换有 1–2 s 动画，切完立刻 layout 会读不到时间尺 → 等稳 + 重试
                for _ in range(6):
                    time.sleep(2.0)
                    try:
                        w = steps.uia_retry(lambda: jy_ui.win())
                        if jy_ui.texts((w.BoundingRectangle.left, w.BoundingRectangle.top,
                                        w.BoundingRectangle.right, w.BoundingRectangle.bottom)):
                            break
                    except Exception:
                        continue
                print("  · 已切到 macOS 全屏")
        except Exception as e:
            print(f"  · 全屏失败(不影响): {e}")
    return w


def layout():
    """v1.1.1: also calibrates the ruler (a bare layout() left x_of() unusable — Mac test hit it 4 times)."""
    import steps
    out = steps.uia_retry(_layout)
    calibrate()
    return out


def _layout():
    import panel
    w = maximise()
    panel.geom()
    tl = w.Control(searchDepth=12, Compare=lambda c, d: (c.AutomationId or "").startswith("timeline_docker_layout"))
    if tl.Exists(0.5, 0):
        r = tl.BoundingRectangle
        L["tl"] = (r.left, r.top, r.right, r.bottom)
    else:
        # after a 剪映 restart the timeline UIA id can be missing: the timeline starts just under the player's
        # 'HH:MM:SS:FF / HH:MM:SS:FF' readout and spans from the material panel's left edge to the window edge
        pl, wr = panel.PLAYER, w.BoundingRectangle
        tcs = [h for h in jy_ui.texts((pl[0], pl[3] - S(20), pl[2], pl[3] + S(160))) if TC_RE.search(h[0].replace(" ", ""))]
        if not tcs:
            raise RuntimeError("timecode readout under the player not found")
        L["tl"] = (panel.MAT[0], int(tcs[0][3][3] + S(22)), wr.right - S(10), wr.bottom - S(20))
    r = _R(*L["tl"])
    # ruler: labels like |00:10 in the top band of the timeline
    band = (r.left, r.top + S(30), r.right, r.top + S(130))
    labels = [h for h in jy_ui.texts(band) if re.search(r"\d{2}:\d{2}", h[0])]
    if not labels:
        raise RuntimeError("ruler labels not found")
    y = sorted(h[2] for h in labels)[len(labels) // 2]
    L["ruler"] = (r.left, int(y - S(16)), r.right, int(y + S(16)))
    # timecode readout: 'HH:MM:SS:FF / HH:MM:SS:FF' just above the timeline
    above = (r.left, r.top - S(160), r.right, r.top)
    tcs = [h for h in jy_ui.texts(above) if TC_RE.search(h[0].replace(" ", ""))]
    if not tcs:
        raise RuntimeError("timecode readout not found")
    b = tcs[0][3]
    L["tc"] = (int(b[0] - S(6)), int(b[1] - S(6)), int(b[2] + S(6)), int(b[3] + S(6)))
    # main track row: the clip header labels ('变速 1.1X …' or file names) sit on top of the thumbnails
    heads = [h for h in jy_ui.texts((r.left, r.top + S(130), r.right, r.bottom)) if "变速" in h[0] or ".mp4" in h[0]]
    L["track_y"] = int(max(h[2] for h in heads) + S(40)) if heads else int(r.top + r.height() * 0.6) if hasattr(r, "height") else None
    return L


class _R:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom

    def height(self):
        return self.bottom - self.top


def _label_time(s):
    # ruler labels look like "00:10", "|00:20", "[01:10", "1 02:30" — never 4-part timecodes
    s = s.replace(" ", "")
    if TC_RE.search(s):
        return None
    m = re.fullmatch(r"[\[\|1Il]?(\d{2}):(\d{2})", s)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def calibrate():
    """Robust linear fit of ruler labels; rejects OCR outliers. Raises if the fit is not trustworthy."""
    global _cal
    import statistics
    pts = sorted((_label_time(h[0]), h[3][0]) for h in jy_ui.texts(L["ruler"]) if _label_time(h[0]) is not None)
    pts = [p for i, p in enumerate(pts) if i == 0 or p[0] != pts[i - 1][0]]
    if len(pts) < 3:
        raise RuntimeError(f"ruler not readable: {pts}")
    slopes = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(pts, pts[1:]) if b[0] > a[0]]
    pps = statistics.median(slopes)
    off = statistics.median(x - t * pps for t, x in pts)
    good = [(t, x) for t, x in pts if abs(x - (off + t * pps)) < S(12)]
    if len(good) < 3 or pps <= 0:
        raise RuntimeError(f"ruler fit unreliable: {pts}")
    # v1.1.1 self-check (Mac test: one run read the 0-s offset as -190): 0 s must sit inside the timeline
    r = L.get("tl")
    if r and not (r[0] - 40 <= off <= r[0] + (r[2] - r[0]) * 0.5):
        if not getattr(calibrate, "_retry", False):
            calibrate._retry = True
            try:
                time.sleep(0.5)
                return calibrate()
            finally:
                calibrate._retry = False
        raise RuntimeError(f"ruler fit puts 0 s outside the timeline: offset {off:.0f}, timeline {r}")
    if _cal is not None and _cal[2] > 0 and abs(pps - _cal[2]) / _cal[2] > 0.05:
        if not getattr(calibrate, "_scale_retry", False):
            calibrate._scale_retry = True
            try:
                time.sleep(0.6)
                return calibrate()
            finally:
                calibrate._scale_retry = False
        raise RuntimeError(f"时间尺缩放比例异常跳变：{_cal[2]:.2f} → {pps:.2f}；保留上一次正确校准")
    _cal = (0.0, off, pps)
    return _cal


def total_frames():
    """Timeline total length from the player readout 'cur / total'."""
    native = _native_progress("totalProgress")
    if native is not None:
        return native
    band = (L["tc"][0] - S(20), L["tc"][1], L["tc"][2] + S(420), L["tc"][3])
    tcs = [m for m in (TC_RE.fullmatch(h[0].replace(" ", "")) for h in jy_ui.texts(band)) if m]
    if not tcs:
        return None
    hh, mi, s, f = map(int, tcs[-1].groups())
    return (hh * 3600 + mi * 60 + s) * FPS + f


def undo():
    """Undo button by UIA id; after a 剪映 restart the UIA tree is gone (v0.8) -> Ctrl+Z."""
    try:
        w = jy_ui.win()
        u = w.Control(searchDepth=12, AutomationId="editor.undo")
        if not u.Exists(1, 0):
            raise LookupError
        r = u.BoundingRectangle
        jy_ui.click((r.left + r.right) / 2, (r.top + r.bottom) / 2)
    except Exception:
        jy_ui.keys("{Ctrl}z", wait=0.3)
    time.sleep(0.6)


def remove_range(a, b, on_step=None):
    """Delete timeline range [a, b) on the main track with ripple; verified by total length, undone on mismatch."""
    before = total_frames()
    expected = round(b * FPS) - round(a * FPS)
    split_at(b)
    if on_step:
        on_step("split_b")
    split_at(a)
    if on_step:
        on_step("split_a")
    calibrate()
    jy_ui.click(x_of((a + b) / 2), L["track_y"])
    time.sleep(0.3)
    jy_ui.keys("{Delete}", wait=0.5)
    time.sleep(0.3)
    after = total_frames()
    if before is None or after is None or abs((before - after) - expected) > 2:
        undo()
        raise RuntimeError(f"cut [{a:.2f},{b:.2f}] removed {None if after is None else before - after} frames, "
                           f"expected {expected}: undone")
    return before - after


def x_of(t):
    t0, x0, pps = _cal
    return x0 + (t - t0) * pps


def _progress_frames(text):
    m = TC_RE.search(text or "")
    if not m:
        return None
    hh, mi, s, f = map(int, m.groups())
    return (hh * 3600 + mi * 60 + s) * FPS + f


def _native_progress(name):
    if not jy_ui.IS_MAC:
        return None
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication
        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack = [app]
        while stack:
            el = stack.pop()
            err, desc = AXUIElementCopyAttributeValue(el, "AXDescription", None)
            if not err and isinstance(desc, str) and desc.startswith(name + "|"):
                return _progress_frames(desc)
            err, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
            if not err:
                stack.extend(children or [])
    except Exception:
        pass
    return None


def read_tc():
    native = _native_progress("currentProgress")
    if native is not None:
        return native
    for h in jy_ui.texts(L["tc"]):
        m = TC_RE.search(h[0].replace(" ", ""))
        if m:
            hh, mi, s, f = map(int, m.groups())
            return (hh * 3600 + mi * 60 + s) * FPS + f
    return None


TOL = 1        # frames: OCR of the readout itself is ±1 frame; 1 frame = 0.033 s


def _seek_mac(target, label=None):
    """Mac: converge by measured click error; do not spray arrow keys into a possibly focused input."""
    import steps
    ry = (L["ruler"][1] + L["ruler"][3]) / 2
    jy_ui.activate()
    xt = x_of(0.5 if target == 0 else target / FPS)
    xmin = x_of(0 if target == 0 else 1.0 / FPS)
    xmax = L["ruler"][2] - S(4)
    cur = None
    seen = set()
    best = None
    for attempt in range(8):
        next_x = min(max(xt, xmin), xmax)
        jy_ui.click(next_x, ry, label=label if attempt == 0 else None)
        time.sleep(0.4)
        cur = read_tc()
        if cur is None:
            continue
        d = target - cur
        if abs(d) <= TOL:
            return cur
        if cur in seen:
            break
        seen.add(cur)
        if best is None or abs(d) < abs(target - best[0]):
            best = (cur, next_x)
        if target == 0:
            break
        corrected = next_x + d / FPS * _cal[2]
        if abs(corrected - next_x) < 0.5:
            break
        xt = corrected
    if best is not None and cur != best[0]:
        jy_ui.click(best[1], ry)
        time.sleep(0.4)
        cur = read_tc()
    stuck = 0
    while cur is not None and abs(target - cur) > TOL and stuck < 2:
        d = target - cur
        jy_ui.keys("{Right}" if d > 0 else "{Left}", wait=0.08)
        time.sleep(0.25)
        after = read_tc()
        if after is None or after == cur:
            stuck += 1
        else:
            stuck = 0
            cur = after
    if cur is not None and abs(target - cur) <= TOL:
        return cur
    if target == 0 and cur is not None:
        jy_ui.auto.DragDrop(x_of(cur / FPS), ry, x_of(0), ry, moveSpeed=1, waitTime=0.4)
        time.sleep(0.25)
        cur = read_tc()
        if cur is not None and abs(cur) <= TOL:
            return cur
    if target == 0 and cur is not None:
        jy_ui.keys("{Home}", wait=0.5)
        time.sleep(0.25)
        cur = read_tc()
        if cur is not None and abs(cur) <= TOL:
            return cur
    now = "读不到" if cur is None else f"{cur / FPS:.2f}s"
    raise steps.Pause(f"播放头没能停到 {target / FPS:.2f}s（现在 {now}）")


def seek(t, label=None):
    """Playhead to t (frame-exact, ±TOL). Click the ruler, then fine-tune with ← →.
    v1.1.2 (Mac test: the playhead stayed 4 frames short every time and ← → / Home did nothing, because the
    overlay — 'Python' in the menu bar — was the frontmost app and got the keys):
      * keys are sent only after 剪映 is brought to the front (osctl.jy_to_front, every SendKeys on Mac);
      * after each key burst the readout is re-read; if it did NOT move, 剪映 is re-fronted and the ruler is
        re-clicked at a position corrected by the measured error — this converges even with no keyboard at all;
      * wait 0.25–0.3 s before reading (剪映 Mac repaints the timecode late)."""
    target = round(t * FPS)
    if jy_ui.IS_MAC:
        return _seek_mac(target, label)
    ry = (L["ruler"][1] + L["ruler"][3]) / 2
    cur = None
    if jy_ui.IS_MAC:
        jy_ui.activate()                       # the overlay / system popups take key focus on Mac
    if target == 0:
        # v1.1.4(mac 实测): {Home} 本身是有效的（一次就回 0），但在「焦点还在输入框」时会被吃掉，
        # 而旧逻辑读不到 0 就掉进下面的「点 0.5 s」分支 → 之后再也回不到 0（三版都停在 0.37 s = 11 帧）。
        # 所以：多按几次 + 点最左端兜底 + 0 秒位置不硬校验（剪映 0 点附近本来就有几帧吸附）。
        for _ in range(6):
            jy_ui.keys("{Home}", wait=0.35)
            time.sleep(0.35)
            cur = read_tc()
            if cur == 0:
                return 0
        jy_ui.click(x_of(1.0 / FPS), ry)
        time.sleep(0.4)
        cur = read_tc()
        if cur is not None and cur <= 3:
            return cur
        return 0
    xt = x_of(max(t, 0.5))
    xmin = x_of(1.0 / FPS)                     # never click the very left edge (does not register)
    if jy_ui.IS_MAC:
        jy_ui.click(xt, ry)                    # 先把焦点从属性面板的输入框挪到时间线，否则 ←→ 被输入框吃掉
        time.sleep(0.35)
    for attempt in range(3):
        jy_ui.click(xt, ry, label=label if attempt == 0 else None)
        time.sleep(0.4)
        cur = read_tc()
        if cur is not None and abs(target - cur) <= 30:
            break
    stuck = 0
    for _ in range(24):
        time.sleep(0.25)
        cur = read_tc()
        if cur is None:
            continue
        d = target - cur
        if d == 0:
            return cur
        jy_ui.keys(("{Right}" if d > 0 else "{Left}") * min(abs(d), 30), wait=0.1)
        time.sleep(0.3)
        after = read_tc()
        if after is not None and after != cur:
            stuck = 0
            continue
        stuck += 1                              # keys did not move the playhead
        if jy_ui.IS_MAC:
            jy_ui.activate()
        if stuck >= 2:                          # keyboard-free fallback: re-click, corrected by the error
            xt = max(xmin, xt + d / FPS * _cal[2])
            jy_ui.click(xt, ry)
            time.sleep(0.4)
    cur = read_tc() if cur is None else cur
    if cur is not None and abs(target - cur) <= TOL:
        return cur
    import steps
    now = "读不到" if cur is None else f"{cur / FPS:.2f}s"
    raise steps.Pause(f"播放头没能停到 {t:.2f}s（现在 {now}）")


def split_at(t, label=None):
    """Ctrl+B splits the *selected* clip: select the main-track clip under t first (clicking a clip does not
    move the playhead), then re-check the playhead and split."""
    seek(t, label)
    jy_ui.click(x_of(t) + S(4), L["track_y"])
    time.sleep(0.2)
    f = read_tc()
    if f is None or abs(f - round(t * FPS)) > TOL:
        f = seek(t)
    jy_ui.keys("{Ctrl}b", wait=0.25)
    return f
