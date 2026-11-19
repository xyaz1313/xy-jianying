"""Building blocks for a live 剪映 edit (mode B), each one verified. Used by live_run.py.

v1.1.1: no fixed screen coordinates (see panel.py: S() / Y() / topband() / tab rows); every value typed with
panel.type_value() and read back. Each step still STOPS (Pause) when its check fails — never "skip and go on"."""
import json
import re
import time

import osctl as auto  # v1.1: Windows = uiautomation, Mac = Quartz

import jy_ui
import panel
import timeline as tl
from panel import S, Y, norm
from style import ST   # v1.1.1: every style value comes from style.json

QUIT_HINT = "按 ⌘Q 退出剪映" if auto.IS_MAC else "从右下角托盘图标退出剪映"
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


EDITOR_WORDS = ("草稿参数", "播放器", "导出", "时间线")


def in_editor():
    if not auto.IS_MAC:
        # UIA id first; after a 剪映 restart it can vanish, so fall back to the 导出 button (editor only) by OCR
        if uia_retry(lambda: jy_ui.win().Control(searchDepth=12, AutomationId="editor.export").Exists(0.2, 0)):
            return True
        wr = jy_ui.win().BoundingRectangle
        return bool([h for h in jy_ui.texts((wr.right - 700, wr.top, wr.right, wr.top + 70)) if norm(h[0]) == "导出"])
    # Mac (2026-11-19 test): 「导出」 is white on blue and OCRs as garbage in a narrow strip -> look for any
    # editor-only word in the whole top band of the window
    wr = jy_ui.win().BoundingRectangle
    hs = jy_ui.texts((wr.left, wr.top, wr.right, wr.top + S(240)))
    return any(any(norm(h[0]).startswith(w) for w in EDITOR_WORDS) for h in hs)


def go_home():
    if not in_editor():
        return
    jy_ui.activate()
    wr = jy_ui.win().BoundingRectangle
    if auto.IS_MAC:
        band = (wr.left, wr.top, wr.left + S(700), wr.top + S(150))
        for t in ("首页", "返回首页"):
            if jy_ui.find(t, band):
                jy_ui.click_text(t, band)
                break
        else:
            # Mac 剪映 shows only a ← arrow; ⌘W closes the draft window and returns to the home page (Mac test)
            auto.SendKeys("{Cmd}w", waitTime=1.0)
    else:
        hits = jy_ui.find("菜单", (0, 0, 600, 70))
        jy_ui.click(hits[0][1], hits[0][2]) if hits else jy_ui.click(155, 26)
        time.sleep(0.7)
        jy_ui.click_text("返回首页", (0, 0, 900, 900))
    wait_for(lambda: not in_editor(), 15, what="回到首页")
    time.sleep(1.5)


JY_EXE = None      # v1.0: no personal path in code — config.json / env JIANYING_EXE / running process / install dirs


def jianying_running():
    return auto.process_running(("JianyingPro.exe",) if not auto.IS_MAC else auto.JY_NAMES)


def start_jianying():
    """Start 剪映 (it then rescans the draft folder) and wait for its home page."""
    import subprocess
    from config import jianying_exe
    exe = JY_EXE or jianying_exe()
    if not exe:
        raise Pause("找不到剪映：在 config.json 的 jianying_exe 里填安装路径（Windows 填 JianyingPro.exe，Mac 填 /Applications/剪映专业版.app）")
    if auto.IS_MAC:
        subprocess.Popen(["open", "-a", exe])
    else:
        subprocess.Popen([exe], close_fds=True)
    wait_for(lambda: jy_ui.win().Exists(0.5, 0), 60, what="剪映启动")
    time.sleep(8)
    import popups
    print("popups closed:", popups.close_popups())


def quit_jianying(timeout=8):
    """v1.2: quit 剪映 completely (a running 剪映 never lists a draft written while it runs). A normal close only
    hides it in the tray, so: graceful close -> wait -> force. 剪映 autosaves its open draft; never call this while
    the owner is editing something unsaved."""
    import subprocess
    if not jianying_running():
        return
    if auto.IS_MAC:
        subprocess.run(["osascript", "-e", 'tell application "剪映专业版" to quit'], capture_output=True)
    else:
        subprocess.run(["taskkill", "/IM", "JianyingPro.exe"], capture_output=True)
    t0 = time.time()
    while jianying_running() and time.time() - t0 < timeout:
        time.sleep(0.5)
    if jianying_running():
        if auto.IS_MAC:
            subprocess.run(["pkill", "-f", "剪映"], capture_output=True)
        else:
            subprocess.run(["taskkill", "/F", "/IM", "JianyingPro.exe"], capture_output=True)
        time.sleep(2)
    if jianying_running():
        raise Pause("剪映退不掉：" + QUIT_HINT)


