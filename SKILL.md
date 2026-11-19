---
name: xy-jianying
description: 【剪映自动剪辑】AI 在剪映专业版里真的动手剪：口播（talking-head）和"过程演示"类横版 16:9 视频，从转写、去气口、隐私打码、脚本导演（3 秒钩子 / 2 秒防跳出 / 5 秒完播）、视觉与画面导演（大字配色、入场动效、不挡脸不居中、无导流词）、BGM，到在剪映里实时操作（美颜、滤镜、一键字幕、大字、加速标，屏幕上有光效层可录屏），再到封面（挑帧 + 横版 16:9 / 竖版 3:4）。每个关键环节先出样片给人确认，剪完只留在剪映草稿箱，人看过、改过、说导出才导出。Windows（有没有 N 卡都行）/ Mac（苹果芯片）+ 剪映专业版；Linux 可用导演层。用户说「剪口播」「帮我剪这条」「去气口」「加字幕」「加大字」「自动剪辑」「用剪映剪」「做光效」「剪个过程演示」「做封面」「导出成片」，或丢来横版口播素材时使用，即使没点名这个 skill。｜小爷出品
license: CC-BY-NC-4.0（完整条款见 LICENSE；商用须经作者书面授权）
compatibility: Windows 10/11（NVIDIA 满配，在 RTX 5070 Ti 验证；无 N 卡走核显 / CPU，在 AMD 核显验证）· macOS 13+（苹果芯片，Metal / VideoToolbox）· Linux（仅导演层，没有剪映）；剪映专业版（国内版，Windows 在 11.8 验证）；Python 3.10+（推荐 3.12）+ FFmpeg；Agent 需能在本机执行命令（Claude Code、Codex、WorkBuddy、豆包、Kimi Code 等）。只做横版 16:9。
metadata:
  slug: xy-jianying
  version: 1.1.4
  displayName: 剪映自动剪辑
  display_name: "剪映自动剪辑"
  display_name_en: "JianYing Auto Edit"
  visibility: "public"
  author: "小爷（风物执守）"
  co_author: "Claude（Anthropic）"
  copyright: "Copyright (c) 2026 小爷（风物执守）"
  homepage: "https://github.com/xyaz1313/xyskill"
---

# xy-jianying：剪映自动剪辑（v1.1.4）

## 开场自报家门
本 skill 被调用后，回复的第一行固定是：**【剪映自动剪辑 xy-jianying】AI 在剪映里真的帮你把横版口播剪完，留在草稿箱等你过目。** 之后再进入正式流程。

小爷出品 · 与 Claude（Anthropic）共同制作 · CC BY-NC 4.0（不得商用，商用请联系作者）。

任何 Agent（Claude、GPT、豆包、Kimi…）都要能照着这份文件把活干完：每一步都有检查，检查不过就**停下来告诉用户**，绝不靠猜继续点。

先读：`references/house-style.md`（风格默认值 = 小爷的风格，可改）· `references/environment.md`（安装、显卡、踩坑）·
`CHANGELOG.md`（当前版本、待办）。过程演示类素材（拍屏、几乎不说话）再读 `references/process-demo-director.md`。
**风格参数：`style.json`**（v1.1.1 起，全部集中在这一个文件：变速 / 去气口 / 人声、美颜预设和数值、滤镜和强度、字幕字体字号描边热词、大字字体字号描边配色动效位置、BGM、封面、导出）——开源，用户想要自己的风格就改它；代码里不再写死这些数。
本机配置：`config.json`（从 `config.example.json` 复制；剪映路径、导出根目录等）——**不要把个人路径写进代码**。

