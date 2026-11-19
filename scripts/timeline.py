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
    import steps
    w = steps.uia_retry(lambda: jy_ui.win())
    jy_ui.auto.maximise(w)
    w.SetActive()
    time.sleep(0.8)
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
    _cal = (0.0, off, pps)
    return _cal


def total_frames():
    """Timeline total length from the player readout 'cur / total'."""
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


def read_tc():
    for h in jy_ui.texts(L["tc"]):
        m = TC_RE.search(h[0].replace(" ", ""))
        if m:
            hh, mi, s, f = map(int, m.groups())
            return (hh * 3600 + mi * 60 + s) * FPS + f
    return None


def seek(t, label=None):
    """Frame-exact playhead move. Clicks the ruler (never at its very left edge, which does not register),
    re-clicks if the jump was missed, then fine-tunes with arrow keys. Raises if it cannot land exactly."""
    target = round(t * FPS)
    ry = (L["ruler"][1] + L["ruler"][3]) / 2
    cur = None
    if jy_ui.IS_MAC:
        jy_ui.activate()                       # the overlay / system popups take key focus on Mac
    if target == 0:
        # v1.1.1: 0 s via Home (a ruler click at the far left does not register) — still READ BACK below
        jy_ui.keys("{Home}", wait=0.3)
        for _ in range(3):
            cur = read_tc()
            if cur == 0:
                return 0
            time.sleep(0.3)
    for attempt in range(3):
        jy_ui.click(x_of(max(t, 0.5)), ry, label=label if attempt == 0 else None)
        time.sleep(0.3)
        cur = read_tc()
        if cur is not None and abs(target - cur) <= 30:
            break
    for _ in range(12):
        cur = read_tc()
        if cur is None:
            time.sleep(0.2)
            continue
        d = target - cur
        if d == 0:
            return cur
        jy_ui.keys(("{Right}" if d > 0 else "{Left}") * min(abs(d), 60), wait=0.1)   # Mac: 60 ms per key (osctl)
        time.sleep(0.15)
    if cur != target:
        import steps
        raise steps.Pause(f"播放头没能停到 {t:.2f}s（现在 {'读不到时间码' if cur is None else f'{cur / FPS:.2f}s'}）")
    return cur


def split_at(t, label=None):
    """Ctrl+B splits the *selected* clip: select the main-track clip under t first (clicking a clip does not
    move the playhead), then re-check the playhead and split."""
    seek(t, label)
    jy_ui.click(x_of(t) + S(4), L["track_y"])
    time.sleep(0.2)
    f = read_tc()
    if f != round(t * FPS):
        f = seek(t)
    jy_ui.keys("{Ctrl}b", wait=0.25)
    return f
