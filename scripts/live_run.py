"""Live AI edit of a talking-head video in 剪映, with the on-screen light-trail overlay. Meant to be filmed.

python live_run.py <job.json> [--from N]
EDL mode (v0.6, the approved script-director cut):
  job.json: {"edl": edl.json, "tx": {"1": tx1.json, ...}, "visual_plan": visual_plan.json, "draft": "short name",
             "screen_clips": [2], "orig": "2:37", "banner_sub": "...", "kw_from": 1}
  step 1 = build_from_edl.py (EDL order incl. hook-first reorder, pauses removed, speed + volume from the EDL);
  step 6 = one keyword pair per visual_plan entry (colour / X / Y / 字号 / entrance animation per keyword).
Legacy plan mode (v0.3): {"plan": plan.json, "edit_plan": edit_plan.json, "files": [...], "draft": ..., "keywords": [...]}
Steps: 1 build draft (A)  2 open + show cuts  3 beauty  4 filter  5 subtitles  6 keywords  7 summary
On any failure: overlay shows '⏸ 暂停', script exits with code 2 and prints the step to resume from.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jy_ui  # noqa: E402
import panel  # noqa: E402
import steps  # noqa: E402
import timeline as tl  # noqa: E402
from steps import CYAN, GREEN, PINK, PURPLE, WHITE, Pause, fx, status  # noqa: E402,F401

PY = sys.executable
# transcript fixes for overlay labels (whisper mishears; longest keys first)
FIX = {"也不纯扯": "这不纯扯", "早餐割韭菜": "在这割韭菜", "思域": "私域", "老饭": "牢饭", "蠢扯": "纯扯",
       "早餐": "在这", "他妈": "××"}


def fixed(s):
    for k, v in FIX.items():
        s = s.replace(k, v)
    return s


def overlay_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:8790/", timeout=0.5)
        return True
    except Exception:
        return False


def ensure_overlay():
    if overlay_up():
        return
    subprocess.Popen([PY, "-X", "utf8", str(HERE / "overlay" / "overlay.py"), "--parent", str(os.getpid())],
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    steps.wait_for(overlay_up, 20, what="光效层启动")
    time.sleep(1.5)


def check_total(expect_s, what):
    """Timeline length must stay what the layout says (±2 frames); anything else = stop that step."""
    f = tl.total_frames()
    if f is None:
        tl.layout()
        f = tl.total_frames()
    if f is None or abs(f - round(expect_s * tl.FPS)) > 2:
        raise Pause(f"{what}：总长 {None if f is None else round(f / tl.FPS, 2)}s ≠ {expect_s:.2f}s")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--skip", default="", help="comma list of steps to skip, e.g. 3,4,5 (calibration drafts)")
    a = ap.parse_args()
    J = json.load(open(a.job, encoding="utf-8"))
    state_p = pathlib.Path(a.job).with_suffix(".state.json")
    S = json.load(open(state_p, encoding="utf-8")) if state_p.exists() else {}
    t_start = time.time()
    ensure_overlay()
    fx(type="clear")
    fx(type="stats", text="")

    def elapsed():
        s = int(time.time() - t_start)
        return f"{s // 60:02d}:{s % 60:02d}"

    step = a.start
    skip = {int(x) for x in a.skip.split(",") if x.strip()}
    try:
        # 1 ─ build the draft (mode A): 19 frame-exact cuts, 1.1x, +6 dB
        if step <= 1:
            edl_mode = "edl" in J
            status("01 生成草稿 · 剪气口 · 换序 · 1.1x · +6dB" if edl_mode else "01 生成草稿 · 剪气口 · 1.1x · +6dB")
            fx(type="banner", text="AI 剪辑开始", sub=J.get("banner_sub", ""), hold=3)
            time.sleep(3.5)
            # v0.8 HANDOFF RULE: never write a draft while 剪映 has a draft open — when that draft is closed 剪映
            # rewrites its draft list from memory and the new draft vanishes (「过程演示正式版」, 2026-11-18).
            # So: go to the home page first; the build happens with no draft open; open_draft then checks the card.
            if len(J["draft"]) > 5:
                raise Pause(f"草稿名「{J['draft']}」太长（首页会截断）：用 5 个字以内的唯一名字")
            if steps.in_editor():
                steps.go_home()
            lay_p = str(state_p.with_suffix(".layout.json"))
            if J.get("builder") == "demo":           # v0.8 process-demo: approved timeline + visual plan
                cmd = [PY, "-X", "utf8", str(HERE / "build_demo.py"), J["edl"], J["timeline"], J["visual_plan"],
                       J["voice"], J["draft"], lay_p]
            elif edl_mode:
                cmd = [PY, "-X", "utf8", str(HERE / "build_from_edl.py"), J["edl"], J["draft"], lay_p, "--tx",
                       *[f"{k}={v}" for k, v in J["tx"].items()]]
            else:
                cmd = [PY, "-X", "utf8", str(HERE / "build_final.py"), J["plan"], J["draft"], lay_p, "--files",
                       *J["files"], "--volume-db", str(J.get("volume_db", 6))]
            out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if out.returncode != 0:
                raise Pause("生成草稿失败：" + out.stderr[-200:])
            print(out.stdout.strip()[-300:])
            S["layout"] = json.load(open(state_p.with_suffix(".layout.json"), encoding="utf-8"))
            json.dump(S, open(state_p, "w", encoding="utf-8"), ensure_ascii=False)
            # v0.8 HANDOFF RULE (2026-11-18, proven twice): a running 剪映 never lists a draft written while it runs —
            # not even after going home. It must be QUIT (tray → 退出; closing the window only hides it) and started
            # again. Not running -> open_draft starts it.
            if steps.jianying_running():
                raise Pause(f"草稿「{J['draft']}」已生成：请从右下角托盘退出剪映（不用重新打开），然后用 --from 2 继续")
            json.dump(S, open(state_p, "w", encoding="utf-8"), ensure_ascii=False)
            step = 2
        lay = S["layout"]
        total = lay["total"]
        cut_sum = sum(c["len"] for c in lay["cuts"])

        # 2 ─ open the draft in 剪映 and show every cut on the real timeline
        if step <= 2:
            status("02 打开草稿")
            steps.open_draft(J["draft"])
            check_total(total, "打开的草稿总长不对")
            ncut = len(lay["cuts"])
            status(f"02 接缝 · {ncut} 处")
            ry = (tl.L["ruler"][1] + tl.L["ruler"][3]) / 2
            removed = 0.0
            for i, c in enumerate(sorted(lay["cuts"], key=lambda c: c["seam"]), 1):
                removed += c["len"]
                x = tl.x_of(c["seam"])
                ctx = f"…{fixed(c['before'])} ✂ {fixed(c['after'])}…" if (c["before"] or c["after"]) else ""
                fx(type="cursor", agent="Claude", to=[x, ry])
                fx(type="fly", **{"from": [x, ry - 40]}, to=[x, tl.L["track_y"]],
                   color=(PINK if c["kind"] in ("气口", "删段") else CYAN), agent="Claude",
                   label=(f"✂ {c['kind']} {c['len']:.2f}s  {ctx}" if c["len"] else f"⇄ {c['kind']}  {ctx}"),
                   dur=0.45, hold=1.4)
                status(f"02 {c['kind']} {i}/{ncut}")
                fx(type="stats", text=f"已剪掉 {removed:.1f}s · 成片 {total:.1f}s · 用时 {elapsed()}")
                time.sleep(0.75)
            step = 3

        # 3 ─ beauty preset on every face segment (clips 1 and 3); skip the screen-filmed clip 2
        if step <= 3 and 3 in skip:
            step = 4
        if step <= 3:
            status("03 美颜")
            tl.layout(); tl.calibrate()
            segs = lay["segments"]
            scr = set(J.get("screen_clips", [2]))
            for s in [s for s in segs if s["clip"] in scr][:1]:
                mid = (s["start"] + min(s["end"], s["start"] + 20)) / 2
                fx(type="fly", **{"from": [panel.PANEL[0], 300]}, to=[tl.x_of(mid), tl.L["track_y"]], color=WHITE,
                   label="✕ 拍屏段不加美颜", dur=0.5, hold=2)
            face = [s for s in segs if s["clip"] not in scr]
            for k, s in enumerate(face, 1):
                if k < J.get("beauty_from", 1):
                    continue
                status(f"03 美颜 {k}/{len(face)}")
                steps.apply_beauty_preset((s["start"] + s["end"]) / 2)
                fx(type="stats", text=f"已剪掉 {cut_sum:.1f}s · 成片 {total:.1f}s · 用时 {elapsed()}")
            step = 4

        if step >= 3:          # resuming mid-way: (re)locate the timeline before touching it
            steps.uia_retry(tl.layout)
            tl.calibrate()

        # 4 ─ filter over the whole timeline
        if step <= 4 and 4 in skip:
            step = 5
        if step <= 4:
            status("04 滤镜 · 高清增强 34")
            steps.add_filter_full("高清增强", 34, total)
            check_total(total, "加滤镜后总长变了")
            step = 5

        # 5 ─ subtitles: one-click recognition with custom words, then the owner's style
        if step <= 5 and 5 in skip:
            step = 6
        if step <= 5:
            status("05 字幕 · 一键识别")
            steps.recognize_subtitles()
            status("05 字幕 · 新青年体 白字黑边")
            steps.style_subtitles(5.0)
            if J.get("builder") == "demo":          # owner rule: 导流 words may be SPOKEN, never shown
                import compliance
                E = json.load(open(J["edl"], encoding="utf-8"))
                T = json.load(open(J["timeline"], encoding="utf-8"))
                win = []
                for sg in T["segments"]:
                    src, a, b = (sg["audio_from"] if "audio_from" in sg else
                                 (sg["src"], sg.get("a_snapped", sg["a"]), sg.get("b_snapped", sg["b"]))
                                 if sg.get("audio") else (None, 0, 0))
                    if not src or src not in E.get("tx", {}):
                        continue
                    for ph in json.load(open(E["tx"][src][0], encoding="utf-8"))["segments"]:
                        if ph["end"] > a and ph["start"] < b and compliance.hits(ph["text"]):
                            k = (sg["out_end"] - sg["out_start"]) / max(b - a, 0.01)
                            win.append((sg["out_start"] + max(0, ph["start"] - a) * k,
                                        sg["out_start"] + min(b - a, ph["end"] - a) * k))
                if win:
                    status("05 字幕 · 导流词只说不显示")
                    print("hidden subtitles:", steps.hide_banned_subtitles(win))
            check_total(total, "加字幕后总长变了")
            step = 6

        # 6 ─ keywords. EDL mode: visual_plan.json decides colour / X / Y / 字号 / entrance animation PER keyword;
        #     font 仓耳榜黑 + preset 2 + stroke 90 are set once on the first keyword and inherited by every clone.
        if step <= 6 and "visual_plan" in J:
            kws = json.load(open(J["visual_plan"], encoding="utf-8"))["keywords"]
            tpl = S.get("kw_tpl", {})
            for i, k in enumerate(kws, 1):
                if i < J.get("kw_from", 1):
                    continue
                t, red, white = max(k["t"], 0.05), k["red"], k.get("white")
                col = k["color"].lstrip("#").upper()
                status(f"06 重点 {i}/{len(kws)} · {red}{(' ' + white) if white else ''} · {k['anim']}")
                if "red" not in tpl:
                    steps.add_default_text_at(t)
                    steps.replace_content(red)
                    steps.style_keyword(col, k["x"], k["y_red"], k["size"], k["anim"])
                    tpl["red"] = red
                    S["kw_tpl"] = tpl
                else:
                    steps.clone_keyword(tpl["red"], t, red, color=col, x=k["x"], y=k["y_red"], size=k["size"],
                                        anim=k["anim"])
                if white:
                    steps.clone_keyword(tpl["red"], t, white, color="FFFFFF", x=k.get("x_white", k["x"]), y=k["y_white"],
                                        size=k["size"], anim=k["anim"])
                S["kw_done"] = i
                json.dump(S, open(state_p, "w", encoding="utf-8"), ensure_ascii=False)
                tl.layout()
                tl.calibrate()
                fx(type="fly", **{"from": [tl.x_of(t), tl.L["track_y"]]}, to=[2900, 520], color="#" + col,
                   label=f"重点 · {red}{(' / ' + white) if white else ''} · {k['anim']}", dur=0.6, hold=1.8)
                fx(type="stats", text=f"已剪掉 {cut_sum:.1f}s · 成片 {total:.1f}s · 用时 {elapsed()}")
            check_total(total, "加大字后总长变了")
            step = 7
        elif step <= 6:
            ep = json.load(open(J["edit_plan"], encoding="utf-8"))
            times = [k["t"] for k in ep["keywords"]]
            pairs = J["keywords"]
            first = True
            for i, (t, pair) in enumerate(zip(times, pairs), 1):
                if pair is None:
                    continue
                red, white = pair
                t = max(t, 0.05)
                status(f"06 重点 {i}/{len(pairs)} · {red}{(' ' + white) if white else ''}")
                if first:
                    steps.add_default_text_at(t)
                    steps.replace_content(red)
                    steps.style_keyword("FF287F", steps.KW["x"], steps.KW["y_red"])
                    red_tpl = red
                    if white:
                        steps.clone_keyword(red_tpl, t, white, color="FFFFFF", y=steps.KW["y_white"])
                        white_tpl = white
                    first = False
                else:
                    steps.clone_keyword(red_tpl, t, red)
                    if white:
                        if "white_tpl" in locals():
                            steps.clone_keyword(white_tpl, t, white)
                        else:
                            steps.clone_keyword(red_tpl, t, white, color="FFFFFF", y=steps.KW["y_white"])
                            white_tpl = white
                tl.layout(); tl.calibrate()
                fx(type="fly", **{"from": [tl.x_of(t), tl.L["track_y"]]}, to=[2900, 520], color=PINK,
                   label=f"重点 · {red}{(' / ' + white) if white else ''}", dur=0.6, hold=1.8)
                fx(type="stats", text=f"已剪掉 {cut_sum:.1f}s · 成片 {total:.1f}s · 用时 {elapsed()}")
            step = 7

        # 7 ─ summary
        status("07 完成")
        nk = len(json.load(open(J["visual_plan"], encoding="utf-8"))["keywords"]) if "visual_plan" in J \
            else len([p for p in J["keywords"] if p])
        fx(type="banner", text=f"原始 {J.get('orig', '2:23')} → 成片 {int(total // 60)}:{int(total % 60):02d}",
           sub=f"{len(lay['cuts'])} 处接缝 · 美颜 · 高清增强 · 字幕 · {nk} 个重点 · 用时 {elapsed()}", hold=8)
        print("DONE", elapsed())
        time.sleep(9)                       # let the owner film the final banner
    except Pause as e:
        status(f"⏸ 暂停：第 {step} 步 · {e}")
        print(f"PAUSED at step {step}: {e}")
        time.sleep(30)                      # keep the pause message on screen for the camera, then clean up
        sys.exit(2)
    except Exception as e:  # noqa: BLE001
        status(f"⏸ 暂停：第 {step} 步出错")
        import traceback; traceback.print_exc()
        print(f"ERROR at step {step}: {e!r}")
        time.sleep(30)
        sys.exit(2)
    finally:
        # v0.7: ALWAYS close the overlay when the run ends. A leftover overlay later turns opaque black, stays on
        # top of everything and the PC looks frozen (owner had to hard-reboot after every run).
        try:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8790/quit", data=b"", method="POST"),
                                   timeout=2)
        except Exception:
            pass
        time.sleep(1)
        jy_ui.overlay_stop()


if __name__ == "__main__":
    main()
