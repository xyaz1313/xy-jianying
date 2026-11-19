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
$HasNv = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if ($HasNv) {
    Write-Host ("· 显卡：" + (& nvidia-smi --query-gpu=name --format=csv,noheader) + "（满配：显卡转写 / 渲染 / OCR）")
} else { Write-Host "· 没有 NVIDIA 显卡：照样能用（标准档）——转写走 CPU，编码走核显（AMD / Intel）或 CPU" }

# 2. Python 依赖（有 N 卡才装 CUDA 12 / 13 运行库）
& python -m pip install -q -r "$Root\requirements.txt"
if ($HasNv) {
    & python -m pip install -q onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12
    & python -m pip install -q nvidia-cublas nvidia-cuda-runtime nvidia-cudnn-cu13 nvidia-cufft nvidia-curand
}
Write-Host "· Python 依赖：已安装"

# 2b. 草稿库 jianying-editor-reliable（生成剪映草稿；固定版本 881edd2）
$Dep = $null
foreach ($d in @((Join-Path (Split-Path -Parent $Root) "jianying-editor-reliable"), "$HOME\.agents\skills\jianying-editor-reliable", "$HOME\.claude\skills\jianying-editor-reliable")) {
    if (Test-Path $d) { $Dep = $d; break }
}
if (-not $Dep) {
    $Dep = Join-Path (Split-Path -Parent $Root) "jianying-editor-reliable"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "· 下载草稿库到 $Dep …"
        & git -c core.autocrlf=false clone -q https://github.com/ydflow/jianying-editor-skill-reliable.git $Dep
        & git -C $Dep checkout -q 881edd24c41672e93dbe5bd258993f785b518857
    } else { Write-Host "✗ 没有 git，草稿库没下载：winget install Git.Git 后重跑本脚本" }
} else { Write-Host "· 草稿库：$Dep" }

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
& python -X utf8 "$Root\scripts\doctor.py"

Write-Host @'
== 安装完成。
- Claude Code / Cursor：新开会话，说「/xy-jianying 帮我剪这条口播」
- Codex：$xy-jianying 帮我剪这条口播
- WorkBuddy / 豆包 / Kimi：调用 xy-jianying 这个 skill（或上传 xy-jianying.skill）
- 想实测一遍：python -X utf8 scripts\doctor.py --full（在这个文件夹里）
- 光效层万一盖住屏幕：Ctrl+Alt+F12
'@