def _draft_cards(name, region, upscale=1):
    import difflib
    short = name[:4]
    hs = [h for h in jy_ui.texts(region, upscale=upscale) if norm(h[0]).startswith(short)]
    return sorted(hs, key=lambda h: -difflib.SequenceMatcher(None, name, norm(h[0])).ratio())


def open_draft(name):
    if not jianying_running():
        start_jianying()
    go_home()
    import popups                                      # ads / tips on the home page block the draft cards
    popups.close_popups()
    # the home page renders BLACK while the overlay is up, and hide/show breaks the overlay's transparency:
    # STOP the overlay process here and start a fresh one once the editor is open
    jy_ui.overlay_stop()
    w = uia_retry(jy_ui.win)
    auto.restore(w)
    w.SetActive()
    time.sleep(1.2)
    if not jy_ui.repaint(w):
        raise Pause("剪映首页一直是黑的（没有重绘）")
    # v0.8: the home-page card TRUNCATES long names (「过程演示正式版」 → 「过程演示正…」): match the first 4 chars,
    # take the most similar. v1.1.1: a card with a BLACK cover has a small title that plain OCR misses (Mac test)
    # -> second pass on a 2x upscaled screenshot.
    r = w.BoundingRectangle                       # only inside 剪映 (other windows may show the same name)
    region = (r.left, r.top, r.right, r.bottom)
    t0, hit = time.time(), None
    while time.time() - t0 < 15 and not hit:
        hit = _draft_cards(name, region) or _draft_cards(name, region, upscale=2)
        if not hit:
            time.sleep(0.8)
    if not hit:
        # v0.8: a draft written while 剪映 is running is not always picked up -> 剪映 must be QUIT and restarted
        raise Pause(f"首页没有草稿「{name}」：请{QUIT_HINT}、再重新打开，然后用 --from 2 继续")
    x0, y0, x1, y1 = hit[0][3]
    jy_ui.click((x0 + x1) / 2, y0 - S(80), label=f"打开草稿 {name}")
    wait_for(in_editor, 30, what="进入编辑页")
    time.sleep(2.5)
    tl.maximise()
    jy_ui.overlay_start()
    time.sleep(1.0)
    tl.layout()                                   # v1.1.1: layout() calibrates the ruler itself


# ---------- timeline helpers ----------
def select_at(t):
    jy_ui.click(tl.x_of(t), tl.L["track_y"])
    time.sleep(0.5)


def panel_tabs():
    rows = panel.tab_rows()
    return [norm(h[0]) for h in rows[0]] if rows else []


# ---------- beauty ----------
def apply_beauty_preset(t, preset=None):
    """Apply the beauty preset (style.json beauty.preset) to the clip under t; verified with beauty.check
    (e.g. 磨皮 = 23 after the preset). An empty check (a built-in preset) only requires 磨皮 > 0."""
    preset = preset or ST["beauty"]["preset"]
    check = dict(ST["beauty"].get("check") or {}) if preset == ST["beauty"]["preset"] else {}
    key = next(iter(check), "磨皮")
    # 剪映 detects the face on the frame under the PLAYHEAD: put the playhead inside this segment first
    tl.seek(t)
    select_at(t)
    if "画面" not in panel_tabs():
        raise Pause("没有选中视频片段")
    panel.tab("画面")
    panel.tab("美颜美体", sub=True)
    time.sleep(0.8)

    def smooth():
        # v1.0 sequence: the 「美颜」 label just under the tab rows, then read the row (row() may scroll down)
        rows = panel.tab_rows()
        y0 = max(h[3][3] for h in rows[1]) if len(rows) > 1 else Y(200)
        try:
            jy_ui.click_text("美颜", (panel.PANEL[0] - S(60), y0, panel.PANEL[0] + S(200), y0 + S(90)), exact=True)
            time.sleep(0.8)
        except LookupError:
            pass
        try:
            return panel._num(panel.get_value(key))
        except LookupError:
            return None

    def open_presets():
        for _ in range(4):                           # v1.2 (#40): the panel may still be loading -> scroll again
            panel.scroll(12, down=False)             # v1.1.1: row() scrolls the panel; 美颜预设 is at the top
            time.sleep(0.6)
            if jy_ui.find("美颜预设", panel.PANEL):
                break
            time.sleep(1.0)
        jy_ui.click_text("美颜预设", panel.PANEL)
        time.sleep(1.2)
    before = None
    open_presets()
    try:
        h = wait_for(lambda: jy_ui.find(preset, panel.PANEL, exact=True) or jy_ui.find(preset, panel.PANEL), 10,
                     what="美颜预设卡片")
    except Pause:
        raise Pause(f"美颜预设里没有「{preset}」：在剪映里存一个同名预设，或在 style.json 的 beauty.preset 改成已有的预设名")
    fx(type="fly", **{"from": [h[0][1], h[0][2] - S(60)]}, to=[tl.x_of(t), tl.L["track_y"]], color=CYAN,
       label=f"美颜 · {preset}", hold=2.2, dur=0.6)
    for off in (60, 75, 45):                    # the card's thumbnail sits above its name (Windows 60, Mac ≈75)
        jy_ui.click(h[0][1], h[0][2] - S(off))
        time.sleep(1.2)
        after = smooth()
        if after is not None and ((check and abs(after - float(check[key])) < 0.51) or (not check and after > 0)):
            panel.scroll(12, down=False)
            return
        open_presets()
    raise Pause(f"美颜预设没套上（{t:.1f}s，{key} {before} → {after}，应为 {check.get(key, '> 0')}）")


