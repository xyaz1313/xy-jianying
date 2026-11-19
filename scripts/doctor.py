"""xy-jianying doctor (v1.1) — "装上能不能马上用？" in one command. Works on Windows, macOS and Linux.

  python scripts/doctor.py            quick check: system, GPU backend, FFmpeg, 剪映, fonts, Python packages -> 档位
  python scripts/doctor.py --full     + real tests: encode a clip, transcribe a spoken sample, OCR, light overlay
  python scripts/doctor.py --ui       + 剪映 UI probe (open 剪映 first; home page or an open draft): screenshot +
                                        every OCR'd label + the panel / timeline rects the live mode would use
                                        (read-only: it only brings 剪映 to the front, never clicks inside it)
  XY_BACKEND=cpu python scripts/doctor.py --full     pretend there is no GPU (test the slow path)

Writes a report folder  <skill>/doctor-report/<date-time>/  (report.md + report.json + screenshots).
Send that folder back to the skill author / your agent when something is ✗.
"""
import datetime
import importlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SKILL = HERE.parent
import platform_env as pe  # noqa: E402

ARGS = set(sys.argv[1:])
FULL = "--full" in ARGS or "--ui" in ARGS
UI = "--ui" in ARGS
OUT = SKILL / "doctor-report" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT.mkdir(parents=True, exist_ok=True)
R = {"version": (SKILL / "VERSION").read_text().strip() if (SKILL / "VERSION").exists() else "?",
     "checks": [], "tests": []}


def row(kind, name, ok, detail=""):
    mark = "✓" if ok is True else ("✗" if ok is False else "·")
    R[kind].append({"name": name, "ok": ok, "detail": str(detail)})
    print(f"  {mark} {name}: {detail}", flush=True)
    return ok


def run(cmd, timeout=600, **kw):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)
    return r, time.time() - t


# ======================================================================== quick checks
print(f"== xy-jianying doctor v{R['version']}  ({datetime.datetime.now():%Y-%m-%d %H:%M})")
print("[系统]")
B = pe.probe(force=True) if "--probe" in ARGS or FULL else pe.probe()
B = pe._backend()
R["backend"] = B
row("checks", "系统", True, f"{platform.system()} {platform.release()} · {platform.machine()} · Python {platform.python_version()}")
if sys.version_info < (3, 10):
    row("checks", "Python 版本", False, "需要 3.10+（推荐 3.12）")
gpu_txt = {"nvidia": "NVIDIA 独显（CUDA）", "apple": "苹果芯片（Metal / VideoToolbox）", "amd": "AMD 显卡/核显（AMF 编码）",
           "intel": "Intel 核显（QSV 编码）", "cpu": "无可用 GPU（全部走 CPU）"}[B["gpu"]]
try:
    import style as _style
    row("checks", "风格参数 style.json", _style.ERROR is None, _style.ERROR or _style.summary().replace("\n", " · ")[:160])
except Exception as _e:  # noqa: BLE001
    row("checks", "风格参数 style.json", False, str(_e))
row("checks", "显卡后端", True, gpu_txt + (f"（XY_BACKEND={B['forced']} 强制）" if B.get("forced") else ""))
r = None
try:
    r, _ = run([str(pe.FF), "-version"], timeout=20)
    row("checks", "FFmpeg", r.returncode == 0, (r.stdout.splitlines() or ["?"])[0][:80] + f" · 编码器 {B['encoder']}")
except Exception as e:
    row("checks", "FFmpeg", False, f"没找到（{e}）— Windows: winget install Gyan.FFmpeg · Mac: brew install ffmpeg")

eng, dev, ct = pe.whisper_cfg()
row("checks", "转写引擎", True, f"{eng} · {dev} · {pe.whisper_model_name()}")

print("[剪映]")
try:
    from config import CFG, jianying_exe
    jy = jianying_exe()
except Exception as e:
    CFG, jy = {}, None
    row("checks", "config.py", False, e)
row("checks", "剪映专业版", bool(jy) if pe.OS != "linux" else None,
    jy or ("Linux 没有剪映：只能用导演层（样片 / 字幕 / 封面）" if pe.OS == "linux" else "没找到 — 在 config.json 填 jianying_exe"))
