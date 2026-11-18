"""Building blocks for a live 剪映 edit (mode B), each one verified. Used by live_run.py."""
import json
import re
import time

import uiautomation as auto

import jy_ui
import panel
import timeline as tl

PINK, CYAN, PURPLE, GREEN, WHITE = "#FF287F", "#5CF2FF", "#A98BFF", "#7DFF8A", "#FFFFFF"
FIX = {}


def fx(**e):
    jy_ui.fx(e)


def status(text):
    fx(type="status", text=text)


class Pause(Exception):
    pass


def wait_for(pred, timeout=20, every=0.5, what="condition"):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = pred()
        if r:
            return r
        time.sleep(every)
    raise Pause(f"等待超时：{what}")


# ---------- open a draft ----------
def uia_retry(fn, tries=6, delay=0.8):
    """UI Automation COM calls fail transiently while 剪映 switches pages (EVENT_E_NO_SUBSCRIBERS etc.)."""
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001  (comtypes COMError and friends)
            last = e
            time.sleep(delay)
    raise Pause(f"UI Automation 一直出错：{last!r}")


def in_editor():
    # UIA id first; after a 剪映 restart it can vanish, so fall back to the 导出 button (editor only) by OCR
    if uia_retry(lambda: jy_ui.win().Control(searchDepth=12, AutomationId="editor.export").Exists(0.2, 0)):
        return True
    wr = jy_ui.win().BoundingRectangle
    return bool([h for h in jy_ui.texts((wr.right - 700, 0, wr.right, 70)) if h[0].replace(" ", "") == "导出"])


def go_home():
    if not in_editor():
        return
    jy_ui.activate()
    hits = jy_ui.find("菜单", (0, 0, 600, 70))
    jy_ui.click(hits[0][1], hits[0][2]) if hits else jy_ui.click(155, 26)
    time.sleep(0.7)
    jy_ui.click_text("返回首页", (0, 0, 900, 900))
    wait_for(lambda: not in_editor(), 15, what="回到首页")
    time.sleep(1.5)


JY_EXE = None      # v1.0: no personal path in code — config.json / env JIANYING_EXE / running process / install dirs


def jianying_running():
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe"], capture_output=True).stdout
    return b"JianyingPro.exe" in out


def start_jianying():
    """Start 剪映 (it then rescans the draft folder) and wait for its home page."""
    import subprocess
    from config import jianying_exe
    exe = JY_EXE or jianying_exe()
    if not exe:
        raise Pause("找不到剪映（JianyingPro.exe）：在 config.json 的 jianying_exe 里填安装路径")
    subprocess.Popen([exe], close_fds=True)
    wait_for(lambda: jy_ui.win().Exists(0.5, 0), 60, what="剪映启动")
    time.sleep(8)
    import popups
    print("popups closed:", popups.close_popups())


