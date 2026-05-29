"""Game data loader - loads from cards.json and dice.json."""
import json
import os

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_json(filename):
    path = os.path.join(_DATA_DIR, filename)
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

CARDS = _load_json("cards.json")
RAINBOW_DICE = _load_json("dice.json")

DICE_NAMES = {4: "四面骰", 6: "六面骰", 8: "八面骰", 12: "十二面骰"}


def dice_spec_text(dice_list):
    """Format dice spec: 3xd4 + 1xd6 + 1xd8"""
    parts = []
    for d in dice_list:
        dn = DICE_NAMES.get(d["type"], "d" + str(d["type"]))
        parts.append(str(d["count"]) + dn)
    return " + ".join(parts)


def card_list_text():
    lines = ["=== 角色卡牌 ==="]
    for name, c in CARDS.items():
        dt = dice_spec_text(c["dice"])
        lines.append(c["emoji"] + " " + name + "  HP:" + str(c["hp"]) + " 攻:" + str(c["atk_level"]) + " 防:" + str(c["def_level"]) + " 骰:" + dt)
        lines.append("   技能「" + c["skill"] + "」" + c["skill_desc"])
    return "\n".join(lines)


def rainbow_list_text():
    lines = ["=== 曜彩骰 ==="]
    for name, d in RAINBOW_DICE.items():
        lines.append(d["emoji"] + " " + name + " - " + d["desc"])
    return "\n".join(lines)
