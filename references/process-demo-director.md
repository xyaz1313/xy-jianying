# 脚本导演 · Process / demo videos (v0.8, first used 2026-11-18)

For footage where the owner films a screen while something works (the AI editing in 剪映, a tool demo…) and only
talks now and then — usually with a short talking-head intro. The talking-head handbook (`script-director.md`)
still applies to the intro and to every spoken line; this file adds what is different.

Worked example: vault note `2026-11-18 Watch AI Edit My Video Live` (17:11 recording + 14 s intro → ~3:00).

## 0. Dossier
1. Transcribe every clip (`transcribe.py`, vad OFF). Lines flagged `suspect` are whisper inventing words over
   silence (「请不吝点赞 订阅…」) — never use them.
2. `python scripts/process_map.py <recording> <tx.json> <out> --every 2` → 2-s thumbnails + activity + OCR.
   Build contact sheets (every 20 s, then every 2 s around candidates) and **look at them**: find where every
   step starts and every visual peak (light trail, keyword slamming in, banner, result playback).
   (Step numbers in a filmed screen are too small for OCR — once `live_run.py` writes its own timed event log,
   align on that instead.)

## 1. Structure
| Part | Rule |
|---|---|
| Hook 0–3 s | the most spectacular picture + the hardest line the owner said, even if from elsewhere (`audio_from`) |
| 2 s | the owner's face appears (intro talking head) |
| 5 s | intro promises "看全过程" → go straight into step 1 |
| Body | the steps in order; a new visual point every 10–15 s |
| End | result banner → result playback under the owner's best "it's done" lines → CTA |

Offer three hooks (A result first · B spectacle + hard line · C plain intro), 15-s preview each; recommend one.

## 2. Speed
- Owner's speech: house speed 1.1x, subtitles.
- Visual peaks (light trails, keywords slamming in, banners): 1–2x.
- Waiting / repetitive checking: 12–24x. Target length ≈ 2:30–3:00 for a 15-min process.
- **Every sped-up part is labelled 「»» 加速 ×N」** (owner, 2026-11-18). Never hide a speed-up.

## 3. Spoken lines (owner rules, 2026-11-18)
- **A sentence is always finished.** Never cut inside a phrase; keep tag words glued to it (对吧 / 啊); cut in the
  quietest spot right after it. `process_render.py` does this automatically (`snap_cut`) when the EDL has `tx`.
  (Preview v1 lost 「重点」 of 「这才是重点」 and cut 「我可以弄很多线，同时就很帅啊」 in half.)
- Pick lines that explain what is on screen or carry the message (真干活 / 不是特效 / 看不出是 AI / 剪完去喝茶);
  drop filler and off-topic chatter.
- Audio is denoised (preview: highpass 80 Hz + afftdn; 剪映: 音频降噪 on every clip).

## 4. Basics still apply
Pause cuts in the intro, 一键识别 subtitles, filter 高清增强 on the whole timeline, beauty only where a face is on
screen (the intro — not the filmed monitor), big text by the visual + layout directors.

## 5. EDL (`edl_demo_*.json`, rendered by `scripts/process_render.py`)
`sources` {key: file} · `tx` {key: [transcript.json, 16k.wav]} · `hooks` {A/B/C: {name, segs}} · `body` [segments]
Segment: `src, a, b` (source seconds) + `speed` (+ `audio: true` to keep its sound) or `audio_from: [src, a, b]`
(picture speed fitted to the borrowed audio), `label`, `step`, optional `skip_with_hook`.