def open_draft(name):
    if not jianying_running():
        start_jianying()
    go_home()
    import popups                                      # ads / tips on the home page block the draft cards
    popups.close_popups()
    # the home page renders BLACK while the overlay is up, and hide/show breaks the overlay's transparency:
    # STOP the overlay process here and start a fresh one once the editor is open
    import ctypes
    jy_ui.overlay_stop()
    w = uia_retry(jy_ui.win)
    ctypes.windll.user32.ShowWindow(w.NativeWindowHandle, 9)      # SW_RESTORE
    w.SetActive()
    time.sleep(1.2)
    if not jy_ui.repaint(w):
        raise Pause("剪映首页一直是黑的（没有重绘）")
    # v0.8: the home-page card TRUNCATES long names (「过程演示正式版」 → 「过程演示正…」), so a 6-char prefix never
    # matched. Match on the first 4 chars, then take the card text most similar to the full name.
    import difflib
    short = name[:4]
    r = w.BoundingRectangle                       # only inside 剪映 (other windows may show the same name)

    def _cards():
        hs = [h for h in jy_ui.texts((r.left, r.top, r.right, r.bottom))
              if h[0].replace(" ", "").startswith(short)]
        return sorted(hs, key=lambda h: -difflib.SequenceMatcher(None, name, h[0].replace(" ", "")).ratio())
    try:
        hit = wait_for(_cards, 15, what=f"草稿 {name}")
    except Pause:
        # v0.8: a draft written while 剪映 is running is not always picked up (剪映 rewrites its draft index from
        # memory when another draft is closed). Closing the window only hides it in the tray -> 剪映 must be QUIT
        # (tray icon → 退出) and started again, then it rescans the draft folder.
        raise Pause(f"首页没有草稿「{name}」：请从右下角托盘图标退出剪映、再重新打开，然后用 --from 2 继续")
    x0, y0, x1, y1 = hit[0][3]
    jy_ui.click((x0 + x1) / 2, y0 - 80, label=f"打开草稿 {name}")
    wait_for(in_editor, 30, what="进入编辑页")
    time.sleep(2.5)
    tl.maximise()
    jy_ui.overlay_start()
    time.sleep(1.0)
    tl.layout()
    tl.calibrate()


# ---------- timeline helpers ----------
def select_at(t):
    jy_ui.click(tl.x_of(t), tl.L["track_y"])
    time.sleep(0.5)


def panel_tabs():
    return [h[0] for h in jy_ui.texts((panel.PANEL[0], panel.PANEL[1], panel.PANEL[2], panel.PANEL[1] + 90))]


# ---------- beauty ----------
def apply_beauty_preset(t, preset="我的预设1"):
    # 剪映 detects the face on the frame under the PLAYHEAD: put the playhead inside this segment first
    tl.seek(t)
    select_at(t)
    if "画面" not in panel_tabs():
        raise Pause("没有选中视频片段")
    panel.tab("画面")
    panel.tab("美颜美体", sub=True)
    time.sleep(0.8)
    jy_ui.click_text("美颜预设", panel.PANEL)
    time.sleep(1.2)
    h = wait_for(lambda: jy_ui.find(preset, panel.PANEL), 10, what="美颜预设卡片")
    card = (h[0][1], h[0][2] - 60)
    fx(type="fly", **{"from": [card[0], card[1]]}, to=[tl.x_of(t), tl.L["track_y"]], color=CYAN,
       label="美颜 · 磨皮23 美白23 匀肤22 清晰18 · 瘦脸21 V脸23 · 大眼30 亮眼27", hold=2.2, dur=0.6)
    for attempt in range(3):
        jy_ui.click(card[0], card[1])
        time.sleep(1.2)
        jy_ui.click_text("美颜", (panel.PANEL[0], 200, panel.PANEL[0] + 200, 270), exact=True)
        time.sleep(0.8)
        try:
            if str(panel.get_value("磨皮")) == "23":
                return
        except LookupError:
            pass
        jy_ui.click_text("美颜预设", panel.PANEL)
        time.sleep(1.0)
    raise Pause(f"美颜预设没套上（{t:.1f}s）")


# ---------- fonts / colours / presets in the text panel ----------
def pick_font(name):
    f = wait_for(lambda: jy_ui.find("字体", (panel.P(-90), 100, panel.P(200), 700), exact=True), 5, what="字体行")
    jy_ui.click(panel.P(400), f[0][2])
    time.sleep(1.0)
    jy_ui.click_text("收藏", (panel.P(-90), f[0][2], panel.PANEL[2], f[0][2] + 160), exact=True)
    time.sleep(0.8)
    h = wait_for(lambda: jy_ui.find(name, (panel.P(-90), f[0][2] + 60, panel.PANEL[2], f[0][2] + 700), exact=True), 8, what=f"字体 {name}")
    jy_ui.click(h[0][1], h[0][2])
    time.sleep(2.0)
    now = [x[0] for x in jy_ui.texts((panel.P(-90), f[0][2] - 25, panel.PANEL[2], f[0][2] + 25))]
    if name not in "".join(now):
        raise Pause(f"字体没换成 {name}：{now}")


