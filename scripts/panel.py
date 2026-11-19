"""Right-hand property panel helpers for 剪映 (mode B): find a row by its label, type a number into its box.

v1.1.1 — no fixed screen coordinates. Every position is either FOUND on screen (OCR anchors: 「素材」 icon row,
「播放器」 title, the property panel's tab rows, row labels) or an offset from such an anchor scaled with S():
all offsets were measured on Windows at 150 % (REF), so S(v) = v on that machine and v·2/1.5 on a Retina Mac.
Y(v) = a Windows window-relative y, moved to this window and scaled the same way.
Values are typed with type_value(): focus → select all → type → Enter → READ BACK; never trusted blind.
"""
import re
import time

import osctl as auto  # v1.1 cross-platform

import jy_ui

PANEL = (3100, 50, 3840, 2080)     # right-hand property panel; recomputed by geom()
MAT = (540, 50, 1760, 1480)        # left material panel (文本 / 滤镜 / 智能字幕 …); recomputed by geom()
PLAYER = None                      # player rect
WIN = None                         # 剪映 window rect
TOP_Y = None                       # y centre of the top icon row (素材 音频 文本 … 滤镜)
REF = 1.5                          # the UI scale every pixel offset in this skill was measured at (Windows 150 %)


class _Rect:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b


def S(v):
    """A pixel distance measured on Windows 150 %, converted to this screen."""
    return int(round(v * auto.ui_scale() / REF))


def Y(v):
    """A y measured on the maximised Windows window (top = 0), converted to this window."""
    top = max(WIN[1], 0) if WIN else 0
    return int(top + S(v))


RIGHT_TABS = ("画面", "音频", "变速", "动画", "调节", "基础", "草稿参数", "文本", "朗读", "AI效果", "字幕", "跟踪", "数字人")


_NATIVE_TAB_IDS = {
    "text_submit": "字幕", "text_text": "文本", "text_animation": "动画",
    "text_tracking": "跟踪", "text_tts": "朗读", "text_digital_human": "数字人",
    "video_screen": "画面", "video_audio": "音频", "video_speed": "变速",
    "video_animation": "动画", "video_adjust": "调节",
    "TextEditSettingPanelFont": "字体",
}


def _native_tab_name(value):
    if value in set(RIGHT_TABS) | {"美颜美体", "入场", "抠像", "美颜预设"}:
        return value
    if isinstance(value, str) and "beauty" in value.lower() and "preset" in value.lower():
        return "美颜预设"
    if isinstance(value, str):
        for prefix in ("VESettingPanelSubTabControl:", "VETreeMainCellItem:", "VETreeSubCellItem:", "root_"):
            if value.startswith(prefix):
                return value[len(prefix):]
    return _NATIVE_TAB_IDS.get(value)


def native_tabs():
    if not auto.IS_MAC:
        return []
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication
        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack, out = [app], []
        while stack:
            el = stack.pop()
            for attr in ("AXValue", "AXDescription", "AXTitle"):
                err, value = AXUIElementCopyAttributeValue(el, attr, None)
                name = _native_tab_name(value) if not err else None
                if name and name not in out:
                    out.append(name)
            err, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
            if not err:
                stack.extend(children or [])
        return out
    except Exception:
        return []


def _native_tab_hit(name):
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication
        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack = [app]
        while stack:
            el = stack.pop()
            for attr in ("AXValue", "AXDescription", "AXTitle"):
                err, value = AXUIElementCopyAttributeValue(el, attr, None)
                if not err and _native_tab_name(value) == name:
                    err, frame = AXUIElementCopyAttributeValue(el, "AXFrame", None)
                    m = re.search(r"x:([\d.-]+) y:([\d.-]+) w:([\d.-]+) h:([\d.-]+)", str(frame))
                    if m:
                        x, y, w, h = map(float, m.groups())
                        scale = auto.ui_scale()
                        return (name, (x + w / 2) * scale, (y + h / 2) * scale,
                                (x * scale, y * scale, (x + w) * scale, (y + h) * scale), 1.0)
            err, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
            if not err:
                stack.extend(children or [])
    except Exception:
        pass
    return None


