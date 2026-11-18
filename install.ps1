# xy-jianying 一键安装（Windows PowerShell）。幂等，可重复跑。
# 小爷出品 · CC BY-NC 4.0
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Name = "xy-jianying"
Write-Host "== xy-jianying 安装：源 $Root"

# 1. 环境检查（只提示，不替你装系统软件）
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { Write-Host "✗ 没找到 Python 3.12：请先安装 https://www.python.org/ 并勾选 Add to PATH"; exit 1 }
Write-Host ("· Python：" + (& python --version))
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Write-Host "· FFmpeg：已安装" } else { Write-Host "✗ 没找到 FFmpeg：winget install Gyan.FFmpeg" }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    Write-Host ("· 显卡：" + (& nvidia-smi --query-gpu=name --format=csv,noheader))
} else { Write-Host "✗ 没找到 NVIDIA 显卡驱动（nvidia-smi）：本 skill 需要 N 卡" }

# 2. Python 依赖（含 CUDA 12 / 13 运行库）
& python -m pip install -q -r "$Root\requirements.txt"
& python -m pip install -q nvidia-cublas-cu12 nvidia-cudnn-cu12
& python -m pip install -q nvidia-cublas nvidia-cuda-runtime nvidia-cudnn-cu13 nvidia-cufft nvidia-curand
Write-Host "· Python 依赖：已安装"

# 3. 链接到已存在的 Agent skills 目录（目录联接，不复制、不占空间）
$targets = @("$HOME\.agents\skills")
foreach ($h in ".claude", ".codex", ".workbuddy", ".cursor", ".kimi-code", ".kimi") {
    if (Test-Path "$HOME\$h") { $targets += "$HOME\$h\skills" }
}
foreach ($t in $targets) {
    New-Item -ItemType Directory -Force -Path $t | Out-Null
    $link = Join-Path $t $Name
    if ((Resolve-Path $Root).Path -eq (Join-Path (Resolve-Path $t).Path $Name)) { Write-Host "· $t：就是源目录"; continue }
    if (Test-Path $link) { Write-Host "· $t：已存在，跳过"; continue }
    New-Item -ItemType Junction -Path $link -Target $Root | Out-Null
    Write-Host "· 已链接到 $link"
}

# 4. 本机配置
if (-not (Test-Path "$Root\config.json")) { Copy-Item "$Root\config.example.json" "$Root\config.json"; Write-Host "· 已生成 config.json（剪映路径留空=自动查找）" }
& python "$Root\scripts\config.py"

Write-Host @'
== 安装完成。
- Claude Code / Cursor：新开会话，说「/xy-jianying 帮我剪这条口播」
- Codex：$xy-jianying 帮我剪这条口播
- WorkBuddy / 豆包 / Kimi：调用 xy-jianying 这个 skill（或上传 xy-jianying.skill）
- 光效层万一盖住屏幕：Ctrl+Alt+F12
'@
