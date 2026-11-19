# Live-edit internals (mode B) — how 剪映 11.8 is driven

Read this before changing anything in `scripts/steps.py`, `scripts/timeline.py`, `scripts/panel.py`,
`scripts/jy_ui.py` or `scripts/live_run.py`.

## Contents
1. Ground rules
2. Window & timeline
3. Number boxes, colours, fonts
4. Beauty, filter, subtitles, keywords
5. Overlay events
6. Known failure modes (and the fix that is already in the code)
7. Position calibration (v0.6)

## 1. Ground rules
- 剪映 11.8 is QML. Windows uses UIA where available. Mac 11.8 also exposes native Accessibility elements:
  use `panel.native_tabs()` / `_native_tab_hit()` for tabs and controls, `timeline._native_progress()` for exact
  timecodes, and native text-field focus + paste for content. OCR still handles geometry, font results and visual
  read-back; coordinates are physical pixels. Mac screen capture uses Quartz directly.
- Every UIA call goes through `steps.uia_retry` (transient `EVENT_E_NO_SUBSCRIBERS` while pages switch).
- **Never press Esc** (un-maximises the window). Close pickers by clicking an inert label.
- **Never type unless a text box is verified focused** (teal selection highlight in pixels). Keys sent to the
  timeline can select or delete everything.
- After any destructive timeline action, compare total length with the expectation; mismatch → undo + stop.

## 2. Window & timeline
- **Geometry (v0.6)**: after a 剪映 restart UIA may expose ONLY the player window
  (`editPanelLoader.editWin`). `panel.geom()` derives everything from it: property panel = right of the player,
  material panel = from the 「素材」 tab to the player, timeline = under the player's timecode readout.
  Code uses `panel.P(dx)` / `panel.M(dx)` offsets — never absolute screen x values.
- `in_editor()`: UIA `editor.export` if present, else OCR 「导出」 in the window's top-right corner.
- **Home page + overlay = black window**: `open_draft` hides the overlay, restores (not maximises) the window,
  searches the draft name only inside 剪映's rect, then maximises the editor and shows the overlay again.
- `timeline.maximise()` → ShowWindow(SW_MAXIMIZE). `timeline.layout()` finds the timeline container (UIA), the
  ruler band, the player timecode and the main-track row by OCR — call it again after any layout change.
- `calibrate()`: OCR ruler labels `mm:ss` only (rejects 4-part timecodes from clip headers), median slope,
  rejects outliers; raises if fewer than 3 consistent labels.
- `seek(t)`: on Mac, click and correct by measured error, use the closest result when snapping interferes, then
  verified single-frame steps; zero uses a clickable 0.5-s point plus drag/Home fallbacks. Native timecode read-back
  is preferred over OCR. Never report 0 without a successful read-back.
- `split_at(t)`: Ctrl+B splits the **selected** clip → select the main-track clip at t first.

## 3. Number boxes, colours, fonts
- `panel.set_value(label, v)`: find the row by OCR; on Mac use native slider-adjacent number frames when available,
  clear overlay effects before reading, and use 2× OCR for small values. Every click has explicit click state;
  type only after a verified teal selection. Mac commits with select-all + paste + Enter and reads the value back.
- `steps.set_xy(x, y)`: OCR glues "X900"; the X box is the left value, Y the right one.
- `steps.set_color(hex)`: click the MIDDLE of the colour swatch (its right end is a dropdown) → picker → Hex box
  (OCR may glue 「Hex FFFFFF」 into one token or miss the white value: fall back to the gap between 「Hex ⌄」
  and the 「100%」 opacity box — never the opacity box itself) → verify highlight → type → Enter → click an inert
  label → **read the swatch pixels back**, retry once, else Pause.