_cfg_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
row("checks", "本机配置 config.json", True if os.path.exists(_cfg_file) else None,   # v1.2 (#1): say it, don't fail
    "已有" if os.path.exists(_cfg_file) else
    f"没有 → 用默认值：导出到 {CFG.get('export_root') or '默认'}；镜像同步（mirror_dir）不可用。要改就复制 config.example.json")
dr = pe.drafts_root()
row("checks", "草稿文件夹", bool(dr and os.path.isdir(dr)) if jy else None, dr or "-")
kw = pe.jianying_font("仓耳榜黑")
row("checks", "大字字体 仓耳榜黑", bool(kw) if jy else None, kw or "剪映里用一次「仓耳榜黑」它就会下载到缓存（预览会先用系统字体）")
row("checks", "预览用系统字体", os.path.exists(pe.font()), pe.font())
dep = pe.dependency_skill("jianying-editor-reliable")
row("checks", "草稿库 jianying-editor-reliable", os.path.isdir(dep), dep)

print("[Python 包]")
need = {"numpy": "numpy", "PIL": "Pillow", "cv2": "opencv-python", "onnxruntime": "onnxruntime",
        "rapidocr_onnxruntime": "rapidocr-onnxruntime", "PySide6": "PySide6"}
need["mlx_whisper" if eng == "mlx" else "faster_whisper"] = "mlx-whisper" if eng == "mlx" else "faster-whisper"
if pe.OS == "win":
    need["uiautomation"] = "uiautomation"
if pe.OS == "mac":
    need.update({"Quartz": "pyobjc-framework-Quartz", "ApplicationServices": "pyobjc-framework-ApplicationServices",
                 "pynput": "pynput"})
if pe.GPU == "apple" and eng != "mlx":
    row("checks", "mlx-whisper", None, "没装：转写会走 CPU（慢）。pip install mlx-whisper 后苹果芯片快很多")
missing = []
for mod, pip in need.items():
    try:
        importlib.import_module(mod)
        row("checks", pip, True, "ok")
    except Exception as e:
        missing.append(pip)
        row("checks", pip, False, f"缺：pip install {pip}  ({type(e).__name__})")

if pe.OS == "mac":
    print("[Mac 权限]（给运行 Python 的那个程序：终端 / 豆包 / WorkBuddy …）")
    try:
        import osctl
        a, s = osctl.accessibility_ok(), osctl.screen_recording_ok()
        row("checks", "辅助功能（点击 / 打字）", a, "系统设置 → 隐私与安全性 → 辅助功能 → 打开该程序" if not a else "已授权")
        row("checks", "屏幕录制（截图 / OCR）", s, "系统设置 → 隐私与安全性 → 屏幕与系统录音 → 打开该程序" if not s else "已授权")
        row("checks", "输入监控（紧急热键 ⌃⌥F12）", None, "要用 ⌃⌥F12 急停就必须打开（系统设置 → 隐私与安全性 → 输入监控）；没开时用 ⌘⌥Esc 强制退出 Python")
    except Exception as e:
        row("checks", "Mac 权限检查", False, e)

tier = pe.tier()
R["tier"] = tier
print(f"\n[档位] {pe.TIER_TEXT[tier]}")