def _swatch_rgb(c):
    import numpy as np
    im = jy_ui.grab((int(c[1] + 105), int(c[2] - 8), int(c[1] + 165), int(c[2] + 8)))
    return np.asarray(im).reshape(-1, 3).mean(axis=0)


def set_color(hexv):
    """Colour swatch -> picker -> Hex box (verified focused) -> type -> Enter -> close -> VERIFY the swatch colour."""
    hexv = hexv.lstrip("#").upper()
    want = [int(hexv[i:i + 2], 16) for i in (0, 2, 4)]
    c = wait_for(lambda: jy_ui.find("颜色", (panel.P(-90), 100, panel.P(200), 900), exact=True), 5, what="颜色行")[0]
    if max(abs(a - b) for a, b in zip(_swatch_rgb(c), want)) < 30:
        return                                            # already this colour
    R = (panel.P(-90), 300, panel.PANEL[2], 1600)
    for attempt in range(2):
        jy_ui.click(c[1] + 135, c[2])                     # middle of the swatch (its right end is a dropdown)
        time.sleep(0.9)
        hits = wait_for(lambda: [h for h in jy_ui.texts(R) if h[0].replace(" ", "").startswith("Hex")], 5, what="Hex")
        hx = hits[0]
        tok = hx[0].replace(" ", "")
        if re.fullmatch(r"Hex[0-9A-Fa-f]{6}", tok):          # OCR glued label + value: aim at the value part
            x0, x1 = hx[3][0], hx[3][2]
            vx, vy = x0 + (x1 - x0) * 0.62, hx[2]
        else:
            vals = [h for h in jy_ui.texts(R) if abs(h[2] - hx[2]) < 20 and h[1] > hx[1] + 20
                    and re.fullmatch(r"#?[0-9A-Fa-f]{6}", h[0].replace(" ", ""))]
            pct = [h for h in jy_ui.texts(R) if abs(h[2] - hx[2]) < 20 and h[0].replace(" ", "").endswith("%")]
            if vals:
                v = min(vals, key=lambda h: h[1])
                vx, vy = v[1], v[2]
            elif pct:                                     # white value text is often missed by OCR: the box is
                vx, vy = (hx[3][2] + pct[0][3][0]) / 2, hx[2]  # the gap between 'Hex ⌄' and the opacity box
            else:
                raise Pause("颜色面板里找不到 Hex 数值框")
        panel._double_click(vx, vy)
        time.sleep(0.3)
        if not panel._box_selected(vx, vy):
            raise Pause("颜色框没选中")
        jy_ui.keys(hexv, wait=0.1)
        jy_ui.keys("{Enter}", wait=0.4)
        jy_ui.click(c[1], c[2] + 120)                     # inert label area closes the picker (never Esc)
        time.sleep(0.6)
        got = _swatch_rgb(c)
        if max(abs(a - b) for a, b in zip(got, want)) < 30:
            return
    raise Pause(f"颜色没设上 {hexv}（现在 {[int(x) for x in got]}）")


def preset_style(n=2):
    p = wait_for(lambda: jy_ui.find("预设样式", (panel.P(-90), 100, panel.P(300), 1200)), 5, what="预设样式")
    y = p[0][2] + 66
    x = p[0][3][0] + 12 + (n - 1) * 78     # first swatch starts under the label
    jy_ui.click(x, y)
    time.sleep(0.8)


def stroke_width(v):
    panel.set_value("粗细", v)


# ---------- subtitles ----------
def _input_focused(box):
    """An empty focused input shows a teal border: look for teal pixels in a band around the placeholder line."""
    import numpy as np
    x0, y0, x1, y1 = box
    im = np.asarray(jy_ui.grab((int(x0) - 40, int(y0) - 22, int(x1) + 600, int(y1) + 22))).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    teal = (g > 120) & (b > 120) & (r < 90) & (g - r > 50)
    return teal.sum() > 40



