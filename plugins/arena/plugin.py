"""Arena battle plugin - QQ message-based card battle game."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config
from core.base import BasePlugin
from core.utils import get_user_id
from .data import CARDS, RAINBOW_DICE, DICE_NAMES, card_list_text, rainbow_list_text
from . import game as gm
from .game import Game


def _ctx(message):
    """Get context ID for game lookup."""
    if hasattr(message, "channel_id") and getattr(message, "channel_id", None):
        return "ch:" + str(message.channel_id)
    if hasattr(message, "_message"):
        m = message._message
        if hasattr(m, "channel_id") and getattr(m, "channel_id", None):
            return "ch:" + str(m.channel_id)
    aid = getattr(getattr(message, "author", None), "user_openid", None)
    if aid:
        return "c2c:" + str(aid)
    return "unknown:" + str(get_user_id(message))


def _name(game, pid):
    if pid == game.p1:
        c = game.p1_card
    else:
        c = game.p2_card
    return CARDS[c]["emoji"] + " " + c if c else "?"


def _hp_bar(cur, mx):
    pct = cur / mx if mx > 0 else 0
    filled = max(0, round(pct * 10))
    return "█" * filled + "░" * (10 - filled) + f" {cur}/{mx}"


def _dice_str(results):
    return " ".join([f"[{v}]" for v in results])


def _battle_status(game):
    p1c = CARDS.get(game.p1_card, {})
    p2c = CARDS.get(game.p2_card, {})
    n1 = p1c.get("emoji","?") + " " + (game.p1_card or "?")
    n2 = p2c.get("emoji","?") + " " + (game.p2_card or "?")
    m1 = p1c.get("hp", 0)
    m2 = p2c.get("hp", 0)
    lines = [f"=== 第{game.round_num}回合 ==="]
    lines.append(f"{n1}  {_hp_bar(game.p1_hp, m1)}")
    lines.append(f"{n2}  {_hp_bar(game.p2_hp, m2)}")
    return chr(10).join(lines)


HELP_TEXT = """=== 对战小游戏 ===

