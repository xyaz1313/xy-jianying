---
type: reference
area: library
created: 2026-11-17
updated: 2026-11-17
project: AI Auto-Editing Pipeline
tags:
  - video-editing
  - automation
  - skill
  - tutorial-source
---
# AI Editing Skill Stack

Back to Knowledge Library MOC · project file: 2026-11-17 AI Auto-Editing with JianYing · tools: Tool Stack

> 用途：AI 自动剪辑这套流程用到的**所有技能（Skill）和依赖的清单**：从哪来、哪个版本、装在哪、怎么装、踩过什么坑。后面打包成 Skill、写教程、教粉丝，都以这份为准。**每次升级版本或改动都在这里更新。**

## Skills
| Skill | 作用 | 来源（网址） | 锁定版本 | 本机安装位置 | 离线备份 |
|-------|------|--------------|----------|--------------|----------|
| **jianying-editor-reliable** | A 模式：生成剪映草稿（素材、字幕、AI 配音、配乐、特效、关键帧），Windows 下可自动导出（剪映 ≤5.9） | https://github.com/ydflow/jianying-editor-skill-reliable · ZIP：https://github.com/ydflow/jianying-editor-skill-reliable/archive/refs/heads/main.zip | `881edd2`（2026-09-19，v1.8.0-reliable.3） | `%USERPROFILE%\.claude\skills\jianying-editor-reliable` | `（作者本地备份）jianying-editor-reliable_881edd2.zip`（5.9 MB） |
| **adu-motion-video**（阿杜） | 代码动效包装模板：大字、图解、3D 多屏，逐帧渲染出 MP4 | https://github.com/adunext/adu-motion-video · 新版模板：https://motiongit.com/@adunext | `4ae737a`（2026-11-14，v3.14.2-rc.1） | `%USERPROFILE%\.claude\skills\adu-motion-video` | `（作者本地备份）adu-motion-video_4ae737a.zip`（37 MB） |
| **xy-jianying**（自研，原名 jianying-live-fx） | B 模式：像人一样操控剪映（点击 + 快捷键）＋ 剪映上方的**实时光效悬浮层**（飞线、光点、AI 光标、标签） | 我们自己的，还没上 GitHub | 2026-11-17 雏形 | `%USERPROFILE%\.claude\skills\jianying-live-fx` | `（作者本地备份）jianying-live-fx_2026-11-17.zip` |

> ⚠️ 为什么要留离线备份：`jianying-editor-reliable` 的上游原项目 `luoluoluo22/jianying-editor-skill` **已经被删了（404）**。开源仓库随时可能消失或改版，教程必须对应一个固定版本。

### 相关但没有安装
- MotionGit 模板目录：https://github.com/motiontemplates/all（100 个模板。只有 #385712 能直接下载，其他的要登录 motiongit.com）
- MotionGit 源码协作：https://motiongit.com/git（git.motiongit.com，基于 Gitea）
- 阿杜导演（阿杜的 AI 剪辑软件，带"代码飞进时间线"界面）：**还没公开下载**

## Runtime dependencies（本机，2026-11-17）
| 依赖 | 版本 | 安装方式 | 谁需要 |
|------|------|----------|--------|
| 剪映专业版（国内版，会员） | 11.8.0.14778 | 官网 https://www.jianying.com/ | 全部 |
| Python | 3.12.10 | `winget install Python.Python.3.12 --scope user` | 全部 |
| Node.js | 26.13.1 LTS | `winget install OpenJS.NodeJS.LTS` | adu-motion-video |
| FFmpeg | 9.0.2 | `winget install Gyan.FFmpeg` | 全部 |
| Git | 2.56.1 | — | 安装 Skill |
| Python 包：jianying-editor-reliable 的 requirements.txt + `playwright install chromium` | 见仓库 | pip（用户级） | jianying-editor-reliable |
| PySide6 | 6.9.1 | pip | xy-jianying 光效层 |
| faster-whisper + CUDA 库 | 安装中 | pip | 转写 / 气口 / 逐字稿 |