# ---------- fonts / colours / presets in the text panel ----------
FONT_TABS = ("全部", "收藏", "最近", "系统", "品牌", "图搜")


def _font_row():
    x0, x1 = panel.label_column()
    return wait_for(lambda: jy_ui.find("字体", (x0, panel.PANEL[1], x1, Y(900)), exact=True), 5, what="字体行")[0]


def pick_font(name):
    """字体 dropdown → (收藏, else the list's search box) → click `name` → VERIFY the row shows it. Pauses if the
    font really is not there. v1.1.1 (Mac test): a text box that still had focus swallowed the first click on the
    dropdown, and the list's category row (全部 收藏 最近 系统 …) OCRs as one string."""
    f = _font_row()
    lx = panel.label_column()[0]
    jy_ui.click(f[1], f[2])                         # move focus off any text box (the label is inert)
    time.sleep(0.3)
    lst = (lx, f[2] + S(20), panel.PANEL[2], f[2] + S(760))

    def list_open():
        return [h for h in jy_ui.texts(lst) if "搜索" in h[0] or any(norm(h[0]).startswith(t) for t in FONT_TABS[:3])]
    arrows = (panel.P(400), panel.PANEL[2] - S(105))      # Windows: P(400) opens it (v0.x)
    if auto.IS_MAC:                                       # Mac test: P(400) lands in the box; the arrow is at the right
        arrows = arrows[::-1]
    for arrow_x in arrows:
        if list_open():
            break
        jy_ui.click(arrow_x, f[2])
        time.sleep(1.0)
    if not list_open():
        raise Pause("字体列表没打开")

    def font_hits():
        return [h for h in jy_ui.texts(lst) if norm(h[0]) == name and not any(t in h[0] for t in ("全部收藏", "最近系统"))]
    hits = []
    fav = [h for h in jy_ui.texts(lst) if norm(h[0]) == "收藏"]
    if fav:
        jy_ui.click(fav[0][1], fav[0][2])
        time.sleep(0.8)
        hits = font_hits()
    if not hits:
        box = [h for h in jy_ui.texts(lst) if "搜索" in h[0]]
        if box:
            jy_ui.click(box[0][1], box[0][2])
            time.sleep(0.3)
            auto.SetClipboardText(name)
            jy_ui.keys("{Ctrl}v", wait=1.5)
            hits = font_hits()
    if not hits:
        raise Pause(f"字体列表里找不到「{name}」（收藏和搜索都没有）")
    h = sorted(hits, key=lambda h: h[2])[0]
    jy_ui.click(h[1], h[2])
    time.sleep(2.0)
    now = [x[0] for x in jy_ui.texts((lx, f[2] - S(25), panel.PANEL[2], f[2] + S(25)))]
    if name not in "".join(now):
        raise Pause(f"字体没换成 {name}：{now}")


def _swatch_rgb(c):
    import numpy as np
    im = jy_ui.grab((int(c[1] + S(105)), int(c[2] - S(8)), int(c[1] + S(165)), int(c[2] + S(8))))
    return np.asarray(im).reshape(-1, 3).mean(axis=0)


def _colour_close(got, want):
    if max(abs(a - b) for a, b in zip(got, want)) < 30:
        return True
    # Mac screenshots are Display-P3: FFE600 reads back ≈ (251,231,77) — blue drifts most (Mac test)
    return auto.IS_MAC and max(abs(got[0] - want[0]), abs(got[1] - want[1])) < 25 and abs(got[2] - want[2]) < 95


