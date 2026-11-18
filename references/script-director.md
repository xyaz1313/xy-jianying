# 脚本导演 · Script Director (talking-head videos)

The agent's job description for stage ② of the owner's editing pipeline. Input: the raw clips + their
transcripts. Output: a **script plan the owner can approve**, plus a rendered preview. Nothing is executed in
剪映 before the owner says yes.

## 0. Prepare the dossier
```
python tools/script_director.py <out_dir> <clip1.mp4> <clip1_tx.json> [<clip2.mp4> <clip2_tx.json> ...]
```
Produces `dossier.md` (every phrase with clip/time/duration, a contact sheet per clip, pause stats, repeated
phrases flagged) — read it fully before deciding anything.

## 1. Understand the piece (write it down)
- **One-sentence point** of the video (what the viewer should believe / do afterwards)
- **Order of clips** (opening / evidence / verdict…) and why
- **Emotion map**: where the speaker is angriest, funniest, most authoritative

## 2. The first 3 seconds — the hook
Pick 2–3 candidate hooks **from what was actually said** (never invent words). Rank by:
1. **Conflict or contradiction** in the first sentence ("你自己能月入十万，还拿出来卖？")
2. **Stakes for the viewer** ("所有做 AI 创业的兄弟们")
3. **Authority** ("我们就是干私域的")
4. Concrete numbers / money / loss
Reject: greetings, "这是一条…的视频", context-setting, anything that needs a previous sentence to make sense.
The hook may be **moved from the middle or the end** of the footage. If it is moved, remove its original
occurrence so it never plays twice.

## 3. Second 2 — don't let them swipe
- The first frame must already show the speaker mid-sentence or the evidence (no breath, no blank)
- A big keyword (仓耳榜黑) lands within the first 1.5 s

## 4. Second 5 — make them stay
- By ~5 s the viewer must know **what is at stake for them** and that **proof is coming** ("我给你们看原视频")
- Cut every generic sentence before the evidence (e.g. "不管你是重度用户还是轻度用户")

## 5. Whole-video retention
- Delete **repeats** (same claim twice) — keep the stronger delivery
- Evidence segments: keep only the 2–3 most damning lines of any third-party audio
- Put a **punchline / reversal** right before the verdict
- End on a short, clear verdict / warning; no long outro
- Target length: as short as the argument allows (this kind of piece: 60–90 s)

## 6. Deliver to the owner
Write into the content note (vault: `01 Content Creation/05 Content/<date> <title>.md`, section *Script director*):
- the one-sentence point, the 2–3 hook options with why, the recommended structure as a table
  (part · source clip · source time · line), what was cut and why, new length vs old length
- render previews with `tools/render_edl.py` (full recommended cut + one 15 s preview per hook option)
- **ask the owner to choose a hook and approve**. Only then hand the EDL to the 画面导演 / 视觉导演.

## EDL format (consumed by render_edl.py and, next, by the live run)
```json
{"files": [...], "speed": 1.1, "volume_db": 6,
 "pauses": {"2": [[a,b], ...]},            // pause/breath ranges to drop inside kept ranges (per clip)
 "edl": [{"clip": 3, "a": 9.84, "b": 19.22, "part": "HOOK", "note": "line"}, ...]}
```
