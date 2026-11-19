---
name: xy-jianying
description: 【剪映自动剪辑】AI 把横版 16:9 口播（talking-head）和"过程演示"视频剪好，直接写成剪映草稿：转写、去气口和改口叠字、隐私打码、脚本导演（3 秒钩子 / 2 秒防跳出 / 5 秒完播）、视觉与画面导演（大字配色、入场动效、不挡脸不居中、无导流词）、字幕、滤镜、BGM，一次写进草稿（几秒）；剪映里只做美颜（全选一次）；再出封面（挑帧 + 横版 16:9 / 竖版 3:4），说导出才导出。每个关键环节先出样片给人确认，剪完留在剪映草稿箱。也能在剪映里实时操作给镜头拍（光效层）。Windows（有没有 N 卡都行）/ Mac（苹果芯片）+ 剪映专业版；Linux 可用导演层。用户说「剪口播」「帮我剪这条」「去气口」「加字幕」「加大字」「自动剪辑」「用剪映剪」「做光效」「剪个过程演示」「做封面」「导出成片」，或丢来横版口播素材时使用，即使没点名这个 skill。｜小爷出品
license: CC-BY-NC-4.0（完整条款见 LICENSE；商用须经作者书面授权）
compatibility: Windows 10/11（NVIDIA 满配，在 RTX 5070 Ti 验证；无 N 卡走核显 / CPU，在 AMD 核显验证）· macOS 13+（苹果芯片，Metal / VideoToolbox）· Linux（仅导演层，没有剪映）；剪映专业版（国内版，Windows 在 11.8 验证）；Python 3.10+（推荐 3.12）+ FFmpeg；Agent 需能在本机执行命令（Claude Code、Codex、WorkBuddy、豆包、Kimi Code 等）。只做横版 16:9。
metadata:
  slug: xy-jianying
  version: 1.2.1
  displayName: 剪映自动剪辑
  display_name: "剪映自动剪辑"
  display_name_en: "JianYing Auto Edit"
  visibility: "public"
  author: "小爷（风物执守）"
  co_author: "Claude（Anthropic）"
  copyright: "Copyright (c) 2026 小爷（风物执守）"
  homepage: "https://github.com/xyaz1313/xyskill"
---

# xy-jianying：剪映自动剪辑（v1.2.1 · Windows 版）

## 开场自报家门
本 skill 被调用后，回复的第一行固定是：**【剪映自动剪辑 xy-jianying】AI 把你的横版口播剪好、直接写进剪映草稿箱，等你过目。** 之后再进入正式流程。

小爷出品 · 与 Claude（Anthropic）共同制作 · CC BY-NC 4.0（不得商用，商用请联系作者）。

任何 Agent（Claude、GPT、豆包、Kimi…）都要能照着这份文件把活干完：每一步都有检查，检查不过就**停下来告诉用户**，绝不靠猜继续点。

先读：`references/house-style.md`（风格默认值 = 小爷的风格，可改）· `references/environment.md`（安装、显卡、踩坑）·
`CHANGELOG.md`（当前版本、待办）。过程演示类素材（拍屏、几乎不说话）再读 `references/process-demo-director.md`。
**风格参数：`style.json`**（全部集中在这一个文件：变速 / 去气口 / 人声、美颜预设和数值、滤镜和强度、字幕字体字号描边热词 **+ 听错词改正表**、大字字体字号描边配色动效位置、BGM、封面、导出）——开源，用户想要自己的风格就改它。
本机配置：`config.json`（从 `config.example.json` 复制；剪映路径、导出根目录等）——**不要把个人路径写进代码**。

## v1.2 的主路线（2026-11-20 样板跑定下的，小爷的方法）
**先把所有东西剪好 → 一次写成剪映草稿（几秒）→ 剪映里只做美颜（全选一次）→ 看一眼 → 说导出才导出。**
9 分钟的口播：写草稿 2.4 秒，美颜约 2 分钟，4K 导出约 3 分钟。旧的「在剪映里一步步点屏幕」路线同一条片子跑了两个多小时没做完（长时间轴上片段只有几像素宽，靠认字点击全部失效），**只留给要拍「AI 在剪映里动手」过程的短视频**（第 6′ 步）。