def recognize_subtitles(words=("私域", "牢饭", "纯扯", "割韭菜", "会销")):
    M = panel.M
    jy_ui.click_text("文本", (M(0), 60, M(0, True), 130))
    time.sleep(0.8)
    if not jy_ui.find("智能字幕", (M(0), 120, M(200), 900)):      # 智能文本 is a toggle group: open it only if shut
        jy_ui.click_text("智能文本", (M(0), 120, M(200), 900))
        time.sleep(0.6)
    jy_ui.click_text("智能字幕", (M(0), 120, M(200), 900))
    time.sleep(1.0)
    btn = jy_ui.find("新增", (M(300, True), 180, M(0, True), 340)) or jy_ui.find("管理", (M(300, True), 180, M(0, True), 340))
    if not btn:
        raise Pause("找不到自定义词汇的 新增/管理 按钮")
    jy_ui.click(btn[0][1], btn[0][2])
    time.sleep(1.2)
    pop = (M(600, True), btn[0][2] + 30, M(0, True), btn[0][2] + 520)       # the vocabulary popup
    if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:      # a second click toggles it shut: reopen
        jy_ui.click(btn[0][1], btn[0][2])
        time.sleep(1.2)
    if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:
        raise Pause("自定义词汇窗口没打开")

    def tags():
        # tags are small grey text: OCR a 2x upscale (plain OCR read 牢饭 as 车证)
        import numpy as np
        im = jy_ui.grab(pop)
        im = im.resize((im.width * 2, im.height * 2))
        res, _ = jy_ui.ocr_engine()(np.array(im)[:, :, ::-1])
        return [t.replace(" ", "").rstrip("X×x") for _, t, _ in (res or [])]

    def have(w, ts):
        import difflib
        return any(w == t or (len(t) <= len(w) + 1 and difflib.SequenceMatcher(None, w, t).ratio() >= 0.5) for t in ts)
    for w in words:
        if have(w, tags()):
            continue
        ph = [h for h in jy_ui.texts(pop) if "enter" in h[0].lower() or "输入关" in h[0]]
        if not ph:
            raise Pause("找不到自定义词汇输入框")
        jy_ui.click(ph[0][1], ph[0][2])
        time.sleep(0.4)
        if not _input_focused(ph[0][3]):
            raise Pause("自定义词汇输入框没有获得焦点（不打字）")
        auto.SetClipboardText(w)
        jy_ui.keys("{Ctrl}v", wait=0.2)
        jy_ui.keys("{Enter}", wait=0.5)
        if not have(w, tags()):
            raise Pause(f"自定义词汇没加上：{w}")
    fx(type="banner", text="自定义词汇", sub=" · ".join(words) + "  → 识别一次就对", hold=2.5)
    jy_ui.click(M(460), 900)
    time.sleep(0.4)
    jy_ui.click_text("开始识别", (M(0), panel.MAT[3] - 260, M(0, True), panel.MAT[3] + 40))
    time.sleep(2)
    wait_for(lambda: not [h for h in jy_ui.texts((M(0), 600, panel.PLAYER[2], panel.MAT[3] + 160)) if "识别中" in h[0]], 120, 2, "字幕识别")
    time.sleep(1)
    tl.layout()
    tl.calibrate()


