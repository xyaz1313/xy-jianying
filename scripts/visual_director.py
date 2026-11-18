"""Visual director: big-keyword plan on an approved EDL cut.

For each keyword spec it finds WHEN the anchor words are spoken (word timestamps → final timeline through the
EDL, pauses and speed), gives it a colour by mood, then hands it to the face-aware layout (director.plan_one)
so the text never covers a face. Renders a preview sheet with the real 仓耳榜黑 font and real colours.

spec.json: {"edl": "edl.json", "tx": {"1": "tx1.json", ...}, "fix": {...},
            "keywords": [{"clip": 3, "anchor": "月入十万", "top": "月入十万？", "bottom": "你拿出来干嘛？",
                          "mood": "bait"}, ...]}
moods: bait (money / lure) = yellow, warn (scam / danger) = pink-red, us (our side / verdict) = green
python visual_director.py <spec.json> <out_dir>
"""
import json
import pathlib
import subprocess
import sys

import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import director  # noqa: E402

COLORS = {"bait": "FFE600", "warn": "FF287F", "us": "2BE36B"}
# entrance animation by mood (names exactly as in 剪映 文本 → 动画 → 入场)
ANIMS = {"bait": "打字机I",      # the lure "types out" like a chat message
         "warn": "放大",        # warnings hit hard
         "us": "向上弹入"}       # our verdict pops up confidently
MOOD_CN = {"bait": "诱饵/钱 → 黄", "warn": "骗局/警告 → 玫红", "us": "我方观点 → 绿"}
DUR = 3.0


def load(p):
    return json.load(open(p, encoding="utf-8"))


def build_map(E):
    """[(clip, src_a, src_b, final_a)] for every kept piece of the EDL (pauses removed)."""
    pauses = {int(k): v for k, v in E.get("pauses", {}).items()}
    sp = E.get("speed", 1.0)

    def minus(clip, a, b):
        rs = [(a, b)]
        for p0, p1 in sorted(pauses.get(clip, [])):
            nx = []
            for r0, r1 in rs:
                if p1 <= r0 or p0 >= r1:
                    nx.append((r0, r1))
                else:
                    if p0 > r0:
                        nx.append((r0, p0))
                    if p1 < r1:
                        nx.append((p1, r1))
            rs = nx
        return [r for r in rs if r[1] - r[0] > 0.05]

    pieces, t = [], 0.0
    for it in E["edl"]:
        for a, b in minus(it["clip"], it["a"], it["b"]):
            pieces.append((it["clip"], a, b, t))
            t += (b - a) / sp
    return pieces, t, sp


def to_final(pieces, sp, clip, s):
    for c, a, b, f in pieces:
        if c == clip and a <= s < b:
            return f + (s - a) / sp
    return None


def to_src(pieces, sp, t):
    for c, a, b, f in pieces:
        if f <= t < f + (b - a) / sp:
            return c, a + (t - f) * sp
    c, a, b, f = pieces[-1]
    return c, b - 0.05


def anchor_time(tx, anchor, fix):
    d = load(tx)
    words = [w for s in d["segments"] for w in s["words"]]
    text, idx = "", []
    for i, w in enumerate(words):
        for ch in w["w"]:
            text += ch
            idx.append(i)
    for k, v in fix.items():           # same-length replacements keep the char→word index valid
        if len(k) == len(v):
            text = text.replace(k, v)
    pos = text.find(anchor)
    if pos < 0:
        return []
    out = []
    while pos >= 0:
        out.append(words[idx[pos]]["s"])
        pos = text.find(anchor, pos + 1)
    return out


