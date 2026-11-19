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
    if wr.right <= wr.left or wr.bottom <= wr.top:
        return False
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
    try:
        wait_for(lambda: not in_editor(), 15, what="回到首页")
    except Pause:
        if not auto.IS_MAC:
            raise
        jy_ui.activate()                           # v1.1.3: ⌘W lost once (Mac test) -> once more, in front
        auto.SendKeys("{Cmd}w", waitTime=1.0)
        wait_for(lambda: not in_editor(), 15, what="回到首页")
    time.sleep(1.5)


JY_EXE = None      # v1.0: no personal path in code — config.json / env JIANYING_EXE / running process / install dirs


def jianying_running():
    return auto.process_running(("JianyingPro.exe",) if not auto.IS_MAC else auto.JY_NAMES)


def quit_jianying(timeout=20):
    """v1.1.2: Mac — `quit app` is ignored by 剪映 (Mac test), so fall back to SIGTERM on its main process."""
    import subprocess
    if not jianying_running():
        return True
    if auto.IS_MAC:
        for app in ("VideoFusion-macOS", "剪映专业版"):
            subprocess.run(["osascript", "-e", f'quit app "{app}"'], capture_output=True)
        for _ in range(10):
            if not jianying_running():
                time.sleep(2)
                return True
            time.sleep(0.5)
        for name in ("VideoFusion-macOS", "剪映专业版", "JianyingPro"):
            subprocess.run(["pkill", "-x", name], capture_output=True)
    else:
        return False                           # Windows unchanged: the user quits 剪映 from the tray
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not jianying_running():
            time.sleep(2)
            return True
        time.sleep(0.5)
    return False


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
    if not hit and not getattr(open_draft, "_restarted", False):
        # v0.8: a draft written while 剪映 is running is not always picked up -> restart 剪映 ONCE ourselves (v1.1.2)
        open_draft._restarted = True
        try:
            if quit_jianying():
                return open_draft(name)
        finally:
            open_draft._restarted = False
    if not hit:
        raise Pause(f"首页没有草稿「{name}」：请{QUIT_HINT}、再重新打开，然后重新运行"
                    f"（验收测试加 --skip-build；live_run.py 加 --from 2）")
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
    if not auto.IS_MAC:
        jy_ui.click(tl.x_of(t), tl.L["track_y"])
        time.sleep(0.5)
        return
    for _ in range(3):
        jy_ui.click(tl.x_of(t), tl.L["track_y"])
        time.sleep(0.5)
        if "画面" in panel_tabs():
            return
    raise Pause("视频片段属性面板没打开")


def panel_tabs():
    if auto.IS_MAC:
        native = panel.native_tabs()
        if native:
            return native
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
        panel.scroll(12, down=False)                 # v1.1.1: row() scrolls the panel; 美颜预设 is at the top
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
    def preset_strength():
        # v1.1.3 (Mac 剪映 11.8): a preset is its own effect with a 「强度」 slider under the cards (自然柔光 → 80);
        # the 美颜 sliders (磨皮 …) stay 0, so 磨皮 > 0 can never prove a built-in preset. 强度 > 0 does.
        try:
            return panel._num(panel.get_value("强度"))
        except LookupError:
            return None
    after = None
    for off in (60, 75, 45):                    # the card's thumbnail sits above its name (Windows 60, Mac ≈75)
        jy_ui.click(h[0][1], h[0][2] - S(off))
        time.sleep(1.2)
        st = preset_strength()
        print(f"beauty: card offset {off} -> 强度 {st}", flush=True)
        if st is not None and st > 0 and not check:
            panel.scroll(12, down=False)
            return
        after = smooth()
        if after is not None and ((check and abs(after - float(check[key])) < 0.51) or (not check and after > 0)):
            panel.scroll(12, down=False)
            return
        open_presets()
    raise Pause(f"美颜预设没套上（{t:.1f}s，预设强度读不到或为 0；{key} 读到 {after}，应为 {check.get(key, '> 0')}）")


# ---------- fonts / colours / presets in the text panel ----------
FONT_TABS = ("全部", "收藏", "最近", "系统", "品牌", "图搜")


def _font_row():
    if auto.IS_MAC:
        native = panel._native_tab_hit("字体")
        if native:
            box = native[3]
            x = box[0] - S(50)
            return ("字体", x, native[2], (x - S(20), box[1], x + S(20), box[3]), 1.0)
    x0, x1 = panel.label_column()
    return wait_for(lambda: jy_ui.find("字体", (x0, panel.PANEL[1], x1, Y(900)), exact=True), 5, what="字体行")[0]