对战          - 创建对战房间
接受          - 接受对战
选卡 角色名    - 选择角色卡牌
选骰 曜彩骰名  - 选择曜彩骰
投掷          - 投掷骰子
重投          - 重新投掷（攻击方可重投2次，防御时部分角色可重投1次）
选 1 2 3      - 选择骰子点数（按编号）
使用曜彩骰    - 使用曜彩骰（每局2次）
投降          - 认输
对战卡牌      - 查看所有角色卡牌
对战曜彩骰    - 查看所有曜彩骰
对战帮助      - 显示本帮助"""


class Plugin(BasePlugin):
    name = "arena"
    version = "1.0.0"
    description = "Card battle mini-game with dice"

    def __init__(self):
        pass

    async def setup(self, bot):
        pass

    async def teardown(self):
        pass

    def get_commands(self):
        return {
            "对战帮助": self._help,
            "对战卡牌": self._card_list,
            "对战曜彩骰": self._rainbow_list,
            "对战": self._challenge,
            "接受": self._accept,
            "选卡": self._select_card,
            "选骰": self._select_rainbow,
            "投掷": self._roll,
            "重投": self._reroll,
            "选": self._pick_dice,
            "使用曜彩骰": self._use_rainbow,
            "投降": self._surrender,
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
            dn = DICE_NAMES.get(c["dice_type"], "d" + str(c["dice_type"]))
            await msg.reply(content=f"你选择了 {c['emoji']} {name}  HP:{c['hp']} 攻:{c['atk_level']} 防:{c['def_level']} 骰:{c['dice_count']}{dn}")
            if g.both_selected():
                g.start_battle()
                atk_card = CARDS[g.p1_card if g.attacker == g.p1 else g.p2_card]
                lines = [f"双方准备完毕！随机先手: {atk_card['emoji']} {atk_card['name']}", ""]
                lines.append(_battle_status(g))
                lines.append("")
                lines.append("[攻击方] 发送「投掷」开始")
                await msg.reply(content=chr(10).join(lines))
        elif result == "invalid_card":
            await msg.reply(content=f"没有名为「{name}」的角色")

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
            await msg.reply(content=f"你选择了 {d['emoji']} {name} - {d['desc']}")
            if g.both_selected():
                g.start_battle()
                atk_card = CARDS[g.p1_card if g.attacker == g.p1 else g.p2_card]
                lines = [f"双方准备完毕！随机先手: {atk_card['emoji']} {atk_card['name']}", ""]
                lines.append(_battle_status(g))
                lines.append("")
                lines.append("[攻击方] 发送「投掷」开始")
                await msg.reply(content=chr(10).join(lines))
        elif result == "invalid_dice":
            await msg.reply(content=f"没有名为「{name}」的曜彩骰")

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
        dn = DICE_NAMES.get(card["dice_type"], "d" + str(card["dice_type"]))
        role = "攻击" if pid == g.attacker else "防御"
        sel_n = card["atk_level"] if pid == g.attacker else card["def_level"]
        # 穿透 check
        if pid == g.defender:
            atk_card = g._card(g.attacker)
            if atk_card["skill"] == "穿透":
                sel_n = max(1, sel_n - 1)
        lines = [_battle_status(g), ""]
        lines.append(f"[{role}方] 投掷结果: {_dice_str(results)}")
        lines.append(f"选取 {sel_n} 个骰子")
        if pid == g.attacker and g.max_rerolls > 0:
            lines.append(f"重投: {g.rerolls_used}/{g.max_rerolls}")
        lines.append("")
        lines.append(f"发送「选 编号...」如: 选 1 3 5")
        if pid == g.attacker and g.rerolls_used < g.max_rerolls:
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
        card = g._card(pid)
        role = "攻击" if pid == g.attacker else "防御"
        sel_n = card["atk_level"] if pid == g.attacker else card["def_level"]
        if pid == g.defender:
            atk_card = g._card(g.attacker)
            if atk_card["skill"] == "穿透":
                sel_n = max(1, sel_n - 1)
        lines = [f"重投结果: {_dice_str(result)}"]
        lines.append(f"已重投: {g.rerolls_used}/{g.max_rerolls}")
        lines.append(f"选取 {sel_n} 个骰子")
        lines.append(f"发送「选 编号...」")
        if g.rerolls_used < g.max_rerolls:
            lines.append("或「重投」再次重投")
        await msg.reply(content=chr(10).join(lines))

    async def _pick_dice(self, msg, args):
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
            await msg.reply(content=f"需要选取 {result[1]} 个骰子")
            return
        if isinstance(result, tuple) and result[0] == "invalid_index":
            await msg.reply(content="骰子编号无效")
            return
        if isinstance(result, tuple) and result[0] == "duplicate":
            await msg.reply(content="不能重复选取同一个骰子")
            return
        # Attacker selected
        if isinstance(result, tuple) and result[0] == "ok" and len(result) == 6:
            _, values, base, bonus, reduction, total = result
            lines = [f"选取 {_dice_str(values)} = {base}"]
            if bonus > 0:
                lines.append(f"加成: +{bonus}")
            if reduction > 0:
                lines.append(f"削弱: -{reduction}")
            lines.append(f"进攻值: {total}")
            lines.append("")
            lines.append(_battle_status(g))
            lines.append("")
            lines.append("[防御方] 发送「投掷」开始")
            await msg.reply(content=chr(10).join(lines))
            return
        # Defender selected -> combat resolved
        if isinstance(result, tuple) and result[0] == "ok" and len(result) == 8:
            _, def_values, def_sum, damage, old_hp, new_hp, game_over, heal_info = result
            lines = [f"选取 {_dice_str(def_values)} = {def_sum}", ""]
            lines.append(f"=== 回合结算 ===")
            lines.append(f"进攻: {g.atk_value} vs 防御: {def_sum}")
            lines.append(f"伤害: {damage}")
            def_name = _name(g, g.defender)
            lines.append(f"{def_name}  HP: {old_hp} -> {new_hp}")
            if heal_info:
                for hid, healed in heal_info:
                    hname = _name(g, hid)
                    lines.append(f"{hname} 圣光回复 {healed}HP")
            if game_over:
                winner_name = _name(g, g.winner)
                lines.append("")
                lines.append(f"游戏结束！{winner_name} 获胜！")
                gm.remove_game(g)
            else:
                lines.append("")
                atk_name = _name(g, g.attacker)
                lines.append(f"下一回合: {atk_name} 攻击")
                lines.append("[攻击方] 发送「投掷」开始")
            # Clear silence at end of round
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
        if result == "no_dice":
            await msg.reply(content="你还没有选择曜彩骰")
            return
        rname = self.p1_rainbow if pid == g.p1 else g.p2_rainbow
        # Actually get it from game
        rn = g.p1_rainbow if pid == g.p1 else g.p2_rainbow
        d = RAINBOW_DICE.get(rn, {})
        emoji = d.get("emoji", "")
        if isinstance(result, tuple):
            if result[0] == "fire":
                await msg.reply(content=f"{emoji} 使用{rn}！本次攻击值+3")
            elif result[0] == "ice":
                await msg.reply(content=f"{emoji} 使用{rn}！对方本次攻击值-3")
            elif result[0] == "thunder":
                old, new_hp, game_over = result[1], result[2], result[3]
                opp = g._other(pid)
                opp_name = _name(g, opp)
                lines = [f"{emoji} 使用{rn}！直接造成5点伤害"]
                lines.append(f"{opp_name}  HP: {old} -> {new_hp}")
                if game_over:
                    winner_name = _name(g, pid)
                    lines.append(f"游戏结束！{winner_name} 获胜！")
                    gm.remove_game(g)
                await msg.reply(content=chr(10).join(lines))
            elif result[0] == "wind":
                await msg.reply(content=f"{emoji} 使用{rn}！本次多1次重投机会")
            elif result[0] == "light":
                old, new_hp = result[1], result[2]
                await msg.reply(content=f"{emoji} 使用{rn}！HP: {old} -> {new_hp}")
            elif result[0] == "dark":
                opp_name = _name(g, g._other(pid))
                await msg.reply(content=f"{emoji} 使用{rn}！{opp_name} 下回合无法使用曜彩骰")
        remaining = g._rainbow_uses(pid)
        # Show remaining after use

    async def _surrender(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="你不在对战中")
            return
        g.surrender(pid)
        winner_name = _name(g, g.winner)
        await msg.reply(content=f"你投降了！{winner_name} 获胜！")
        gm.remove_game(g)