def style_subtitles(sample_t=5.0):
    """Select one subtitle (style applies to all: '应用到全部字幕' is on) and set the owner's subtitle look."""
    tl.seek(sample_t)
    # find the subtitle row by OCR (its labels near sample_t), never the filter row
    r = tl.L["tl"]
    xc = tl.x_of(sample_t)
    hits = [h for h in jy_ui.texts((int(xc) - 200, r[1] + 60, int(xc) + 200, tl.L["track_y"] - 45))
            if "高清" not in h[0] and "变速" not in h[0] and ".mp4" not in h[0]]
    if not hits:
        raise Pause("时间线上找不到字幕轨")
    h = min(hits, key=lambda h: abs(h[1] - xc))
    jy_ui.click(h[1], h[2])
    time.sleep(0.8)
    tabs = panel_tabs()
    if "字幕" not in tabs and "文本" not in tabs:
        raise Pause(f"没有选中字幕：{tabs}")
    if "文本" in tabs:
        panel.tab("文本")
    pick_font("新青年体")
    panel.set_value("字号", 6)
    preset_style(2)
    set_color("FFFFFF")
    panel.scroll(8)
    stroke_width(70)
    panel.scroll(12, down=False)


# ---------- big keyword text ----------
def set_xy(x=None, y=None):
    lab, _ = panel.row("位置")
    band = [h for h in jy_ui.texts((panel.PANEL[0], int(lab[2]) - 28, panel.PANEL[2], int(lab[2]) + 28))
            if re.fullmatch(r"[XYxy]?-?[\d.]+", h[0].replace(" ", "")) and h[1] > panel.PANEL[0] + 120]
    band.sort(key=lambda h: h[1])
    if len(band) < 2:
        raise Pause(f"位置行没读全：{[h[0] for h in band]}")
    # OCR may glue the 'X' label to the value ("X900"): click the value part (right side of that token)
    xb = band[0]
    xbox = (xb[0], xb[3][2] - 25 if xb[0][:1] in "XxYy" else xb[1], xb[2])
    yb = band[-1]
    for val, box in ((x, (None, xbox[1], xbox[2])), (y, (None, yb[1], yb[2]))):
        if val is None or box is None:
            continue
        jy_ui.click(box[1], box[2])
        time.sleep(0.25)
        if not panel._box_selected(box[1], box[2]):
            panel._double_click(box[1], box[2])
            time.sleep(0.25)
        if not panel._box_selected(box[1], box[2]):
            raise Pause("位置框没选中")
        jy_ui.keys(str(val), wait=0.08)
        jy_ui.keys("{Enter}", wait=0.3)


def replace_content(text):
    # v0.8: on a SUBTITLE clip the first text in this band is the 「文本、排列、气泡、花字应用到全部字幕」 checkbox
    # row — double-clicking it un-ticked the checkbox (2026-11-18). Skip that row, take the content box below it.
    c = wait_for(lambda: [h for h in jy_ui.texts((panel.P(20), 180, panel.PANEL[2], 330))
                          if h[0].strip() and "应用到全部" not in h[0] and "排列" not in h[0]], 5, what="文字内容框")[0]
    panel._double_click(c[1], c[2])
    time.sleep(0.3)
    if not panel._box_selected(c[1], c[2]):
        raise Pause("文字内容没选中")
    auto.SetClipboardText(text)
    jy_ui.keys("{Ctrl}v", wait=0.4)
    jy_ui.click(panel.P(50), 330)                     # leave the box (inert area under the content box)
    time.sleep(0.3)


def add_default_text_at(t):
    tl.seek(t)
    M = panel.M
    jy_ui.click_text("文本", (M(0), 60, M(0, True), 130))
    time.sleep(0.6)
    jy_ui.click_text("新建文本", (M(0), 120, M(200), 900))
    time.sleep(0.8)
    card = wait_for(lambda: jy_ui.find("默认文本", (M(140), 120, M(0, True), 700)), 5, what="默认文本卡片")[0]
    auto.MoveTo(int(card[1]), int(card[2]))
    time.sleep(0.6)
    jy_ui.click(card[1] + 43, card[2] + 43)
    time.sleep(1.2)
    if "文本" not in panel_tabs():
        raise Pause("新文本没加上")


KW = dict(font="仓耳榜黑", size=13, x=1300, y_red=950, y_white=250, stroke=90, anim="放大")


