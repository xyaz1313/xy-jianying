# 风物执守 · xy-jianying 剪映自动剪辑

> AI 在**剪映专业版**里真的动手剪：横版 16:9 口播、过程演示类视频，从去气口、钩子、大字、字幕、美颜滤镜、BGM 到封面，
> 每一步先出样片给你确认，剪完**留在剪映草稿箱**——你看过、改过、说「导出」才导出。

![Version](https://img.shields.io/badge/version-1.0.0-2e6b4f.svg?style=flat-square)
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
| 转写 | 显卡跑 whisper large-v3，逐字时间戳；自动标出"幻听"出来的可疑句 |
| 去气口 / 隐私 | 0.35 秒以上的停顿去掉；第三方姓名、电话、聊天列表打码，脏话消音 |
| 脚本导演 | 3 秒钩子、2 秒防跳出、5 秒完播；三个钩子各出样片；**话一定讲完才剪**（整句检查） |
| 视觉 / 画面导演 | 大字按情绪配色（黄 / 玫红 / 绿）+ 入场动效；不挡脸、不居中、两行贴紧；**导流词一律拦下** |
| 过程演示 | 十几分钟的操作录屏剪成两三分钟：光影瞬间原速、等待加速并标「»» 加速 ×N」，你的金句保留 |
| 剪映实操 | 生成草稿（逐帧精确、变速、降噪人声、BGM）→ 在剪映里实时加美颜、滤镜、一键字幕、大字 |
| 封面 | 自动挑帧（不露牙、眼睛有神）给你选 → 横版 16:9 + 竖版 3:4，按小爷的排版 |
| 导出 | 只在你说了之后：4K 30fps，视频 + 两张封面放同一个文件夹，剪映的「发布」按钮绝不点 |

## 需要什么

- Windows 10/11 · **剪映专业版**（国内版，已在 11.8 验证；需自行安装，会员功能如美颜预设按你的账号）
- **NVIDIA 显卡**（已在 RTX 5070 Ti 验证；CUDA 12 + 13 运行库用 pip 装）
- Python 3.12、FFmpeg、Agent 能在本机执行命令
- 只做**横版 16:9**（竖版回头再做）

## 怎么装

```powershell
# 在 xy-jianying 目录里（PowerShell）
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

它会：检查 Python / FFmpeg / 显卡 → 装 Python 依赖 → 把本 skill 链接到已安装的 Agent 的 skills 目录
（`~/.agents/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/.workbuddy/skills`、`~/.cursor/skills`、`~/.kimi-code/skills`）
→ 生成 `config.json`（剪映路径留空会自动查找；导出根目录默认 `D:\视频成品`）。

豆包 / 悟空等没有本地 skills 目录约定的客户端：在客户端里上传 `xy-jianying.skill`（就是 zip）或 `SKILL.md` 所在目录。

## 安全与规矩

- 光效层万一盖住屏幕：**Ctrl+Alt+F12** 立刻关掉，不用重启。
- 它不会替你发布、不会登录任何账号、不会点任何付费或推广按钮。
- 素材、逐字稿、方案都只在你自己的电脑上。

## 许可

CC BY-NC 4.0 —— 可以免费使用、修改、分享，须署名「小爷（风物执守）· xy-jianying」；**不得商用**（含售卖、付费课程 / 社群 / 代剪服务的组成部分）。商业授权请联系作者。
详见 [LICENSE](LICENSE)。小爷的其他商业与私域 Skill：[风物执守 · XY 操盘系统](https://github.com/xyaz1313/xyskill)。
