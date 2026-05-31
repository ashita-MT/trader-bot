"""Arena battle plugin v4 - unified effect system."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config
from core.base import BasePlugin
from core.utils import get_user_id
from .data import CARDS, RAINBOW_DICE, DICE_NAMES, dice_spec_text, card_list_text, rainbow_list_text
from . import game as gm
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from plugins.admin.admin import register_plugin
from .game import Game


def _save_msg_ctx(game, pid, msg):
    """Save message context for a player."""
    if not game:
        return
    api = getattr(msg, "_api", None)
    if not api:
        inner = getattr(msg, "_message", None)
        if inner:
            api = getattr(inner, "_api", None)
    game.msg_ctx[pid] = {"api": api, "msg": msg}

async def _send_to_other(game, current_pid, content):
    """Send a message to the other player."""
    other_pid = game._other(current_pid)
    ctx = game.msg_ctx.get(other_pid)
    if not ctx:
        return
    api = ctx.get("api")
    msg_obj = ctx.get("msg")
    if not api or not msg_obj:
        return
    try:
        # Detect context type from stored msg
        inner = getattr(msg_obj, "_message", msg_obj)
        if hasattr(inner, "group_openid") and inner.group_openid:
            await api.post_group_message(
                group_openid=inner.group_openid,
                msg_type=0,
                content=content,
            )
        elif hasattr(inner, "channel_id") and inner.channel_id:
            await api.post_message(
                channel_id=inner.channel_id,
                msg_type=0,
                content=content,
            )
        elif hasattr(inner, "author"):
            uid = None
            if hasattr(inner.author, "user_openid") and inner.author.user_openid:
                uid = inner.author.user_openid
            elif hasattr(inner.author, "member_openid") and inner.author.member_openid:
                uid = inner.author.member_openid
            if uid:
                await api.post_c2c_message(
                    openid=uid,
                    msg_type=0,
                    content=content,
                )
    except Exception as e:
        print(f"[Arena] send to other failed: {e}", flush=True)


def _ctx(message):
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
    cn = game.p1_card if pid == game.p1 else game.p2_card
    c = CARDS.get(cn, {})
    return c.get("emoji", "?") + " " + (cn or "?")


def _hp_bar(cur, mx):
    pct = cur / mx if mx > 0 else 0
    filled = max(0, round(pct * 10))
    return "[" + "#" * filled + "." * (10 - filled) + "] " + str(cur) + "/" + str(mx)


def _roll_str(results, rainbow_data=None):
    """Format dice results with detailed info.
    Normal dice: [d4:3] [d6:5]
    Rainbow dice: [??:12] with star if value triggers special effect
    """
    parts = []
    for idx, r in enumerate(results):
        val = r["value"]
        if r.get("rainbow"):
            # Rainbow die: show name and value
            label = r.get("label", "\u66dc\u5f69")
            # Check if this value triggers a special effect
            special_mark = ""
            if rainbow_data:
                sv = rainbow_data.get("special_values", {})
                if str(val) in sv:
                    special_mark = "\u2605"  # star marker
            parts.append("[" + label + ":" + str(val) + special_mark + "]")
        elif r["mingding"]:
            parts.append("[\u547d\u5b9a:" + str(val) + "]")
        else:
            dn = DICE_NAMES.get(r["type"], "d" + str(r["type"]))
            parts.append("[" + dn + ":" + str(val) + "]")
    return " ".join(parts)


def _format_battle_start(game):
    """Format the battle start message showing both lineups and first attacker."""
    p1c = CARDS.get(game.p1_card, {})
    p2c = CARDS.get(game.p2_card, {})
    n1 = p1c.get("emoji", "?") + " " + game.p1_card
    n2 = p2c.get("emoji", "?") + " " + game.p2_card
    dt1 = dice_spec_text(p1c.get("dice", []))
    dt2 = dice_spec_text(p2c.get("dice", []))
    rd1 = RAINBOW_DICE.get(game.p1_rainbow, {})
    rd2 = RAINBOW_DICE.get(game.p2_rainbow, {})

    atk_name = n1 if game.attacker == game.p1 else n2
    def_name = n2 if game.attacker == game.p1 else n1

    lines = ["=== \u94f6\u6cb3\u6218\u529b\u515a ===", ""]
    lines.append("\u3010" + n1 + "\u3011")
    lines.append("  HP:" + str(p1c.get("hp", 0)) + " \u653b:" + str(p1c.get("atk_level", 0)) + " \u9632:" + str(p1c.get("def_level", 0)) + " \u9ab0:" + dt1)
    if rd1:
        lines.append("  \u66dc\u5f69: " + rd1.get("emoji", "") + " " + game.p1_rainbow)
    lines.append("")
    lines.append("\u3010" + n2 + "\u3011")
    lines.append("  HP:" + str(p2c.get("hp", 0)) + " \u653b:" + str(p2c.get("atk_level", 0)) + " \u9632:" + str(p2c.get("def_level", 0)) + " \u9ab0:" + dt2)
    if rd2:
        lines.append("  \u66dc\u5f69: " + rd2.get("emoji", "") + " " + game.p2_rainbow)
    lines.append("")
    lines.append("\u5148\u624b: " + atk_name)
    lines.append("\u540e\u624b: " + def_name)
    lines.append("")
    lines.append(_battle_status(game))
    lines.append("")
    lines.append("[\u653b\u51fb\u65b9] \u53d1\u9001\u300c\u6295\u63b7\u300d\u5f00\u59cb")
    return lines


def _battle_status(game):
    p1c = CARDS.get(game.p1_card, {})
    p2c = CARDS.get(game.p2_card, {})
    n1 = p1c.get("emoji", "?") + " " + (game.p1_card or "?")
    n2 = p2c.get("emoji", "?") + " " + (game.p2_card or "?")
    m1 = p1c.get("hp", 0)
    m2 = p2c.get("hp", 0)
    lines = ["=== \u7b2c" + str(game.round_num) + "\u56de\u5408 ==="]
    lines.append(n1 + "  " + _hp_bar(game.p1_hp, m1))
    lines.append(n2 + "  " + _hp_bar(game.p2_hp, m2))
    for pid, nm in [(game.p1, n1), (game.p2, n2)]:
        etxt = game.get_effects_text(pid)
        if etxt != "\u65e0":
            lines.append(nm + " \u6548\u679c: " + etxt)
        db = game.dongchuan_bonus.get(pid, 0)
        if db > 0:
            lines.append(nm + " \u6d1e\u7a7f\u53e0\u52a0: +" + str(db) + "\u653b")
    return chr(10).join(lines)


HELP_TEXT = """=== \u94f6\u6cb3\u6218\u529b\u515a ===