# ======================================================================== real tests
if FULL:
    print("\n[实测]")
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    # 1) encode: 10 s 1080p test clip with the chosen encoder
    try:
        clip = tmp / "enc_test.mp4"
        r, dt = run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                     "testsrc2=s=1920x1080:r=30:d=10", "-f", "lavfi", "-i", "sine=f=440:d=10",
                     *pe.venc(23), "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)], timeout=300)
        row("tests", f"编码 10 秒 1080p（{B['encoder']}）", r.returncode == 0 and clip.exists(),
            f"{dt:.1f}s" if r.returncode == 0 else r.stderr[-300:])
        r, dt = run([str(pe.FF), "-hide_banner", "-loglevel", "error", *pe.hwaccel(), "-i", str(clip),
                     "-vf", "fps=1,scale=320:-2", str(tmp / "thumb_%02d.png")], timeout=120)
        row("tests", "解码 + 抽帧" + (f"（{pe.hwaccel()[1]}）" if pe.hwaccel() else "（CPU）"), r.returncode == 0,
            f"{dt:.1f}s" if r.returncode == 0 else r.stderr[-300:])
    except Exception as e:
        row("tests", "编码 / 解码", False, e)

    # 2) drawtext with the preview font (speed badges, labels)
    try:
        r, _ = run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=1",
                    "-vf", f"drawtext=fontfile='{pe.ff_font()}':text='»» 加速 ×8':fontsize=46:fontcolor=0xFFE600:x=20:y=20",
                    "-frames:v", "1", str(OUT / "drawtext_test.png")], timeout=60)
        row("tests", "中文字幕绘制（加速标）", r.returncode == 0, "看 drawtext_test.png" if r.returncode == 0 else r.stderr[-200:])
    except Exception as e:
        row("tests", "中文字幕绘制", False, e)

    # 3) OCR on a rendered label image
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGB", (900, 160), (30, 30, 34))
        ImageDraw.Draw(im).text((30, 40), "导出  播放器  智能字幕", font=ImageFont.truetype(pe.font(), 56), fill=(235, 235, 235))
        im.save(OUT / "ocr_test.png")
        import numpy as np
        t = time.time()
        ocr = pe.ocr_engine()
        res, _ = ocr(np.array(im)[:, :, ::-1])
        txt = "".join(x[1] for x in res or [])
        row("tests", "文字识别 OCR（" + ("CUDA" if pe.ocr_cuda() else "CPU") + "）",
            "播放器" in txt and "导出" in txt, f"读到「{txt}」 {time.time() - t:.1f}s")
    except Exception as e:
        row("tests", "文字识别 OCR", False, f"{type(e).__name__}: {e}")

    # 4) transcription on a spoken sample (macOS `say` / Windows SAPI); skipped if no Chinese TTS voice
    try:
        sample = tmp / "speech.wav"
        line = "大家好，我是小爷。今天给大家演示一下，人工智能怎么自动剪辑视频。"
        made = False
        if pe.OS == "mac":
            aiff = tmp / "speech.aiff"
            for voice in ("Tingting", "Ting-Ting", "Meijia", "Sinji"):
                if run(["say", "-v", voice, "-o", str(aiff), line], timeout=60)[0].returncode == 0 and aiff.exists():
                    made = True
                    break
            src = aiff
        elif pe.OS == "win":
            wavtmp = tmp / "speech_sapi.wav"
            ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                  "$v=$s.GetInstalledVoices()|?{$_.VoiceInfo.Culture.Name -like 'zh*'}|select -First 1;"
                  "if(-not $v){exit 3}; $s.SelectVoice($v.VoiceInfo.Name);"
                  f"$s.SetOutputToWaveFile('{wavtmp}'); $s.Speak('{line}'); $s.Dispose()")
            made = run(["powershell", "-NoProfile", "-Command", ps], timeout=60)[0].returncode == 0 and wavtmp.exists()
            src = wavtmp
        if made:
            run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                 str(sample)], timeout=60)
            print("  · 转写测试中（第一次会下载模型，几分钟）…", flush=True)
            r, dt = run([sys.executable, "-X", "utf8", str(HERE / "transcribe.py"), str(tmp / "tx"), str(sample)],
                        timeout=3600)
            got = ""
            j = tmp / "tx" / "speech.json"
            if j.exists():
                got = "".join(s["text"] for s in json.load(open(j, encoding="utf-8"))["segments"])
            hit = sum(1 for w in ("小爷", "演示", "自动剪辑", "视频") if w in got)
            row("tests", f"语音转文字（{eng} · {dev}）", r.returncode == 0 and hit >= 2,
                f"{dt:.0f}s（含加载模型）读到「{got.strip()[:60]}」" if r.returncode == 0 else r.stderr[-400:])
        else:
            row("tests", "语音转文字", None, "跳过：系统没有中文朗读声音（不影响使用；用你自己的素材测）")
    except Exception as e:
        row("tests", "语音转文字", False, f"{type(e).__name__}: {e}")

    # 5) light overlay: start, answer, quit by itself
    if pe.OS in ("win", "mac"):
        try:
            import urllib.request
            p = subprocess.Popen([sys.executable, "-X", "utf8", str(HERE / "overlay" / "overlay.py"), "--parent",
                                  str(os.getpid())], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace")
            up = False
            for _ in range(60):
                try:
                    urllib.request.urlopen("http://127.0.0.1:8790/", timeout=0.5)
                    up = True
                    break
                except Exception:
                    time.sleep(0.25)
                if p.poll() is not None:
                    break
            try:
                urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8790/quit", data=b"", method="POST"),
                                       timeout=1)
            except Exception:
                pass
            try:
                p.wait(8)
            except Exception:
                p.kill()
            log = (p.stdout.read() if p.stdout else "")[-600:]
            row("tests", "光效层 启动 / 退出", up and p.poll() is not None,
                ("ok · " if up else "没起来 · ") + " | ".join(l for l in log.splitlines() if l.strip())[-300:])
        except Exception as e:
            row("tests", "光效层", False, e)

