"""Arena battle plugin v2 - mixed dice, dongchuan, mingding."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config
from core.base import BasePlugin
from core.utils import get_user_id
from .data import CARDS, RAINBOW_DICE, DICE_NAMES, dice_spec_text, card_list_text, rainbow_list_text
from . import game as gm
from .game import Game


def _ctx(message):
    if hasattr(message, "channel_id") and getattr(message, "channel_id", None):
        return "ch:" + str(message.channel_id)
    if hasattr(message, "_message"):
        m = message._message
        if hasattr(m, "channel_id") and getattr(m, "channel_id", None):
            return "ch:" + str(m.channel_id)
    aid = getattr(getattr(message, "author", None), "user_openid", None)
    if aid: return "c2c:" + str(aid)
    return "unknown:" + str(get_user_id(message))


def _name(game, pid):
    cn = game.p1_card if pid == game.p1 else game.p2_card
    c = CARDS.get(cn, {})
    return c.get("emoji","?") + " " + (cn or "?")


def _hp_bar(cur, mx):
    pct = cur / mx if mx > 0 else 0
    filled = max(0, round(pct * 10))
    return "||" + "||" * filled + ".." * (10 - filled) + "|| " + str(cur) + "/" + str(mx)


def _roll_str(results):
    """Format roll results with type labels and 命定 markers."""
    parts = []
    for r in results:
        if r["mingding"]:
            parts.append("[命运:" + str(r["value"]) + "]")
        else:
            dn = DICE_NAMES.get(r["type"], "d" + str(r["type"]))
            parts.append("[" + dn + ":" + str(r["value"]) + "]")
    return " ".join(parts)


def _battle_status(game):
    p1c = CARDS.get(game.p1_card, {})
    p2c = CARDS.get(game.p2_card, {})
    n1 = p1c.get("emoji","?") + " " + (game.p1_card or "?")
    n2 = p2c.get("emoji","?") + " " + (game.p2_card or "?")
    m1 = p1c.get("hp", 0)
    m2 = p2c.get("hp", 0)
    lines = ["=== 第" + str(game.round_num) + "回合 ==="]
    lines.append(n1 + "  " + _hp_bar(game.p1_hp, m1))
    lines.append(n2 + "  " + _hp_bar(game.p2_hp, m2))
    # Show dongchuan bonuses
    for pid, name in [(game.p1, n1), (game.p2, n2)]:
        db = game.dongchuan_bonus.get(pid, 0)
        if db > 0:
            lines.append(name + " 洞穿叠加: +" + str(db) + "攻")
    return chr(10).join(lines)


HELP_TEXT = """=== 对战小游戏 ===
对战          - 创建对战房间
接受          - 接受对战
选卡 角色名    - 选择角色卡牌
选骰 曜彩骰名  - 选择曜彩骰
投掷          - 投掷骰子
重投          - 重新投掷
选 1 2 3      - 选择骰子（按编号）
使用曜彩骰    - 使用曜彩骰（每局2次）
投降          - 认输
对战卡牌      - 查看所有角色卡牌
对战曜彩骰    - 查看所有曜彩骰
对战帮助      - 显示本帮助"""


class Plugin(BasePlugin):
    name = "arena"
    version = "2.0.0"
    description = "Card battle mini-game with mixed dice, dongchuan, mingding"

    async def setup(self, bot): pass
    async def teardown(self): pass

    def get_commands(self):
        return {
            "对战帮助": self._help, "对战卡牌": self._card_list, "对战曜彩骰": self._rainbow_list,
            "对战": self._challenge, "接受": self._accept,
            "选卡": self._select_card, "选骰": self._select_rainbow,
            "投掷": self._roll, "重投": self._reroll, "选": self._pick,
            "使用曜彩骰": self._use_rainbow, "投降": self._surrender,
        }

    async def _help(self, msg, args):
        await msg.reply(content=HELP_TEXT)

    async def _card_list(self, msg, args):
        await msg.reply(content=card_list_text())

    async def _rainbow_list(self, msg, args):
        await msg.reply(content=rainbow_list_text())

    async def _challenge(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        if gm.get_game(pid, ctx):
            await msg.reply(content="你已在对战中，请先结束当前对战")
            return
        if gm.get_pending(ctx):
            await msg.reply(content="当前已有待接受的对战，请先「接受」")
            return
        gm.create_challenge(pid, ctx)
        await msg.reply(content="对战房间已创建！等待对手发送「接受」")

    async def _accept(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        if gm.get_game(pid, ctx):
            await msg.reply(content="你已在对战中")
            return
        g = gm.accept_challenge(pid, ctx)
        if not g:
            await msg.reply(content="当前没有待接受的对战，发送「对战」创建")
            return
        lines = ["对战开始！双方请选卡牌和曜彩骰", ""]
        lines.append("发送「选卡 角色名」选择角色")
        lines.append("发送「选骰 曜彩骰名」选择曜彩骰")
        lines.append("")
        lines.append(card_list_text())
        lines.append("")
        lines.append(rainbow_list_text())
        await msg.reply(content=chr(10).join(lines))

    async def _select_card(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g or g.state != Game.SELECTING:
            await msg.reply(content="当前不需要选卡")
            return
        if not args:
            await msg.reply(content="格式: 选卡 角色名")
            return
        name = args[0]
        result = g.select_card(pid, name)
        if result == "ok":
            c = CARDS[name]
            dt = dice_spec_text(c["dice"])
            await msg.reply(content="你选择了 " + c["emoji"] + " " + name + "  HP:" + str(c["hp"]) + " 攻:" + str(c["atk_level"]) + " 防:" + str(c["def_level"]) + " 骰:" + dt)
            if g.both_selected():
                g.start_battle()
                ac = CARDS[g.p1_card if g.attacker == g.p1 else g.p2_card]
                lines = ["双方准备完毕！随机先手: " + ac["emoji"] + " " + ac["name"], ""]
                lines.append(_battle_status(g))
                lines.append("")
                lines.append("[攻击方] 发送「投掷」开始")
                await msg.reply(content=chr(10).join(lines))
        elif result == "invalid_card":
            await msg.reply(content="没有名为「" + name + "」的角色")

    async def _select_rainbow(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g or g.state != Game.SELECTING:
            await msg.reply(content="当前不需要选骰")
            return
        if not args:
            await msg.reply(content="格式: 选骰 曜彩骰名")
            return
        name = args[0]
        result = g.select_rainbow(pid, name)
        if result == "ok":
            d = RAINBOW_DICE[name]
            await msg.reply(content="你选择了 " + d["emoji"] + " " + name + " - " + d["desc"])
            if g.both_selected():
                g.start_battle()
                ac = CARDS[g.p1_card if g.attacker == g.p1 else g.p2_card]
                lines = ["双方准备完毕！随机先手: " + ac["emoji"] + " " + ac["name"], ""]
                lines.append(_battle_status(g))
                lines.append("")
                lines.append("[攻击方] 发送「投掷」开始")
                await msg.reply(content=chr(10).join(lines))
        elif result == "invalid_dice":
            await msg.reply(content="没有名为「" + name + "」的曜彩骰")

    async def _roll(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        results = g.roll(pid)
        if results is None:
            await msg.reply(content="当前不是你的投掷阶段")
            return
        card = g._card(pid)
        role = "攻击" if pid == g.attacker else "防御"
        mi = g._mingding_indices()
        if pid == g.attacker:
            n = g._effective_atk(pid) - len(mi)
        else:
            n = card["def_level"] - len(mi)
            atk_card = g._card(g.attacker)
            if atk_card["skill"] == "穿透": n = max(0, n - 1)
        n = max(0, n)
        lines = [_battle_status(g), ""]
        lines.append("[" + role + "方] 投掷: " + _roll_str(results))
        if len(mi) > 0:
            lines.append("命定骰子自动选入")
        lines.append("选取 " + str(n) + " 个骰子")
        if g.max_rerolls > 0:
            lines.append("重投: " + str(g.rerolls_used) + "/" + str(g.max_rerolls))
        lines.append("")
        lines.append("发送「选 编号...」如: 选 1 3 5")
        if g.rerolls_used < g.max_rerolls:
            lines.append("或「重投」重新投掷")
        await msg.reply(content=chr(10).join(lines))

    async def _reroll(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        result = g.reroll(pid)
        if result is None:
            await msg.reply(content="当前不可重投")
            return
        if result == "no_rerolls":
            await msg.reply(content="重投次数已用完")
            return
        mi = g._mingding_indices()
        if pid == g.attacker:
            n = g._effective_atk(pid) - len(mi)
        else:
            n = g._card(pid)["def_level"] - len(mi)
        n = max(0, n)
        lines = ["重投: " + _roll_str(result)]
        if len(mi) > 0: lines.append("命定骰子自动选入")
        lines.append("已重投: " + str(g.rerolls_used) + "/" + str(g.max_rerolls))
        lines.append("选取 " + str(n) + " 个骰子")
        lines.append("发送「选 编号...」")
        if g.rerolls_used < g.max_rerolls: lines.append("或「重投」")
        await msg.reply(content=chr(10).join(lines))

    async def _pick(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        try:
            indices = [int(x) for x in args]
        except ValueError:
            await msg.reply(content="格式: 选 编号 编号 ...（如: 选 1 3 5）")
            return
        result = g.select_dice(pid, indices)
        if result is None:
            await msg.reply(content="当前不是选取阶段")
            return
        if isinstance(result, tuple) and result[0] == "wrong_count":
            await msg.reply(content="需要选取 " + str(result[1]) + " 个骰子" + ("（命定已自动选入）" if result[2] > 0 else ""))
            return
        if isinstance(result, tuple) and result[0] == "invalid_index":
            await msg.reply(content="骰子编号无效")
            return
        # Attacker selected
        if isinstance(result, tuple) and result[0] == "ok_atk":
            _, values, total, dongchuan = result
            vals_str = " + ".join(str(v) for v in values)
            lines = ["选取 " + vals_str + " = " + str(total)]
            if dongchuan:
                lines.append("💀 洞穿触发！无视对方防御，攻击等级+1")
            lines.append("进攻值: " + str(total))
            lines.append("")
            lines.append(_battle_status(g))
            lines.append("")
            lines.append("[防御方] 发送「投掷」开始")
            await msg.reply(content=chr(10).join(lines))
            return
        # Defender selected -> combat resolved
        if isinstance(result, tuple) and result[0] == "ok_def":
            _, def_values, def_sum, damage, old_hp, new_hp, game_over, heal_info, has_dongchuan = result
            vals_str = " + ".join(str(v) for v in def_values)
            lines = ["选取 " + vals_str + " = " + str(def_sum), ""]
            lines.append("=== 回合结算 ===")
            if has_dongchuan:
                lines.append("进攻: " + str(g.atk_value) + " [洞穿] vs 防御: " + str(def_sum))
                lines.append("伤害: " + str(damage) + "（无视防御）")
            else:
                lines.append("进攻: " + str(g.atk_value) + " vs 防御: " + str(def_sum))
                lines.append("伤害: " + str(damage))
            dn = _name(g, g.defender)
            lines.append(dn + "  HP: " + str(old_hp) + " -> " + str(new_hp))
            for hid, healed in heal_info:
                lines.append(_name(g, hid) + " 圣光回复 " + str(healed) + "HP")
            if game_over:
                lines.append("")
                lines.append("游戏结束！" + _name(g, g.winner) + " 获胜！")
                gm.remove_game(g)
            else:
                lines.append("")
                lines.append("下一回合: " + _name(g, g.attacker) + " 攻击")
                lines.append("[攻击方] 发送「投掷」开始")
            g.silenced = {g.p1: False, g.p2: False}
            await msg.reply(content=chr(10).join(lines))
            return

    async def _use_rainbow(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        result = g.use_rainbow(pid)
        if result == "silenced":
            await msg.reply(content="你被沉默了，本回合无法使用曜彩骰")
            return
        if result == "no_uses":
            await msg.reply(content="曜彩骰使用次数已用完")
            return
        if isinstance(result, tuple) and result[0] == "too_late":
            await msg.reply(content="" + rn + " 只能在前" + str(result[1]) + "回合使用")
            return
        if result == "no_dice":
            await msg.reply(content="你还没有选择曜彩骰")
            return
        rn = g._rainbow_name(pid)
        d = RAINBOW_DICE.get(rn, {})
        emoji = d.get("emoji", "")
        remaining = g._rainbow_uses(pid)
        if isinstance(result, tuple) and result[0] == "mingding":
            _, rname, rdata = result
            faces_str = ",".join(str(f) for f in rdata["faces"])
            await msg.reply(content=emoji + " 使用" + rname + "！下次投掷额外获得命定骰子(面:" + faces_str + ")，必须选入\n剩余次数: " + str(remaining))

    async def _surrender(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        g.surrender(pid)
        await msg.reply(content="你投降了！" + _name(g, g.winner) + " 获胜！")
        gm.remove_game(g)