def set_color(hexv):
    """Colour swatch -> picker -> Hex box -> type -> Enter -> READ the Hex box back -> close -> check the swatch."""
    hexv = hexv.lstrip("#").upper()
    want = [int(hexv[i:i + 2], 16) for i in (0, 2, 4)]
    x0, x1 = panel.label_column()
    c = wait_for(lambda: jy_ui.find("颜色", (x0, panel.PANEL[1], x1, Y(1200)), exact=True), 5, what="颜色行")[0]
    if _colour_close(_swatch_rgb(c), want):
        return                                            # already this colour
    R = (x0, c[2], panel.PANEL[2], panel.PANEL[3])
    for attempt in range(2):
        jy_ui.click(c[1] + S(135), c[2])                  # middle of the swatch (its right end is a dropdown)
        time.sleep(0.9)
        hits = wait_for(lambda: [h for h in jy_ui.texts(R) if norm(h[0]).startswith("Hex")], 5, what="Hex")
        hx = hits[0]
        tok = norm(hx[0])
        if re.fullmatch(r"Hex[0-9A-Fa-f]{6}", tok):          # OCR glued label + value: aim at the value part
            vx, vy = hx[3][0] + (hx[3][2] - hx[3][0]) * 0.62, hx[2]
        else:
            band = [h for h in jy_ui.texts(R) if abs(h[2] - hx[2]) < S(20)]
            vals = [h for h in band if h[1] > hx[1] + S(20) and re.fullmatch(r"#?[0-9A-Fa-f]{6}", norm(h[0]))]
            pct = [h for h in band if norm(h[0]).endswith("%")]
            if vals:
                v = min(vals, key=lambda h: h[1])
                vx, vy = v[1], v[2]
            elif pct:                                     # white value text is often missed by OCR: the box is
                vx, vy = (hx[3][2] + pct[0][3][0]) / 2, hx[2]  # the gap between 'Hex ⌄' and the opacity box
            else:
                raise Pause("颜色面板里找不到 Hex 数值框")

        def hex_now():
            time.sleep(0.3)
            band = "".join(norm(h[0]) for h in jy_ui.texts((hx[3][0] - S(10), hx[2] - S(22), panel.PANEL[2], hx[2] + S(22))))
            return hexv in band.upper()
        try:
            panel.type_value(vx, vy, hexv, hex_now, defocus=(hx[1], hx[2] - S(60)), what="颜色 Hex")
        except Pause:
            if attempt:
                raise
        jy_ui.click(c[1], c[2] + S(120))                  # inert label area closes the picker (never Esc)
        time.sleep(0.6)
        got = _swatch_rgb(c)
        if _colour_close(got, want):
            return
    raise Pause(f"颜色没设上 {hexv}（现在 {[int(x) for x in got]}）")


def preset_style(n=2):
    p = wait_for(lambda: jy_ui.find("预设样式", (panel.label_column()[0], panel.PANEL[1], panel.P(300), Y(1200))), 5,
                 what="预设样式")
    y = p[0][2] + S(66)
    x = p[0][3][0] + S(12) + (n - 1) * S(78)     # first swatch starts under the label
    jy_ui.click(x, y)
    time.sleep(0.8)


def stroke_width(v):
    """描边 粗细. v1.1.1: the 描边 section can be collapsed (Mac test: 「粗细」 not found) -> tick 描边 first."""
    try:
        panel.set_value("粗细", v)
        return
    except LookupError:
        pass
    panel.scroll(12, down=False)
    try:
        panel.checkbox("描边")
    except LookupError:
        raise Pause("找不到「描边」（文本 → 基础 下面）")
    time.sleep(0.6)
    panel.set_value("粗细", v)


# ---------- subtitles ----------
def _input_focused(box):
    """Windows: an empty focused input shows a teal border: look for teal pixels in a band around the placeholder."""
    import numpy as np
    x0, y0, x1, y1 = box
    im = np.asarray(jy_ui.grab((int(x0) - S(40), int(y0) - S(22), int(x1) + S(600), int(y1) + S(22)))).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    teal = (g > 120) & (b > 120) & (r < 90) & (g - r > 50)
    return teal.sum() > 40