def _norm_anim(s):
    # OCR reads the roman numeral in 打字机I / 打字机II as 1 / l / | / ] / ！
    s = s.replace(" ", "")
    return re.sub(r"[1l|\]Ii!！]", "I", s)


def _card_selected(cx, cy):
    """An applied animation card has a teal border (the 「无」 card has it when nothing is applied)."""
    import numpy as np
    a = np.asarray(jy_ui.grab((int(cx) - 62, int(cy) - 62, int(cx) + 62, int(cy) + 62))).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return int(((g > 150) & (b > 150) & (r < 90)).sum()) > 150


def set_anim(name):
    """文本 → 动画 → 入场 → apply `name` and VERIFY it (teal border on its card).
    v0.6: a card that is not downloaded yet only DOWNLOADS on the first click (v0.3–v0.5 never applied the
    animation and did not notice). So: click → wait → if not applied, click the download arrow → wait → click."""
    panel.tab("动画")
    time.sleep(0.8)
    jy_ui.click_text("入场", (panel.PANEL[0], 120, panel.PANEL[2], 200))
    time.sleep(0.8)
    want = _norm_anim(name)

    def look():
        return [h for h in jy_ui.texts(panel.PANEL) if _norm_anim(h[0]) == want and h[2] > 280]
    hits = []
    for _ in range(4):                       # the card may be below the fold
        hits = look()
        if hits:
            break
        panel.scroll(3)
    if not hits:
        panel.scroll(12, down=False)
        raise Pause(f"找不到入场动画 {name}")
    h = hits[0]
    cx, cy = h[1], h[2] - 65                 # card centre (label sits under the card)
    ok = _card_selected(cx, cy)
    for attempt in range(3):
        if ok:
            break
        jy_ui.click(cx, cy)
        for _ in range(8):
            time.sleep(0.6)
            ok = _card_selected(cx, cy)
            if ok:
                break
        if ok:
            break
        jy_ui.click(cx + 26, cy + 26)        # the download arrow (bottom-right of the card)
        for _ in range(16):
            time.sleep(0.6)
            ok = _card_selected(cx, cy)
            if ok:
                break
    panel.scroll(12, down=False)
    if not ok:
        raise Pause(f"入场动画没套上：{name}")
    panel.tab("文本")


def style_keyword(color, x, y, size=None, anim=None):
    """Full style for the FIRST keyword (font, preset, stroke are inherited by every clone)."""
    pick_font(KW["font"])
    panel.set_value("字号", size or KW["size"])
    preset_style(2)
    set_color(color)
    set_xy(x, y)
    panel.scroll(8)
    stroke_width(KW["stroke"])
    panel.scroll(12, down=False)
    set_anim(anim or KW["anim"])


def find_segment(text):
    """Timeline segment whose label starts with text[:2]; returns (x, y)."""
    import difflib
    r = tl.L["tl"]
    key = text.replace(" ", "")[:4]
    best, score = None, 0.0
    for h in jy_ui.texts((r[0], r[1] + 60, r[2], r[3])):
        lab = h[0].replace(" ", "")[:len(key)]
        s = difflib.SequenceMatcher(None, key, lab).ratio()
        if s > score:
            best, score = h, s
    if best is None or score < 0.5:
        raise Pause(f"时间线上找不到 {text}")
    return best[1], best[2]


def clone_keyword(template_text, t, text, color=None, x=None, y=None, size=None, anim=None):
    """Copy the template keyword clip, paste at t, then set content + colour + size + X/Y + animation
    (all of them on EVERY clone — the plan differs per keyword)."""
    x0, y0 = find_segment(template_text)
    jy_ui.click(x0, y0)
    time.sleep(0.4)
    jy_ui.keys("{Ctrl}c", wait=0.3)
    tl.seek(t)
    jy_ui.keys("{Ctrl}v", wait=0.8)
    time.sleep(0.6)
    if "文本" not in panel_tabs():
        raise Pause("粘贴的大字没选中")
    panel.tab("文本")
    replace_content(text)
    if size:
        panel.set_value("字号", size)
    if color:
        set_color(color)
    if x is not None or y is not None:
        set_xy(x, y)
    if anim:
        set_anim(anim)


