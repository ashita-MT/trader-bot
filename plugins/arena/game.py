"""Game state machine v3 - with rainbow dice effect system."""
import random
from .data import CARDS, RAINBOW_DICE

_pending = {}
_games = {}
_player_idx = {}


class Game:
    WAITING = "waiting"
    SELECTING = "selecting"
    ATK_ROLL = "atk_roll"
    ATK_SELECT = "atk_select"
    DEF_ROLL = "def_roll"
    DEF_SELECT = "def_select"
    FINISHED = "finished"

    def __init__(self, p1, p2, ctx):
        self.p1 = p1; self.p2 = p2; self.ctx = ctx
        self.state = self.WAITING
        self.p1_card = None; self.p2_card = None
        self.p1_rainbow = None; self.p2_rainbow = None
        self.p1_hp = 0; self.p2_hp = 0
        self.p1_rainbow_uses = 2; self.p2_rainbow_uses = 2
        self.attacker = None; self.defender = None
        self.round_num = 0
        self.roll_results = []
        self.rerolls_used = 0; self.max_rerolls = 2
        self.atk_value = 0; self.winner = None
        self.dongchuan_bonus = {p1: 0, p2: 0}
        self.mingding_pending = {p1: None, p2: None}
        self.silenced = {p1: False, p2: False}
        # Rainbow effect state
        self.heal_stacks = {p1: 0, p2: 0}
        self.overload_stacks = {p1: 0, p2: 0}
        self.thorn_stacks = {p1: 0, p2: 0}
        self.hack_active = {p1: False, p2: False}
        self.evolution_active = {p1: False, p2: False}
        self.magic_bullet_pending = {p1: False, p2: False}
        self.pending_3_damage = 0  # magic bullet damage to apply

    def _other(self, pid): return self.p2 if pid == self.p1 else self.p1
    def _card(self, pid):
        name = self.p1_card if pid == self.p1 else self.p2_card
        return CARDS[name] if name else None
    def _card_name(self, pid): return self.p1_card if pid == self.p1 else self.p2_card
    def _hp(self, pid): return self.p1_hp if pid == self.p1 else self.p2_hp
    def _set_hp(self, pid, val):
        if pid == self.p1: self.p1_hp = val
        else: self.p2_hp = val
    def _rainbow_uses(self, pid): return self.p1_rainbow_uses if pid == self.p1 else self.p2_rainbow_uses
    def _rainbow_name(self, pid): return self.p1_rainbow if pid == self.p1 else self.p2_rainbow
    def _use_rainbow_count(self, pid):
        if pid == self.p1: self.p1_rainbow_uses -= 1
        else: self.p2_rainbow_uses -= 1
    def _effective_atk(self, pid):
        return self._card(pid)["atk_level"] + self.dongchuan_bonus[pid]

    def _roll_dice(self, pid):
        card = self._card(pid)
        results = []
        for spec in card["dice"]:
            for _ in range(spec["count"]):
                val = random.randint(1, spec["type"])
                results.append({"value": val, "type": spec["type"], "mingding": False, "label": ""})
        rdata = self.mingding_pending.get(pid)
        if rdata:
            faces = rdata["faces"]
            val = random.choice(faces)
            md = rdata.get("mingding", False)
            label = "命运" if md else ""
            results.append({"value": val, "type": 0, "mingding": md, "label": label, "rainbow_val": val})
            self._apply_rainbow_effect(pid, rdata, val)
            self.mingding_pending[pid] = None
        return results

    def _apply_rainbow_effect(self, pid, rdata, val):
        """Apply rainbow die effect based on rolled value."""
        effect = rdata.get("effect", "none")
        msgs = []
        if effect == "evolution":
            if val == 2:
                self.evolution_active[pid] = True
                msgs.append("真·进化触发！本次攻击/防御值翻倍")
        elif effect == "heal":
            self.heal_stacks[pid] += val
            msgs.append("真·医嘱：获得" + str(val) + "层治愈")
        elif effect == "overload":
            self.overload_stacks[pid] += val
            msgs.append("真·贷款：获得" + str(val) + "层超载")
        elif effect == "hack":
            triggered = False
            if val == 6:
                triggered = True
            elif val == 4:
                triggered = random.random() < 0.25
            if triggered:
                self.hack_active[pid] = True
                msgs.append("真·奇术师触发！获得骇入")
        elif effect == "heartbeat":
            if val == 9:
                if pid == self.p1: self.p1_rainbow_uses += 1
                else: self.p2_rainbow_uses += 1
                msgs.append("真·心跳触发！+1曜彩骰使用次数")
        elif effect == "thorns":
            if val == 8:
                self.thorn_stacks[pid] += 2
                msgs.append("真·战狂：+2荆棘")
            elif val == 12:
                self.thorn_stacks[pid] += 3
                msgs.append("真·战狂：+3荆棘")
        elif effect == "magic_bullet":
            self.magic_bullet_pending[pid] = True
            msgs.append("真·魔弹待发")
        return msgs

    def _apply_thorns(self, pid):
        """Apply thorn damage at turn start."""
        ts = self.thorn_stacks.get(pid, 0)
        if ts > 0:
            old = self._hp(pid)
            self._set_hp(pid, max(0, old - ts))
            self.thorn_stacks[pid] = 0
            return (ts, old, self._hp(pid))
        return None

    def accept(self):
        if self.state != self.WAITING: return False
        self.state = self.SELECTING; return True

    def select_card(self, pid, card_name):
        if self.state != self.SELECTING: return "not_selecting"
        if card_name not in CARDS: return "invalid_card"
        if pid == self.p1: self.p1_card = card_name
        elif pid == self.p2: self.p2_card = card_name
        else: return "not_player"
        return "ok"

    def select_rainbow(self, pid, dice_name):
        if self.state != self.SELECTING: return "not_selecting"
        if dice_name not in RAINBOW_DICE: return "invalid_dice"
        if pid == self.p1: self.p1_rainbow = dice_name
        elif pid == self.p2: self.p2_rainbow = dice_name
        else: return "not_player"
        return "ok"

    def both_selected(self):
        return all([self.p1_card, self.p2_card, self.p1_rainbow, self.p2_rainbow])

    def start_battle(self):
        self.p1_hp = CARDS[self.p1_card]["hp"]
        self.p2_hp = CARDS[self.p2_card]["hp"]
        if random.random() < 0.5: self.attacker, self.defender = self.p1, self.p2
        else: self.attacker, self.defender = self.p2, self.p1
        self.round_num = 1; self.state = self.ATK_ROLL

    def roll(self, pid):
        if self.state == self.ATK_ROLL and pid == self.attacker:
            # Apply thorns at turn start
            self.max_rerolls = 2; self.rerolls_used = 0
            self.roll_results = self._roll_dice(pid)
            self.state = self.ATK_SELECT
            return self.roll_results
        elif self.state == self.DEF_ROLL and pid == self.defender:
            card = self._card(pid)
            self.max_rerolls = 1 if card["skill"] == "魔导" else 0
            self.rerolls_used = 0
            self.roll_results = self._roll_dice(pid)
            self.state = self.DEF_SELECT
            return self.roll_results
        return None

    def reroll(self, pid):
        can = False
        if self.state == self.ATK_SELECT and pid == self.attacker: can = True
        elif self.state == self.DEF_SELECT and pid == self.defender: can = True
        if not can: return None
        if self.rerolls_used >= self.max_rerolls: return "no_rerolls"
        self.roll_results = self._roll_dice(pid)
        self.rerolls_used += 1
        return self.roll_results

    def _mingding_indices(self):
        return {i for i, r in enumerate(self.roll_results) if r["mingding"]}

    def _apply_hack(self, defender_pid):
        """Change opponent highest non-rainbow die to 2."""
        if not self.hack_active.get(defender_pid, False): return None
        # Find highest non-rainbow die in defender roll
        best_idx = -1; best_val = -1
        for i, r in enumerate(self.roll_results):
            if not r.get("rainbow_val") and r["value"] > best_val:
                best_val = r["value"]; best_idx = i
        if best_idx >= 0 and best_val > 2:
            self.roll_results[best_idx]["value"] = 2
            self.hack_active[defender_pid] = False
            return (best_idx + 1, best_val)
        self.hack_active[defender_pid] = False
        return None

    def select_dice(self, pid, indices):
        mi = self._mingding_indices()
        if self.state == self.ATK_SELECT and pid == self.attacker:
            n = self._effective_atk(pid)
            mc = len(mi); need = max(0, n - mc)
            pi = [i for i in indices if (i-1) not in mi]
            if len(pi) != need: return ("wrong_count", need, mc)
            all_idx = set(indices) | {(i+1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_idx): return ("invalid_index",)
            values = [self.roll_results[i-1]["value"] for i in sorted(all_idx)]
            total = sum(values)
            dongchuan = all(v == 4 for v in values)
            if dongchuan:
                self.dongchuan_bonus[pid] += 1
                self._pending_dongchuan = True
            # Apply heal
            heal_msgs = self._consume_heal(pid)
            # Apply evolution
            if self.evolution_active.get(pid):
                total *= 2; self.evolution_active[pid] = False
            # Apply overload (attack)
            ov = self.overload_stacks.get(pid, 0)
            if ov > 0:
                total += ov
            self.atk_value = total
            self.state = self.DEF_ROLL
            return ("ok_atk", values, total, dongchuan, heal_msgs, ov)
        elif self.state == self.DEF_SELECT and pid == self.defender:
            card = self._card(pid)
            n = card["def_level"]
            atk_card = self._card(self.attacker)
            if atk_card["skill"] == "穿透": n = max(1, n - 1)
            mc = len(mi); need = max(0, n - mc)
            pi = [i for i in indices if (i-1) not in mi]
            if len(pi) != need: return ("wrong_count", need, mc)
            all_idx = set(indices) | {(i+1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_idx): return ("invalid_index",)
            values = [self.roll_results[i-1]["value"] for i in sorted(all_idx)]
            def_sum = sum(values)
            # Apply hack (change attacker highest die)
            hack_result = self._apply_hack(pid)
            # Re-read values if hack changed them
            if hack_result:
                values = [self.roll_results[i-1]["value"] for i in sorted(all_idx)]
                def_sum = sum(values)
            # Apply heal
            heal_msgs = self._consume_heal(pid)
            # Apply evolution
            if self.evolution_active.get(pid):
                def_sum *= 2; self.evolution_active[pid] = False
            # Apply overload (defense: self damage)
            ov = self.overload_stacks.get(pid, 0)
            ov_self_dmg = 0
            if ov > 0:
                ov_self_dmg = ov // 2
            return self._resolve(pid, values, def_sum, hack_result, heal_msgs, ov_self_dmg)
        return None

    def _consume_heal(self, pid):
        hs = self.heal_stacks.get(pid, 0)
        msgs = []
        if hs > 0:
            mx = CARDS[self._card_name(pid)]["hp"]
            cur = self._hp(pid)
            healed = min(hs, mx - cur)
            if healed > 0:
                self._set_hp(pid, cur + healed)
                msgs.append("治愈恢复" + str(healed) + "HP")
            self.heal_stacks[pid] = 0
        return msgs

    def _resolve(self, def_pid, def_values, def_sum, hack_result, heal_msgs, ov_self_dmg):
        atk_card = self._card(self.attacker)
        def_card = self._card(def_pid)
        has_dongchuan = getattr(self, "_pending_dongchuan", False)
        self._pending_dongchuan = False
        if has_dongchuan:
            damage = self.atk_value
        else:
            damage = max(0, self.atk_value - def_sum)
            if def_card["skill"] == "坚守": damage = max(0, damage - 2)
        if atk_card["skill"] == "暗影" and self.atk_value > 12 and not has_dongchuan:
            damage *= 2
        # Magic bullet: 3 damage to defender
        mb_dmg = 0
        if self.magic_bullet_pending.get(self.attacker):
            mb_dmg = 3; self.magic_bullet_pending[self.attacker] = False
        total_damage = damage + mb_dmg
        # Overload self damage
        if ov_self_dmg > 0:
            old_self = self._hp(def_pid)
            self._set_hp(def_pid, max(0, self._hp(def_pid) - ov_self_dmg))
        old_hp = self._hp(def_pid)
        new_hp = max(0, old_hp - total_damage)
        self._set_hp(def_pid, new_hp)
        game_over = new_hp <= 0
        if game_over:
            self.state = self.FINISHED; self.winner = self.attacker
        # 圣光 heal
        saint_heal = []
        for pid in [self.p1, self.p2]:
            c = self._card(pid)
            if c["skill"] == "圣光":
                mx = CARDS[self._card_name(pid)]["hp"]
                cur = self._hp(pid)
                if cur > 0 and cur < mx:
                    h = min(3, mx - cur); self._set_hp(pid, cur + h)
                    saint_heal.append((pid, h))
        if not game_over:
            self.attacker, self.defender = self.defender, self.attacker
            self.round_num += 1
            # Apply thorns to new attacker at turn start
            thorn_result = self._apply_thorns(self.attacker)
            if thorn_result and self._hp(self.attacker) <= 0:
                self.state = self.FINISHED; self.winner = self.defender
                game_over = True
            self.state = self.ATK_ROLL
        # Clear overload after use
        self.overload_stacks[self.attacker if not game_over else self.p1] = 0
        return ("ok_def", def_values, def_sum, damage, old_hp, new_hp, game_over, saint_heal, has_dongchuan, hack_result, heal_msgs, mb_dmg, ov_self_dmg)

    def use_rainbow(self, pid):
        if self.silenced[pid]: return "silenced"
        if self._rainbow_uses(pid) <= 0: return "no_uses"
        rname = self._rainbow_name(pid)
        if not rname: return "no_dice"
        rdata = RAINBOW_DICE[rname]
        max_round = rdata.get("max_round")
        if max_round and self.round_num > max_round:
            return ("too_late", max_round)
        self._use_rainbow_count(pid)
        opp = self._other(pid)
        if "faces" in rdata:
            self.mingding_pending[pid] = rdata
            return ("activated", rname, rdata)
        return "unknown"

    def surrender(self, pid):
        self.state = self.FINISHED; self.winner = self._other(pid)


def create_challenge(challenger, ctx): _pending[ctx] = challenger
def get_pending(ctx): return _pending.get(ctx)

def accept_challenge(acceptor, ctx):
    challenger = _pending.pop(ctx, None)
    if not challenger or challenger == acceptor: return None
    gk = (ctx, min(challenger, acceptor), max(challenger, acceptor))
    g = Game(challenger, acceptor, ctx); g.accept()
    _games[gk] = g
    _player_idx[(ctx, challenger)] = gk
    _player_idx[(ctx, acceptor)] = gk
    return g

def get_game(pid, ctx):
    gk = _player_idx.get((ctx, pid))
    return _games.get(gk) if gk else None

def remove_game(game):
    gk = _player_idx.get((game.ctx, game.p1))
    if gk:
        _games.pop(gk, None)
        _player_idx.pop((game.ctx, game.p1), None)
        _player_idx.pop((game.ctx, game.p2), None)