def recognize_subtitles(words=None):
    words = tuple(words or ST["subtitle"]["hotwords"])
    M = panel.M
    jy_ui.click_text("文本", panel.topband())
    time.sleep(0.8)
    side = (M(0), panel.MAT[1], M(200), Y(900))
    if not jy_ui.find("智能字幕", side):      # 智能文本 is a toggle group: open it only if shut
        jy_ui.click_text("智能文本", side)
        time.sleep(0.6)
    jy_ui.click_text("智能字幕", side)
    time.sleep(1.0)
    top = (M(300, True), panel.MAT[1], M(0, True), Y(340))
    btn = jy_ui.find("新增", top) or jy_ui.find("管理", top)
    if not btn:
        raise Pause("找不到自定义词汇的 新增/管理 按钮")
    jy_ui.click(btn[0][1], btn[0][2])
    time.sleep(1.2)
    pop = (M(600, True), btn[0][2] + S(30), M(0, True), btn[0][2] + S(520))       # the vocabulary popup
    if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:      # a second click toggles it shut: reopen
        jy_ui.click(btn[0][1], btn[0][2])
        time.sleep(1.2)
    if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:
        raise Pause("自定义词汇窗口没打开")

    def tags():
        # tags are small grey text: OCR a 2x upscale (plain OCR read 牢饭 as 车证)
        return [norm(h[0]).rstrip("X×x") for h in jy_ui.texts(pop, upscale=2)]

    def have(w, ts):
        import difflib
        return any(w == t or (len(t) <= len(w) + 1 and difflib.SequenceMatcher(None, w, t).ratio() >= 0.5) for t in ts)
    for w in words:
        if have(w, tags()):
            continue
        ph = [h for h in jy_ui.texts(pop) if "enter" in h[0].lower() or "输入关" in h[0]]
        if not ph:
            raise Pause("找不到自定义词汇输入框")
        # Windows: an empty focused input shows a teal border (checked before typing); Mac: no such border ->
        # select-all + paste, and the tag list read back is the check
        panel.type_value(ph[0][1], ph[0][2], w, lambda: have(w, tags()), paste=True, what=f"自定义词汇「{w}」",
                         focused=lambda b=ph[0][3]: _input_focused(b))
    fx(type="banner", text="自定义词汇", sub=" · ".join(words) + "  → 识别一次就对", hold=2.5)
    jy_ui.click(M(460), Y(900))
    time.sleep(0.4)
    jy_ui.click_text("开始识别", (M(0), panel.MAT[3] - S(260), M(0, True), panel.MAT[3] + S(40)))
    time.sleep(2)
    wait_for(lambda: not [h for h in jy_ui.texts((M(0), Y(600), panel.PLAYER[2], panel.MAT[3] + S(160))) if "识别中" in h[0]],
             max(120, int(30 + 0.5 * ((tl.total_frames() or 0) / tl.FPS))), 2, "字幕识别")   # v1.2 (#37): long videos
    time.sleep(1)
    tl.layout()


def style_subtitles(sample_t=5.0):
    """Select one subtitle (style applies to all: '应用到全部字幕' is on) and set the owner's subtitle look."""
    tl.seek(sample_t)
    r = tl.L["tl"]
    xc = tl.x_of(sample_t)
    hits = [h for h in jy_ui.texts((int(xc) - S(200), r[1] + S(60), int(xc) + S(200), tl.L["track_y"] - S(45)))
            if "高清" not in h[0] and "变速" not in h[0] and ".mp4" not in h[0]]
    tabs = []
    cands = [(h[1], h[2]) for h in sorted(hits, key=lambda h: abs(h[1] - xc))[:5]]
    # v1.2 (#47): on a long timeline subtitle clips are a few px wide with no text -> try every track row at x(t)
    import numpy as np
    top = int(r[1] + S(60))
    col = np.asarray(jy_ui.grab((int(xc) - 1, top, int(xc) + 2, int(tl.L["track_y"] - S(30))))).astype(int).mean(axis=1)
    run = []
    for i, c in enumerate(col):
        if c.max() - c.min() > 40 and c.max() > 90:            # coloured clip pixels (not the dark background)
            run.append(i)
        elif run:
            if len(run) >= S(12):
                cands.append((xc, top + (run[0] + run[-1]) / 2))
            run = []
    for x, y in cands:
        jy_ui.click(x, y)
        time.sleep(0.8)
        tabs = panel_tabs()
        if "字幕" in tabs:
            break
    else:
        raise Pause(f"没有选中字幕：{tabs}")
    if "文本" in tabs:
        panel.tab("文本")
    sub = ST["subtitle"]
    pick_font(sub["font"])
    panel.set_value("字号", sub["size"])
    preset_style(sub["preset_style"])
    set_color(sub["color"])
    panel.scroll(8)
    stroke_width(sub["stroke"])
    panel.scroll(12, down=False)


# ---------- big keyword text ----------
def set_xy(x=None, y=None):
    # v1.2: the 「位置」 row sits below 「位置大小 / 缩放 / 等比缩放」 and is often out of view; row("位置") then matched the
    # 「位置大小」 HEADER (no numbers) -> 「位置行没读全」. Scroll until the EXACT label shows; read at 2x (tiny 0s).
    labs = []
    for _ in range(6):
        labs = [h for h in jy_ui.texts(panel.PANEL) if norm(h[0]) == "位置"]
        if labs:
            break
        panel.scroll(2)
        time.sleep(0.4)
    if not labs:
        raise Pause("「位置」行不在面板里")
    lab = labs[0]

    def band():
        hs = [h for h in jy_ui.texts((panel.label_column()[0], int(lab[2]) - S(28), panel.PANEL[2], int(lab[2]) + S(28)),
                                     upscale=2)
              if re.fullmatch(r"[XYxy]?-?[\d.]+", norm(h[0])) and h[1] > lab[3][2] + S(40)]
        return sorted(hs, key=lambda h: h[1])
    b = band()
    if len(b) < 2:
        raise Pause(f"位置行没读全：{[h[0] for h in b]}")
    # OCR may glue the 'X' label to the value ("X900"): click the value part (right side of that token)
    xb, yb = b[0], b[-1]
    boxes = {0: (xb[3][2] - S(25) if xb[0][:1] in "XxYy" else xb[1], xb[2]), 1: (yb[1], yb[2])}
    for i, val in ((0, x), (1, y)):
        if val is None:
            continue

        def ok(i=i, val=val):
            time.sleep(0.3)
            cur = band()
            got = panel._num(re.sub(r"^[XYxy]", "", cur[0 if i == 0 else -1][0])) if len(cur) >= 2 else None
            return got is not None and abs(got - float(val)) < 1.5
        panel.type_value(*boxes[i], val, ok, defocus=(lab[1], lab[2]), what="位置 " + "XY"[i])


