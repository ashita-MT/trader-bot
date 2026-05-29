"""Game state machine and battle logic."""
import random
from .data import CARDS, RAINBOW_DICE, DICE_NAMES

# In-memory game storage
_pending = {}   # context_id -> challenger_id
_games = {}     # game_key -> Game
_player_idx = {}  # (context_id, player_id) -> game_key


class Game:
    WAITING = "waiting"
    SELECTING = "selecting"
    ATK_ROLL = "atk_roll"
    ATK_SELECT = "atk_select"
    DEF_ROLL = "def_roll"
    DEF_SELECT = "def_select"
    FINISHED = "finished"

    def __init__(self, p1, p2, ctx):
        self.p1 = p1
        self.p2 = p2
        self.ctx = ctx
        self.state = self.WAITING
        self.p1_card = None
        self.p2_card = None
        self.p1_rainbow = None
        self.p2_rainbow = None
        self.p1_hp = 0
        self.p2_hp = 0
        self.p1_rainbow_uses = 2
        self.p2_rainbow_uses = 2
        self.attacker = None
        self.defender = None
        self.round_num = 0
        self.roll_results = []
        self.rerolls_used = 0
        self.max_rerolls = 2
        self.atk_value = 0
        self.winner = None
        # effects: per-player dict
        self.effects = {p1: {}, p2: {}}
        # 战士 iron wall flag
        self.iron_wall = {p1: False, p2: False}
        # 暗曜 silence flag
        self.silenced = {p1: False, p2: False}

    def _other(self, pid):
        return self.p2 if pid == self.p1 else self.p1

    def _card(self, pid):
        name = self.p1_card if pid == self.p1 else self.p2_card
        return CARDS[name] if name else None

    def _hp(self, pid):
        return self.p1_hp if pid == self.p1 else self.p2_hp

    def _set_hp(self, pid, val):
        if pid == self.p1:
            self.p1_hp = val
        else:
            self.p2_hp = val

    def _rainbow_uses(self, pid):
        return self.p1_rainbow_uses if pid == self.p1 else self.p2_rainbow_uses

    def _use_rainbow_count(self, pid):
        if pid == self.p1:
            self.p1_rainbow_uses -= 1
        else:
            self.p2_rainbow_uses -= 1

    def accept(self):
        if self.state != self.WAITING:
            return False
        self.state = self.SELECTING
        return True

    def select_card(self, pid, card_name):
        if self.state != self.SELECTING:
            return "not_selecting"
        if card_name not in CARDS:
            return "invalid_card"
        if pid == self.p1:
            self.p1_card = card_name
        elif pid == self.p2:
            self.p2_card = card_name
        else:
            return "not_player"
        return "ok"

    def select_rainbow(self, pid, dice_name):
        if self.state != self.SELECTING:
            return "not_selecting"
        if dice_name not in RAINBOW_DICE:
            return "invalid_dice"
        if pid == self.p1:
            self.p1_rainbow = dice_name
        elif pid == self.p2:
            self.p2_rainbow = dice_name
        else:
            return "not_player"
        return "ok"

    def both_selected(self):
        return all([self.p1_card, self.p2_card, self.p1_rainbow, self.p2_rainbow])

    def start_battle(self):
        self.p1_hp = CARDS[self.p1_card]["hp"]
        self.p2_hp = CARDS[self.p2_card]["hp"]
        if random.random() < 0.5:
            self.attacker, self.defender = self.p1, self.p2
        else:
            self.attacker, self.defender = self.p2, self.p1
        self.round_num = 1
        self.state = self.ATK_ROLL

    def roll(self, pid):
        if self.state == self.ATK_ROLL and pid == self.attacker:
            card = self._card(pid)
            extra = self.effects[pid].get("extra_rerolls", 0)
            self.max_rerolls = 2 + extra
            self.rerolls_used = 0
            self.roll_results = [random.randint(1, card["dice_type"]) for _ in range(card["dice_count"])]
            self.state = self.ATK_SELECT
            return self.roll_results
        elif self.state == self.DEF_ROLL and pid == self.defender:
            card = self._card(pid)
            self.roll_results = [random.randint(1, card["dice_type"]) for _ in range(card["dice_count"])]
            self.rerolls_used = 0
            # 法师 魔导: defender gets 1 reroll
            if card["skill"] == "魔导":
                self.max_rerolls = 1
            else:
                self.max_rerolls = 0
            self.state = self.DEF_SELECT
            return self.roll_results
        return None

    def reroll(self, pid):
        if self.state == self.ATK_SELECT and pid == self.attacker:
            if self.rerolls_used >= self.max_rerolls:
                return "no_rerolls"
            card = self._card(pid)
            self.roll_results = [random.randint(1, card["dice_type"]) for _ in range(card["dice_count"])]
            self.rerolls_used += 1
            return self.roll_results
        elif self.state == self.DEF_SELECT and pid == self.defender:
            if self.rerolls_used >= self.max_rerolls:
                return "no_rerolls"
            card = self._card(pid)
            self.roll_results = [random.randint(1, card["dice_type"]) for _ in range(card["dice_count"])]
            self.rerolls_used += 1
            return self.roll_results
        return None

    def select_dice(self, pid, indices):
        """Select dice by 1-based indices. Returns (values, sum, extra_info) or error string."""
        if self.state == self.ATK_SELECT and pid == self.attacker:
            card = self._card(pid)
            n = card["atk_level"]
            if len(indices) != n:
                return ("wrong_count", n)
            if any(i < 1 or i > len(self.roll_results) for i in indices):
                return ("invalid_index",)
            if len(set(indices)) != len(indices):
                return ("duplicate",)
            values = sorted([self.roll_results[i-1] for i in indices], reverse=True)
            base = sum(values)
            bonus = 0
            # 铁壁
            if self.iron_wall[pid]:
                bonus += 2
                self.iron_wall[pid] = False
            # 炎曜骰
            bonus += self.effects[pid].get("atk_bonus", 0)
            self.effects[pid]["atk_bonus"] = 0
            # 冰曜骰 (set by defender)
            reduction = self.effects[self._other(pid)].get("atk_reduction", 0)
            self.effects[self._other(pid)]["atk_reduction"] = 0
            self.atk_value = max(0, base + bonus - reduction)
            self.state = self.DEF_ROLL
            return ("ok", values, base, bonus, reduction, self.atk_value)
        elif self.state == self.DEF_SELECT and pid == self.defender:
            card = self._card(pid)
            n = card["def_level"]
            # 穿透: attacker reduces def selection by 1
            atk_card = self._card(self.attacker)
            if atk_card["skill"] == "穿透":
                n = max(1, n - 1)
            if len(indices) != n:
                return ("wrong_count", n)
            if any(i < 1 or i > len(self.roll_results) for i in indices):
                return ("invalid_index",)
            if len(set(indices)) != len(indices):
                return ("duplicate",)
            values = sorted([self.roll_results[i-1] for i in indices], reverse=True)
            def_sum = sum(values)
            return self._resolve_combat(pid, values, def_sum)
        return None

    def _resolve_combat(self, def_pid, def_values, def_sum):
        damage = max(0, self.atk_value - def_sum)
        def_card = self._card(def_pid)
        atk_card = self._card(self.attacker)
        # 骑士 坚守
        if def_card["skill"] == "坚守":
            damage = max(0, damage - 2)
        # 刺客 暗影
        if atk_card["skill"] == "暗影" and self.atk_value > 12:
            damage *= 2
        old_hp = self._hp(def_pid)
        new_hp = max(0, old_hp - damage)
        self._set_hp(def_pid, new_hp)
        # 铁壁: set flag for defender
        if def_card["skill"] == "铁壁":
            self.iron_wall[def_pid] = True
        game_over = new_hp <= 0
        if game_over:
            self.state = self.FINISHED
            self.winner = self.attacker
        # 牧师 圣光 heal
        heal_info = []
        for pid in [self.p1, self.p2]:
            c = self._card(pid)
            if c["skill"] == "圣光":
                max_hp = CARDS[self.p1_card if pid == self.p1 else self.p2_card]["hp"]
                cur = self._hp(pid)
                if cur > 0 and cur < max_hp:
                    healed = min(3, max_hp - cur)
                    self._set_hp(pid, cur + healed)
                    heal_info.append((pid, healed))
        if not game_over:
            self.attacker, self.defender = self.defender, self.attacker
            self.round_num += 1
            self.effects = {self.p1: {}, self.p2: {}}
            self.state = self.ATK_ROLL
        return ("ok", def_values, def_sum, damage, old_hp, new_hp, game_over, heal_info)

    def use_rainbow(self, pid):
        if self.silenced[pid]:
            return "silenced"
        uses = self._rainbow_uses(pid)
        if uses <= 0:
            return "no_uses"
        rname = self.p1_rainbow if pid == self.p1 else self.p2_rainbow
        if not rname:
            return "no_dice"
        self._use_rainbow_count(pid)
        opp = self._other(pid)
        if rname == "炎曜骰":
            self.effects[pid]["atk_bonus"] = self.effects[pid].get("atk_bonus", 0) + 3
            return ("fire",)
        elif rname == "冰曜骰":
            self.effects[opp]["atk_reduction"] = self.effects[opp].get("atk_reduction", 0) + 3
            return ("ice",)
        elif rname == "雷曜骰":
            old = self._hp(opp)
            new_hp = max(0, old - 5)
            self._set_hp(opp, new_hp)
            if new_hp <= 0:
                self.state = self.FINISHED
                self.winner = pid
                return ("thunder", old, new_hp, True)
            return ("thunder", old, new_hp, False)
        elif rname == "风曜骰":
            self.effects[pid]["extra_rerolls"] = self.effects[pid].get("extra_rerolls", 0) + 1
            return ("wind",)
        elif rname == "光曜骰":
            max_hp = CARDS[self.p1_card if pid == self.p1 else self.p2_card]["hp"]
            cur = self._hp(pid)
            healed = min(5, max_hp - cur)
            self._set_hp(pid, min(max_hp, cur + healed))
            return ("light", cur, cur + healed)
        elif rname == "暗曜骰":
            self.silenced[opp] = True
            return ("dark",)
        return "unknown"

    def surrender(self, pid):
        self.state = self.FINISHED
        self.winner = self._other(pid)
        return True


# === Public API ===

def create_challenge(challenger, ctx):
    _pending[ctx] = challenger
    return True

def get_pending(ctx):
    return _pending.get(ctx)

def accept_challenge(acceptor, ctx):
    challenger = _pending.pop(ctx, None)
    if not challenger or challenger == acceptor:
        return None
    gk = _game_key(challenger, acceptor, ctx)
    g = Game(challenger, acceptor, ctx)
    g.accept()
    g.state = Game.SELECTING
    _games[gk] = g
    _player_idx[(ctx, challenger)] = gk
    _player_idx[(ctx, acceptor)] = gk
    return g

def get_game(pid, ctx):
    gk = _player_idx.get((ctx, pid))
    if gk:
        return _games.get(gk)
    return None

def remove_game(game):
    gk = _player_idx.get((game.ctx, game.p1))
    if gk:
        _games.pop(gk, None)
        _player_idx.pop((game.ctx, game.p1), None)
        _player_idx.pop((game.ctx, game.p2), None)

def _game_key(p1, p2, ctx):
    return (ctx, min(p1, p2), max(p1, p2))