def _native_number_hit(label_y):
    if not auto.IS_MAC:
        return None
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication

        def get(el, name):
            err, value = AXUIElementCopyAttributeValue(el, name, None)
            return None if err else value

        def frame(el):
            m = re.search(r"x:([\d.-]+) y:([\d.-]+) w:([\d.-]+) h:([\d.-]+)", str(get(el, "AXFrame")))
            return tuple(map(float, m.groups())) if m else None

        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack, sliders = [app], []
        while stack:
            el = stack.pop()
            if get(el, "AXDescription") == "slider" and frame(el):
                sliders.append(el)
            stack.extend(get(el, "AXChildren") or [])
        scale = auto.ui_scale()
        sliders.sort(key=lambda el: abs((frame(el)[1] + frame(el)[3] / 2) * scale - label_y))
        for slider in sliders:
            sf = frame(slider)
            if abs((sf[1] + sf[3] / 2) * scale - label_y) > S(100):
                continue
            parent = get(slider, "AXParent")
            children = list(get(parent, "AXChildren") or [])
            i = children.index(slider)
            if i + 1 < len(children) and frame(children[i + 1]):
                x, y, w, h = frame(children[i + 1])
                return ((x + w / 2) * scale, (y + h / 2) * scale)
    except Exception:
        pass
    return None


def norm(s):
    return s.replace(" ", "")


def _player_by_ocr(wr):
    """Player rect without UI Automation: 「播放器」 title = top-left; the right-hand property panel's tabs = right
    edge; the 'HH:MM:SS:FF / HH:MM:SS:FF' readout = bottom. Falls back to 剪映's default proportions."""
    W, H = wr.right - wr.left, wr.bottom - wr.top
    ts = jy_ui.texts((wr.left, wr.top, wr.right, wr.top + int(H * 0.78)))
    title = [t for t in ts if norm(t[0]).startswith("播放器")]   # 「播放器-时间线01」
    left = int(title[0][3][0] - 20) if title else wr.left + int(W * 0.30)
    top = int(title[0][3][3] + 11 * auto.ui_scale()) if title else wr.top + int(H * 0.06)
    tabs = [t for t in ts if norm(t[0]) in RIGHT_TABS and t[1] > left + W * 0.2 and t[2] < top + H * 0.03]
    right = int(min(t[3][0] for t in tabs) - 25) if tabs else wr.left + int(W * 0.78)
    tc = [t for t in ts if re.search(r"\d{2}:\d{2}:\d{2}:\d{2}", norm(t[0])) and left < t[1] < right]
    # the readout sits ~40 pt below the video area (measured on Windows 150 %: UIA bottom 1359, readout top 1418)
    bottom = int(min(t[3][1] for t in tc) - 40 * auto.ui_scale()) if tc else wr.top + int(H * 0.62)
    return (left, top, right, bottom)


def geom():
    """Locate the player, the property panel and the material panel. Player: UIA id on Windows, OCR elsewhere.
    Material panel: from the 「素材」 label of the top icon row, searched anywhere above the player (its height
    differs per platform: Windows y≈95, Mac ≈190 because of the title bar)."""
    global PANEL, MAT, PLAYER, WIN, TOP_Y
    import steps
    w = steps.uia_retry(jy_ui.win)
    wr = w.BoundingRectangle
    WIN = (wr.left, wr.top, wr.right, wr.bottom)
    ed = w.Control(searchDepth=3, AutomationId="editPanelLoader.editWin")
    if ed.Exists(1, 0):
        r = ed.BoundingRectangle
        PLAYER = (r.left, r.top, r.right, r.bottom)
    else:
        PLAYER = _player_by_ocr(wr)          # Mac geometry uses OCR; supported controls use native AX elsewhere
    r = _Rect(*PLAYER)
    PANEL = (r.right + S(10), Y(50), wr.right - S(10), wr.bottom - S(10))
    H = wr.bottom - wr.top
    zone = (wr.left, max(wr.top, 0), r.left, max(r.top + S(60), wr.top + int(H * 0.16)))
    tabs = sorted([h for h in jy_ui.texts(zone) if norm(h[0]).startswith("素材")], key=lambda h: h[2])
    if not tabs:
        raise steps.Pause("找不到左上角「素材」那一排图标（剪映没在编辑页，或者窗口太小）")
    TOP_Y = int(tabs[0][2])
    left = int(tabs[0][3][0] - S(35))
    MAT = (left, TOP_Y - S(40), r.left - S(15), r.bottom + S(110))  # its bottom bar (开始识别 …) is below the player
    return PANEL, MAT, PLAYER