# ---------- filter ----------
def _purple_right_edge(y, x0, x1):
    import numpy as np
    x0, x1 = int(max(0, x0 - 4)), int(x1)
    im = np.asarray(jy_ui.grab((x0, int(y) - 3, x1, int(y) + 3))).astype(int).mean(axis=0)
    purple = (im[:, 2] > 110) & (im[:, 2] - im[:, 0] > 40)
    xs = np.nonzero(purple)[0]
    if not len(xs):
        return None
    # the clip's icon/label interrupts the purple fill, so take the right-most purple pixel in the window
    return x0 + int(xs.max())


def _purple_row(x0, x1):
    """y of the top-most timeline row that has a purple (filter) clip starting near x0, or None.
    v0.8: on a long timeline the default 3-s filter clip is too narrow to show its 「高清增强」 label (icon only),
    so the clip is found by colour, not by OCR."""
    import numpy as np
    r = tl.L["tl"]
    im = np.asarray(jy_ui.grab((int(x0), int(r[1]) + 40, int(x1), int(r[3])))).astype(int)
    # filter purple ≈ (90, 75, 200): red clearly present. The BGM / voice tracks are dark BLUE (red ≈ 20) and were
    # mistaken for the filter when the filter row was scrolled out of view (「演示终版」, 2026-11-18)
    R, G, B = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    purple = (B > 130) & (R > 60) & (B - G > 60) & (R - G > -15)
    rows = np.nonzero(purple.sum(axis=1) >= 6)[0]
    if not len(rows):
        return None
    run = [rows[0]]                                   # first contiguous band = the top-most purple clip
    for y in rows[1:]:
        if y - run[-1] > 2:
            break
        run.append(y)
    return int(r[1]) + 40 + int(np.mean(run))


def scroll_tracks_top():
    """Scroll the timeline's track area to the TOP (new filter / effect rows are added above everything)."""
    r = tl.L["tl"]
    auto.MoveTo(int(r[0] + (r[2] - r[0]) * 0.3), int((r[1] + r[3]) / 2))   # inside the tracks, no calibration needed
    for _ in range(12):
        auto.WheelUp(waitTime=0.05)
    time.sleep(0.4)


