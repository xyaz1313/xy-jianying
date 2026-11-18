"""Right-hand property panel helpers for 剪映 (mode B): find a row by its label, type a number into its box."""
import re
import time

import uiautomation as auto

import jy_ui

PANEL = (3100, 50, 3840, 2080)     # right-hand property panel; recomputed by geom()
MAT = (540, 50, 1760, 1480)        # left material panel (文本 / 滤镜 / 智能字幕 …); recomputed by geom()
PLAYER = None                      # player window rect (UIA 'editPanelLoader.editWin')


def geom():
    """Locate the three upper panels from the player window, which is the one UIA element 剪映 11.8 still exposes
    after a restart (the timeline / export ids can disappear). Everything else is an offset from these rects."""
    global PANEL, MAT, PLAYER
    import steps
    w = steps.uia_retry(jy_ui.win)
    wr = w.BoundingRectangle
    ed = w.Control(searchDepth=3, AutomationId="editPanelLoader.editWin")
    if not ed.Exists(1, 0):
        raise LookupError("player window not found")
    r = ed.BoundingRectangle
    PLAYER = (r.left, r.top, r.right, r.bottom)
    PANEL = (r.right + 10, 50, wr.right - 10, wr.bottom - 10)
    tabs = [h for h in jy_ui.texts((0, 50, r.left, 120)) if h[0].replace(" ", "").startswith("素材")]
    left = int(tabs[0][3][0] - 35) if tabs else 540
    MAT = (left, 50, r.left - 15, r.bottom + 110)   # the panel's own bottom bar (开始识别 …) sits below the player rect
    return PANEL, MAT, PLAYER


def P(dx):
    """x in the property panel, measured from its left edge (old layout: 3100 + dx)."""
    return int(PANEL[0] + dx)


def M(dx, from_right=False):
    """x in the material panel: from its left edge (old 540 + dx) or from its right edge (old 1760 - dx)."""
    return int(MAT[2] - dx if from_right else MAT[0] + dx)


def tab(name, sub=False):
    region = (PANEL[0], PANEL[1], PANEL[2], PANEL[1] + (220 if sub else 90))
    jy_ui.click_text(name, region if not sub else (PANEL[0], PANEL[1] + 90, PANEL[2], PANEL[1] + 220), exact=True)
    time.sleep(0.7)


def scroll(n, down=True):
    auto.MoveTo(PANEL[0] + 300, PANEL[1] + 900)
    for _ in range(n):
        (auto.WheelDown if down else auto.WheelUp)(1)
    time.sleep(0.4)


def row(label, scroll_tries=6):
    """Return (label_hit, number_hit) for a slider row, scrolling down until the label is visible."""
    for i in range(scroll_tries):
        hits = jy_ui.texts(PANEL)
        cand = [h for h in hits if h[1] < PANEL[0] + 260]
        labs = [h for h in cand if h[0].replace(" ", "") == label] or \
               [h for h in cand if h[0].replace(" ", "").startswith(label) and len(h[0].strip()) <= len(label) + 3]
        if labs:
            lab = labs[0]
            # re-OCR just this row: tiny values like a lone "0" are often missed in a full-panel pass
            band = jy_ui.texts((PANEL[0], int(lab[2]) - 28, PANEL[2], int(lab[2]) + 28))
            nums = [h for h in band if h[1] > PANEL[0] + 120 and re.fullmatch(r"-?[\d.]+(dB|%|x|s|°)?", h[0].replace(" ", ""))]
            if nums:
                return lab, max(nums, key=lambda h: h[1])
            # empty number box: right side of the row
            return lab, (None, PANEL[2] - 140, lab[2], None, None)
        scroll(4)
    raise LookupError(f"row '{label}' not found")


def _double_click(x, y):
    import ctypes
    auto.SetCursorPos(int(x), int(y))
    for _ in range(2):
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
        time.sleep(0.05)


def _box_selected(cx, cy):
    """剪映 is QML (no UIA focus info). A focused number box shows its text with a teal selection highlight:
    look for it in pixels before ever sending keys."""
    import numpy as np
    im = np.asarray(jy_ui.grab((int(cx) - 45, int(cy) - 16, int(cx) + 45, int(cy) + 16))).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    teal = (g > 70) & (b > 70) & (r < 60) & (g - r > 35)
    return teal.mean() > 0.04


def set_value(label, value, fx_label=None, color=None):
    lab, num = row(label)
    x, y = num[1], num[2]
    jy_ui.click(x, y, label=fx_label)          # unfocused box: one click focuses + selects all
    time.sleep(0.25)
    ok = _box_selected(x, y)
    if not ok:                                  # box was already focused -> the click only moved the caret
        _double_click(x, y)
        time.sleep(0.25)
        ok = _box_selected(x, y)
    if not ok:                                  # last resort: defocus on the inert row label, click again
        auto.Click(int(lab[1]), int(lab[2]), waitTime=0.25)
        auto.Click(int(x), int(y), waitTime=0.25)
        ok = _box_selected(x, y)
    if not ok:
        # never type into the timeline: digits/Enter there could edit the wrong thing
        raise RuntimeError(f"number box for '{label}' did not take focus")
    if color:
        jy_ui.fx({"type": "click", "at": [num[1], num[2]], "color": color})
    jy_ui.keys(str(value), wait=0.08)      # text is already selected -> typing replaces it
    jy_ui.keys("{Enter}", wait=0.25)
    return lab, num


def get_value(label):
    return row(label)[1][0]


def checkbox(title, on=True):
    """Tick the checkbox left of a section title (e.g. 脸型, 五官精修)."""
    for _ in range(6):
        hits = [h for h in jy_ui.texts(PANEL) if h[0].replace(" ", "") == title]
        if hits:
            h = hits[0]
            jy_ui.click(h[3][0] - 30, h[2])
            time.sleep(0.4)
            return h
        scroll(4)
    raise LookupError(title)
