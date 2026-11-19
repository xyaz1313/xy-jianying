# 风物执守 · xy-jianying 剪映自动剪辑

> AI 在**剪映专业版**里真的动手剪：横版 16:9 口播、过程演示类视频，从去气口、钩子、大字、字幕、美颜滤镜、BGM 到封面，
> 每一步先出样片给你确认，剪完**留在剪映草稿箱**——你看过、改过、说「导出」才导出。

![Version](https://img.shields.io/badge/version-1.1.0-2e6b4f.svg?style=flat-square)
![Platforms](https://img.shields.io/badge/Windows%20%7C%20macOS%20%7C%20Linux-supported-4a90d9.svg?style=flat-square)
![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-c6ff00.svg?style=flat-square)

**支持：Claude Code、Codex、豆包、WorkBuddy、Kimi Code，以及其他能在本机执行命令的 Agent。**
小爷出品 · 与 Claude（Anthropic）共同制作。

## 上手三步

1. 装好（见下方「怎么装」），把素材丢进一个文件夹（小爷习惯用桌面「视频临时文件」）。
2. 在 Agent 里直接说：

```text
/xy-jianying 帮我把「视频临时文件」里这条横版口播剪了。
```

3. 按它的节奏确认三次：去气口样片 → 脚本和钩子（三个钩子各一段 15 秒样片）→ 大字 / 位置 / BGM 预览。确认后它进剪映剪，屏幕上有光效层显示每个真实操作，可以拍下来当素材。剪完你去剪映草稿箱检查、手动改，再说「导出」。

## 能做什么

| 环节 | 它会做 |
| --- | --- |
| 转写 | whisper 逐字时间戳（N 卡 / 苹果芯片自动加速，没有就用 CPU）；自动标出"幻听"出来的可疑句 |
| 去气口 / 隐私 | 0.35 秒以上的停顿去掉；第三方姓名、电话、聊天列表打码，脏话消音 |
| 脚本导演 | 3 秒钩子、2 秒防跳出、5 秒完播；三个钩子各出样片；**话一定讲完才剪**（整句检查） |
| 视觉 / 画面导演 | 大字按情绪配色（黄 / 玫红 / 绿）+ 入场动效；不挡脸、不居中、两行贴紧；**导流词一律拦下** |
| 过程演示 | 十几分钟的操作录屏剪成两三分钟：光影瞬间原速、等待加速并标「»» 加速 ×N」，你的金句保留 |
| 剪映实操 | 生成草稿（逐帧精确、变速、降噪人声、BGM）→ 在剪映里实时加美颜、滤镜、一键字幕、大字 |
| 封面 | 自动挑帧（不露牙、眼睛有神）给你选 → 横版 16:9 + 竖版 3:4，按小爷的排版 |
| 导出 | 只在你说了之后：4K 30fps，视频 + 两张封面放同一个文件夹，剪映的「发布」按钮绝不点 |

## 需要什么

**剪映专业版**（国内版；需自行安装，会员功能如美颜预设按你的账号）+ Python 3.10+（推荐 3.12）+ FFmpeg + 能在本机执行命令的 Agent。
> **v1.1.1 状态（2026-11-19）**：Windows 版稳定——在 Windows 11 + 剪映专业版 11.8 上一条命令验收 11 / 11 通过（打开草稿、定位、切口、美颜、滤镜、一键字幕 + 样式、大字全套、复制大字、回首页）。**Mac 版还在测试中**，测完会另发版本。

装完会自动体检，告诉你这台电脑是哪一档：

| 档位 | 电脑 | 能用什么 |
| --- | --- | --- |
| 满配 | Windows + NVIDIA 显卡 | 全部，最快（RTX 5070 Ti：2 分钟口播 4 秒转完） |
| 标准 | Windows，没有 N 卡（核显 / CPU） | 全部；转写走 CPU（8 核 CPU：2 分钟口播约 16 秒），编码走 AMD / Intel 核显 |
| Mac（**测试中**） | macOS 13+，苹果芯片（M1–M5） | 导演层 + 生成剪映草稿 + 转写（苹果芯片）已在真机跑通；实时操作剪映 + 光效层**还在 Mac 上测试**，暂时以 Windows 版为准 |
| 仅导演 | Linux，或没装剪映 | 转写、去气口、脚本、样片、字幕、封面；剪映那一步跳过（剪映没有 Linux 版） |
- 只做**横版 16:9**（竖版回头再做）

## 怎么装

**Windows**（在 xy-jianying 目录里打开 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**Mac / Linux**（在「终端」里）：

```bash
cd ~/Downloads/xy-jianying && bash install.sh
```

体检随时可以再跑：Windows `python -X utf8 scripts\doctor.py --full`，Mac `bash run.sh doctor.py --full`。

它会：检查 Python / FFmpeg / 显卡（Mac 会用 Homebrew 补装 Python、FFmpeg）→ 装 Python 依赖（Mac 装在自带的 `.venv` 里）→ 下载草稿库 jianying-editor-reliable → 把本 skill 链接到已安装的 Agent 的 skills 目录
（`~/.agents/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/.workbuddy/skills`、`~/.cursor/skills`、`~/.kimi-code/skills`）
→ 生成 `config.json`（剪映路径留空会自动查找；导出根目录默认 Windows `D:\视频成品`、Mac `~/Movies/视频成品`）→ 体检。

**想要自己的剪辑风格？** 改技能根目录的 `style.json`：美颜预设、滤镜和强度、字幕字体 / 字号 / 描边 / 热词、大字字体 / 字号 / 配色 / 入场动效、BGM 音量、封面排版、变速和去气口，全在这一个文件里，每项旁边有中文说明。

Mac 第一次让 AI 操作剪映前：**系统设置 → 隐私与安全性**，给你用来跑 AI 的程序（终端 / 豆包 / WorkBuddy）打开「辅助功能」和「屏幕与系统录音」。

豆包 / 悟空等没有本地 skills 目录约定的客户端：在客户端里上传 `xy-jianying.skill`（就是 zip）或 `SKILL.md` 所在目录。

## 安全与规矩

- 光效层万一盖住屏幕：**Ctrl+Alt+F12**（Mac：⌃⌥F12，或 ⌘⌥Esc 强制退出 Python）立刻关掉，不用重启。
- 它不会替你发布、不会登录任何账号、不会点任何付费或推广按钮。
- 素材、逐字稿、方案都只在你自己的电脑上。

## 许可

CC BY-NC 4.0 —— 可以免费使用、修改、分享，须署名「小爷（风物执守）· xy-jianying」；**不得商用**（含售卖、付费课程 / 社群 / 代剪服务的组成部分）。商业授权请联系作者。
详见 [LICENSE](LICENSE)。小爷的其他商业与私域 Skill：[风物执守 · XY 操盘系统](https://github.com/xyaz1313/xyskill)。
