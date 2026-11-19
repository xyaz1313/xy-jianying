"""One-command acceptance test for the live 剪映 layer (mode B). Mac & Windows. v1.1.1

  Windows:  python -X utf8 scripts/tests/acceptance.py --media <a 口播 clip with a face and speech>
  Mac:      bash run.sh tests/acceptance.py --media <clip>

What it does, on its OWN test draft 「XY验收」 only (never another draft, never export / publish / login):
  0 make the draft from --media (or 20 s colour bars without --media: beauty + subtitles are then skipped)
  1 open it   2 light overlay   3 find panels + timeline + ruler   4 seek 00:05   5 split 00:10 + undo
  6 beauty preset   7 filter 0 s → end + strength 34   8 auto subtitles + style (font / size / white / stroke)
  9 big keyword: add text, replace content, font, size, colour FFE600, position, stroke, entrance animation
 10 clone the keyword at 00:06 (white)   11 back to the home page
Every step is CHECKED (read back from the screen). A failed step is recorded with a screenshot and an OCR dump
of the whole window, then the test goes on with the next step (it is a throw-away draft) so one run shows
everything. Result: doctor-report/<time>-acceptance/report.md + a zip on the Desktop to send back.

For the AI running this: run the ONE command, do not edit any file, send the zip back. Nothing else.
"""
import argparse
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import jy_ui  # noqa: E402
import osctl  # noqa: E402
import panel  # noqa: E402
import platform_env as pe  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402
import style  # noqa: E402
from style import ST  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--media", help="a 口播 clip (face + speech), ideally 20–90 s")
ap.add_argument("--draft", default="XY验收")
ap.add_argument("--skip-build", action="store_true", help="draft already exists: do not rebuild it")
ap.add_argument("--only", help="run only these steps after 1–3, e.g. 6,7 (debugging)")
ap.add_argument("--beauty", help="beauty preset name (default: style.json beauty.preset = 我的预设1), e.g. 自然柔光")
A = ap.parse_args()
NAME = A.draft
PLAT = "mac" if osctl.IS_MAC else "win"
OUT = pe.SKILL / "doctor-report" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-acceptance")
OUT.mkdir(parents=True, exist_ok=True)
LOG = []
T0 = time.time()


def say(s):
    print(s, flush=True)
    with open(OUT / "log.txt", "a", encoding="utf-8") as f:
        f.write(s + "\n")


def shot(tag):
    try:
        jy_ui.grab().save(OUT / f"{tag}.png")
    except Exception as e:
        say(f"  (screenshot failed: {e})")