def replace_content(text):
    """Replace the selected text clip's content (verified by reading it back).
    v0.8: on a SUBTITLE clip the first text in this band is the 「文本、排列、气泡、花字应用到全部字幕」 checkbox
    row — double-clicking it un-ticked the checkbox. Skip that row, take the content box below it.
    v1.1.1: the band starts BELOW the panel's tab rows (Mac: the band hit the 「文本」 tab)."""
    rows = panel.tab_rows()
    y0 = int(max(h[3][3] for h in rows[min(1, len(rows) - 1)]) + S(10)) if rows else Y(180)
    c = wait_for(lambda: [h for h in jy_ui.texts((panel.P(20), y0, panel.PANEL[2], y0 + S(200)))
                          if h[0].strip() and "应用到全部" not in h[0] and "排列" not in h[0]], 5, what="文字内容框")[0]
    import difflib

    def ok():
        time.sleep(0.4)
        now = "".join(norm(h[0]) for h in jy_ui.texts((panel.P(20), c[3][1] - S(10), panel.PANEL[2], c[3][3] + S(40))))
        t = norm(text)
        return t in now or difflib.SequenceMatcher(None, t, now[:len(t) + 2]).ratio() >= 0.6
    panel.type_value(c[1], c[2], text, ok, paste=True, what="文字内容")
    jy_ui.click(panel.P(50), c[3][3] + S(70))       # leave the box (inert area under the content box)
    time.sleep(0.3)


def _text_clip_at(t):
    """A 「默认文本」 clip already on the timeline at t (a resumed run must not add a second one)."""
    r = tl.L["tl"]
    x = tl.x_of(t)
    return [h for h in jy_ui.texts((int(x) - S(10), r[1] + S(40), int(x) + S(260), r[3])) if "默认文本" in h[0]]


def add_default_text_at(t):
    tl.seek(t)
    old = _text_clip_at(t)
    if old:                                          # idempotent (Mac test: 3 re-runs left 3 「默认文本」 clips)
        jy_ui.click(old[0][1], old[0][2])
        time.sleep(0.8)
        if "文本" in panel_tabs():
            return
    M = panel.M
    jy_ui.click_text("文本", panel.topband())
    time.sleep(0.6)
    side = (M(0), panel.MAT[1], M(200), Y(900))
    jy_ui.click_text("新建文本", side)
    time.sleep(0.8)
    card = wait_for(lambda: jy_ui.find("默认文本", (M(140), panel.MAT[1], M(0, True), Y(700))), 5, what="默认文本卡片")[0]
    auto.MoveTo(int(card[1]), int(card[2]))
    time.sleep(0.6)
    jy_ui.click(card[1] + S(43), card[2] + S(43))
    time.sleep(1.2)
    if "文本" not in panel_tabs():
        raise Pause("新文本没加上")


_K = ST["keyword"]
KW = dict(font=_K["font"], size=_K["size"], x=_K["x"], y_red=_K["y_top"], y_white=_K["y_bottom"], stroke=_K["stroke"],
          anim=_K["default_anim"], color=_K["default_color"], preset=_K["preset_style"])


def _norm_anim(s):
    # OCR reads the roman numeral in 打字机I / 打字机II as 1 / l / | / ] / ！
    return re.sub(r"[1l|\]Ii!！]", "I", norm(s))


def _card_selected(cx, cy):
    """An applied animation card has a teal border (the 「无」 card has it when nothing is applied)."""
    import numpy as np
    k = S(62)
    a = np.asarray(jy_ui.grab((int(cx) - k, int(cy) - k, int(cx) + k, int(cy) + k))).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return int(((g > 150) & (b > 150) & (r < 90)).sum()) > 150 * (k / 62) ** 2