- `steps.set_anim(name)`: 动画 → 入场 → card whose label equals `name` with I/1/l/|/!/！ normalised
  (「打字机I」 is OCR'd as 「打字机！」). Card centre = label y − 65. A card that is not downloaded only
  DOWNLOADS on the first click: click → wait → click the download arrow (centre + 26, + 26) → wait → verify the
  teal border on THAT card (the 「无」 card carries it when nothing is applied). Never trust a click alone.
- `steps.pick_font(name)`: 字体 dropdown → 收藏 → click the name → verify the row now shows it.

## 4. Beauty, filter, subtitles, keywords
- **Beauty**: `seek` INTO the segment (face detection uses the playhead frame), select it → 画面 → 美颜美体 →
  美颜预设 → 「我的预设1」 → back to 美颜 → verify 磨皮 = 23 (retry ×3). Screen clips get no beauty.
- **Filter**: seek 0 → 滤镜 → 收藏 → hover 高清增强 → "+" → find the new purple clip's right-most pixel on its
  row → drag that edge to `x_of(end)` → verify edge ≈ end and total length unchanged → 强度 34.
- **Subtitles** (v0.6 UI: 「自定义词汇识别 · 管理」 opens a popup with tags + an input line): 「智能文本」 is a
  toggle group — click it only if 「智能字幕」 is hidden; read the tags on a 2× upscaled crop; type a missing word
  only after the input shows a teal focus border, then re-read the tags.
  Flow: 文本 → 智能文本 → 智能字幕 → 自定义词汇 (domain words, e.g. 私域/牢饭/纯扯) → 开始识别 → wait
  until "识别中" disappears → select a subtitle on the subtitle row (OCR, never the filter row) → 新青年体,
  字号 6, preset 2, white, stroke 70 ("应用到全部字幕" is on by default).
- **Keywords**: first keyword from 新建文本 → hover 默认文本 → "+" → replace content (double-click, verify
  highlight, paste) → 仓耳榜黑 → 字号 → preset 2 → colour → X/Y → stroke 90 → 动画 → 入场 → animation.
  Following ones: click the template clip (fuzzy OCR on the label: 入→人 happens) → Ctrl+C → seek → Ctrl+V →
  replace content → 字号 → colour → X/Y → 入场动画 (ALL of them on every clone in EDL mode; values from
  `visual_plan.json`).

## 5. Overlay events (HTTP POST 127.0.0.1:8790/event, physical px)
`status{text}` · `stats{text}` · `banner{text, sub, hold}` · `cursor{agent, to}` · `click{at}` ·
`fly{from, to, label, color, agent, box, dur, hold}` · `clear`.

## 6. Known failure modes (fixed — keep the fixes)
| Symptom | Cause | Fix in code |
|---|---|---|
| Ctrl+A selected the whole timeline | typed without a focused box | teal-highlight check before typing |
| Filter moved to the end instead of extended | grabbed mid-clip (icon breaks the purple run) | right-most purple pixel + verify |
| Beauty preset "当前画面暂未识别到人脸" | playhead outside the segment | seek into the segment first |
| First keyword landed at 70 s | ruler click at t≈0 ignored, 10 s arrow cap | click ≥0.5 s, uncapped stepping, raise |
| Subtitle style applied to filter | clicked a fixed y offset | OCR the subtitle row |
| Wrong draft opened | home page truncates long names | short, unique draft names |
| 2 s removal deleted 16 s | ruler calibration polluted by clip timecodes | strict mm:ss + outlier rejection + length check |
| Draft not found / editor not detected after restart | UIA tree reduced to the player window | `panel.geom()` + OCR fallbacks |
| Screen all black on the home page | overlay window + maximised home page | hide overlay on home, restore window |
| Keyword colour stayed white | colour typed into the opacity box | Hex-box fallback + swatch read-back |
| 「打字机I」 not found | OCR reads I as ！ | normalised name match |
| Corner keywords ran off the frame | UX/UY were estimates | calibrated constants (§7) |
| Entrance animation silently missing | first click only downloads the card | download + click + teal-border check |
| Timeline 0.29 s longer after keywords | last 3 s text clip past the video end | clamp t ≤ total − 3 s in visual_director |
| Vocabulary typed blindly | no focus check | 2× OCR of tags; type only into a verified-focused input |
| Contact-sheet frames cropped wrong | pixel-based video-rect detection on dark footage | geometric 16:9 rect in the player |
| After EVERY run the whole screen goes black, nothing reacts to clicks, owner must hard-reboot (v0.7) | nothing ever stopped the overlay after 「07 完成」: it stayed always-on-top, re-raised itself every second, later turned opaque black (QWebEngine) and, with 剪映 missing, fell back to covering the whole primary screen; it is click-through, so clicks went to invisible windows | `live_run.py` `finally:` POST /quit + `overlay_stop()` on DONE / pause / error; overlay quits by itself when its `--parent` PID exits, after 15 min without events, or when 剪映 is gone/minimised for 3 s (no fullscreen fallback); global emergency hotkey **Ctrl+Alt+F12** (fallback Ctrl+Alt+Shift+F12; was Ctrl+Alt+Q until 2026-11-18 — clashed with 剪映 返回草稿页); tested by `scripts/tests/test_overlay_safety.py` |

## 7. Position calibration (v0.6)
On a throwaway draft (e.g. 「校准一号」, one face clip, keyword at a known time): select the keyword, move it
off-canvas (X 9000) for a baseline frame, then for several (X, Y, 字号) set the values, **deselect by clicking the
grey player area above the video** (clicking the empty timeline moves the playhead), grab the player, and take the
bounding box of |frame − baseline| > 90 inside the video rect. Fit px-per-unit for X and Y and ink size per 字号,
write them into `director.py` (UX, UY, CHAR_W, LINE_H), re-run `visual_director.py`, and confirm with a real
preview frame. v0.6 numbers: UX 0.500, UY 0.501, CHAR_W 0.081, LINE_H 0.190 (4K canvas, 仓耳榜黑, stroke 90).
Use the GEOMETRIC video rect (player width × 9/16, centred) — pixel detection lost 13 px on a dark edge and biased
UX by 1.6 %. Tool: `scripts/calibrate_positions.py`; check a finished draft with `scripts/verify_draft.py`.

## 8. Setting the video cover (v0.9 draft, verified 2026-11-18 on 「过程演示正式版」)
1. Timeline header: OCR 「封面」 (left of the main track) → click → dialog 「封面设计」 opens (centred).
2. Frame strip at the bottom of the dialog: the 「+」 left of the strip (≈ dialog-left + 315 px, strip y) imports a local
   image → Windows 「打开」 dialog with the 文件名 box focused → paste the full path (clipboard) → Enter.
3. The preview shows the imported cover → click OCR 「设为封面」 → dialog closes; the timeline 「封面」 thumbnail now
   shows the cover (check it by a crop of the track header).
Cover images come from `scripts/cover_render.py` (16:9 for the draft, 3:4 handed to the owner).
