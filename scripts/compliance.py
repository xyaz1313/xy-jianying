"""Platform compliance for anything that will be SEEN in the video (v0.8, owner rule 2026-11-18).

Douyin / Xiaohongshu / … penalise 导流 (pulling viewers off-platform or "free gift" hooks). The owner caught
「横版Skill / 免费送你」 on the CTA keyword: 「免费送」 must never appear. Big text that hits this list is REFUSED
(the visual director stops). SPOKEN lines that hit it STAY in the audio (owner 2026-11-18: that is the
私域 hook — 「找我拿」), but their SUBTITLES are deleted (`steps.hide_banned_subtitles`, run by live_run step 5).

  python compliance.py "<text>" ["<text>" …]      -> prints hits, exit 1 if any
  from compliance import hits; hits("横版Skill 免费送你") -> ["免费送", "送你"]

Engineering labels (「STEP n · …」, step names, internal notes) are a separate rule: they may show on the live
overlay while editing, never in the delivered draft (build_demo.py writes no step chips by default).
"""
import re
import sys

BANNED = [
    # free-gift / giveaway hooks
    "免费送", "白送", "送你", "送给你", "送给大家", "免费领", "领取", "免费拿", "0元", "零元",
    # moving people off-platform
    "私信", "私我", "加微信", "加我微信", "加V", "加v", "vx", "VX", "微信号", "二维码", "扫码", "进群", "加群",
    "评论区扣", "扣1", "主页领", "看主页", "链接在", "点链接",
]


def hits(text):
    t = re.sub(r"\s+", "", text or "")
    return [w for w in BANNED if w in t]


def check_keywords(keywords):
    """keywords: [{'red':…, 'white':…}] -> list of (text, hits)."""
    out = []
    for k in keywords:
        for line in (k.get("red") or k.get("top"), k.get("white") or k.get("bottom")):
            h = hits(line)
            if h:
                out.append((line, h))
    return out


if __name__ == "__main__":
    bad = [(t, hits(t)) for t in sys.argv[1:] if hits(t)]
    for t, h in bad:
        print(f"✗ 「{t}」 → {h}")
    print("✓ ok" if not bad else f"{len(bad)} line(s) would count as 导流")
    sys.exit(1 if bad else 0)