\u3010\u5f00\u59cb\u6e38\u620f\u3011
1. A \u53d1\u9001\u300c\u5bf9\u6218\u300d\u521b\u5efa\u623f\u95f4
2. B \u53d1\u9001\u300c\u63a5\u53d7\u300d\u52a0\u5165
3. \u53cc\u65b9\u5404\u81ea\u9009\u5361\u724c\u548c\u66dc\u5f69\u9ab0
4. \u968f\u673a\u4e00\u65b9\u83b7\u5f97\u5148\u624b

\u3010\u56de\u5408\u6d41\u7a0b\u3011
\u653b\u51fb\u65b9: \u6295\u63b7 -> \u9009\u53d6\u9ab0\u5b50 -> \u7ed3\u7b97\u653b\u51fb\u503c
\u9632\u5fa1\u65b9: \u6295\u63b7 -> \u9009\u53d6\u9ab0\u5b50 -> \u7ed3\u7b97\u9632\u5fa1\u503c
\u4f24\u5bb3 = \u653b\u51fb\u503c - \u9632\u5fa1\u503c\uff0c\u653b\u9632\u4e92\u6362\uff0c\u751f\u547d\u5f52\u96f6\u8d25\u5317

\u3010\u6307\u4ee4\u5217\u8868\u3011
\u5bf9\u6218             - \u521b\u5efa\u623f\u95f4\uff0c\u83b7\u53d6\u623f\u95f4\u7801
\u63a5\u53d7 \u623f\u95f4\u7801       - \u52a0\u5165\u6307\u5b9a\u623f\u95f4
\u9009\u5361 \u89d2\u8272\u540d       - \u9009\u62e9\u89d2\u8272
\u9009\u9ab0 \u66dc\u5f69\u9ab0\u540d     - \u9009\u62e9\u66dc\u5f69\u9ab0
\u6295\u63b7 / \u91cd\u6295         - \u6295\u63b7\u9ab0\u5b50 / \u91cd\u65b0\u6295\u63b7
\u9009 1 2 3         - \u6309\u7f16\u53f7\u9009\u53d6\u9ab0\u5b50
\u4f7f\u7528\u66dc\u5f69\u9ab0       - \u4f7f\u7528\u66dc\u5f69\u9ab0\uff08\u6bcf\u5c402\u6b21\uff09
\u6295\u964d             - \u8ba4\u8f93
\u5bf9\u6218\u5361\u724c / \u5bf9\u6218\u66dc\u5f69\u9ab0 - \u67e5\u770b\u5361\u724c / \u66dc\u5f69\u9ab0
\u94f6\u6cb3\u6218\u529b\u515a\u5e2e\u52a9           - \u663e\u793a\u672c\u5e2e\u52a9"""


class Plugin(BasePlugin):
    name = "arena"
    version = "4.0.0"
    description = "银河战力党"

    async def setup(self, bot):
        register_plugin("arena", "银河战力党 — 12 角色 + 19 曜彩骰 + 22 种效果")

    async def teardown(self):
        pass

    def get_commands(self):
        return {
            "\u94f6\u6cb3\u6218\u529b\u515a\u5e2e\u52a9": self._help,
            "\u5bf9\u6218\u5361\u724c": self._cards,
            "\u5bf9\u6218\u66dc\u5f69\u9ab0": self._rainbows,
            "\u5bf9\u6218": self._challenge,
            "\u63a5\u53d7": self._accept,
            "\u9009\u5361": self._pick_card,
            "\u9009\u9ab0": self._pick_rainbow,
            "\u6295\u63b7": self._roll,
            "\u91cd\u6295": self._reroll,
            "\u9009": self._pick,
            "\u4f7f\u7528\u66dc\u5f69\u9ab0": self._use_rainbow,
            "\u6295\u964d": self._surrender,
        }

    async def _help(self, msg, args):
        await msg.reply(content=HELP_TEXT)

    async def _cards(self, msg, args):
        await msg.reply(content=card_list_text())

    async def _rainbows(self, msg, args):
        await msg.reply(content=rainbow_list_text())

    async def _challenge(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        if gm.get_game(pid, ctx):
            await msg.reply(content="\u4f60\u5df2\u5728\u5bf9\u6218\u4e2d")
            return
        if gm.get_pending(ctx):
            await msg.reply(content="\u5f53\u524d\u5df2\u6709\u5f85\u63a5\u53d7\u7684\u5bf9\u6218")
            return
        gm.create_challenge(pid, ctx)
        await msg.reply(content="\u5bf9\u6218\u623f\u95f4\u5df2\u521b\u5efa\uff01\u7b49\u5f85\u5bf9\u624b\u53d1\u9001\u300c\u63a5\u53d7\u300d")

    async def _accept(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        if gm.get_game(pid, ctx):
            await msg.reply(content="\u4f60\u5df2\u5728\u5bf9\u6218\u4e2d")
            return
        g = gm.accept_challenge(pid, ctx)
        if not g:
            await msg.reply(content="\u6ca1\u6709\u5f85\u63a5\u53d7\u7684\u5bf9\u6218")
            return
        lines = ["\u5bf9\u6218\u5f00\u59cb\uff01\u53cc\u65b9\u8bf7\u9009\u5361\u724c\u548c\u66dc\u5f69\u9ab0", ""]
        lines.append(card_list_text())
        lines.append("")
        lines.append(rainbow_list_text())
        await msg.reply(content=chr(10).join(lines))

    async def _pick_card(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if g:
            _save_msg_ctx(g, pid, msg)
        if not g or g.state != Game.SELECTING:
            await msg.reply(content="\u5f53\u524d\u4e0d\u9700\u8981\u9009\u5361")
            return
        if not args:
            await msg.reply(content="\u683c\u5f0f: \u9009\u5361 \u89d2\u8272\u540d")
            return
        name = args[0]
        result = g.select_card(pid, name)
        if result == "ok":
            c = CARDS[name]
            dt = dice_spec_text(c["dice"])
            await msg.reply(content="\u4f60\u9009\u62e9\u4e86 " + c["emoji"] + " " + name + "  HP:" + str(c["hp"]) + " \u653b:" + str(c["atk_level"]) + " \u9632:" + str(c["def_level"]) + " \u9ab0:" + dt)
            if g.both_selected():
                g.start_battle()
                lines = _format_battle_start(g)
                text = chr(10).join(lines)
                await msg.reply(content=text)
                await _send_to_other(g, pid, text)
        elif result == "invalid_card":
            await msg.reply(content="\u6ca1\u6709\u540d\u4e3a\u300c" + name + "\u300d\u7684\u89d2\u8272")

    async def _pick_rainbow(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if g:
            _save_msg_ctx(g, pid, msg)
        if not g or g.state != Game.SELECTING:
            await msg.reply(content="\u5f53\u524d\u4e0d\u9700\u8981\u9009\u9ab0")
            return
        if not args:
            await msg.reply(content="\u683c\u5f0f: \u9009\u9ab0 \u66dc\u5f69\u9ab0\u540d")
            return
        name = args[0]
        result = g.select_rainbow(pid, name)
        if result == "ok":
            d = RAINBOW_DICE[name]
            await msg.reply(content="\u4f60\u9009\u62e9\u4e86 " + d["emoji"] + " " + name + " - " + d["desc"])
            if g.both_selected():
                g.start_battle()
                lines = _format_battle_start(g)
                text = chr(10).join(lines)
                await msg.reply(content=text)
                await _send_to_other(g, pid, text)
        elif result == "invalid_dice":
            await msg.reply(content="\u6ca1\u6709\u540d\u4e3a\u300c" + name + "\u300d\u7684\u66dc\u5f69\u9ab0")

    async def _roll(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if g:
            _save_msg_ctx(g, pid, msg)
        if not g:
            await msg.reply(content="\u4f60\u4e0d\u5728\u5bf9\u6218\u4e2d")
            return
        result = g.roll(pid)
        if result is None:
            await msg.reply(content="\u5f53\u524d\u4e0d\u662f\u4f60\u7684\u6295\u63b7\u9636\u6bb5")
            return
        if isinstance(result, tuple) and result[0] in ("game_over_thorns", "game_over_turn"):
            _, msgs = result
            lines = [m for m in msgs if m != "GAME_OVER"]
            lines.append("\u8346\u68d8\u51fb\u8d25\uff01" if result[0] == "game_over_thorns" else "\u4e2d\u6bd2\u51fb\u8d25\uff01" + _name(g, g.winner) + " \u83b7\u80dc\uff01")
            await msg.reply(content=chr(10).join(lines))
            gm.remove_game(g)
            return
        _, results, start_msgs = result
        card = g._card(pid)
        role = "\u653b\u51fb" if pid == g.attacker else "\u9632\u5fa1"
        mi = g._mingding_indices()
        if pid == g.attacker:
            n = g._effective_atk(pid) - len(mi)
        else:
            n = g._effective_def(pid) - len(mi)
        n = max(0, n)
        lines = [_battle_status(g), ""]
        if start_msgs:
            for sm in start_msgs:
                if sm != "GAME_OVER":
                    lines.append(sm)
            lines.append("")
        # Get rainbow data for marking special values
        rdata = None
        rinfo = getattr(g, "rainbow_roll_info", {}).get(pid)
        if rinfo:
            rdata = rinfo.get("rdata")
        roll_text = _roll_str(results, rdata)
        lines.append("[" + role + "\u65b9] \u6295\u63b7: " + roll_text)
        if len(mi) > 0:
            lines.append("\u547d\u5b9a\u9ab0\u5b50\u81ea\u52a8\u9009\u5165")
        lines.append("\u9009\u53d6 " + str(n) + " \u4e2a\u9ab0\u5b50")
        if g.max_rerolls > 0:
            lines.append("\u91cd\u6295: " + str(g.rerolls_used) + "/" + str(g.max_rerolls))
        lines.append("")
        lines.append("\u53d1\u9001\u300c\u9009 \u7f16\u53f7...\u300d\u5982: \u9009 1 3 5")
        if g.rerolls_used < g.max_rerolls:
            lines.append("\u6216\u300c\u91cd\u6295\u300d\u91cd\u65b0\u6295\u63b7")
        await msg.reply(content=chr(10).join(lines))
        # Notify other player
        if pid == g.attacker:
            await _send_to_other(g, pid, _name(g, pid) + " \u6295\u63b7\u5b8c\u6210\uff0c\u7b49\u5f85\u9009\u53d6\u9ab0\u5b50...")

    async def _reroll(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="\u4f60\u4e0d\u5728\u5bf9\u6218\u4e2d")
            return
        result = g.reroll(pid)
        if result is None:
            await msg.reply(content="\u5f53\u524d\u4e0d\u53ef\u91cd\u6295")
            return
        if result == "no_rerolls":
            await msg.reply(content="\u91cd\u6295\u6b21\u6570\u5df2\u7528\u5b8c")
            return
        mi = g._mingding_indices()
        if pid == g.attacker:
            n = g._effective_atk(pid) - len(mi)
        else:
            n = g._effective_def(pid) - len(mi)
        n = max(0, n)
        rdata = None
        rinfo = getattr(g, "rainbow_roll_info", {}).get(pid)
        if rinfo:
            rdata = rinfo.get("rdata")
        lines = ["\u91cd\u6295: " + _roll_str(result, rdata)]
        if len(mi) > 0:
            lines.append("\u547d\u5b9a\u9ab0\u5b50\u81ea\u52a8\u9009\u5165")
        lines.append("\u5df2\u91cd\u6295: " + str(g.rerolls_used) + "/" + str(g.max_rerolls))
        lines.append("\u9009\u53d6 " + str(n) + " \u4e2a\u9ab0\u5b50")
        lines.append("\u53d1\u9001\u300c\u9009 \u7f16\u53f7...\u300d")
        if g.rerolls_used < g.max_rerolls:
            lines.append("\u6216\u300c\u91cd\u6295\u300d")
        await msg.reply(content=chr(10).join(lines))

    async def _pick(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if g:
            _save_msg_ctx(g, pid, msg)
        if not g:
            await msg.reply(content="\u4f60\u4e0d\u5728\u5bf9\u6218\u4e2d")
            return
        try:
            indices = [int(x) for x in args]
        except ValueError:
            await msg.reply(content="\u683c\u5f0f: \u9009 \u7f16\u53f7 \u7f16\u53f7 ...\uff08\u5982: \u9009 1 3 5\uff09")
            return
        result = g.select_dice(pid, indices)
        if result is None:
            await msg.reply(content="\u5f53\u524d\u4e0d\u662f\u9009\u53d6\u9636\u6bb5")
            return
        if isinstance(result, tuple) and result[0] == "wrong_count":
            await msg.reply(content="\u9700\u8981\u9009\u53d6 " + str(result[1]) + " \u4e2a\u9ab0\u5b50" + ("\uff08\u547d\u5b9a\u5df2\u81ea\u52a8\u9009\u5165\uff09" if result[2] > 0 else ""))
            return
        if isinstance(result, tuple) and result[0] == "invalid_index":
            await msg.reply(content="\u9ab0\u5b50\u7f16\u53f7\u65e0\u6548")
            return

        if isinstance(result, tuple) and result[0] == "ok_atk":
            _, values, total, dongchuan, heal_msgs, strength, overload, desperation_bonus, ascend_result, value_effect_msgs = result
            vals_str = " + ".join(str(v) for v in values)
            base_sum = sum(values)
            atk_name = _name(g, pid)
            lines = ["=== \u653b\u51fb\u9636\u6bb5 ==="]
            lines.append(atk_name)
            lines.append("  \u9ab0\u5b50: " + vals_str + " = " + str(base_sum))
            if ascend_result:
                lines.append("  \u8dc3\u5347: \u9ab0\u5b50" + str(ascend_result[0]) + "\u53f7 " + str(ascend_result[1]) + " -> " + str(ascend_result[2]))
            for vem in value_effect_msgs:
                lines.append("  " + vem)
            for hm in heal_msgs:
                lines.append("  " + hm)
            if dongchuan:
                lines.append("  \u6d1e\u7a7f\u89e6\u53d1\uff01\u653b\u51fb\u7b49\u7ea7+1")
            bonus_parts = []
            if strength > 0:
                bonus_parts.append("\u529b\u91cf+" + str(strength))
            if overload > 0:
                bonus_parts.append("\u8d85\u8f7d+" + str(overload))
            if desperation_bonus > 0:
                bonus_parts.append("\u80cc\u6c34+" + str(desperation_bonus))
            if bonus_parts:
                lines.append("  \u52a0\u6210: " + " ".join(bonus_parts))
            lines.append("  \u2500\u2500")
            lines.append("  \u653b\u51fb\u503c: " + str(total))
            lines.append("")
            lines.append(_battle_status(g))
            atk_text = chr(10).join(lines)
            await msg.reply(content=atk_text)
            # Send attack result to both players
            await _send_to_other(g, pid, atk_text)
            # Send roll prompt to defender, waiting to attacker
            def_prompt = _name(g, g.defender) + " \u8bf7\u53d1\u9001\u300c\u6295\u63b7\u300d\u5f00\u59cb\u9632\u5fa1"
            await _send_to_other(g, g.defender, def_prompt)
            await msg.reply(content="\u7b49\u5f85\u5bf9\u65b9\u9632\u5fa1...")
            return

        if isinstance(result, tuple) and result[0] == "ok_def":
            (def_values, def_sum, damage, old_hp, new_hp, game_over,
             saint_heal, has_dongchuan, hack_result, heal_msgs, mb_dmg, ov_self_dmg,
             lifesteal_msgs, counter_msgs, reflect_msgs, forcefield_active, round_msgs) = result[1:]
            vals_str = " + ".join(str(v) for v in def_values)
            def_base = sum(def_values)
            atk_name = _name(g, g.attacker)
            def_name = _name(g, pid)

            # === Round effects before resolution ===
            if round_msgs:
                for rm_msg in round_msgs:
                    if rm_msg != "GAME_OVER":
                        lines_round = [rm_msg]

            # === Defense phase ===
            lines = ["=== \u9632\u5fa1\u9636\u6bb5 ==="]
            lines.append(def_name)
            lines.append("  \u9ab0\u5b50: " + vals_str + " = " + str(def_base))
            if hack_result:
                lines.append("  \u9a87\u5165: \u5bf9\u624b\u7b2c" + str(hack_result[0]) + "\u9897 " + str(hack_result[1]) + " -> 2")
            for hm in heal_msgs:
                lines.append("  " + hm)
            toughness = get_stacks(g.effects[pid], TOUGHNESS) if hasattr(g, 'effects') else 0
            if toughness > 0:
                lines.append("  \u52a0\u6210: \u97e7\u6027+" + str(toughness))
            lines.append("  \u2500\u2500")
            lines.append("  \u9632\u5fa1\u503c: " + str(def_sum))

            # === Resolution ===
            lines.append("")
            lines.append("=== \u56de\u5408\u7ed3\u7b97 ===")
            # Show round effects
            if round_msgs:
                for rm_msg in round_msgs:
                    if rm_msg != "GAME_OVER":
                        lines.append("  " + rm_msg)
            if forcefield_active and damage == 0:
                lines.append("  \u529b\u573a\u62b5\u6d88\u4e86\u6240\u6709\u4f24\u5bb3\uff01")
            if has_dongchuan:
                lines.append("  " + atk_name + " [\u6d1e\u7a7f] " + str(g.atk_value) + " vs " + str(def_sum))
                lines.append("  \u4f24\u5bb3: " + str(g.atk_value) + " - " + str(def_sum) + " = " + str(damage) + "\uff08\u65e0\u89c6\u9632\u5fa1\uff09")
            else:
                lines.append("  " + atk_name + " " + str(g.atk_value) + " vs " + def_name + " " + str(def_sum))
                lines.append("  \u4f24\u5bb3: " + str(g.atk_value) + " - " + str(def_sum) + " = " + str(damage))
            extra_dmg = []
            if mb_dmg > 0:
                extra_dmg.append("\u9b54\u5f39\u7729\u4f24+" + str(mb_dmg))
            if ov_self_dmg > 0:
                extra_dmg.append("\u8d85\u8f7d\u81ea\u4f24-" + str(ov_self_dmg))
            if extra_dmg:
                lines.append("  " + " ".join(extra_dmg))
            for hid, healed in saint_heal:
                lines.append("  " + _name(g, hid) + " \u5723\u5149\u6062\u590d " + str(healed) + "HP")
            for lm in lifesteal_msgs:
                lines.append("  " + lm)
            for cm in counter_msgs:
                lines.append("  " + cm)
            for rm in reflect_msgs:
                lines.append("  " + rm)

            # === HP status ===
            lines.append("")
            lines.append("=== \u6218\u51b5 ===")
            p1c = CARDS.get(game.p1_card if hasattr(game, 'p1_card') else g.p1_card, {})
            p2c = CARDS.get(g.p2_card, {})
            m1 = p1c.get("hp", 0)
            m2 = p2c.get("hp", 0)
            n1 = _name(g, g.p1)
            n2 = _name(g, g.p2)
            e1 = g.get_effects_text(g.p1)
            e2 = g.get_effects_text(g.p2)
            hp1_str = n1 + "  HP: " + str(g._hp(g.p1)) + "/" + str(m1)
            hp2_str = n2 + "  HP: " + str(g._hp(g.p2)) + "/" + str(m2)
            if e1 != "\u65e0":
                hp1_str += "  [" + e1 + "]"
            if e2 != "\u65e0":
                hp2_str += "  [" + e2 + "]"
            lines.append(hp1_str)
            lines.append(hp2_str)

            if game_over:
                lines.append("")
                lines.append("\u6e38\u620f\u7ed3\u675f\uff01" + _name(g, g.winner) + " \u83b7\u80dc\uff01")
                result_text = chr(10).join(lines)
                await msg.reply(content=result_text)
                await _send_to_other(g, pid, result_text)
                gm.remove_game(g)
            else:
                lines.append("")
                lines.append("\u4e0b\u4e00\u56de\u5408: " + _name(g, g.attacker) + " \u653b\u51fb")
                result_text = chr(10).join(lines)
                await msg.reply(content=result_text)
                await _send_to_other(g, pid, result_text)
            return

    async def _use_rainbow(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="\u4f60\u4e0d\u5728\u5bf9\u6218\u4e2d")
            return
        result = g.use_rainbow(pid)
        if result == "no_uses":
            await msg.reply(content="\u66dc\u5f69\u9ab0\u4f7f\u7528\u6b21\u6570\u5df2\u7528\u5b8c")
            return
        if result == "no_dice":
            await msg.reply(content="\u4f60\u8fd8\u6ca1\u6709\u9009\u62e9\u66dc\u5f69\u9ab0")
            return
        rn = g._rainbow_name(pid)
        d = RAINBOW_DICE.get(rn, {})
        emoji = d.get("emoji", "")
        remaining = g._rainbow_uses(pid)
        if isinstance(result, tuple) and result[0] == "too_late":
            await msg.reply(content=rn + " \u53ea\u80fd\u5728\u524d" + str(result[1]) + "\u56de\u5408\u4f7f\u7528")
            return
        if isinstance(result, tuple) and result[0] == "wrong_phase":
            phase = result[1]
            phase_text = "\u653b\u51fb" if phase == "atk" else "\u9632\u5fa1"
            await msg.reply(content=rn + " \u53ea\u80fd\u5728" + phase_text + "\u65f6\u4f7f\u7528")
            return
        if isinstance(result, tuple) and result[0] == "condition_not_met":
            await msg.reply(content=rn + " \u7684\u4f7f\u7528\u6761\u4ef6\u672a\u8fbe\u6807")
            return
        if isinstance(result, tuple) and result[0] == "activated":
            _, rname, rdata = result
            desc = rdata.get("desc", "")
            await msg.reply(content=emoji + " \u4f7f\u7528" + rname + "\uff01\n" + desc + "\n\u5269\u4f59\u6b21\u6570: " + str(remaining))

    async def _surrender(self, msg, args):
        pid = get_user_id(msg)
        ctx = _ctx(msg)
        g = gm.get_game(pid, ctx)
        if not g:
            await msg.reply(content="\u4f60\u4e0d\u5728\u5bf9\u6218\u4e2d")
            return
        g.surrender(pid)
        await msg.reply(content="\u4f60\u6295\u964d\u4e86\uff01" + _name(g, g.winner) + " \u83b7\u80dc\uff01")
        gm.remove_game(g)