def dump(tag):
    """Everything OCR sees in the 剪映 window + the computed geometry: what Claude needs to fix a failed step."""
    try:
        r = jy_ui.win().BoundingRectangle
        ts = jy_ui.texts((r.left, r.top, r.right, r.bottom))
        json.dump({"window": [r.left, r.top, r.right, r.bottom], "scale": osctl.ui_scale(),
                   "PANEL": panel.PANEL, "MAT": panel.MAT, "PLAYER": panel.PLAYER, "TOP_Y": panel.TOP_Y,
                   "timeline": tl.L, "cal": tl._cal,
                   "texts": [[t[0], int(t[1]), int(t[2]), [int(v) for v in t[3]]] for t in ts]},
                  open(OUT / f"{tag}_ocr.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception as e:
        say(f"  (ocr dump failed: {e})")


def run(n, what, fn, needed=False, skip=None):
    if A.only and n > 3 and str(n) not in A.only.split(","):
        return None
    if skip:
        LOG.append({"step": n, "what": what, "result": "skip", "detail": skip})
        say(f"– {n:>2} {what}：跳过（{skip}）")
        return None
    t = time.time()
    steps.status(f"{jy_ui.AGENT} · 验收 {n} · {what}")
    try:
        detail = fn()
        LOG.append({"step": n, "what": what, "result": "ok", "detail": str(detail or ""), "sec": round(time.time() - t, 1)})
        say(f"✓ {n:>2} {what} {detail or ''}  ({time.time() - t:.0f}s)")
        shot(f"{n:02d}_ok")
        return True
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, KeyboardInterrupt):
            raise
        tb = traceback.format_exc()
        LOG.append({"step": n, "what": what, "result": "FAIL", "detail": f"{type(e).__name__}: {e}", "trace": tb[-2500:],
                    "sec": round(time.time() - t, 1)})
        say(f"✗ {n:>2} {what}：{type(e).__name__}: {e}")
        shot(f"{n:02d}_FAIL")
        dump(f"{n:02d}_FAIL")
        if needed:
            raise SystemExit(f"✗ 第 {n} 步是后面所有步骤的前提，测试到此为止")
        return False


def quit_jianying():
    if not steps.jianying_running():
        return
    if osctl.IS_MAC:
        for app in ("VideoFusion-macOS", "剪映专业版"):
            subprocess.run(["osascript", "-e", f'quit app "{app}"'], capture_output=True)
        for _ in range(40):
            if not steps.jianying_running():
                time.sleep(2)
                return
            time.sleep(0.5)
    raise SystemExit(f"✗ 剪映还开着：请先{steps.QUIT_HINT}，再运行这条命令（新草稿要剪映重新打开才看得到）")


def build():
    work = pe.SKILL / ".cache" / "acceptance"
    work.mkdir(parents=True, exist_ok=True)
    if A.media:
        clip = pathlib.Path(A.media).expanduser()
        if not clip.is_file():
            raise SystemExit(f"✗ 找不到素材 {clip}")
        cut = work / "media_60s.mp4"                       # keep the test short: first 60 s
        subprocess.run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-t", "60",
                        "-c", "copy", str(cut)], check=True)
        clip = cut
    else:
        clip = work / "bars.mp4"
        subprocess.run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=s=1920x1080:r=30:d=20", "-f", "lavfi", "-i", "sine=f=660:d=20:beep_factor=4",
                        *pe.venc(23), "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)], check=True)
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "build_draft.py"), NAME, "1.0", str(clip)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("生成草稿失败：" + r.stderr[-800:])
    return r.stdout.strip().splitlines()[-1][:120]


def geometry():
    panel.geom()
    tl.layout()
    return f"PANEL={panel.PANEL} MAT={panel.MAT} PLAYER={panel.PLAYER} cal={tuple(round(v, 1) for v in tl._cal)}"


def seek5():
    f = tl.seek(5.0)
    if f != 150:
        raise RuntimeError(f"播放头在第 {f} 帧，应为 150")
    return "第 150 帧"


def split_undo():
    before = tl.total_frames()
    tl.split_at(10.0)
    time.sleep(0.6)
    tl.undo()
    time.sleep(0.6)
    after = tl.total_frames()
    if before is None or before != after:
        raise RuntimeError(f"总长 {before} → {after}")
    return f"总长 {before} 帧不变"


def beauty():
    steps.apply_beauty_preset(3.0, A.beauty)
    return A.beauty or ST["beauty"]["preset"]


def filt():
    total = tl.total_frames() / tl.FPS
    steps.add_filter_full(total=total)
    return f"「{ST['filter']['name']}」0 → {total:.1f}s，强度 {ST['filter']['strength']}"


def subtitles():
    steps.recognize_subtitles()
    steps.style_subtitles(5.0)
    s = ST["subtitle"]
    return f"识别 + {s['font']} / {s['size']} / #{s['color']} / 描边 {s['stroke']}"


STATE = {}


def keyword():
    steps.add_default_text_at(2.0)
    steps.replace_content("验收大字")
    mood = ST["keyword"]["moods"]["bait"]
    steps.style_keyword(mood["color"], steps.KW["x"], steps.KW["y_red"], anim=mood["anim"])
    STATE["kw"] = "验收大字"
    k = ST["keyword"]
    return f"{k['font']} / {k['size']} / #{mood['color']} / 位置 / 描边 {k['stroke']} / {mood['anim']}"