def pick_font(name):
    """字体 dropdown → (收藏, else the list's search box) → click `name` → VERIFY the row shows it. Pauses if the
    font really is not there. v1.1.1 (Mac test): a text box that still had focus swallowed the first click on the
    dropdown, and the list's category row (全部 收藏 最近 系统 …) OCRs as one string."""
    f = _font_row()
    lx = panel.label_column()[0]
    jy_ui.keys("{Esc}", wait=0.4)                   # v1.1.4(mac): 关掉上一次可能残留的字体列表
    jy_ui.click(f[1], f[2])                         # move focus off any text box (the label is inert)
    time.sleep(0.3)
    lst = (lx, f[2] + S(20), panel.PANEL[2], f[2] + S(760))
    wr_ = jy_ui.win().BoundingRectangle

    def list_open():
        # v1.1.3: look in the WHOLE window — on Mac 11.8 the list may open above the row or as a floating popup;
        # the box placeholder is 「搜索字体名称或风格」
        nonlocal lst
        hs = jy_ui.texts((wr_.left, wr_.top, wr_.right, wr_.bottom))
        box = [h for h in hs if "搜索字体" in h[0] or "名称或风格" in h[0]]
        tabs = [h for h in hs if h[1] > panel.PANEL[0] - S(400) and any(norm(h[0]).startswith(t) for t in FONT_TABS[:3])
                and abs(h[2] - f[2]) > S(15)]
        ref = box or tabs
        if ref:
            y0 = min(h[2] for h in ref)
            lst = (min(lx, int(min(h[3][0] for h in ref)) - S(40)), int(y0 - S(40)), panel.PANEL[2], int(y0 + S(760)))
            return ref
        return []
    cur = [h for h in jy_ui.texts((lx, f[2] - S(25), panel.PANEL[2], f[2] + S(25))) if h[1] > f[3][2] + S(20)]
    arrows = [panel.P(400), panel.PANEL[2] - S(105)]        # Windows: P(400) opens it (v0.x)
    if auto.IS_MAC:
        # v1.1.4(mac 实测 2026-11-19): PANEL[2]-S(30)=3337 落在窗口最右边缘，点了不响应；
        # PANEL[2]-S(105)=3262 / -S(70)=3297 / -S(270)=3097 / P(400)=3090 实测都能打开列表。
        arrows = [panel.PANEL[2] - S(105), panel.PANEL[2] - S(70), panel.PANEL[2] - S(270)] \
                 + ([cur[0][1]] if cur else []) + [panel.P(400)]
        native = panel._native_tab_hit("字体")
        if native:
            arrows.insert(0, native[1])
    for attempt in range(2):
        for arrow_x in arrows:
            if list_open():
                break
            jy_ui.click(f[1], f[2])                 # focus off any text box first (Mac: the box ate the click)
            time.sleep(0.3)
            jy_ui.click(arrow_x, f[2])
            time.sleep(1.2)
        if list_open():
            break
        jy_ui.keys("{Esc}", wait=0.4)
    if not list_open():
        raise Pause("字体列表没打开（点了下拉箭头 / 字体框，没看到「搜索字体名称或风格」）")

    def font_hits():
        hs = [h for h in jy_ui.texts(lst) if norm(h[0]) == name and not any(t in h[0] for t in ("全部收藏", "最近系统"))]
        # v1.1.4(mac 实测): 搜索后「搜索框里显示的就是关键词本身」，OCR 会把它当成一条命中项，
        # 而代码取 y 最小的 → 点中的是搜索框，字体永远不变（实测 hits 是 (2841,736) 搜索框 + (2890,1042) 结果）。
        by = search_y
        if by is None:
            box = [b for b in jy_ui.texts(lst) if "搜索" in b[0]]
            by = box[0][2] if box else None
        if by is not None:
            hs = [h for h in hs if abs(h[2] - by) > S(40)]
        return hs
    hits = []
    search_y = None
    fav = [h for h in jy_ui.texts(lst) if norm(h[0]) == "收藏"]
    if fav:
        jy_ui.click(fav[0][1], (fav[0][2] + fav[0][3][3]) / 2)
        time.sleep(0.8)
        hits = font_hits()
    if not hits:
        box = [h for h in jy_ui.texts(lst) if "搜索" in h[0]]
        if box:
            search_y = box[0][2]
            jy_ui.click(box[0][1], box[0][2])
            time.sleep(0.3)
            jy_ui.keys("{Ctrl}a", wait=0.3)      # v1.1.4(mac): 清掉上一次的搜索词，否则会拼成「新青年体仓耳榜黑」
            auto.SetClipboardText(name)
            jy_ui.keys("{Ctrl}v", wait=0.5)
            jy_ui.keys("{Enter}", wait=1.0)
            hits = font_hits()
            if hits:
                # v1.1.4(mac 实测): 列表里命中项的 OCR 坐标点下去并不生效（点完字体仍是「系统」），
                # 改成键盘选：输入关键词 → {Down} 选中第一项 → {Enter} 确认（下拉搜索的标准交互）
                jy_ui.keys("{Down}", wait=0.5)
                time.sleep(0.3)
                jy_ui.keys("{Enter}", wait=0.6)
                time.sleep(1.6)
                now = [x[0] for x in jy_ui.texts((lx, f[2] - S(25), panel.PANEL[2], f[2] + S(25)))]
                if name in "".join(now):
                    return name
    if not hits:
        # v1.1.4(mac 实测): 剪映 11.8 的字体搜索框不实时过滤（粘进中文名列表不变），
        # 所以搜索失败后再在列表里滚动找一遍（滚轮 or {PageDown}）
        for _ in range(8):
            try:
                import pyautogui as pg
                pg.scroll(-6, x=int((lst[0] + lst[2]) / 2), y=int((lst[1] + lst[3]) / 2))
            except Exception:
                jy_ui.keys("{PageDown}", wait=0.3)
            time.sleep(0.5)
            hits = font_hits()
            if hits:
                break
    if not hits:
        raise Pause(f"字体列表里找不到「{name}」（收藏和搜索都没有）；不替换字体")
    h = sorted(hits, key=lambda h: h[2])[0]
    # v1.1.4(mac 实测): OCR 给的是文字框「顶部」，点顶部会落在行间缝隙（字体永远不变）；
    # 点 (顶部+底部)/2 才中——实测点 y=1051 成功，点 y=1042 失败。
    jy_ui.click(h[1], (h[2] + h[3][3]) / 2)
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
            if auto.IS_MAC and _native_text_has(hexv):
                return True
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
    ENTRY = ("智能字幕", "识别字幕")

    def entry():
        for e in ENTRY:
            h = jy_ui.find(e, side)
            if h:
                return h
        return None
    if not entry():
        # Windows / older Mac: 智能文本 is a toggle group under 文本: open it only if shut
        for grp in ("智能文本", "智能字幕"):
            if jy_ui.find(grp, side):
                jy_ui.click_text(grp, side)
                time.sleep(0.6)
                break
    if not entry():
        # v1.1.2: 剪映 Mac 11.8 — no 智能文本 group; recognition sits under the top-level 「字幕」 tab
        if jy_ui.find("字幕", panel.topband(), exact=True):
            jy_ui.click_text("字幕", panel.topband(), exact=True)
            time.sleep(1.0)
    h = entry()
    if not h:
        raise Pause("找不到「智能字幕 / 识别字幕」入口（文本 → 智能文本，或顶部「字幕」）")
    jy_ui.click(h[0][1], (h[0][2] + h[0][3][3]) / 2)   # v1.1.4(mac): 点行中心
    time.sleep(1.0)
    top = (M(300, True), panel.MAT[1], M(0, True), Y(340))
    def vocab():
        # v1.1.3: the custom vocabulary only improves recognition — it is OPTIONAL (Mac 11.8: the 管理 popup
        # did not open). Failing here must not kill the subtitles.
        btn = jy_ui.find("新增", top) or jy_ui.find("管理", top)
        if not btn:
            return False
        jy_ui.click(btn[0][1], (btn[0][2] + btn[0][3][3]) / 2)   # v1.1.4(mac): 点行中心
        time.sleep(1.2)
        pop = (M(600, True), btn[0][2] + S(30), M(0, True), btn[0][2] + S(520))       # the vocabulary popup
        if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:      # a second click toggles it shut: reopen
            jy_ui.click(btn[0][1], (btn[0][2] + btn[0][3][3]) / 2)
            time.sleep(1.2)
        if not [h for h in jy_ui.texts(pop) if "自定义词汇" in h[0]]:
            return False

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
                return False
            # Windows: an empty focused input shows a teal border (checked before typing); Mac: no such border ->
            # select-all + paste, and the tag list read back is the check
            panel.type_value(ph[0][1], ph[0][2], w, lambda: have(w, tags()), paste=True, what=f"自定义词汇「{w}」",
                             focused=lambda b=ph[0][3]: _input_focused(b))
        return True
    try:
        vocab_ok = vocab()
    except Pause as e:
        print(f"自定义词汇：{e}", flush=True)
        vocab_ok = False
    if not vocab_ok:
        print("⚠ 自定义词汇窗口没打开：跳过热词，直接识别字幕", flush=True)
        jy_ui.keys("{Esc}", wait=0.4)
    if vocab_ok:
        fx(type="banner", text="自定义词汇", sub=" · ".join(words) + "  → 识别一次就对", hold=2.5)
    jy_ui.click(M(460), Y(900))
    time.sleep(0.4)
    jy_ui.click_text("开始识别", (M(0), panel.MAT[3] - S(260), M(0, True), panel.MAT[3] + S(40)))
    time.sleep(2)
    wait_for(lambda: not [h for h in jy_ui.texts((M(0), Y(600), panel.PLAYER[2], panel.MAT[3] + S(160))) if "识别中" in h[0]],
             120, 2, "字幕识别")
    time.sleep(1)
    tl.layout()