def topband():
    """The top icon row (素材 音频 文本 贴纸 特效 转场 滤镜 …), from the material panel's left edge to the player."""
    return (MAT[0], TOP_Y - S(40), PLAYER[0], TOP_Y + S(40))


def P(dx):
    """x in the property panel, measured from its left edge (old layout: 3100 + dx)."""
    return int(PANEL[0] + S(dx))


def M(dx, from_right=False):
    """x in the material panel: from its left edge (old 540 + dx) or from its right edge (old 1760 - dx)."""
    return int(MAT[2] - S(dx) if from_right else MAT[0] + S(dx))


def label_column():
    """x range where the property panel's row labels (字体 颜色 字号 磨皮 …) sit. Wider than the panel's left edge:
    on Mac the labels start left of the OCR-estimated player edge."""
    return PANEL[0] - S(120), PANEL[0] + S(260)


# ---------- tab rows ----------
def _rows(region):
    """OCR hits of a region grouped into horizontal rows (top to bottom)."""
    hits = sorted([h for h in jy_ui.texts(region) if norm(h[0])], key=lambda h: h[2])
    rows = []
    for h in hits:
        if rows and abs(h[2] - rows[-1][-1][2]) <= S(16):
            rows[-1].append(h)
        else:
            rows.append([h])
    return rows


def _pick(row, name):
    exact = [h for h in row if norm(h[0]) == name]
    if exact:
        return exact[0]
    pre = [h for h in row if len(norm(h[0])) >= 2 and (norm(h[0]).startswith(name) or name.startswith(norm(h[0])))
           and len(norm(h[0])) <= len(name) + 2]
    return pre[0] if pre else None


def tab_rows():
    """The property panel's tab rows: row 0 = first-level (画面 音频 变速 … / 文本 动画 …), row 1 = second level
    (基础 抠像 美颜美体 … / 基础 模板 气泡 花字), row 2 = third level (美颜 美型 …). Found by OCR, not by height."""
    region = (PANEL[0] - S(60), PANEL[1], PANEL[2], PANEL[1] + S(330))
    rows = [r for r in _rows(region) if 1 <= len(r) <= 9 and all(len(norm(h[0])) <= 6 for h in r)]
    first = next((i for i, r in enumerate(rows) if any(norm(h[0]) in RIGHT_TABS for h in r)), None)
    return rows[first:] if first is not None else rows


def tab(name, sub=False, level=None):
    """Click a tab by name in the first-level row (sub=False), the second (sub=True) or any `level`."""
    lv = level if level is not None else (1 if sub else 0)
    if auto.IS_MAC:
        for _ in range(10):
            native = _native_tab_hit(name)
            if native:
                jy_ui.click(native[1], native[2])
                time.sleep(0.7)
                if name == "美颜美体" and not _native_tab_hit("美颜预设"):
                    jy_ui.click(native[1], native[2])
                    time.sleep(0.7)
                return native
            time.sleep(0.3)
    rows = tab_rows()
    order = ([rows[lv]] if lv < len(rows) else []) + [r for i, r in enumerate(rows) if i != lv]
    for r in order:                          # the expected row first, then the others (layout differs per build)
        h = _pick(r, name)
        if h:
            jy_ui.click(h[1], h[2])
            time.sleep(0.7)
            return h
    raise LookupError(f"tab '{name}' not found: {[[norm(h[0]) for h in r] for r in rows]}")


def scroll(n, down=True):
    auto.MoveTo(PANEL[0] + S(300), PANEL[1] + S(850))
    for _ in range(n):
        (auto.WheelDown if down else auto.WheelUp)(1)
    time.sleep(0.4)