def add_filter_full(name="高清增强", strength=34, total=None):
    tl.seek(0.0)
    scroll_tracks_top()
    tl.calibrate()
    M = panel.M
    y = _purple_row(tl.x_of(0) - 2, tl.x_of(6))
    if y is None:                                      # idempotent: a resumed run must not add a second filter
        jy_ui.click_text("滤镜", (M(0), 60, M(0, True), 130))
        time.sleep(1.0)
        jy_ui.click_text("收藏", (M(0), 120, M(200), 500))
        time.sleep(0.8)
        h = wait_for(lambda: jy_ui.find(name, (M(140), 120, M(0, True), 1300), exact=True), 10, what=f"滤镜 {name}")
        cx, cy = h[0][1], h[0][2] - 90
        auto.MoveTo(int(cx), int(cy))
        time.sleep(0.7)
        jy_ui.click(cx + 67, cy + 50)                  # the "+" that appears on hover
        time.sleep(1.2)
        scroll_tracks_top()
        tl.calibrate()
        y = wait_for(lambda: _purple_row(tl.x_of(0) - 2, tl.x_of(6)), 8, what="新滤镜片段（紫色）")
    end = total or (tl.total_frames() / tl.FPS)

    def purple_at(x):
        return _purple_right_edge(y, x - 2, x + 2) is not None

    def starts_at_zero():
        # the clip's left part is its 「高清增强」 label (not purple): look for the purple border right at 0 s
        return _purple_right_edge(y, tl.x_of(0) - 2, tl.x_of(0) + 12) is not None

    # v0.8: on a 3-min timeline the 3-s filter clip is ~40 px wide; a grab 2 px off the edge MOVED the whole clip
    # to the end instead of extending it (「演示终版」). So: look for the edge only in the first 4 s, then check BOTH
    # ends after the drag (purple at 0 s and right edge at the end); otherwise undo and retry with another offset.
    # a filter clip that is NOT at 0 s (moved by an earlier bad grab) -> drag its body back to 0 first
    if not starts_at_zero():
        xs = [x for x in range(int(tl.x_of(0)), int(tl.x_of(end)) + 2, 2) if purple_at(x)]
        if xs:
            l, r_ = xs[0], xs[-1]
            auto.DragDrop(int((l + r_) / 2), int(y), int(tl.x_of(0) + (r_ - l) / 2 + 1), int(y), moveSpeed=0.5,
                          waitTime=0.8)
            time.sleep(0.6)
            if not starts_at_zero():
                raise Pause("滤镜片段没能挪回 0 秒")
    ok = False
    for off in (1, 2, 0, 3):
        redge = _purple_right_edge(y, tl.x_of(0), tl.x_of(4))
        if redge is None:
            raise Pause("找不到新滤镜片段的右边缘")
        auto.DragDrop(int(redge) + off, int(y), int(tl.x_of(end)) + 2, int(y), moveSpeed=0.5, waitTime=0.8)
        time.sleep(0.6)
        redge2 = _purple_right_edge(y, tl.x_of(0), tl.x_of(end) + 40)
        start_ok = starts_at_zero()
        if start_ok and redge2 is not None and abs(redge2 - tl.x_of(end)) <= 8:
            ok = True
            break
        tl.undo()                                    # moved instead of stretched (or fell short): undo, retry
        time.sleep(0.6)
    if not ok:
        raise Pause("滤镜没能从 0 秒拉到片尾（试了 4 个抓点）")
    fx(type="fly", **{"from": [tl.x_of(0), y]}, to=[tl.x_of(end), y], color=PURPLE, label=f"滤镜 · {name} {strength}",
       hold=2.5, dur=1.2)
    time.sleep(0.8)
    panel.set_value("强度", strength)
    if str(panel.get_value("强度")).split(".")[0] != str(strength):
        raise Pause("滤镜强度没设上")


# ---------- compliance on the subtitle track (v0.8, owner rule 2026-11-18) ----------
def hide_banned_subtitles(windows):
    """The owner's spoken 私域 hook (「…可以送给你们」) stays in the AUDIO; its subtitle must not show.
    windows = [(t0, t1), …] output times where a banned phrase is spoken. Clicks along the subtitle row in each
    window, reads the clip's text, deletes clips whose text hits compliance.py. Returns the deleted texts."""
    import compliance
    scroll_tracks_top()
    tl.calibrate()
    labs = [h for h in jy_ui.texts(tl.L["tl"]) if h[0].replace(" ", "").startswith(("A", "Α")) and len(h[0].strip()) <= 4]
    if not labs:
        raise Pause("找不到字幕轨道")
    sub_y = sorted(h[2] for h in labs)[len(labs) // 2]
    deleted = []
    for t0, t1 in windows:
        t = max(0.0, t0 - 1.0)
        while t <= t1 + 1.0:
            jy_ui.click(tl.x_of(t), sub_y)
            time.sleep(0.45)
            content = "".join(h[0] for h in jy_ui.texts((panel.P(20), 180, panel.PANEL[2], 280)) if h[0].strip())
            if compliance.hits(content.replace("文本、排列、气泡、花字应用到全部字幕", "")):
                jy_ui.keys("{Delete}", wait=0.6)
                deleted.append(content)
                fx(type="banner", text="字幕不出导流词", sub="声音保留，字幕删掉", hold=1.5)
                continue
            t += 0.4
    return deleted