def style_subtitles(sample_t=5.0):
    """Select one subtitle (style applies to all: '应用到全部字幕' is on) and set the owner's subtitle look."""
    tl.seek(sample_t)
    r = tl.L["tl"]
    xc = tl.x_of(sample_t)
    hits = [h for h in jy_ui.texts((int(xc) - S(200), r[1] + S(60), int(xc) + S(200), tl.L["track_y"] - S(45)))
            if "高清" not in h[0] and "变速" not in h[0] and ".mp4" not in h[0]]
    if not hits:
        raise Pause("时间线上找不到字幕轨")
    tabs = []
    for h in sorted(hits, key=lambda h: abs(h[1] - xc))[:5]:     # subtitle clips are narrow: try the nearest few
        jy_ui.click(h[1], (h[2] + h[3][3]) / 2)   # v1.1.4(mac): 字幕片段点中心
        time.sleep(0.8)
        tabs = panel_tabs()
        if "字幕" in tabs or "文本" in tabs:
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
def _native_xy_boxes():
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication

        def get(el, name):
            err, value = AXUIElementCopyAttributeValue(el, name, None)
            return None if err else value

        def frame(el):
            m = re.search(r"x:([\d.-]+) y:([\d.-]+) w:([\d.-]+) h:([\d.-]+)", str(get(el, "AXFrame")))
            return tuple(map(float, m.groups())) if m else None

        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack, found = [app], {}
        while stack:
            el = stack.pop()
            desc = get(el, "AXDescription")
            if desc in ("automationpositionValue", "automationfirstUpButton", "automationsecondUpButton"):
                found[desc] = frame(el)
            stack.extend(get(el, "AXChildren") or [])
        if len(found) != 3 or not all(found.values()):
            return None
        xb, first, second = (found[k] for k in ("automationpositionValue", "automationfirstUpButton", "automationsecondUpButton"))
        scale = auto.ui_scale()
        yy = second[0] - (first[0] - (xb[0] + xb[2])) - xb[2]
        return (((xb[0] + xb[2] / 2) * scale, (xb[1] + xb[3] / 2) * scale),
                ((yy + xb[2] / 2) * scale, (xb[1] + xb[3] / 2) * scale))
    except Exception:
        return None