## 第 0 步：体检（每台新电脑、每次出问题先跑）
- Windows：`python -X utf8 scripts/doctor.py`　· Mac / Linux：`bash run.sh doctor.py`（**Mac/Linux 所有脚本都用 `bash run.sh <脚本名> 参数`**，它用 install.sh 建的 `.venv`）
- 加 `--full` 实测编码 / 转写 / OCR / 光效层；加 `--ui` 探测剪映界面（只读）。报告在 `doctor-report/<时间>/report.md`。
- 把它报的**档位**原样告诉用户：满配（Win+N 卡）/ 标准（Win 无 N 卡，转写慢几倍）/ Mac / 仅导演（Linux 或没装剪映：做到样片、字幕、封面为止，跳过第 5、6 步）。
- 有 ✗ 就先按提示修（缺包、Mac 权限……），修不好就停下来把 report.md 给用户看，不要硬跑。
- Mac 上快捷键里的 `{Ctrl}` 自动变成 ⌘；光效层紧急关闭是 ⌃⌥F12（笔记本 fn+⌃⌥F12），不行就 ⌘⌥Esc 强制退出 Python。

## 铁律
1. **人把关，不全自动。** 剪完只留在剪映**草稿箱**；用户在剪映里看一遍、手动改；用户说「导出」才导出。
2. **导出（只在用户说了之后）**：4K 30fps MP4 → `<导出根目录>\YYYY-MM-DD 标题\`，**视频 + `封面-横版16x9.png` + `封面-竖版3x4.png` 放同一个文件夹**（剪映会多建一层同名子文件夹，挪平）。剪映导出完成窗口里的「发布」**永远不点**。
3. **三次确认才进剪映**：(a) 去气口样片 (b) 脚本方案 + 钩子 (c) 大字 / 位置 / BGM 预览。
4. **大字**：不挡脸、**不居中**（有人 → 离脸远的上角；没人 → 更空的那一侧，`director.busyness`）；仓耳榜黑、粗黑描边、两行贴紧、每组都有入场动效。
5. **话要讲完**：每个带声音的剪点都过 `scripts/speech_cuts.py`（剪到整句后、带上「对吧 / 啊」、落在最安静处）。
6. **合规**：画面上（大字 / 字幕）不出现导流词（`scripts/compliance.py`）；口播里的私域钩子**声音保留、字幕删掉**；工程标签（STEP n…）只在光效层出现，不进成片；第三方姓名、电话、聊天列表打码，脏话消音。
7. **能用显卡就用显卡，由 `scripts/platform_env.py` 自动选**（不要在脚本里写死 cuda / nvenc / 字体路径）：N 卡 → CUDA whisper + NVENC + CUDA OCR；苹果芯片 → mlx-whisper + VideoToolbox；AMD/Intel 核显 → AMF/QSV 编码 + CPU 转写；都没有 → CPU。测试慢路径：`XY_BACKEND=cpu`。
8. **光效层不能赖着不走**：`live_run.py` 结束必关；它自己也会在父进程退出 / 空闲 15 分钟 / 剪映不在时退出。万一黑屏：**Ctrl+Alt+F12**（Mac：⌃⌥F12 / ⌘⌥Esc）。
9. **把草稿交给剪映前**：剪映必须**完全退出**（Windows：托盘 → 退出，只点 × 会缩到托盘；Mac：⌘Q）——运行中的剪映不认中途写进来的草稿；脚本会自己启动剪映、关广告弹窗（**绝不点「立即试听 / 开通」类按钮**）。草稿名 ≤ 5 个字、唯一。
10. **改了 skill 就走迭代流程**（见下）；每期的决定和产物存进用户的笔记（如 Obsidian）。

## 流程（一条视频）
| # | 阶段 | 运行 | 人确认 |
|---|---|---|---|
| 1 | 抽音频 + 转写（自动选 GPU / CPU） | `ffmpeg -i clip.mp4 -vn -ac 1 -ar 16000 clip.wav` → `python scripts/transcribe.py <out> clip1.wav …`（可疑句自动标记） | — |
| 2 | 顺序、去气口（≥0.35 s，留 0.12 s）、隐私 | `scripts/privacy_mosaic.py`；样片 `scripts/render_edl.py` | ✅ (a) |
| 3 | **脚本导演** | 口播：`scripts/script_director.py` + `references/script-director.md`；过程演示：`scripts/process_map.py` + `references/process-demo-director.md` + `scripts/process_render.py`（三个钩子各 15 s 样片 + 全片样片） | ✅ (b) |
| 3b | 整句检查 | `python scripts/speech_cuts.py check <edl.json>` | — |
| 4 | **视觉 + 画面导演** | 口播：`scripts/visual_director.py`；过程演示：`scripts/process_visual.py`（真实画面上避脸、合成预览、导流词拦截）；BGM 见 house-style | ✅ (c) |
| 5 | 生成剪映草稿（A 模式，逐帧精确） | 口播：`scripts/build_from_edl.py`；过程演示：`scripts/build_demo.py`（变速、借声、降噪人声、加速标、BGM） | — |
| 6 | **剪映里实时剪（B 模式，可录屏）** | `python scripts/live_run.py job.json [--from N] [--skip …]`：打开草稿 + 接缝光影 → 美颜 → 滤镜 → 一键字幕（导流句字幕自动删）→ 大字 + 入场动效 → 完成横幅 | 可用相机拍下全过程 |
| 6b | 核对草稿 | `python scripts/verify_draft.py visual_plan.json <frames_dir> <sheet.jpg>` | — |
| 7 | 封面 | `scripts/cover_frames.py`（打分挑帧：不露牙、眼睛有神）→ 用户挑 → `scripts/cover_render.py`（横版 16:9 + 竖版 3:4）→ 剪映「封面 → + → 设为封面」（`references/live-edit-internals.md` §8） | ✅ 用户挑帧和文案 |
| 8 | **留在草稿箱，用户检查、手动改** | 不导出 | ✅ 用户 |
| 9 | 导出（用户说了才做） | 见铁律 2 | 用户发布 |

情绪 → 颜色 → 入场（默认值在 `scripts/visual_director.py`）：`bait` 钱 / 好奇 → `FFE600` 黄 → 打字机I · `warn` 警告 / 硬观点 → `FF287F` 玫红 → 放大 · `us` 我方观点 → `2BE36B` 绿 → 向上弹入。第二行永远白色。

位置单位（4K 画布实测）：**2 个剪映单位 = 1 像素**，X=Y=0 为中心；仓耳榜黑 + 描边 90 在字号 14 时每字 0.081 画宽、每行 0.190 画高。
默认大字：字号 13（= 字号 8 × 缩放 160%），两行贴紧（行距 0.01165 H / 字号），贴外侧边（边距 1.6% W、顶 1.7% H）；只有会挡脸才缩小。
剪映版本、画布或字体变了就在一个废草稿上重新校准（`references/live-edit-internals.md` §7）。

剪映是怎么被操控的（OCR 点击、逐帧定位、安全填数、每个已知故障和修法）：**`references/live-edit-internals.md`**——改 `scripts/` 前必读。

## 迭代流程（像 iOS 一样发版）
1. 先快照：把整个 skill 目录复制到 `skill-workspaces/xy-jianying-workspace/iteration-N/`。
2. 改；在本文件标题和 `CHANGELOG.md` 里升版本（改了什么 · 为什么 · 怎么验证的）。
3. 跑 `evals/evals.json`（行为变了就新旧对比），结果放 `iteration-N/`。
4. 待办做完就移进发版说明；用户的新意见写进待办或直接变成规则（写进代码，不做一次性修补）。
5. 同步到维护者的镜像目录（`config.json` → `mirror_dir`，小爷的是他 Obsidian 里的副本），镜像是给其他 Agent 的权威版本。
6. 打包：`python -m scripts.package_skill <skill目录> <输出目录>`（Anthropic 官方 skill-creator 脚本）→ `xy-jianying.skill`。

## 目录
`SKILL.md` · `README.md` · `LICENSE` · `VERSION` · `CHANGELOG.md` · `config.example.json` · `install.ps1`（Windows）· `install.sh` + `run.sh`（Mac / Linux）· `MAC-TEST.md` · `requirements.txt` ·
`agents/openai.yaml`（Codex 界面描述）· `scripts/`（全部代码；`platform_env.py` 选后端、`osctl.py` Win/Mac 鼠标键盘窗口、`doctor.py` 体检；`overlay/` 光效层；`tests/`）·
`references/`（house-style、environment、script-director、process-demo-director、live-edit-internals）· `assets/` · `evals/evals.json`
