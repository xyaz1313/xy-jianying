# CHANGELOG — xy-jianying（原 jianying-live-fx）

Each iteration: what changed, why (owner feedback / failure seen), how it was verified. Newest first.
Backlog at the bottom. Any agent working on this skill appends here.

## v1.1.1 — 2026-11-19 · Mac 实测后：一套代码不写死坐标 + 改数值读回核对 + 一条命令验收
**Why** — the owner's Mac test (MacBook Air, macOS 27.2, 剪映 11.8, run by 豆包 for ~12 h): install / doctor / draft /
live smoke passed, but every "type a value" action failed and many regions missed: the live layer had Windows-150 %
pixel bands and a teal-highlight focus check baked in. 豆包's own patches swapped in Mac numbers and loosened checks
(skip on failure, 6-frame tolerance) — kept its findings, not those patches.
**What**
- `panel.py` — no fixed coordinates: `S(v)` scales every offset measured on Windows 150 % to this screen, `Y(v)` moves a
  window-relative y to this window, `topband()` = the 素材 / 文本 / 滤镜 icon row found by OCR, `tab_rows()` finds the
  property panel's tab rows by OCR (no 90 / 220 px bands), `label_column()` widened for Mac.
- `panel.type_value()` — the one way to enter a value: click / double-click / defocus+click; Windows still types only
  when the box shows its teal focus (unchanged behaviour), Mac selects all (⌘A) and types; **every value is read back**
  (number rows, Hex box, text content, position X/Y, custom vocabulary) and a mismatch stops the run.
- `steps.py` — all regions via S()/Y()/topband(); `pick_font` defocuses first, checks the list really opened, uses
  收藏 then the list's search box, still stops if the font is missing; beauty preset name from `config.json`
  `beauty_preset` (Mac has no 「我的预设1」 until the owner saves one) with a clear stop; `stroke_width` opens a collapsed
  描边 section; subtitle clip picking tries the nearest 5 hits; `add_default_text_at` reuses an existing 「默认文本」
  (re-runs added duplicates); `open_draft` retries on a 2x-upscaled screenshot (black-cover cards); Mac `in_editor`
  looks for editor-only words, Mac `go_home` falls back to ⌘W; filter purple test excludes magenta.
- `timeline.py` — `layout()` calibrates itself; ruler fit self-check (0 s must lie in the timeline); `seek(0)` = Home +
  read-back (the filter landed late on Mac); still frame-exact (no loosened tolerance).
- `osctl.py` (from the Mac test) — ignore 剪映 helper / tray processes; prefer on-screen windows; activate via
  NSRunningApplication (follows full-screen Spaces); refuse a 剪映 window on a secondary display; clamp clicks to the
  main display; Mac key events 60 ms apart (repeated arrows were swallowed). `overlay.py` — joins all Spaces only on a
  single display (multi-display drew one copy per screen). `platform_env` — Mac prefers Homebrew `ffmpeg-full`
  (plain ffmpeg lacks drawtext). `install.sh` — `${VAR}` before Chinese text (bash 3.2 "unbound variable"), installs
  ffmpeg-full; `run.sh` — `tests/x.py` resolves under scripts/. `doctor` — 输入监控 is required for ⌃⌥F12.
- **`style.json` (new)** — owner: the skill is open source, every value we tuned must be in the package so users can
  change it and 豆包 knows what to check. All style values in one commented file: rhythm (1.10x, pauses ≥0.35 s keep
  0.12 s, +6 dB), beauty preset + its values + the read-back check (磨皮 23), filter 高清增强 34, subtitles (hotwords,
  新青年体 6, preset 2, white, stroke 70), keyword (仓耳榜黑 13 / 14, stroke 90, mood colours + entrance animations, default
  position), BGM (22 22, -6.3 dB, no fade), cover layout, export. `scripts/style.py` loads it (built-in defaults if it is
  missing / broken; legacy config.json font / preset keys still override); steps / live_run / visual_director / director /
  cover_render / script_director read it; doctor checks it; the acceptance test prints and saves the values it used.