def set_xy(x=None, y=None):
    lab, _ = panel.row("位置")
    if auto.IS_MAC:
        panel.scroll(4)
        lab, _ = panel.row("位置")

    def band():
        hs = [h for h in jy_ui.texts((panel.label_column()[0], int(lab[2]) - S(28), panel.PANEL[2], int(lab[2]) + S(28)),
                                      upscale=2 if auto.IS_MAC else 1)
              if re.fullmatch(r"[XYxy]?-?[\d.]+", norm(h[0])) and h[1] > lab[3][2] + S(40)]
        hs = sorted(hs, key=lambda h: h[1])
        pure = [h for h in hs if re.fullmatch(r"-?[\d.]+", norm(h[0]))]
        return pure or hs
    native = _native_xy_boxes() if auto.IS_MAC else None
    if native:
        boxes = {0: native[0], 1: native[1]}
    else:
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
            got = panel._num(cur[0 if i == 0 else -1][0]) if len(cur) >= 2 else None
            return got is not None and abs(got - float(val)) < 1.5
        panel.type_value(*boxes[i], val, ok, defocus=(lab[1], lab[2]), what="位置 " + "XY"[i])


def _native_text_values():
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication

        def get(el, name):
            err, value = AXUIElementCopyAttributeValue(el, name, None)
            return None if err else value

        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack, values = [app], []
        while stack:
            el = stack.pop()
            if get(el, "AXRole") == "AXTextField":
                value = get(el, "AXValue")
                if isinstance(value, str):
                    values.append(value)
            stack.extend(get(el, "AXChildren") or [])
        return values
    except Exception:
        return []