## 第 0 步：体检（每台新电脑、每次出问题先跑）
- Windows：`python -X utf8 scripts/doctor.py`　· Mac / Linux：`bash run.sh doctor.py`（**Mac/Linux 所有脚本都用 `bash run.sh <脚本名> 参数`**，它用 install.sh 建的 `.venv`）
- 加 `--full` 实测编码 / 转写 / OCR / 光效层；加 `--ui` 探测剪映界面（只读）。报告在 `doctor-report/<时间>/report.md`。
- **这是 Windows 版安装包**（v1.2 主路线全流程 + 导出已在 Windows 验证）。**Mac 用单独的 Mac 版安装包**（xy-jianying-Mac，Kimi 维护，真机验收 12/12）——两个平台的「操控剪映界面」代码不一样，分开发版、互不改动（2026-11-20 小爷定的：一个平台的修改曾把另一个平台碰坏）。
- 把它报的**档位**原样告诉用户：满配（Win+N 卡）/ 标准（Win 无 N 卡，转写慢几倍）/ Mac / 仅导演（Linux 或没装剪映：做到样片、字幕、封面为止）。
- 有 ✗ 就先按提示修，修不好就停下来把 report.md 给用户看，不要硬跑。

## 铁律
1. **人把关，不全自动。** 剪完只留在剪映**草稿箱**；用户在剪映里看一遍、手动改；用户说「导出」才导出。
2. **导出（只在用户说了之后）**：`scripts/export_draft.py`，4K 30fps MP4 → `<导出根目录>\YYYY-MM-DD 标题\`，**视频 + `封面-横版16x9.png` + `封面-竖版3x4.png` 放同一个文件夹**（剪映 11.8 **不会**自动建这层文件夹，脚本建好再把 mp4 挪进去）。剪映导出窗口里的「发布」「开通 AI Ultra」「收起至首页」**永远不点**。
3. **三次确认才进剪映**：(a) 去气口样片（含成片回听结果）(b) 脚本方案 + 钩子 (c) **大字清单**（时间 · 两行文字 · 颜色 / 动效 · 原话）→ 再出位置预览。**每个确认点都直接发到对话里**（文件卡片 + 表格），笔记只做存档。
4. **大字**：不挡脸、**不居中**（有人 → 离脸远的上角；没人 → 更空的那一侧）；仓耳榜黑、粗黑描边、两行贴紧、每组都有入场动效；一行最好 ≤ 6 个字（长了会被缩到 9–10 号）。
5. **话要讲完、叠字要删**：剪点用 `cut_points.py`（按音量，不切进字里），样片渲染后**必跑** `listen_back.py`（成片回听），可疑处用 `retx.py fragment` 单独转写确认。**同一句式 3 秒内又说一遍 = 改口，留最后一遍**（「你的女朋友｜你把AI当做你的女朋友」）；只有明确列举（第一 / 第二）才是排比；拿不准就列出来问。
6. **合规**：画面上（大字 / 字幕）不出现导流词（`scripts/compliance.py`）；口播里的私域钩子**声音保留、字幕删掉**；工程标签只在光效层出现；第三方姓名、电话、聊天列表打码，脏话消音。
7. **能用显卡就用显卡，由 `scripts/platform_env.py` 自动选**（不要在脚本里写死 cuda / nvenc / 字体路径）。
8. **光效层不能赖着不走**（只在第 6′ 步用）：`live_run.py` 结束必关；万一黑屏：**Ctrl+Alt+F12**（Mac：⌃⌥F12 / ⌘⌥Esc）。
9. **剪映草稿的两条硬规矩**：① 剪映一保存草稿就**加密** `draft_content.json` → 永远**新建**草稿，不改已打开过的（要改就换个名字重新生成，几秒的事）；② 运行中的剪映不认中途写进来的草稿 → 打开前先 `steps.quit_jianying()`（正常关只会缩到托盘，脚本会强制结束）。草稿名 ≤ 5 个字、唯一。广告弹窗绝不点「立即试听 / 开通」。
10. **界面操作的纪律**：同一类失败出现**两次**就停下来换方法，不要一个个打补丁重跑；会「加东西」的步骤没确认幂等就不许重跑（重跑 4 次叠了 4 个大字）；读不到总长 / 时间码 = 停下，什么都不按（可能有窗口挡在剪映前面）。
11. **改了 skill 就走迭代流程**（见下）；每期的决定和产物存进用户的笔记（如 Obsidian）。

## 流程（一条口播）
| # | 阶段 | 运行 | 人确认 |
|---|---|---|---|
| 1 | 抽音频 + 转写 | `ffmpeg -i clip.mp4 -vn -ac 1 -ar 16000 clip.wav` → `scripts/transcribe.py <out> clip.wav` | — |
| 1b | **修稿** | `retx.py suspects tx.json`（平均每字 > 0.45 s 的词：里面藏着重说 / 咳嗽 / 停顿）→ `retx.py window clip.wav a-b …` 单独重转 + 音量条 | — |
| 2 | 去气口 + 删重拍 / 改口 / 语气词、隐私 | 写 plan.json（保留哪些原片区间）→ **`cut_points.py plan.json edl.json`** → `render_edl.py` 样片 → **`listen_back.py`** → 有问题的剪点用 `retx.py fragment` + 音量条确认后写 `"exact": true` 再出一版 | ✅ (a) |
| 3 | **脚本导演** | `script_director.py` + `references/script-director.md`（3 个钩子各 15 s 样片 + 全片样片）；长口播（8–12 分钟干货）只删不重排 | ✅ (b) |
| 4 | **大字清单 → 视觉导演** | 先发清单表；勾完后 `visual_director.py spec.json out/`（避脸、合成预览；锚点写稿子里的原字，含听错的字）；人脸框是假的就在 spec 里写 `faces` | ✅ (c) |
| 5 | **字幕** | `subs_from_cut.py preview.mp4 subs.json --hotwords 本期词…`（转写**剪好的样片本身**；改正表在 style.json）→ 查钩子句、结尾 Respect、热词 | — |
| 6 | **一次写成草稿** | **`build_full.py edl.json visual_plan.json subs.json <草稿名>`**：剪辑 + 变速 + 人声 + 滤镜（0→片尾）+ 字幕 + 全部大字（颜色 / 位置 / 字号 / 描边 / 动效 / 时长） | — |
| 7 | **美颜（全选一次）** | **`beauty_all.py <草稿名> --restart --expect-frames N`**：锁住主轨以上的轨道 → 点主轨 → Ctrl+A → 画面 → 美颜美体 → 美颜预设 → 解锁 → 抽查 3 段磨皮 + 总长 | — |
| 8 | 封面 | `cover_frames.py`（打分挑帧：不露牙、眼睛有神；原画与小图同一帧）→ 用户挑 → `cover_render.py`（横版 16:9 + 竖版 3:4） | ✅ 用户挑帧和文案 |
| 9 | **留在草稿箱，用户检查、手动改** | 不导出；截 2–3 帧核对大字位置 / 字幕 / 美颜 | ✅ 用户 |
| 10 | 导出（用户说了才做） | `export_draft.py <草稿名> "YYYY-MM-DD 标题" --covers 横版 竖版`（见铁律 2） | 用户发布 |
| 6′ | （可选）**拍过程**：剪映里实时剪 + 光效层 | `live_run.py job.json`（适合 1–3 分钟的短片；长片会慢、会卡，见 CHANGELOG v1.2） | 可用相机拍下全过程 |

情绪 → 颜色 → 入场（`style.json` keyword.moods）：`bait` 钱 / 好奇 → `FFE600` 黄 → 打字机I · `warn` 警告 / 硬观点 → `FF287F` 玫红 → 放大 · `us` 我方观点 → `2BE36B` 绿 → 向上弹入。第二行永远白色。

位置单位：剪映界面 **2 个单位 = 1 像素**（4K 画布），X=Y=0 为中心；草稿文件里 = 半个画布（`transform_x = X / 3840`，`transform_y = Y / 2160`）。默认大字字号 13，两行贴紧，贴外侧边（边距 1.6% W、顶 1.7% H）。

剪映界面是怎么被操控的（OCR 点击、逐帧定位、安全填数、每个已知故障和修法）：**`references/live-edit-internals.md`**——改界面相关的 `scripts/` 前必读。

## 迭代流程（像 iOS 一样发版）
1. 先快照：把整个 skill 目录复制到 `skill-workspaces/xy-jianying-workspace/iteration-N/`。
2. 改；在本文件标题和 `CHANGELOG.md` 里升版本（改了什么 · 为什么 · 怎么验证的）。
3. 跑 `evals/evals.json`（行为变了就新旧对比），结果放 `iteration-N/`。
4. 待办做完就移进发版说明；用户的新意见写进待办或直接变成规则（写进代码，不做一次性修补）。
5. 同步到维护者的镜像目录（`config.json` → `mirror_dir`，小爷的是他 Obsidian 里的副本），镜像是给其他 Agent 的权威版本。
6. 打包：`python -m scripts.package_skill <skill目录> <输出目录>`（Anthropic 官方 skill-creator 脚本）→ `xy-jianying.skill`。

## 目录
`SKILL.md` · `README.md` · `LICENSE` · `VERSION` · `CHANGELOG.md` · `config.example.json` · `style.json` · `install.ps1`（Windows）· `install.sh` + `run.sh`（Mac / Linux）· `MAC-TEST.md` · `requirements.txt` ·
`agents/openai.yaml` · `scripts/`（**v1.2 主路线**：`cut_points.py` `listen_back.py` `retx.py` `asr.py` `subs_from_cut.py` `build_full.py` `beauty_all.py` `export_draft.py`；导演层：`transcribe.py` `script_director.py` `visual_director.py` `render_edl.py` `cover_frames.py` `cover_render.py`；界面层：`steps.py` `panel.py` `timeline.py` `jy_ui.py` `osctl.py` `live_run.py` `overlay/`；`platform_env.py` `doctor.py` `tests/`）·
`references/`（house-style、environment、script-director、process-demo-director、live-edit-internals）· `assets/` · `evals/evals.json`