## GPU（2026-11-17 实测）
- **NVIDIA GeForce RTX 5070 Ti**，16 GB 显存，算力 12.0（Blackwell 架构），驱动 **621.24**（2026-11-07），支持 CUDA 13.5 ✅
- 电脑上还有 AMD Radeon 核显，以及两个虚拟显示设备（Oray 向日葵、GameViewer 网易 UU 远程）。**容易被误用成核显**
- FFmpeg：`-hwaccel cuda` 硬件解码 4K HEVC，10 秒素材只要 **1.6 秒**；`hevc_nvenc` 硬件编码 4K，10 秒素材 **3.1 秒** ✅。Agent 处理 4K 素材时一律用 NVDEC/NVENC
- 剪映：`ve_hw_check.ini` 里 `device_name=NVIDIA GeForce RTX 5070 Ti`，`cuda=1`、`cuvid=1`，`vesdk.ini` 里 `gpu=auto` ✅（剪映已经识别到 5070 Ti）
- Windows「图形设置」里**没有给剪映单独指定高性能 GPU**。建议小爷手动设置：设置 → 系统 → 屏幕 → 显示卡 → 添加 `<剪映安装目录>\JianyingPro.exe（config.json → jianying_exe，留空自动查找）` → 选"高性能（RTX 5070 Ti）"（这是系统设置，Agent 不代改）
- 语音转写（faster-whisper）走 CUDA；之后的超分、降噪、人脸分析也优先用这张卡

### GPU usage audit (2026-11-18) — 小爷要求"把这张卡用好"
| 环节 | 用的硬件 | 实测速度 |
|---|---|---|
| 语音转写 faster-whisper large-v3（CUDA 12） | ✅ 5070 Ti | 20.5 秒素材 1.9 秒；90 秒素材 6.8 秒 |
| FFmpeg 解码 / 编码（NVDEC / NVENC）：打码渲染、所有预览 | ✅ 5070 Ti | 4K HEVC 解码约 6 倍实时 |
| 剪映（含美颜、滤镜、导出） | ✅ 5070 Ti（`nvidia-smi` 进程列表里能看到 JianyingPro.exe） | — |
| 屏幕 / 画面文字识别 OCR（RapidOCR on onnxruntime-gpu，**CUDA 13**） | ✅ **已从 CPU 搬到 5070 Ti** | 单帧 0.39s → **0.13s**；4K 全屏 2–3s → **0.55s** |
| 人脸检测（OpenCV Haar） | CPU（量很小，每个大字只抽 6 帧） | — |
- 安装要点：`onnxruntime-gpu` 1.32 需要 CUDA 13 的库：`pip install nvidia-cublas nvidia-cuda-runtime nvidia-cudnn-cu13 nvidia-cufft nvidia-curand`（**不带 -cu13 后缀的才是 CUDA 13 版**，带后缀的 cu13 包装不上）；DLL 在 `nvidia/cu13/bin/x86_64`，统一用 `tools/gpu_env.py` 登记。CUDA 12（给 faster-whisper）和 CUDA 13 两套可以并存
- 必须先卸掉 CPU 版 `onnxruntime` 再装 `onnxruntime-gpu`

## Install recipe（教程用的最小步骤）
```bash
# 1. 装好剪映专业版（国内版），登录后打开一次再关掉（这样才会生成草稿目录）
# 2. 装依赖
winget install Python.Python.3.12 --scope user
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
# 3. 装 Skill 到用户级目录（所有 Claude Code 会话都能用）
cd ~/.claude/skills
git -c core.autocrlf=false clone https://github.com/ydflow/jianying-editor-skill-reliable.git jianying-editor-reliable
git -c core.autocrlf=false clone https://github.com/adunext/adu-motion-video.git adu-motion-video
# 4. 装 Python 依赖
python -m pip install --user -r jianying-editor-reliable/requirements.txt
python -m playwright install chromium
python adu-motion-video/scripts/pipeline.py setup
# 5. 只读自检
python jianying-editor-reliable/scripts/doctor.py --json
python adu-motion-video/scripts/pipeline.py doctor
```