def _native_text_has(text):
    wanted = text.upper().lstrip("#")
    return any(wanted in value.upper().lstrip("#") for value in _native_text_values())


def _native_replace_content(text):
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateApplication, AXUIElementSetAttributeValue

        def get(el, name):
            err, value = AXUIElementCopyAttributeValue(el, name, None)
            return None if err else value

        app = AXUIElementCreateApplication(jy_ui.win().ProcessId)
        stack, fields = [app], []
        while stack:
            el = stack.pop()
            if get(el, "AXRole") == "AXTextField":
                fields.append(el)
            stack.extend(get(el, "AXChildren") or [])
        if len(fields) != 1:
            return False
        field = fields[0]
        AXUIElementSetAttributeValue(field, "AXFocused", True)
        AXUIElementSetAttributeValue(field, "AXValue", text)
        return get(field, "AXValue") == text
    except Exception:
        return False


def replace_content(text):
    """Replace the selected text clip's content (verified by reading it back).
    v0.8: on a SUBTITLE clip the first text in this band is the 「文本、排列、气泡、花字应用到全部字幕」 checkbox
    row — double-clicking it un-ticked the checkbox. Skip that row, take the content box below it.
    v1.1.1: the band starts BELOW the panel's tab rows (Mac: the band hit the 「文本」 tab)."""
    if auto.IS_MAC:
        t0 = time.time()
        while time.time() - t0 < 5:
            if _native_replace_content(text):
                auto.SetClipboardText(text)
                jy_ui.keys("{Ctrl}a", wait=0.1)
                jy_ui.keys("{Ctrl}v", wait=0.2)
                jy_ui.keys("{Enter}", wait=0.2)
                return
            time.sleep(0.3)
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
    pick_font(KW["font"])
    panel.set_value("字号", size or KW["size"])
    preset_style(KW["preset"])
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
    if auto.IS_MAC:
        return
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
    # v1.1.3 (Mac test: one long drag moved the edge only 3 s → 4.6 s, then the guard "right edge must be in the
    # first 4 s" refused to go on): grab the CURRENT right edge wherever it is and drag again; every drag that
    # lengthens the clip is kept (no undo), a drag that moved the clip off 0 s is undone.
    offs = (1, 2, 0, 3)
    stall = 0
    for i in range(0 if ok else 45):         # stops early: 6 drags in a row with no progress
        redge = _purple_right_edge(y, tl.x_of(0), tl.x_of(end) + S(40))
        if redge is None:
            raise Pause(f"找不到新滤镜片段的右边缘 {dbg}")
        if starts_at_zero() and abs(redge - tl.x_of(end)) <= S(8):
            ok = True
            break
        off = offs[stall % len(offs)]
        goal = min(tl.x_of(end) + 2, redge + S(900))      # shorter drags register better on Mac
        auto.DragDrop(int(redge) + S(off), int(y), int(goal), int(y), moveSpeed=0.5, waitTime=0.8)
        time.sleep(0.6)
        redge2 = _purple_right_edge(y, tl.x_of(0), tl.x_of(end) + S(40))
        z = starts_at_zero()
        dbg.append(dict(off=off, y=int(y), redge=int(redge), after=None if redge2 is None else int(redge2),
                        end_x=int(tl.x_of(end)), zero=z))
        print("filter drag:", dbg[-1], flush=True)
        if not z:                                    # grabbed the body: the clip MOVED -> undo that drag
            tl.undo()
            time.sleep(0.6)
            if not starts_at_zero():
                raise Pause(f"滤镜片段被拖离了 0 秒、撤销也没回来 {dbg}")
            stall += 1
            continue
        if z and redge2 is not None and abs(redge2 - tl.x_of(end)) <= S(8):
            ok = True
            break
        if redge2 is None or redge2 <= redge + 2:    # nothing happened: try another grab point
            stall += 1
            if stall >= 6:
                break
        else:
            stall = 0
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
