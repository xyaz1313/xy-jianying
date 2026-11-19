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
CTA = ("立即试听", "立即开通", "立即续费", "立即体验", "立即领取", "去看看", "立即购买", "免费试用", "立即升级")   # v1.2.1: 「AI Ultra」 ad


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


def _find_close_x(cta, r):
    """v1.2.1 fallback: the 2026-11-20 「AI Ultra」 dialog has a dark-grey panel (≈28) and NO dimmed backdrop, so
    _dialog_box's «first near-black run» finds nothing. Find the 「×」 itself: in the area up-right of the CTA, the
    compact light-grey blob (≈ 12–50 px square) that lies furthest up and right."""
    import cv2
    x0, y0 = int(cta[1]), int(r.top + 100)
    x1, y1 = int(r.right - 20), int(cta[2] - 200)
    if x1 - x0 < 40 or y1 - y0 < 40:
        return None
    a = np.asarray(jy_ui.grab((x0, y0, x1, y1))).astype(int)
    m = ((a.min(axis=2) > 140) & (a.max(axis=2) - a.min(axis=2) < 40)).astype(np.uint8)      # light grey, not coloured
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if 12 <= w <= 50 and 12 <= h <= 50 and 0.6 < w / h < 1.6 and area < 0.6 * w * h:   # thin strokes, square
            g = (lab[y:y + h, x:x + w] == i)
            k = max(2, min(w, h) // 5)
            corners = all(g[a:b, c:d].any() for a, b, c, d in ((0, k, 0, k), (0, k, w - k, w), (h - k, h, 0, k), (h - k, h, w - k, w)))
            mids = any(g[a:b, c:d].any() for a, b, c, d in ((0, k, w // 2 - 1, w // 2 + 1), (h - k, h, w // 2 - 1, w // 2 + 1),
                                                             (h // 2 - 1, h // 2 + 1, 0, k), (h // 2 - 1, h // 2 + 1, w - k, w)))
            centre = g[h // 2 - k:h // 2 + k, w // 2 - k:w // 2 + k].any()
            if not (corners and centre and not mids):        # the shape of an 「×」: four corners + centre, no edge midpoints
                continue
            score = (x + w / 2) - (y + h / 2)
            if best is None or score > best[0]:
                best = (score, x0 + cen[i][0], y0 + cen[i][1])
    return None if best is None else (best[1], best[2])


def close_popups(rounds=3):
    w = jy_ui.win()
    r = w.BoundingRectangle
    closed = []
    for _ in range(rounds):
        ts = jy_ui.texts((r.left, r.top, r.right, r.bottom))
        d = [t for t in ts if t[0].strip() in DISMISS]
        # v1.2.1: only CTAs in the middle of the window count (dialogs are centred); the home sidebar's small
        # 「SVIP · 立即续费」 link was taken for the ad's button -> no dialog found -> nothing closed
        cx = (r.left + r.right) / 2
        c = sorted([t for t in ts if t[0].strip() in CTA and t[2] > r.top + 200
                    and r.left + 0.3 * (r.right - r.left) < t[1] < r.right - 0.05 * (r.right - r.left)],
                   key=lambda t: abs(t[1] - cx))
        if d:
            jy_ui.click(d[0][1], d[0][2], label="关闭提示")
            closed.append(d[0][0])
        elif c:
            box = _dialog_box(c[0])
            if box is not None:
                right, top = box
                px, py = right - 31, top + 31
            else:
                xy = _find_close_x(c[0], r)
                if xy is None:
                    break
                px, py = xy
            jy_ui.click(px, py, label="关闭广告")          # the 「×」 — never the CTA itself
            closed.append(f"× of {c[0][0]} at ({px:.0f},{py:.0f})")
        else:
            break
        time.sleep(1.0)
    return closed