# ======================================================================== 剪映 UI probe (read-only)
if UI:
    print("\n[剪映界面探测]（只读：只把剪映切到前台、截图、识字）")
    try:
        import jy_ui
        import osctl
        w = jy_ui.win()
        if not w.Exists(2, 0.5):
            row("tests", "剪映窗口", False, "没找到窗口：先打开剪映（首页或者打开一个草稿），再跑 --ui")
        else:
            w.SetActive()
            time.sleep(1.0)
            r = w.BoundingRectangle
            row("tests", "剪映窗口", True, f"{getattr(w, 'owner', '') or w.Name} rect=({r.left},{r.top},{r.right},{r.bottom})"
                + (f" · Retina 缩放 {osctl.SCALE:g}" if pe.OS == "mac" else ""))
            shot = jy_ui.grab()
            shot.save(OUT / "ui_full.png")
            ts = jy_ui.texts((r.left, r.top, r.right, r.bottom))
            (OUT / "ui_texts.tsv").write_text("\n".join(f"{int(t[1])}\t{int(t[2])}\t{t[0]}\t{t[4]:.2f}" for t in ts),
                                              encoding="utf-8")
            row("tests", "识字", len(ts) > 10, f"{len(ts)} 处文字 → ui_texts.tsv")
            import steps
            ed = steps.in_editor()
            row("tests", "页面", True, "编辑页（有「导出」）" if ed else "首页 / 其他页")
            if ed:
                import panel
                try:
                    P = panel.geom()
                    row("tests", "面板定位（素材 / 播放器 / 属性）", True, f"PANEL={P[0]} MAT={P[1]} PLAYER={P[2]}")
                except Exception as e:
                    row("tests", "面板定位", False, f"{type(e).__name__}: {e}")
                try:
                    import timeline as tl
                    L = tl._layout()
                    row("tests", "时间线定位", True, {k: v for k, v in L.items()})
                    try:
                        row("tests", "时间尺校准", True, tl.calibrate())
                    except Exception as e:
                        row("tests", "时间尺校准", False, e)
                except Exception as e:
                    row("tests", "时间线定位", False, f"{type(e).__name__}: {e}")
            else:
                cards = [t for t in ts if t[0].strip() in ("开始创作", "草稿", "本地草稿", "剪辑草稿")]
                row("tests", "首页元素", bool(cards), [c[0] for c in cards] or "没认出「开始创作 / 草稿」")
    except Exception as e:
        row("tests", "剪映界面探测", False, traceback.format_exc()[-600:])

# ======================================================================== report
bad = [c for c in R["checks"] + R["tests"] if c["ok"] is False]
R["summary"] = {"tier": tier, "tier_text": pe.TIER_TEXT[tier], "problems": len(bad), "missing_pip": missing}
(OUT / "report.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
md = [f"# xy-jianying 体检报告 v{R['version']}", "", f"- 时间：{datetime.datetime.now():%Y-%m-%d %H:%M}",
      f"- 档位：**{pe.TIER_TEXT[tier]}**", f"- 后端：`{json.dumps({k: B[k] for k in ('os', 'gpu', 'encoder', 'machine')})}`",
      f"- 问题：{len(bad)} 个", "", "| | 项目 | 结果 |", "|---|---|---|"]
md += [f"| {'✓' if c['ok'] is True else '✗' if c['ok'] is False else '·'} | {c['name']} | {c['detail'].replace('|', '/')[:300]} |"
       for c in R["checks"] + R["tests"]]
if missing:
    md += ["", "补装：", "```", f"{sys.executable} -m pip install " + " ".join(missing), "```"]
(OUT / "report.md").write_text("\n".join(md), encoding="utf-8")
print(f"\n== 档位：{pe.TIER_TEXT[tier]}")
print(f"== {'没有问题 ✓' if not bad else f'{len(bad)} 个问题 ✗（看上面 ✗ 那几行）'}")
print(f"== 报告：{OUT}")
if missing:
    print("== 补装：" + f"{sys.executable} -m pip install " + " ".join(missing))
sys.exit(1 if bad else 0)
