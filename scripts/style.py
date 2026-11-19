"""The house style, read from <skill>/style.json (open source: edit that file to make the style your own).

  from style import ST
  ST["filter"]["strength"]      -> 34
  ST["keyword"]["moods"]["warn"]["color"] -> "FF287F"

Keys starting with "_" are notes for humans and are dropped. A missing / broken style.json falls back to the
built-in defaults below (the same values), so an edit never fails because of a typo — but doctor.py reports it.
Legacy: config.json keys keyword_font / subtitle_font / beauty_preset still override (v1.1.0 configs).
"""
import copy
import json
import pathlib

SKILL = pathlib.Path(__file__).resolve().parent.parent
FILE = SKILL / "style.json"

DEFAULTS = {
    "rhythm": {"speed": 1.10, "pause_min_s": 0.35, "pause_keep_s": 0.12, "voice_db": 6},
    "beauty": {"preset": "我的预设1", "check": {"磨皮": 23}, "values": {}},
    "filter": {"name": "高清增强", "strength": 34},
    "subtitle": {"hotwords": ["私域", "牢饭", "纯扯", "割韭菜", "会销"], "font": "新青年体", "size": 6, "preset_style": 2,
                 "color": "FFFFFF", "stroke": 70, "y": -1577},
    "keyword": {"font": "仓耳榜黑", "size": 13, "size_no_person": 14, "preset_style": 2, "stroke": 90,
                "default_color": "FF287F", "default_anim": "放大", "x": 1300, "y_top": 950, "y_bottom": 250,
                "moods": {"bait": {"color": "FFE600", "anim": "打字机I"}, "warn": {"color": "FF287F", "anim": "放大"},
                          "us": {"color": "2BE36B", "anim": "向上弹入"}},
                "second_line_color": "FFFFFF"},
    "bgm": {"name": "22 22", "volume_db": -6.3, "fade": False},
    "cover": {"font": "仓耳榜黑", "top_color": "FF287F", "bottom_color": "FFFFFF", "landscape_fill_width": 0.575,
              "landscape_centre_y": 0.726, "portrait_fill_width": 0.86, "portrait_centre_y": 0.47},
    "export": {"resolution": "4K", "fps": 30, "covers": ["封面-横版16x9.png", "封面-竖版3x4.png"]},
}
ERROR = None


def _clean(d):
    if isinstance(d, dict):
        return {k: _clean(v) for k, v in d.items() if not str(k).startswith("_")}
    return d


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("check",):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load():
    global ERROR
    st = copy.deepcopy(DEFAULTS)
    try:
        _merge(st, _clean(json.loads(FILE.read_text(encoding="utf-8"))))
    except FileNotFoundError:
        ERROR = "style.json 不存在，用内置默认值"
    except Exception as e:  # noqa: BLE001
        ERROR = f"style.json 读不了（{e}），用内置默认值"
    try:
        from config import CFG
        for key, (sec, sub) in {"keyword_font": ("keyword", "font"), "subtitle_font": ("subtitle", "font"),
                                "beauty_preset": ("beauty", "preset")}.items():
            if CFG.get(key) and key in _user_config_keys():
                st[sec][sub] = CFG[key]
    except Exception:
        pass
    return st


def _user_config_keys():
    p = SKILL / "config.json"
    try:
        return {k for k, v in json.loads(p.read_text(encoding="utf-8")).items() if v not in ("", None)}
    except Exception:
        return set()


ST = load()


def summary():
    """One-paragraph Chinese summary of the style actually in use (printed by the acceptance test)."""
    b, f, s, k = ST["beauty"], ST["filter"], ST["subtitle"], ST["keyword"]
    moods = "、".join(f"{v['color']} {v['anim']}" for v in k["moods"].values())
    return (f"变速 {ST['rhythm']['speed']}x · 去 ≥{ST['rhythm']['pause_min_s']}s 停顿留 {ST['rhythm']['pause_keep_s']}s · "
            f"人声 +{ST['rhythm']['voice_db']}dB\n美颜预设「{b['preset']}」（核对 {b['check'] or '不核对数值'}）\n"
            f"滤镜「{f['name']}」强度 {f['strength']}\n字幕 {s['font']} {s['size']} 号 · 预设样式 {s['preset_style']} · "
            f"#{s['color']} · 描边 {s['stroke']} · 热词 {'/'.join(s['hotwords'])}\n大字 {k['font']} {k['size']} 号 · 描边 {k['stroke']} · "
            f"配色动效 {moods}\nBGM「{ST['bgm']['name']}」{ST['bgm']['volume_db']} dB")


if __name__ == "__main__":
    print(ERROR or "style.json ✓")
    print(summary())
