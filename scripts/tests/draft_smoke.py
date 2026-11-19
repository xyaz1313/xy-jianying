"""A-mode smoke test: make a small test draft 「XY测试」 (20 s generated clip) in 剪映's draft folder. Mac & Windows.

  python scripts/tests/draft_smoke.py          (Mac: bash run.sh tests/draft_smoke.py)

剪映 must be QUIT first (Mac ⌘Q / Windows tray → 退出): a running 剪映 does not see new drafts.
Then open 剪映: the home page must list 「XY测试」, it must open and play (colour bars, 20 s, a beep, one title).
Never touches any other draft.
"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import osctl  # noqa: E402
import platform_env as pe  # noqa: E402
import steps  # noqa: E402

NAME = "XY测试"
if steps.jianying_running():
    sys.exit(f"✗ 剪映还开着：请先{steps.QUIT_HINT}，再运行本测试。")
root = pe.drafts_root()
print("草稿文件夹:", root, "（存在）" if root and pathlib.Path(root).is_dir() else "（不存在！先打开一次剪映再退出）")
work = pe.SKILL / ".cache" / "smoke"
work.mkdir(parents=True, exist_ok=True)
clip = work / "xy_test_clip.mp4"
subprocess.run([str(pe.FF), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                "testsrc2=s=1920x1080:r=30:d=20", "-f", "lavfi", "-i", "sine=f=660:d=20:beep_factor=4",
                *pe.venc(23), "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)], check=True)
print("测试素材:", clip)
r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "build_draft.py"), NAME, "1.0", str(clip)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode != 0:
    sys.exit("✗ 生成草稿失败：\n" + r.stderr[-1500:])
out = r.stdout.strip().splitlines()[-1]
try:
    info = json.loads(out)
    print("✓ 草稿已生成:", info.get("save"))
except Exception:
    print(r.stdout[-800:])
d = pathlib.Path(root) / NAME
print("草稿目录:", d, "✓" if d.is_dir() else "✗ 没找到（看上面的 save 路径）")
print(f"""
下一步（人做）：打开剪映 → 首页应该有「{NAME}」→ 点开 → 能播放 20 秒彩条 + 嘀嘀声？
把结果告诉 AI：看到了 / 没看到 / 打开报错（截图）。""" + ("\nMac 版剪映路径：" + str(osctl.JY_NAMES) if osctl.IS_MAC else ""))