## Known pitfalls（教程里一定要讲）
1. **Windows 换行符坑**：Git 默认 `core.autocrlf=true`，会把文本文件改成 CRLF 换行，导致阿杜模板的字体校验失败（报错 `Bundled font installation is damaged`）。**clone 的时候加上 `-c core.autocrlf=false`**；已经 clone 过的，执行 `git config core.autocrlf false && git rm --cached -r -q . && git reset --hard` 修复
2. **剪映新版会加密草稿**：11.8 版打开过的草稿，`draft_content.json` 会被加密，所以只能"生成新草稿"，不能改剪映已经打开过的草稿。不破解；B 模式直接操作界面，不受影响
3. **剪映 >5.9 不支持自动导出**：需要在剪映里手动点导出
4. 新生成的草稿要**重启剪映**（或者进出一次草稿列表）才能看到；`Claude_Full_Test` 一直没出现，原因待查
5. winget 装完后，新开的终端才会读到新的 PATH；Agent 可以用绝对路径
6. Node 安装时会弹出管理员权限确认（UAC），需要人点"是"

## Tutorial outline seeds（以后写教程用）
> 小爷的计划（2026-11-17）：整套流程跑通、调好之后，会接入**飞书 Bot**，把这一章写进飞书课件。小爷说这一章"非常非常重要"。在那之前，所有流程、版本、踩坑都先存在这里和 2026-11-17 AI Auto-Editing with JianYing。

- 第 1 课：为什么用剪映国内版而不是达芬奇（门槛、会员、生态）
- 第 2 课：一键装环境 + 两个 Skill + 自检
- 第 3 课：A 模式：一句话让 AI 搭好整条草稿
- 第 4 课：B 模式 + 实时光效：AI 当着镜头在剪映里剪片
- 第 5 课：阿杜模板做包装动效
- 第 6 课：踩坑合集（上面的 Known pitfalls）

## v1.1 跨平台（2026-11-18）
| 档位 | 机器 | 后端（`scripts/platform_env.py` 自动选，`doctor.py` 报告） | 实测 |
|---|---|---|---|
| 满配 | Windows + NVIDIA | faster-whisper large-v3 CUDA fp16 · NVENC/NVDEC · OCR CUDA | RTX 5070 Ti：2 分钟口播 4 s；10 s 1080p 编码 0.8 s |
| 标准 | Windows 无 N 卡 | faster-whisper large-v3-turbo CPU int8 · AMF（AMD）/ QSV（Intel）/ libx264 · OCR CPU | Ryzen 7 9800X3D + AMD 核显（`XY_BACKEND=amd`）：2 分钟口播 16 s；编码 1.0 s；OCR 0.9 s |
| Mac | macOS 13+ 苹果芯片 | mlx-whisper large-v3-turbo（Metal）· VideoToolbox · OCR CPU · Quartz 点击 / 键盘（`scripts/osctl.py`）· 光效层 PySide6 | 待 M5 实测（`MAC-TEST.md`） |
| 仅导演 | Linux / 没装剪映 | CPU / CUDA；剪映步骤跳过 | — |

- Mac 没有 Windows 的 UI 自动化树：播放器 / 时间线全部靠 OCR 定位（`panel._player_by_ocr`）。在 Windows 上关掉 UIA 模拟过：和 UIA 结果相差 ≤ 11 px，时间线、时间尺校准完全一致。
- Mac 权限：辅助功能（点击 / 打字）、屏幕与系统录音（截图）、输入监控（紧急热键 ⌃⌥F12，可选）。
- Mac 安装用自带 `.venv`（Homebrew 的 Python 不让 pip 装到系统里），所有脚本经 `bash run.sh <脚本>` 运行。
- 强制走慢路径测试：`XY_BACKEND=cpu|amd|intel|apple|nvidia`；换模型：`XY_WHISPER_MODEL=large-v3`。