def row(label, scroll_tries=6):
    """Return (label_hit, number_hit) for a slider row, scrolling down until the label is visible."""
    x0, x1 = label_column()
    for i in range(scroll_tries):
        hits = jy_ui.texts((x0, PANEL[1], PANEL[2], PANEL[3]))
        cand = [h for h in hits if h[1] < x1]
        labs = [h for h in cand if norm(h[0]) == label] or \
               [h for h in cand if norm(h[0]).startswith(label) and len(h[0].strip()) <= len(label) + 3]
        if labs:
            lab = sorted(labs, key=lambda h: h[2])[0]
            # re-OCR just this row: tiny values like a lone "0" are often missed in a full-panel pass
            band = jy_ui.texts((x0, int(lab[2]) - S(28), PANEL[2], int(lab[2]) + S(28)),
                               upscale=2 if auto.IS_MAC else 1)
            nums = [h for h in band if h[1] > lab[3][2] + S(40) and re.fullmatch(r"-?[\d.]+(dB|%|x|s|°)?", norm(h[0]))]
            if nums:
                return lab, max(nums, key=lambda h: h[1])
            # empty number box: right side of the row
            return lab, (None, PANEL[2] - S(140), lab[2], None, None)
        scroll(4)
    raise LookupError(f"row '{label}' not found")


def _double_click(x, y):
    auto.DoubleClick(int(x), int(y), waitTime=0.05)


def _box_selected(cx, cy):
    """A focused input shows a teal selection highlight; used as a gate on Windows and Mac."""
    import numpy as np
    im = np.asarray(jy_ui.grab((int(cx) - S(45), int(cy) - S(16), int(cx) + S(45), int(cy) + S(16)))).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    teal = (g > 70) & (b > 70) & (r < 60) & (g - r > 35)
    return teal.mean() > 0.04


def type_value(x, y, value, readback, defocus=None, paste=False, what="数值", focused=None):
    """Put `value` into the input at (x, y) and VERIFY it with readback() -> bool.

    attempt 1: click · 2: double-click · 3: click an inert spot (defocus) then click.
    Both platforms verify the teal selection before typing; Mac then uses select-all + paste + Enter and reads back."""
    import steps
    if auto.IS_MAC:
        paste = True
    for attempt in range(3):
        if attempt == 0:
            jy_ui.click(x, y)
        elif attempt == 1:
            _double_click(x, y)
        else:
            if defocus:
                auto.Click(int(defocus[0]), int(defocus[1]), waitTime=0.25)
            jy_ui.click(x, y)
        jy_ui.fx({"type": "clear"})
        time.sleep(0.3)
        teal = focused() if focused else _box_selected(x, y)
        if not teal:
            continue                                  # never type into an unverified box
        if auto.IS_MAC or not teal:
            jy_ui.keys("{Ctrl}a", wait=0.15)          # Mac: select the whole existing value before pasting
        if paste:
            auto.SetClipboardText(str(value))
            jy_ui.keys("{Ctrl}v", wait=0.3)
        else:
            jy_ui.keys(str(value), wait=0.08)
        jy_ui.keys("{Enter}", wait=0.35)
        if readback():
            return attempt + 1
    raise steps.Pause(f"{what}没填进去：{value}")


def _num(s):
    m = re.search(r"-?\d+(\.\d+)?", s or "")
    return float(m.group()) if m else None


def set_value(label, value, fx_label=None, color=None):
    lab, num = row(label)
    # v1.1.4(mac 实测): OCR 给的是文字框「顶部」，点顶部会落在行间缝隙 → 点行中心才中
    x, y = num[1], (num[2] + num[3][3]) / 2 if num[3] else num[2]
    native = _native_number_hit(lab[2])
    if native:
        x, y = native
    if fx_label:
        jy_ui.fx({"type": "status", "text": fx_label})
    if color:
        jy_ui.fx({"type": "click", "at": [x, y], "color": color})

    def ok():
        time.sleep(0.3)
        got = _num(get_value(label))
        return got is not None and abs(got - float(value)) < 0.51
    type_value(x, y, value, ok, defocus=(lab[1], lab[2]), what=f"「{label}」")
    return lab, num


def get_value(label):
    return row(label)[1][0]


def checkbox(title, on=True):
    """Tick the checkbox left of a section title (e.g. 脸型, 五官精修)."""
    for _ in range(6):
        hits = [h for h in jy_ui.texts(PANEL) if norm(h[0]) == title]
        if hits:
            h = hits[0]
            jy_ui.click(h[3][0] - S(30), h[2])
            time.sleep(0.4)
            return h
        scroll(4)
    raise LookupError(title)