def set_anim(name):
    """文本 → 动画 → 入场 → apply `name` and VERIFY it (teal border on its card).
    v0.6: a card that is not downloaded yet only DOWNLOADS on the first click. So: click → wait → if not applied,
    click the download arrow → wait → click."""
    panel.tab("动画")
    time.sleep(0.8)
    panel.tab("入场", sub=True)
    time.sleep(0.8)
    want = _norm_anim(name)
    rows = panel.tab_rows()
    below = max(h[3][3] for h in rows[1]) if len(rows) > 1 else Y(280)

    def look():
        return [h for h in jy_ui.texts(panel.PANEL) if _norm_anim(h[0]) == want and h[2] > below]
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
    cx, cy = h[1], h[2] - S(65)              # card centre (label sits under the card)
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
        jy_ui.click(cx + S(26), cy + S(26))  # the download arrow (bottom-right of the card)
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
    panel.scroll(15, down=False)                       # v1.2: a scrolled panel hid the 「字体」 row
    time.sleep(0.4)
    pick_font(KW["font"])
    panel.set_value("字号", size or KW["size"])
    preset_style(KW["preset"])
    set_color(color)
    try:                                               # v1.2: 剪映 remembered 缩放 58 % for new text -> keywords half size
        if panel._num(str(panel.get_value("缩放"))) != 100:
            panel.set_value("缩放", 100)
    except LookupError:
        pass
    set_xy(x, y)
    panel.scroll(8)
    stroke_width(KW["stroke"])
    panel.scroll(12, down=False)
    set_anim(anim or KW["anim"])


def find_segment(text):
    """Timeline segment whose label starts with text[:2]; returns (x, y)."""
    import difflib
    r = tl.L["tl"]
    key = norm(text)[:4]
    best, score = None, 0.0
    for h in jy_ui.texts((r[0], r[1] + S(60), r[2], r[3])):
        lab = norm(h[0])[:len(key)]
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
    """y of the top-most timeline row ABOVE the main track that has a solid purple (filter) bar near x0, or None.
    v0.8: found by colour (a 3-s clip on a long timeline shows no label). v1.1.1 (acceptance test, 2026-11-19): the
    owner's video has purple lights — scattered purple pixels in the MAIN track's thumbnails were taken for a filter,
    so no filter was added and the main clip was dragged instead. Now: only rows above the main track, and only a
    solid run ≥ S(24) px of filter purple (≈ 90, 75, 200) counts; magenta (≈ 230, 60, 240) is excluded."""
    import numpy as np
    r = tl.L["tl"]
    top = int(r[1]) + S(40)
    bottom = int(tl.L["track_y"]) - S(60) if tl.L.get("track_y") else int(r[3])
    if bottom <= top:
        return None
    im = np.asarray(jy_ui.grab((int(x0), top, int(x1), bottom))).astype(int)
    R, G, B = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    purple = (B > 130) & (R > 60) & (R < 205) & (B - G > 60) & (B - R > 40)
    need = S(24)
    good = []
    for yy in range(purple.shape[0]):
        run = best = 0
        for v in purple[yy]:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= need:
            good.append(yy)
    if not good:
        return None
    run = [good[0]]                                   # first contiguous band = the top-most purple clip
    for yy in good[1:]:
        if yy - run[-1] > 2:
            break
        run.append(yy)
    return top + int(np.mean(run))


def scroll_tracks_top():
    """Scroll the timeline's track area to the TOP (new filter / effect rows are added above everything)."""
    r = tl.L["tl"]
    auto.MoveTo(int(r[0] + (r[2] - r[0]) * 0.3), int((r[1] + r[3]) / 2))   # inside the tracks, no calibration needed
    for _ in range(12):
        auto.WheelUp(waitTime=0.05)
    time.sleep(0.4)


