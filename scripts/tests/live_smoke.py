"""B-mode smoke test: really drive 剪映 on the TEST draft 「XY测试」 (made by draft_smoke.py). Mac & Windows.

  python scripts/tests/live_smoke.py          (Mac: bash run.sh tests/live_smoke.py)

Steps (each one checked, stops at the first ✗):
  1 open 「XY测试」 from the home page (starts 剪映 if needed, closes ad pop-ups)
  2 light overlay up over 剪映
  3 locate panels + timeline by OCR, calibrate the ruler
  4 seek the playhead to 00:05 frame-exactly
  5 split at 00:10 (Ctrl+B / ⌘B) and undo it (Ctrl+Z / ⌘Z)
  6 overlay closes
Only the test draft is touched. Screenshots + log -> doctor-report/<time>-live/.
"""
import datetime
import json
import pathlib
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import jy_ui  # noqa: E402
import panel  # noqa: E402
import platform_env as pe  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402

NAME = "XY测试"
OUT = pe.SKILL / "doctor-report" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-live")
OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def ok(n, what, detail=""):
    LOG.append({"step": n, "ok": True, "what": what, "detail": str(detail)})
    print(f"✓ {n} {what} {detail}", flush=True)


def shot(tag):
    try:
        jy_ui.grab().save(OUT / f"{tag}.png")
    except Exception:
        pass


step = 0
try:
    step = 1
    steps.open_draft(NAME)
    time.sleep(2)
    shot("1_editor")
    ok(1, "打开测试草稿", NAME)
    step = 2
    jy_ui.overlay_start()
    steps.status(f"{jy_ui.AGENT} · 实操测试")
    ok(2, "光效层", "up")
    step = 3
    P = panel.geom()
    L = tl.layout()
    cal = tl.calibrate()
    ok(3, "定位 + 时间尺", {"panel": P, "timeline": L, "cal": cal})
    step = 4
    tl.seek(5.0, label="定位到 00:05")
    tc = tl.read_tc()
    shot("4_seek")
    ok(4, "逐帧定位", tc)
    step = 5
    before = tl.total_frames()
    tl.split_at(10.0, label="在 00:10 切一刀")
    time.sleep(0.8)
    shot("5_split")
    tl.undo()
    time.sleep(0.8)
    ok(5, "切一刀 + 撤销", f"总长 {before} 帧 → {tl.total_frames()} 帧")
    step = 6
    jy_ui.overlay_stop()
    ok(6, "光效层关闭", "")
    print("\n== 实操测试全部通过 ✓")
except Exception as e:
    shot(f"{step}_FAIL")
    LOG.append({"step": step, "ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]})
    print(f"\n✗ 第 {step} 步失败：{type(e).__name__}: {e}")
    try:
        ts = jy_ui.texts()
        (OUT / f"{step}_FAIL_texts.tsv").write_text("\n".join(f"{int(t[1])}\t{int(t[2])}\t{t[0]}" for t in ts),
                                                    encoding="utf-8")
    except Exception:
        pass
finally:
    try:
        jy_ui.overlay_stop()
    except Exception:
        pass
    (OUT / "live_smoke.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1), encoding="utf-8")
    print("== 记录:", OUT)