def clone():
    if "kw" not in STATE:
        raise RuntimeError("第 9 步没成功，没有模板大字可复制")
    steps.clone_keyword(STATE["kw"], 6.0, "第二行", color=ST["keyword"]["second_line_color"], y=steps.KW["y_white"])
    return "第二行 / 白"


def home():
    steps.go_home()
    return "首页"


say(f"== xy-jianying 验收测试 · {PLAT} · 草稿「{NAME}」 · 素材 {A.media or '彩条（无人脸/人声）'}")
say(f"   报告文件夹：{OUT}")
say("   本次用的风格参数（style.json）：\n     " + style.summary().replace("\n", "\n     "))
if style.ERROR:
    say("   ⚠ " + style.ERROR)
(OUT / "style_used.json").write_text(json.dumps(ST, ensure_ascii=False, indent=1), encoding="utf-8")
if osctl.IS_MAC:
    say(f"   辅助功能：{'✓' if osctl.accessibility_ok() else '✗ 没开'}   屏幕录制：{'✓' if osctl.screen_recording_ok() else '✗ 没开'}")
try:
    if not A.skip_build:
        quit_jianying()
        run(0, "生成测试草稿", build, needed=True)
    run(1, "打开测试草稿", lambda: steps.open_draft(NAME) or NAME, needed=True)
    run(2, "光效层", lambda: jy_ui.overlay_start() and "up")
    run(3, "定位面板 + 时间线 + 时间尺", geometry, needed=True)
    run(4, "播放头定位 00:05", seek5)
    run(5, "切一刀 00:10 + 撤销", split_undo)
    nomedia = None if A.media else "彩条素材没有人脸"
    run(6, "美颜预设", beauty, skip=nomedia)
    run(7, "滤镜 高清增强 0 秒 → 片尾 + 强度", filt)
    run(8, "一键字幕 + 字幕样式", subtitles, skip=None if A.media else "彩条素材没有人声")
    run(9, "大字：加文本 / 改字 / 字体 / 字号 / 颜色 / 位置 / 描边 / 动效", keyword)
    run(10, "复制大字到 00:06（白字）", clone)
    run(11, "回首页", home)
except SystemExit as e:
    say(str(e))
finally:
    try:
        jy_ui.overlay_stop()
    except Exception:
        pass

ok = sum(1 for x in LOG if x["result"] == "ok")
bad = [x for x in LOG if x["result"] == "FAIL"]
lines = [f"# xy-jianying 验收测试 · {PLAT} · {datetime.datetime.now():%Y-%m-%d %H:%M}", "",
         f"- 草稿：{NAME}　素材：{A.media or '彩条'}　用时：{(time.time() - T0) / 60:.1f} 分钟",
         f"- 结果：**{ok} 步通过，{len(bad)} 步失败**，{sum(1 for x in LOG if x['result'] == 'skip')} 步跳过", "",
         "| 步骤 | 内容 | 结果 | 说明 |", "|---|---|---|---|"]
for x in LOG:
    lines.append(f"| {x['step']} | {x['what']} | {'✓' if x['result'] == 'ok' else '✗' if x['result'] == 'FAIL' else '–'} | "
                 f"{x['detail'].replace('|', '/')[:160]} |")
lines += ["", "## 本次用的风格参数（style.json）", "", "```", style.summary(), "```"]
lines += ["", "失败的步骤各有一张截图（NN_FAIL.png）和整个剪映窗口的文字识别结果（NN_FAIL_ocr.json），发给 Claude 就能改。"]
(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
json.dump(LOG, open(OUT / "report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
desk = pathlib.Path.home() / "Desktop"
zp = shutil.make_archive(str(desk / f"xy-acceptance-{PLAT}-{OUT.name[:13]}"), "zip", OUT)
say("")
say("\n".join(lines[:4]))
say(f"== 结果包：{zp}（把它发给 Claude）")
sys.exit(0 if not bad else 1)