def add_filter_full(name=None, strength=None, total=None):
    """Filter from 0 s to the end. The new clip lands at the PLAYHEAD -> seek(0) must be exact (v1.1.1: seek(0)
    uses Home + read-back; on Mac the old ←-key nudging fell short and the clip landed late: 「没能挪回 0 秒」)."""
    name = name or ST["filter"]["name"]
    strength = ST["filter"]["strength"] if strength is None else strength
    tl.seek(0.0)
    scroll_tracks_top()
    tl.calibrate()
    M = panel.M
    y = _purple_row(tl.x_of(0) - 2, tl.x_of(6))
    if y is None:                                      # idempotent: a resumed run must not add a second filter
        jy_ui.click_text("滤镜", panel.topband())
        time.sleep(1.0)
        jy_ui.click_text("收藏", (M(0), panel.MAT[1], M(200), Y(500)))
        time.sleep(0.8)
        h = wait_for(lambda: jy_ui.find(name, (M(140), panel.MAT[1], M(0, True), Y(1300)), exact=True), 10,
                     what=f"滤镜 {name}")
        cx, cy = h[0][1], h[0][2] - S(90)
        auto.MoveTo(int(cx), int(cy))
        time.sleep(0.7)
        jy_ui.click(cx + S(67), cy + S(50))            # the "+" that appears on hover
        time.sleep(1.2)
        scroll_tracks_top()
        tl.calibrate()
        y = wait_for(lambda: _purple_row(tl.x_of(0) - 2, tl.x_of(6)), 8, what="新滤镜片段（紫色）")
    end = total or (tl.total_frames() / tl.FPS)

    def purple_at(x):
        return _purple_right_edge(y, x - 2, x + 2) is not None

    def starts_at_zero():
        # the clip's left part is its 「高清增强」 label (not purple): look for the purple border right at 0 s
        return _purple_right_edge(y, tl.x_of(0) - 2, tl.x_of(0) + S(12)) is not None

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
    # v0.8: grab the right edge (a grab 2 px off MOVES the clip): check BOTH ends after the drag, undo + retry
    ok = False
    dbg = []
    # already 0 s → end (a resumed / repeated run): nothing to drag (grabbing the middle of a long clip MOVES it)
    full_end = _purple_right_edge(y, tl.x_of(end) - S(30), tl.x_of(end) + S(40))
    if starts_at_zero() and full_end is not None and abs(full_end - tl.x_of(end)) <= S(8):
        ok = True
    for off in (() if ok else (1, 2, 0, 3)):
        redge = _purple_right_edge(y, tl.x_of(0), tl.x_of(4))
        if redge is None:
            raise Pause(f"找不到新滤镜片段的右边缘 {dbg}")
        if redge >= tl.x_of(4) - S(3):
            raise Pause(f"滤镜片段比 4 秒长、又没到片尾：右边缘不在前 4 秒里，不敢拖（会整段挪走）{dbg}")
        before = (starts_at_zero(), redge)
        auto.DragDrop(int(redge) + S(off), int(y), int(tl.x_of(end)) + 2, int(y), moveSpeed=0.5, waitTime=0.8)
        time.sleep(0.6)
        redge2 = _purple_right_edge(y, tl.x_of(0), tl.x_of(end) + S(40))
        z = starts_at_zero()
        dbg.append(dict(off=off, y=int(y), redge=int(redge), after=None if redge2 is None else int(redge2),
                        end_x=int(tl.x_of(end)), zero=z))
        print("filter drag:", dbg[-1], flush=True)
        if z and redge2 is not None and abs(redge2 - tl.x_of(end)) <= S(8):
            ok = True
            break
        if (z, redge2) != before:                    # the drag changed something (moved / fell short): undo it
            tl.undo()                                # (never undo a no-op drag: that would undo ADDING the filter)
            time.sleep(0.6)
    if not ok:
        raise Pause(f"滤镜没能从 0 秒拉到片尾（试了 4 个抓点）：{dbg}")
    fx(type="fly", **{"from": [tl.x_of(0), y]}, to=[tl.x_of(end), y], color=PURPLE, label=f"滤镜 · {name} {strength}",
       hold=2.5, dur=1.2)
    time.sleep(0.8)
    jy_ui.click(tl.x_of(end * 0.6), y)               # select the filter clip (a skipped drag leaves nothing selected)
    time.sleep(0.8)
    panel.set_value("强度", strength)               # verified by read-back inside set_value


# ---------- compliance on the subtitle track (v0.8, owner rule 2026-11-18) ----------
def hide_banned_subtitles(windows):
    """The owner's spoken 私域 hook (「…可以送给你们」) stays in the AUDIO; its subtitle must not show.
    windows = [(t0, t1), …] output times where a banned phrase is spoken. Clicks along the subtitle row in each
    window, reads the clip's text, deletes clips whose text hits compliance.py. Returns the deleted texts."""
    import compliance
    scroll_tracks_top()
    tl.calibrate()
    labs = [h for h in jy_ui.texts(tl.L["tl"]) if norm(h[0]).startswith(("A", "Α")) and len(h[0].strip()) <= 4]
    if not labs:
        raise Pause("找不到字幕轨道")
    sub_y = sorted(h[2] for h in labs)[len(labs) // 2]
    deleted = []
    for t0, t1 in windows:
        t = max(0.0, t0 - 1.0)
        while t <= t1 + 1.0:
            jy_ui.click(tl.x_of(t), sub_y)
            time.sleep(0.45)
            content = "".join(h[0] for h in jy_ui.texts((panel.P(20), Y(180), panel.PANEL[2], Y(280))) if h[0].strip())
            if compliance.hits(content.replace("文本、排列、气泡、花字应用到全部字幕", "")):
                jy_ui.keys("{Delete}", wait=0.6)
                deleted.append(content)
                fx(type="banner", text="字幕不出导流词", sub="声音保留，字幕删掉", hold=1.5)
                continue
            t += 0.4
    return deleted
