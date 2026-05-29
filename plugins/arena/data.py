"""Game data: character cards and rainbow dice."""

CARDS = {
    "战士": {
        "name": "战士", "emoji": "⚔️",
        "hp": 30, "atk_level": 2, "def_level": 2,
        "dice_count": 4, "dice_type": 6,
        "skill": "铁壁", "skill_desc": "受到伤害后，下次攻击+2",
    },
    "法师": {
        "name": "法师", "emoji": "🔮",
        "hp": 22, "atk_level": 3, "def_level": 1,
        "dice_count": 5, "dice_type": 8,
        "skill": "魔导", "skill_desc": "防御时可重投1次",
    },
    "骑士": {
        "name": "骑士", "emoji": "🛡️",
        "hp": 35, "atk_level": 1, "def_level": 3,
        "dice_count": 4, "dice_type": 6,
        "skill": "坚守", "skill_desc": "受到伤害-2（最少0）",
    },
    "刺客": {
        "name": "刺客", "emoji": "🗡️",
        "hp": 25, "atk_level": 3, "def_level": 1,
        "dice_count": 6, "dice_type": 4,
        "skill": "暗影", "skill_desc": "攻击值>12时伤害翻倍",
    },
    "弓手": {
        "name": "弓手", "emoji": "🏹",
        "hp": 28, "atk_level": 2, "def_level": 2,
        "dice_count": 5, "dice_type": 6,
        "skill": "穿透", "skill_desc": "对方防御时少选1个骰子",
    },
    "牧师": {
        "name": "牧师", "emoji": "✨",
        "hp": 26, "atk_level": 1, "def_level": 2,
        "dice_count": 4, "dice_type": 6,
        "skill": "圣光", "skill_desc": "每回合开始回复3HP",
    },
}

RAINBOW_DICE = {
    "炎曜骰": {"name": "炎曜骰", "emoji": "🔥", "desc": "本次攻击值+3"},
    "冰曜骰": {"name": "冰曜骰", "emoji": "❄️", "desc": "本次对方攻击值-3"},
    "雷曜骰": {"name": "雷曜骰", "emoji": "⚡", "desc": "直接造成5点伤害"},
    "风曜骰": {"name": "风曜骰", "emoji": "🌀", "desc": "本次多1次重投机会"},
    "光曜骰": {"name": "光曜骰", "emoji": "💫", "desc": "回复5点HP"},
    "暗曜骰": {"name": "暗曜骰", "emoji": "🌑", "desc": "使对方下回合无法使用曜彩骰"},
}

DICE_NAMES = {4: "四面骰", 6: "六面骰", 8: "八面骰", 12: "十二面骰"}


def card_list_text():
    lines = ["=== 角色卡牌 ==="]
    for name, c in CARDS.items():
        dn = DICE_NAMES.get(c["dice_type"], "d" + str(c["dice_type"]))
        lines.append(c["emoji"] + " " + name + "  HP:" + str(c["hp"]) + " 攻:" + str(c["atk_level"]) + " 防:" + str(c["def_level"]) + " 骰:" + str(c["dice_count"]) + dn)
        lines.append("   技能「" + c["skill"] + "」" + c["skill_desc"])
    return "\n".join(lines)


def rainbow_list_text():
    lines = ["=== 曜彩骰 ==="]
    for name, d in RAINBOW_DICE.items():
        lines.append(d["emoji"] + " " + name + " - " + d["desc"])
    return "\n".join(lines)