def main():
    S = load(sys.argv[1])
    import compliance
    bad = compliance.check_keywords(S.get("keywords", []))
    if bad:                                            # owner rule 2026-11-18: no 导流 words in big text, ever
        raise SystemExit("大字里有导流词（平台会判导流），先改词：" + "; ".join(f"{t} → {h}" for t, h in bad))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    E = load(S["edl"])
    pieces, total, sp = build_map(E)
    plan, tiles = [], []
    kfont = ImageFont.truetype(director.KW_FONT, 38)
    lfont = ImageFont.truetype(director.FONT, 18)
    last_end = -99
    for k in S["keywords"]:
        times = [to_final(pieces, sp, k["clip"], s) for s in anchor_time(S["tx"][str(k["clip"])], k["anchor"], S.get("fix", {}))]
        times = [t for t in times if t is not None]
        if not times:
            print("!! anchor not in the cut:", k["anchor"]); continue
        t = max(times[0] - 0.15, 0.05)
        if t < last_end + 0.3:                      # never overlap two keywords
            t = last_end + 0.3
        # v0.6: a 剪映 text clip is DUR (3 s) long — it must end by the end of the video, or the timeline grows
        t = min(t, round(total - DUR - 0.01, 2))
        last_end = t + DUR
        fb, shown, person = [], None, False
        for dt in (0.0, 0.6, 1.2, 1.8, 2.4, 3.0):
            c, s = to_src(pieces, sp, min(t + dt, total - 0.1))
            img = director.frame_at(E["files"][c - 1], s)
            if img is None:
                continue
            if str(c) not in [str(x) for x in S.get("screen_clips", [])]:
                person = True
                fb += director.faces(img)
            if shown is None or dt == 1.2:
                shown = img
        if person and not fb:
            # a person is on screen but the face was not detected (hand, turn, blur): assume a centred face
            fb = [(0.28, 0.0, 0.72, 0.75)]
        p = director.plan_one(k["top"], k.get("bottom") or "", fb, [shown] if shown is not None else None)
        p.update({"t": round(t, 2), "red": k["top"], "white": k.get("bottom"), "mood": k["mood"],
                  "color": COLORS[k["mood"]], "anim": k.get("anim") or ANIMS[k["mood"]]})
        plan.append(p)
        pil = Image.fromarray(cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)).resize((640, 360))
        d = ImageDraw.Draw(pil)
        for b in fb:
            d.rectangle([b[0] * 640, b[1] * 360, b[2] * 640, b[3] * 360], outline=(0, 255, 255), width=2)
        col = tuple(int(COLORS[k["mood"]][i:i + 2], 16) for i in (0, 2, 4))
        for (x0, y0, x1, y1), txt, cc in zip(p["boxes"], [k["top"], k.get("bottom")], [col, (255, 255, 255)]):
            if txt:
                # v0.6: draw at the CALIBRATED size (ink box height incl. stroke = box height)
                # v0.7: fit the real font to the calibrated line WIDTH (box height = line pitch, lines touch)
                fs = 60
                while fs > 10:
                    kfont = ImageFont.truetype(director.KW_FONT, fs)
                    if kfont.getlength(txt) <= (x1 - x0) * 640:
                        break
                    fs -= 1
                d.text(((x0 + x1) / 2 * 640, (y0 + y1) / 2 * 360), txt, font=kfont, fill=cc, anchor="mm",
                       stroke_width=max(2, fs // 8), stroke_fill=(0, 0, 0))
        # v0.7: label strip ABOVE the frame (it used to cover the top line, which now sits 1.7 % from the top)
        tile = Image.new("RGB", (640, 390), (0, 0, 0))
        tile.paste(pil, (0, 30))
        pil, d = tile, ImageDraw.Draw(tile)
        d.text((8, 5), f"{int(t // 60)}:{t % 60:04.1f}  {MOOD_CN[k['mood']]} · {p['reason']}", font=lfont,
               fill=(255, 80, 80) if p["covers_face"] else (255, 255, 255))
        tiles.append(pil)
    cols = 3
    sheet = Image.new("RGB", (640 * cols, 390 * ((len(tiles) + cols - 1) // cols)), (20, 20, 20))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 640, (i // cols) * 390))
    sheet.save(out / "visual_preview.jpg", quality=90)
    json.dump({"total": total, "keywords": plan}, open(out / "visual_plan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for p in plan:
        print(f"{int(p['t'] // 60)}:{p['t'] % 60:04.1f}  [{p['mood']:4s}] {p['anim']:5s} {p['red']} / {p['white']}  → {p['reason']}")


if __name__ == "__main__":
    main()
