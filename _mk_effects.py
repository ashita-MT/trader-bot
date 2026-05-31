# encoding: utf-8
"""Effect system for arena battle game."""

EFFECTS = {
    "heal":        {"name": "\u6cbb\u6108", "emoji": "\U0001f49a", "desc": "\u6062\u590dHP\uff0c\u751f\u6548\u540e\u79fb\u9664", "persist": False},
    "combo":       {"name": "\u8fde\u51fb", "emoji": "\u2694\ufe0f", "desc": "\u989d\u5916\u653b\u51fb\uff0c\u751f\u6548\u540e\u79fb\u9664", "persist": False},
    "strength":    {"name": "\u529b\u91cf", "emoji": "\U0001f4aa", "desc": "\u653b\u51fb+\u5c42\u6570\uff0c\u6301\u7eed", "persist": True},
    "toughness":   {"name": "\u97e7\u6027", "emoji": "\U0001f6e1\ufe0f", "desc": "\u9632\u5fa1+\u5c42\u6570\uff0c\u6301\u7eed", "persist": True},
    "instant":     {"name": "\u77ac\u4f24", "emoji": "\u26a1", "desc": "\u7acb\u523b\u9020\u6210\u4f24\u5bb3", "persist": False},
    "ascend":      {"name": "\u8dc3\u5347", "emoji": "\u2b06\ufe0f", "desc": "\u6700\u5c0f\u9ab0\u5b50\u53d8\u6700\u5927\u503c", "persist": False},
    "hack":        {"name": "\u9a87\u5165", "emoji": "\U0001f3ad", "desc": "\u5bf9\u624b\u6700\u5927\u9ab0\u5b50\u53d82", "persist": False},
    "poison":      {"name": "\u4e2d\u6bd2", "emoji": "\u2620\ufe0f", "desc": "\u56de\u5408\u540e\u53d7\u4f24\u5bb3\uff0c\u5c42\u6570-1", "persist": True},
    "lifesteal":   {"name": "\u8679\u5438", "emoji": "\U0001f9db", "desc": "\u653b\u51fb\u65f6\u6062\u590d\u4f24\u5bb3\u6bd4\u4f8bHP", "persist": False},
    "counter":     {"name": "\u53cd\u51fb", "emoji": "\u21a9\ufe0f", "desc": "\u9632\u5fa1>\u653b\u51fb\u65f6\u53cd\u51fb\u5dee\u503c", "persist": False},
    "upgrade":     {"name": "\u5347\u7ea7", "emoji": "\u23eb", "desc": "\u9ab0\u5b50\u9762\u6570\u63d0\u5347\uff0c\u6700\u591ad12", "persist": False},
    "pierce":      {"name": "\u6d1e\u7a7f", "emoji": "\U0001f480", "desc": "\u65e0\u89c6\u9632\u5fa1\u548c\u529b\u573a", "persist": False},
    "reflect":     {"name": "\u53cd\u4f24", "emoji": "\U0001fa9e", "desc": "\u53d7\u51fb\u65f6\u9020\u6210\u9632\u5fa1\u6bd4\u4f8b\u77ac\u4f24", "persist": False},
    "toxic":       {"name": "\u731b\u6bd2", "emoji": "\u2623\ufe0f", "desc": "\u4e2d\u6bd2\u4f24\u5bb3\u7ffb\u500d\uff0c\u4e0d\u53e0\u52a0", "persist": True},
    "thorns":      {"name": "\u8346\u68d8", "emoji": "\U0001f33f", "desc": "\u56de\u5408\u524d\u53d7\u4f24\u5bb3\uff0c\u7ed3\u7b97\u540e\u6e05\u9664", "persist": False},
    "unyielding":  {"name": "\u4e0d\u5c48", "emoji": "\U0001f525", "desc": "\u4fdd\u75591HP\uff0c\u56de\u5408\u540e\u79fb\u9664", "persist": False},
    "disrupt":     {"name": "\u5e72\u6270", "emoji": "\U0001f300", "desc": "\u6bcf\u5c42-1\u91cd\u6295\u6b21\u6570", "persist": True},
    "forcefield":  {"name": "\u529b\u573a", "emoji": "\U0001f6e1\ufe0f", "desc": "\u514d\u75ab\u5e38\u89c4\u4f24\u5bb3\uff0c\u56de\u5408\u540e\u79fb\u9664", "persist": False},
    "fated":       {"name": "\u547d\u5b9a", "emoji": "\U0001f3b0", "desc": "\u9ab0\u5b50\u6295\u51fa\u540e\u5fc5\u9009", "persist": False},
    "overload":    {"name": "\u8d85\u8f7d", "emoji": "\u26a1", "desc": "\u653b\u51fb+\u5c42\u6570\uff0c\u9632\u5fa1\u81ea\u4f2450%", "persist": True},
    "desperation": {"name": "\u80cc\u6c34", "emoji": "\U0001f30a", "desc": "HP\u964d\u4e3a1\uff0c\u83b7\u5f97\u52a0\u6210\uff0c\u653b\u51fb\u540e\u79fb\u9664", "persist": False},
    "lucky":       {"name": "\u5f3a\u8fd0", "emoji": "\U0001f340", "desc": "\u6295\u63b7\u70b9\u6570\u5fc5\u4e3a\u6700\u5927\u503c", "persist": True},
}


def new_effects():
    """Create empty effects dict."""
    return {}


def get_stacks(eff, key):
    return eff.get(key, 0) if isinstance(eff.get(key), (int, float)) else (1 if eff.get(key) else 0)


def has(eff, key):
    v = eff.get(key, False)
    return v is True or (isinstance(v, (int, float)) and v > 0)


def add(eff, key, val=1):
    if isinstance(val, bool):
        eff[key] = val
    else:
        eff[key] = eff.get(key, 0) + val


def remove(eff, key):
    eff.pop(key, None)


def clear_temporary(eff):
    to_del = [k for k in eff if k in EFFECTS and not EFFECTS[k]["persist"]]
    for k in to_del:
        del eff[k]


def clear_expired_after_turn(eff):
    """Clear effects that expire after a turn."""
    for k in ["unyielding", "forcefield", "thorns"]:
        eff.pop(k, None)


def clear_expired_after_attack(eff):
    """Clear effects that expire after an attack."""
    for k in ["desperation"]:
        eff.pop(k, None)


def effect_summary(eff):
    """Return list of active effect strings."""
    lines = []
    for key, val in eff.items():
        if key not in EFFECTS:
            continue
        ed = EFFECTS[key]
        if isinstance(val, bool) and val:
            lines.append(ed["emoji"] + " " + ed["name"])
        elif isinstance(val, (int, float)) and val > 0:
            lines.append(ed["emoji"] + " " + ed["name"] + ": " + str(int(val)) + "\u5c42")
    return lines