- **Main screen only (owner, 2026-11-19 — he works on a vertical extended screen next to the main one):** the first
  Windows acceptance run found 剪映 on the extended screen (x = −1956) and stopped at step 1 ("home page black": the
  all-screens screenshot's origin moved, every crop was off). Now `jy_ui.win()` moves 剪映 onto the main screen first
  (Windows SetWindowPos, Mac maximise onto the main display — Finder's desktop bounds spanned all screens),
  screenshots are main-screen only, every click / drag / move off the main screen raises (Mac no longer clamps),
  and the overlay hides itself when 剪映 is not on the main screen.
- `scripts/tests/acceptance.py` — ONE command runs all 11 live actions on its own draft 「XY验收」, reads each back,
  records ✓/✗ with a screenshot and a full-window OCR dump per failure, zips the result to the Desktop.
- `MAC-TEST.md` rewritten: 豆包 runs 3 commands and must not edit any file.
- Found by the Windows acceptance runs (2026-11-19): **filter** — the owner's video has purple lights; scattered purple
  pixels in the main track's thumbnails were taken for a filter clip, so no filter was added and the MAIN clip was
  dragged (then undone). `_purple_row` now looks only above the main track and needs a solid purple run; a filter that
  already spans 0 s → end is not dragged again (grabbing a long clip's middle moves it) and is selected before setting
  强度; a no-op drag is never undone (that undid ADDING the filter). **Beauty** — reading 磨皮 first scrolled the panel
  so 「美颜预设」 was out of view: scroll to the top before opening the presets.
**Verified** — Windows (RTX, 4K 150 %, extended vertical screen attached): `tests/acceptance.py` on 「XY验收」 with the
owner's 14 s talking-head clip: **11 / 11 ✓** (4.4 min): open · overlay · geometry · seek 150 · split+undo · beauty
「我的预设1」 (磨皮 23 read back) · filter 高清增强 0→14.1 s + 34 · auto subtitles + 新青年体 / 6 / white / stroke 70 · keyword
(add, replace text, 仓耳榜黑, 13, FFE600, X/Y, stroke 90, 打字机I) · clone (white) · home. Mac: pending owner run.

## v1.1.0 — 2026-11-18 · cross-platform：Windows（有 / 无 N 卡）· macOS（苹果芯片）· Linux（仅导演）
**Why** — owner: many people have no NVIDIA card or use a Mac; the skill must install and run right away everywhere,
light overlay included, and the standard test runner is 豆包 / WorkBuddy (free for most people), not Claude.
**What**
- `scripts/platform_env.py` — one place that picks the backend: OS, GPU (nvidia / apple / amd / intel / cpu, probed by
  real 0.5 s ffmpeg encodes, cached in `.cache/backend.json`), `FF` (PATH / WinGet / Homebrew), `hwaccel()`, `venc(q)`
  (NVENC / VideoToolbox / AMF / QSV / x264), `whisper_cfg()` (CUDA fp16 / mlx Metal / CPU int8 + large-v3-turbo),
  `ocr_engine()` (CUDA or CPU), system CJK font, 剪映 data / drafts / cloud-font dirs on Win + Mac, `tier()`.
  `XY_BACKEND=cpu|amd|…` forces a path for testing. All 10 render scripts and transcribe.py use it — no more
  hard-coded cuda / nvenc / C:\Windows\Fonts / WinGet paths.
- `scripts/osctl.py` — same small API (Click, DragDrop, SendKeys, Wheel, clipboard, WindowControl, maximise…) on
  Windows (uiautomation) and macOS (Quartz events + AppleScript; Retina pixel→point conversion; {Ctrl} → ⌘).
  jy_ui / steps / panel / timeline / overlay use it.
- Mac has no UIA tree → OCR fallbacks: `panel._player_by_ocr` (「播放器…」 title, right-panel tabs, timecode readout),
  in_editor, go_home. Simulated on Windows with UIA disabled: player rect within 11 px of UIA; timeline + ruler identical.
- Overlay on Mac: Qt tool window kept visible (WA_MacAlwaysShowToolWindow), ⌃⌥F12 via pynput, POST /hide /show.
- `scripts/doctor.py` — 体检 + 档位 + real tests (`--full`: encode, decode, drawtext, OCR, spoken-sample
  transcription, overlay start/quit; `--ui`: read-only 剪映 UI probe) → `doctor-report/<time>/report.md`.
- `install.sh` + `run.sh` (Mac / Linux: Homebrew python@3.12 + ffmpeg + git, own `.venv`, draft library pinned
  881edd2, links into agent skill dirs, runs doctor). `install.ps1`: CUDA wheels only with an NVIDIA card, clones the
  draft library, runs doctor. `requirements.txt` with platform markers. `config.example.json` fixed (the
  `"D:\视频成品"` value was invalid JSON) — empty values = per-OS defaults (Mac export root `~/Movies/视频成品`).
- `scripts/tests/overlay_demo.py`, `draft_smoke.py` (test draft 「XY测试」), `live_smoke.py` (open → OCR layout →
  seek → split → undo); `MAC-TEST.md` (owner steps + copy-paste prompt for 豆包 + T1–T7 with pass criteria).
- Overlay cursor name from `XY_AGENT` (豆包 / WorkBuddy …).
**How verified (Windows, this PC)** — doctor `--full` ✓ on NVIDIA (encode 0.8 s, OCR 1.8 s, 2-min speech 4 s) and
with `XY_BACKEND=amd` (real AMD iGPU AMF encode 1.0 s, CPU OCR 0.9 s, CPU whisper turbo 2-min speech 16 s);
doctor `--ui` ✓ on a real draft; overlay safety 3/3; overlay_demo ✓; draft_smoke build ✓; all modules import.
**Not verified yet** — everything Mac (needs the owner's M5 run of MAC-TEST.md); live_smoke on Windows (owner's own
draft was open); Linux.

## v1.0.0 — 2026-11-18 · first release as **xy-jianying**（剪映自动剪辑）｜小爷出品
**Why** — the owner decided to publish the editing skill on its own (not inside XYSkill), usable by any agent,
non-commercial, following his XYSkill conventions and the Anthropic Agent Skills standard.
**What**
- Renamed `jianying-live-fx` → **`xy-jianying`**; SKILL.md frontmatter passes the official `quick_validate.py`
  (`name`, `description` ending 「｜小爷出品」, `license`, `compatibility`, XY fields under `metadata`: slug, version,
  displayName, visibility, author 小爷（风物执守）, co_author Claude（Anthropic））; 「开场自报家门」 first line.
- `LICENSE` CC BY-NC 4.0 (Copyright (c) 2026 小爷（风物执守）, co-created with Claude; commercial use needs the
  author's written permission); `VERSION`; `README.md` (上手三步 · 能做什么 · 需要什么 · 怎么装 · 许可);
  `agents/openai.yaml` (Codex); `install.ps1` (checks Python / FFmpeg / NVIDIA, pip deps incl. CUDA 12/13 wheels,
  junctions into ~/.agents, .claude, .codex, .workbuddy, .cursor, .kimi-code skills, creates config.json);
  `requirements.txt`; `config.example.json` + `scripts/config.py` (剪映 path: config → env → running process →
  install dirs; export root; fonts; BGM).
- No personal paths left in code or docs (author's machine paths replaced by config / `%USERPROFILE%`).
- Everything from v0.8 (process-demo mode, sentence-safe cuts, compliance, popups, cover module, export rule) is
  part of this release — see the v0.8 entry below.
- **Emergency hotkey fix**: with 剪映 in the foreground, Ctrl+Alt+F12 did nothing (剪映 swallows the combo — RegisterHotKey
  never fired). The overlay now also installs a low-level keyboard hook (WH_KEYBOARD_LL), which sees the keys before 剪映.
**How verified** — `quick_validate.py` ✓, `package_skill.py` → `xy-jianying.skill`; overlay safety tests 3/3 twice from
the new location **with 剪映 in the foreground** (hotkey 0.3 s); `config.py` finds 剪映 automatically; install.ps1 parses (not executed on the author's machine).

## v0.8 — in progress (new mode: process / demo videos; first job 「Watch AI Edit My Video Live」)
**Why** — owner filmed the whole 15-min live edit (17:11 Pocket 3 recording + 14 s intro) and wants it cut to
~3 min with the full pipeline, logging every bug on the way.
**What so far**
- `references/process-demo-director.md` — the script director's handbook for this video type (hook / speed /
  spoken-line rules).
- `scripts/process_map.py` — 2-s thumbnails (NVDEC), GPU OCR, activity, speech per sample.
- `scripts/process_render.py` — renders a process-demo EDL preview on the GPU: per-segment speed, borrowed audio,
  **sentence-safe cuts** (`snap_cut`: phrase edges + tag words + quietest 20 ms), **「»» 加速 ×N」 on every
  speed-up**, denoise (highpass + afftdn).
- `transcribe.py` — `suspect` flag per phrase (no-speech prob, logprob, known hallucinations such as
  「请不吝点赞 订阅 转发」 and the leaked prompt); `--vad` tried and documented as worse.
**Owner review of preview v1** — 「这才是重点」 lost 「重点」; 「我可以弄很多线，同时…」 cut mid-sentence; speed-ups
must be labelled; audio hiss → all fixed in preview v3 (3:01). 「这个导演还是很有脑子的」.
- `scripts/speech_cuts.py` — the sentence rule as ONE shared module (snap + word-level check CLI) for every
  video type; `process_render.py` uses it. Owner: "以后碰到同样的问题还能不能解决" → rule in code, not a one-off.
  First check of the earlier talking-head cut list (「反诈正式版」, already approved): 18 ✗ / many ⚠ — most are
  deliberate (scammer-clip excerpts, 来来来 repetition) or whisper timing noise; the ⚠ "tight" ones come from the
  0.06 s keep around pauses → backlog.
- Owner approved preview v3 (3:01) on 2026-11-18.
- `scripts/process_visual.py` — visual + layout directors for process demos: keywords from a spec anchored to the
  approved timeline, faces found on the REAL preview frames, step chips 「STEP n · …」 bottom-left, speed badges,
  composited preview with the real font + contact sheet.
- **Owner rule: big text is never centred** → `director.plan_one(..., imgs)`: no face → the emptier corner, judged by
  `busyness()` (edge density + texture under the text boxes on the real frames). Matched all three of the owner's
  examples (不是特效 → left, 全程自动 → right on the wall, 录完丢进来 → left). Applies to talking heads too
  (`visual_director.py` passes its frame).
- Owner approved the visual plan v2 (2026-11-18 14:50). New house rule: **BGM** 「22 22」 (DiCrow, 剪映 收藏) at
  −6.3 dB (owner: −5.3 still covers the voice), NO fade-out (completion rate), for videos with sped-up / silent stretches; `visual_plan_demo.json` carries a `bgm` block; preview mixed
  (`visual/preview_visual_bgm.mp4`).
- `scripts/build_demo.py` (mode A for process demos): approved timeline + visual plan → new draft. Tracks: Main
  (43 segments, speed fitted per segment, muted) · Voice (19 speech pieces from the DENOISED 48 kHz track, same speed)
  · BGM (-6.3 dB, no fades) · Steps (7 chips) · Speed (24 「»» 加速 ×N」). Speeds in the draft 0.91–23.86x.
  `live_run.py` job key `"builder": "demo"`. First build: 「过程演示正式版」 181.38 s = timeline, all 5 tracks end
  where planned (checked in draft_info.json).
- Handoff fixes from the live run: `steps.open_draft` matches the first 4 chars + most similar card (home cards
  truncate long names); `live_run` step 1 goes home before writing a draft and refuses names > 5 chars (a draft
  written while another draft is open vanished from 剪映's list; window close only hides 剪映 in the tray →
  quit + reopen needed); `add_filter_full` finds the filter clip by colour (`_purple_row`) and is idempotent
  (on a 3-min timeline the 3-s filter clip shows no label).
- **Result**: 「过程演示正式版」 3:01.4, steps 2–7 done (4–7 in one pass, 10:52), 8/8 keywords verified in the 剪映
  player, no face covered, overlay closed every time. No export.
- **Owner review of the finished draft**: 「免费送你」 = 导流 → CTA changed live to 「自动剪辑 / 横版Skill」
  (right-aligned again); the 7 STEP chips deleted live (engineering labels). Rules made permanent:
  `scripts/compliance.py` (banned 导流 words; visual directors refuse such big text; spoken lines listed for the
  owner — this video: 6:28 「这个skill可以送给你们」), `build_demo.py` / `process_visual.py` write no STEP chips
  unless `--labels`. One-off fix script kept in the job folder (`fix_final_v1.py`); lesson: never SW_RESTORE a
  maximised 剪映 window (it shrinks and gets covered) — use SW_MAXIMIZE.
- 「演示终版」 (v4 cut, 2:55.8) built + live-edited. New hardening on the way: `steps.jianying_running` /
  `start_jianying` (a running 剪映 never lists drafts written while it runs → quit before handoff, script starts it);
  `popups.py` (startup promo dialogs: never click the CTA, click the computed 「×」); `_purple_row` needs real red
  (BGM blue was taken for the filter); `add_filter_full` grabs 1–2 px OUTSIDE the edge, checks both ends, undoes and
  retries (`timeline.undo` falls back to Ctrl+Z without UIA), moves a stray filter clip back to 0 s first;
  `scroll_tracks_top`. Overlay emergency hotkey moved to **Ctrl+Alt+F12** (Ctrl+Alt+Q is 剪映's 返回草稿页);
  overlay safety tests 3/3 again.
- Owner: spoken 导流 hook stays in the AUDIO, its subtitle goes, big text never says it → `steps.hide_banned_subtitles`
  + live_run step 5 (demo builder: windows from tx + timeline); applied to 「过程演示正式版」 (now the final cut).
- Cover module started (v0.9 draft): `cover_frames.py` (score + pick frames, owner chooses), `cover_render.py`
  (owner style: 16:9 with text in the central 4:3, 3:4 two stacked frames with the text across the seam).
**Open on this run** — traditional→simplified for whisper text (opencc install needs the owner's OK); live_run
event log with timestamps (bug: step numbers unreadable by OCR on filmed screens); visual + layout directors and the
剪映 build for this mode.

## v0.7 — 2026-11-18 (owner style for big text: bigger, two lines touching, edge-aligned)
**Why** — owner reviewed 「彩排五号」: "已经非常完美了", only the big text is too small; the two lines must always
touch. Owner hand-tuned keyword 0:09 as the reference: red 字号 8 · 缩放 160% · X 2186 · Y 1761, white 字号 8 ·
缩放 157% · X 2331 · Y 1125 (both right-aligned to one edge ≈ 61 px from the right, lines touching).
**What**
- `director.py` layout rewritten: default **字号 13** (= 8 × 160 %, 缩放 stays 100 %), screen footage 14; line pitch
  = line box = 0.01165 H per 字号 (lines touch); each line aligned to the OUTER edge (margin 1.6 % W, top 1.7 % H) →
  the plan now has `x_white` (own X per line); latin letters count 0.7 char. Fallback order when a face would be
  covered: other side → step down (0.12 / 0.24 H) → shrink 1 字号 at a time (min 9).
- Face boxes reduced to the face core (12 % in from the sides, 15 % down from the top; pad 0.012) — Haar boxes
  include hair/ears, which is why v0.6 shrank to 字号 8–10 where the owner's own layout fits fine.
- `live_run.py` step 6 uses `x_white`; `steps.KW` size 14 → 13.
- `visual_director.py` preview: label strip moved above the frame (it hid the top line); font fitted to the line
  width, so the preview shows the real size.
**How verified** — `plan_one` on the reference pair gives X 2157 / 2273, Y 1756 / 1103 at 字号 13 (owner: 2186 / 2331,
1761 / 1125 at 12.8 / 12.6). Re-ran on 「彩排五号」's spec → 11 keywords: 9 at 字号 13–14, two at 12, none over a face
(`Attachments/2026-11-18 Anti-Scam visual plan v07.jpg`). **Filmed run 2026-11-18 11:14–11:29** (`job_film.json`, new draft 「反诈正式版」): all 7 steps in ONE uninterrupted
run (15:02, no pause, no resume), total 1:25.63 kept; 11/11 keywords placed. `verify_draft.py` frames from 剪映's
own player: every keyword at 字号 13/14, two lines touching, edge-aligned, none over a face, nothing off-frame
(`Attachments/2026-11-18 Anti-Scam film v07 frames.jpg`). No export.
**Overlay black-screen lock (owner, after the filmed run)** — "每一次剪辑完之后都会这样": a black always-on-top
  window with 「AI EDIT // 07 完成」 covered everything and nothing reacted; owner had to hard-reboot after every run.
  Cause: the overlay was never stopped after the run; it re-raised itself every second, turned opaque black, and fell
  back to covering the whole screen when 剪映 was not found; being click-through, clicks went to hidden windows.
  Fix: `live_run.py` `finally:` closes it (DONE after a 9 s banner, pause/error after 30 s); `overlay.py` quits when its
  `--parent` PID exits (`jy_ui.overlay_start` / `ensure_overlay` pass it), after 15 min idle, or when 剪映 is gone /
  minimised for 3 s (no fullscreen fallback); global emergency hotkey **Ctrl+Alt+Q** (fallback Ctrl+Alt+F12).
  Verified (`scripts/tests/test_overlay_safety.py`): parent exit → gone in 0.5 s; Ctrl+Alt+Q → 0.3 s; POST /quit →
  0.3 s. The 剪映-minimised rule is not tested yet (剪映 was in use).
- `verify_draft.py`: creates its frames dir; label strip moved above the frame (it hid the top keyword line on the
  contact sheet and looked like the text was cut off — the raw frames were fine).

## v0.6 — 2026-11-18 (unattended 04:00 run: plan wired in, positions calibrated, rehearsal 「彩排五号」)
**What**
- `live_run.py` **EDL mode**: job `{edl, tx, visual_plan, draft, screen_clips, orig}` → step 1 runs
  `build_from_edl.py` (hook-first reorder, pauses removed, 1.1x, +6 dB from the EDL); step 2 shows every seam
  (气口 / 删段 / 换序 / 钩子提前) with transcript-fixed labels (思域→私域, 老饭→牢饭, 蠢扯→纯扯, 早餐→在这,
  他妈→××); beauty on every segment whose clip is not in `screen_clips`; step 6 places each keyword with its OWN
  colour / X / Y / 字号 / entrance animation from `visual_plan.json` (font 仓耳榜黑 + preset 2 + stroke 90 set on
  the first one and inherited). Total-length check after open, filter, subtitles and keywords. New `--skip 3,4,5`,
  job keys `kw_from` / `beauty_from` for resuming inside a step.
- **Calibrated** 剪映 position units (draft 「校准一号」, difference-image method, text deselected):
  UX 0.414→**0.508**, UY 0.52→**0.501**, CHAR_W 0.072→**0.0823**, LINE_H 0.11→**0.190** (`director.py`).
  ≈ 2 units per 4K pixel. Re-ran `visual_director.py` → `Attachments/anti-scam-job/v06/visual_plan.json`.
- **Geometry without UIA**: after a 剪映 restart only the player window is in the UIA tree → `panel.geom()`
  derives property panel / material panel / timeline from it + OCR; all absolute coordinates replaced by
  `panel.P()` / `panel.M()` offsets; `in_editor()` falls back to OCR 「导出」.
- **Overlay**: home page + overlay = black screen, and hide/show makes the QWebEngine overlay OPAQUE BLACK →
  `open_draft` stops the overlay process before the home page and starts a fresh one in the editor; `grab()`
  restarts the overlay whenever the screen is black; overlay windows found by PID (hidden windows are invisible to
  UIA) and filtered to the layered click-through one (never show its helper windows).
- **Colour fix**: OCR glued 「Hex FFFFFF」 / missed the white value → colour was typed into the opacity box and
  every keyword stayed white (also true in v0.3!). Now: Hex box by regex or the gap before 「100%」, then the
  swatch pixels are read back (retry once, else Pause).
- **Animation fix**: 「打字机I」 is OCR'd as 「打字机！」 → normalised name match (`set_anim`).
- Home-page draft search limited to 剪映's window (another window showed 「彩排五号」 too); ORT plugin-EP
  warning silenced (CUDA EP confirmed active, 4K OCR 0.35 s).
- `visual_director.py` preview draws text at the calibrated size; keyword start clamped to `total − 3 s` (a 3 s
  剪映 text clip past the video end made the timeline 0.29 s longer — caught by the new length check).
- **Entrance animations were never applied** (v0.3–v0.5 too): the first click on a not-yet-downloaded card only
  downloads it. `set_anim` now clicks → waits → clicks the download arrow → waits, and verifies the card's teal
  border (else Pause). All 18 keyword clips of 「彩排五号」 re-applied and verified.
- **Subtitles**: custom vocabulary is now a 「管理」 popup; tags are OCR'd on a 2× upscale (牢饭 was read as 车证);
  a missing word is typed ONLY after the input shows a teal focus border (v0.5 pasted + Enter blindly);
  「智能文本」 is a toggle group (clicked only when 「智能字幕」 is hidden); material panel bottom +110 px
  (「开始识别」 sits below the player rect).
- New tools: `scripts/calibrate_positions.py`, `scripts/verify_draft.py` (frames at every keyword + contact
  sheet), `scripts/keyword_anim_check.py` (apply + verify every entrance animation).
- Final constants: UX **0.500** (exactly 2 units/px; the first fit 0.508 had a 1.6 % video-rect bias), UY 0.501,
  CHAR_W 0.081, LINE_H 0.190.

**Why** — owner's backlog: wire visual plan + EDL into the live runner; UX/UY were estimates; full rehearsal.

**How verified** (content note → "Unattended rehearsal v0.6")
- 「校准一号」: before/after frames (`Attachments/2026-11-18 Calibration before.png` / `after.png`).
- 「彩排五号」 rehearsal: all 7 steps reached DONE (resumed with `--from` 3 → 5 → 6 after each fix); total
  2569 frames = 1:25.63 after every step; beauty 11/11 face segments with 磨皮 = 23 read back, none on clip 2;
  filter 高清增强 34 full length; subtitles 一键识别 + 新青年体 white/stroke 70, spelled 私域/纯扯/会销/牢饭;
  18/18 keyword clips read back = plan (字号, X, Y, colour) and 18/18 entrance animations verified; preview
  frames at all 11 keyword times + 5 other points: every keyword inside the frame, none over a face
  (`Attachments/2026-11-18 Rehearsal v06 frames.jpg`). Re-opening the draft from the home page (overlay
  stop/start) tested. No export.
- Evals (`evals/evals.json` eval 1): see `iteration-6/eval_results.md` in the skill workspace.

## v0.5 — 2026-11-18 (restructured to the official Agent Skills standard)
- Owner supplied Anthropic's `skills-main` repo (spec at agentskills.io; `skill-creator` authoring guide) and
  asked that this skill follow it.
- Layout now `SKILL.md` + `scripts/` (was `tools/`, `overlay/`, `tests/`) + `references/` + `assets/` + `evals/`.
- SKILL.md rewritten: "pushy" description with trigger phrases (剪口播 / 去气口 / 加大字 / 光效…), <500 lines,
  hard rules + pipeline only; details moved to `references/live-edit-internals.md`,
  `references/script-director.md`, `references/house-style.md`, `references/environment.md` (progressive
  disclosure).
- Iteration loop formalised (snapshot → change → evals → changelog → vault sync); first snapshot kept at
  `~/.claude/skill-workspaces/jianying-live-fx-workspace/iteration-4/skill-snapshot/`.
- `evals/evals.json`: regression case "anti-scam-three-clips" with 10 assertions.
- Verified: every script still imports from its new location; overlay path updated in `live_run.py`.

## v0.4 — 2026-11-18 (first real video: 反诈「送产品月入十万」)
- **Script director**: dossier tool (`script_director.py`), handbook (`SCRIPT_DIRECTOR.md`), EDL preview
  renderer (`render_edl.py`). Owner picked hook A (真人怼镜头); cut 1:49 → 1:25; preview re-transcribed to
  check every seam.
- **Visual director** (`visual_director.py`): keyword times from word timestamps through the EDL; colours by mood
  (yellow / pink-red / green); entrance animation by mood (打字机I / 放大 / 向上弹入).
- **Layout director** (`director.py`): face detection on 6 frames per keyword; corners away from the face,
  beside-face fallback, shrink to 60%; person clips with no detected face are treated as "person present"
  (assume centred face). Previews render with the real 仓耳榜黑 from 剪映's cache.
- **EDL → draft** (`build_from_edl.py`): reorder supported; seams classified (气口 / 删段 / 换序 / 钩子提前).
- **GPU**: OCR moved to the RTX 5070 Ti (onnxruntime-gpu 1.32 + CUDA 13 wheels): 0.39 → 0.13 s per frame,
  4K full screen 2–3 s → 0.55 s. `gpu_env.py` registers CUDA 12 + 13 DLL dirs.
- Owner rules added: never export (leave in draft box); big text never covers faces; font always 仓耳榜黑.

## v0.3 — 2026-11-18 (full rehearsal 彩排三号, passed after fixes)
- `live_run.py` 7 steps with pause/resume (`--from N`), state file.
- Fixes: UIA COMError retry; short unique draft names (home page truncates); beauty needs playhead inside the
  segment (face detection on playhead frame) + read-back check; filter drag grabbed mid-clip and moved it →
  right-most purple pixel + verify edge = end; subtitle row selected by OCR; resume steps re-calibrate;
  seek at t≈0 (ruler left edge ignores clicks) → click 0.5 s then frame-step, raise if not exact.

## v0.2 — 2026-11-17 (mode-B building blocks)
- OCR-driven clicking, frame-exact seek, verified number entry (teal highlight), filter / volume / subtitles
  (文稿匹配 tried, then replaced by owner's 一键识别 + custom vocabulary), keyword text styling.
- Safety: every timeline removal checks total-length delta; mismatch → undo + stop.

## v0.1 — 2026-11-17
- Transparent click-through overlay over 剪映 (PySide6 + QWebEngine), light trails / cursors / labels.
- Mode A draft generation (bypasses H.264 re-encode; 剪映 reads HEVC).

## Backlog (next iterations)
- [ ] Talking-head builder: run `speech_cuts.snap_cut` on EDL ends and pause edges (now keep 0.06 s each side → tails can be clipped); re-check 「反诈正式版」's 18 ✗ points with the owner by ear
- [x] ~~Wire `visual_plan.json` + EDL layout into `live_run.py`; calibrate position units~~ → v0.6
- [x] ~~Full rehearsal~~ → v0.6 「彩排五号」
- [ ] Owner's filmed run: `python scripts/live_run.py Attachments/anti-scam-job/v06/job_film.json` (draft 「反诈正式版」)
- [ ] One uninterrupted end-to-end run of the v0.6 code (the rehearsal needed 3 resumes while fixing; each fixed
      path was re-tested on its own, but not all in one pass)
- [ ] Read back animation + colour inside `live_run` step 6 for every clone (now: colour read back, animation
      verified by teal border; position read-back only in the audit tool)
- [ ] Subtitle fix-ups after 一键识别: e.g. 「AI在创业」 → 「AI创业」 (not in the custom vocabulary)
- [ ] Overlay: find why QWebEngine loses transparency after hide/show; until then never hide it — restart it
- [ ] Mode-B live cutting: zoom timeline ×4, horizontal scroll handling, selection-box pixel check
- [ ] Layout director: know "screen clips" without config; better face detector on GPU (YuNet / SCRFD ONNX)
- [ ] Visual director: line length / font size budget from the face box; more animation variety
- [ ] Cover (封面) module — owner: next session
- [ ] 剪映 froze once during review: reduce load (fewer tracks?) and detect a hung window
