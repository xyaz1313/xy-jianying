#!/usr/bin/env bash
# xy-jianying 一键安装（macOS / Linux）。幂等，可重复跑。  用法：bash install.sh
# 小爷出品 · CC BY-NC 4.0
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
NAME="xy-jianying"
OS="$(uname -s)"
echo "== xy-jianying 安装：${ROOT}（$OS $(uname -m)）"

# ---------- 1. 系统软件：Python 3.10+、FFmpeg、git
if [ "$OS" = "Darwin" ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "✗ 没有 Homebrew。先在「终端」里粘贴下面这行装好（会要你输入开机密码，自己输）："
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "  装完关掉终端重新打开，再跑一次：bash install.sh"
    exit 1
  fi
  # ffmpeg-full: Homebrew's plain ffmpeg has no drawtext (Chinese captions / speed badges)
  for pkg in python@3.12 ffmpeg-full git; do
    if brew list --versions "$pkg" >/dev/null 2>&1; then echo "· ${pkg}：已安装"; else echo "· 安装 $pkg …"; brew install "$pkg"; fi
  done
  PY_SYS="$(brew --prefix python@3.12)/bin/python3.12"
else
  PY_SYS="$(command -v python3.12 || command -v python3)"
  command -v ffmpeg >/dev/null 2>&1 || echo "✗ 没有 FFmpeg：sudo apt install ffmpeg（或你的发行版的包管理器）"
  command -v git >/dev/null 2>&1 || echo "✗ 没有 git：sudo apt install git"
  [ -n "$PY_SYS" ] || { echo "✗ 没有 Python 3：sudo apt install python3 python3-venv"; exit 1; }
fi
echo "· Python：$("$PY_SYS" --version)"

# ---------- 2. 独立的 Python 环境（.venv，不碰系统 Python）
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "· 创建 Python 环境 .venv …"
  "$PY_SYS" -m venv "$ROOT/.venv" || { echo "✗ 创建 .venv 失败"; exit 1; }
fi
PY="$ROOT/.venv/bin/python"
"$PY" -m pip install -q --upgrade pip
echo "· 安装 Python 依赖（第一次几分钟）…"
"$PY" -m pip install -q -r "$ROOT/requirements.txt" || { echo "✗ pip 安装失败（看上面的报错）"; exit 1; }
if [ "$OS" = "Linux" ] && command -v nvidia-smi >/dev/null 2>&1; then
  echo "· 检测到 NVIDIA：补装 CUDA 版 OCR / 转写运行库"
  "$PY" -m pip install -q onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12
fi
echo "· Python 依赖：已安装"

# ---------- 3. 草稿库 jianying-editor-reliable（生成剪映草稿用；固定版本 881edd2）
DEP=""
for d in "$(dirname "$ROOT")/jianying-editor-reliable" "$HOME/.agents/skills/jianying-editor-reliable" \
         "$HOME/.claude/skills/jianying-editor-reliable"; do
  [ -d "$d" ] && DEP="$d" && break
done
if [ -z "$DEP" ]; then
  DEP="$(dirname "$ROOT")/jianying-editor-reliable"
  echo "· 下载草稿库到 $DEP …"
  git -c core.autocrlf=false clone -q https://github.com/ydflow/jianying-editor-skill-reliable.git "$DEP" \
    && git -C "$DEP" checkout -q 881edd24c41672e93dbe5bd258993f785b518857 \
    || echo "✗ 草稿库下载失败（网络？）。剪映草稿这一步会不可用，其他照常"
else
  echo "· 草稿库：$DEP"
fi

# ---------- 4. 链接到各个 Agent 的 skills 目录（软链接，不复制）
link() {
  local t="$1"; mkdir -p "$t"
  if [ "$(cd "$t" && pwd)/$NAME" = "$ROOT" ]; then echo "· ${t}：就是源目录"; return; fi
  if [ -e "$t/$NAME" ] || [ -L "$t/$NAME" ]; then echo "· ${t}：已存在，跳过"; return; fi
  ln -s "$ROOT" "$t/$NAME" && echo "· 已链接到 $t/$NAME"
  [ -d "$DEP" ] && [ ! -e "$t/jianying-editor-reliable" ] && ln -s "$DEP" "$t/jianying-editor-reliable"
}
link "$HOME/.agents/skills"
for h in .claude .codex .workbuddy .cursor .kimi-code .kimi .trae .doubao; do
  [ -d "$HOME/$h" ] && link "$HOME/$h/skills"
done

# ---------- 5. 本机配置 + 体检
[ -f "$ROOT/config.json" ] || { cp "$ROOT/config.example.json" "$ROOT/config.json"; echo "· 已生成 config.json（留空 = 自动查找）"; }
chmod +x "$ROOT/run.sh" 2>/dev/null
echo
"$PY" -X utf8 "$ROOT/scripts/doctor.py"
cat <<'EOF'

== 安装完成。
- 以后所有脚本都用：bash <这个文件夹>/run.sh <脚本名> [参数]      例：bash run.sh doctor.py --full
- 让 AI 用：在豆包 / WorkBuddy / Claude Code / Codex 里说「用 xy-jianying 帮我剪这条口播」
- Mac 第一次实时操作剪映前：系统设置 → 隐私与安全性 → 打开「辅助功能」和「屏幕与系统录音」
  （给你用来跑 AI 的那个程序：终端 / 豆包 / WorkBuddy）
- 光效层万一盖住屏幕：⌃⌥F12（笔记本键盘 fn+⌃⌥F12），或 ⌘⌥Esc 强制退出 Python
EOF
