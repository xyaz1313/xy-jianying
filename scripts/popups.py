"""Close 剪映's home-page popups (ads, tips) after a (re)start — v0.8, 2026-11-18.

剪映 shows a promo dialog on start (e.g. 「AI视频后期剪辑实战教学 … 立即试听」). It blocks the draft cards, Esc does
not close it, and its 「×」 is drawn on the banner image (OCR can't read it). Rule: NEVER click the call-to-action
(立即试听 / 立即开通 / 去看看 …); click a harmless dismiss button if there is one (知道了 / 我知道了 / 关闭 / 取消),
otherwise find the dialog's frame from its CTA button and click the 「×」 in its top-right corner.
"""
import time

import numpy as np

import jy_ui

DISMISS = ("我知道了", "知道了", "关闭", "取消", "暂不", "以后再说", "跳过")
CTA = ("立即试听", "立即开通", "立即续费", "立即体验", "立即领取", "去看看", "立即购买", "免费试用")


def _dialog_box(cta):
    """(right, top) of the dialog around a CTA button. 剪映 centres its dialogs in the window, and the dimmed
    backdrop next to the dialog is near-black, so: right edge = first >=10 px dark run to the right of the CTA,
    bottom edge = first dark run below it, top = mirror of the bottom around the window's centre line.
    (Measured on the 2026-11-18 promo: corner (2380, 673), 「×」 at corner + (-31, +31).)"""
    x, y = int(cta[1]), int(cta[2])
    W = jy_ui.win().BoundingRectangle

    def first_dark(vals, start):
        for i in range(len(vals) - 10):
            if all(v <= 18 for v in vals[i:i + 10]):
                return start + i
        return None
    row = np.asarray(jy_ui.grab((x, y - 2, W.right, y + 2))).astype(int).mean(axis=(0, 2))
    right = first_dark(row, x)
    col = np.asarray(jy_ui.grab((x - 2, y, x + 2, W.bottom))).astype(int).mean(axis=(1, 2))
    bottom = first_dark(col, y)
    if right is None or bottom is None:
        return None
    top = (W.top + W.bottom) - bottom
    return right, top


def close_popups(rounds=3):
    w = jy_ui.win()
    r = w.BoundingRectangle
    closed = []
    for _ in range(rounds):
        ts = jy_ui.texts((r.left, r.top, r.right, r.bottom))
        d = [t for t in ts if t[0].strip() in DISMISS]
        c = [t for t in ts if t[0].strip() in CTA and t[2] > r.top + 200]
        if d:
            jy_ui.click(d[0][1], d[0][2], label="关闭提示")
            closed.append(d[0][0])
        elif c:
            box = _dialog_box(c[0])
            if box is None:
                break
            right, top = box
            jy_ui.click(right - 31, top + 31, label="关闭广告")
            closed.append(f"× of {c[0][0]} at ({right - 31:.0f},{top + 31:.0f})")
        else:
            break
        time.sleep(1.0)
    return closed
