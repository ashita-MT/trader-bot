"""Game state machine and battle logic - v2 with mixed dice, dongchuan, mingding."""
import random
from .data import CARDS, RAINBOW_DICE

# In-memory game storage
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
        self.roll_results = []  # list of {value, type, mingding, label}
        self.rerolls_used = 0
        self.max_rerolls = 2
        self.atk_value = 0
        self.winner = None
        # 洞穿 permanent bonus per player
        self.dongchuan_bonus = {p1: 0, p2: 0}
        # 命定 pending: {pid: faces_list or None}
        self.mingding_pending = {p1: None, p2: None}
        # Silence flag
        self.silenced = {p1: False, p2: False}

    def _other(self, pid):
        return self.p2 if pid == self.p1 else self.p1

    def _card(self, pid):
        name = self.p1_card if pid == self.p1 else self.p2_card
        return CARDS[name] if name else None

    def _card_name(self, pid):
        return self.p1_card if pid == self.p1 else self.p2_card

    def _hp(self, pid):
        return self.p1_hp if pid == self.p1 else self.p2_hp

    def _set_hp(self, pid, val):
        if pid == self.p1: self.p1_hp = val
        else: self.p2_hp = val

    def _rainbow_uses(self, pid):
        return self.p1_rainbow_uses if pid == self.p1 else self.p2_rainbow_uses

    def _rainbow_name(self, pid):
        return self.p1_rainbow if pid == self.p1 else self.p2_rainbow

    def _use_rainbow(self, pid):
        if pid == self.p1: self.p1_rainbow_uses -= 1
        else: self.p2_rainbow_uses -= 1

    def _effective_atk(self, pid):
        card = self._card(pid)
        return card["atk_level"] + self.dongchuan_bonus[pid]

    def _roll_dice(self, pid):
        """Roll all dice for a player, including 命定 if pending."""
        card = self._card(pid)
        results = []
        for spec in card["dice"]:
            for _ in range(spec["count"]):
                val = random.randint(1, spec["type"])
                results.append({"value": val, "type": spec["type"], "mingding": False, "label": ""})
        # Add 命定 die if pending
        rdata = self.mingding_pending.get(pid)
        if rdata:
            faces = rdata["faces"]
            val = random.choice(faces)
            md = rdata.get("mingding", False)
            label = "命运" if md else ""
            results.append({"value": val, "type": 0, "mingding": md, "label": label})
            self.mingding_pending[pid] = None
        return results

    def accept(self):
        if self.state != self.WAITING: return False
        self.state = self.SELECTING
        return True

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
        if random.random() < 0.5:
            self.attacker, self.defender = self.p1, self.p2
        else:
            self.attacker, self.defender = self.p2, self.p1
        self.round_num = 1
        self.state = self.ATK_ROLL

    def roll(self, pid):
        if self.state == self.ATK_ROLL and pid == self.attacker:
            self.max_rerolls = 2
            self.rerolls_used = 0
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
        """Return set of indices that are 命定."""
        return {i for i, r in enumerate(self.roll_results) if r["mingding"]}

    def select_dice(self, pid, indices):
        """Select dice by 1-based indices."""
        mi = self._mingding_indices()
        if self.state == self.ATK_SELECT and pid == self.attacker:
            n = self._effective_atk(pid)
            # 命定 dice are auto-included, player picks the rest
            mingding_count = len(mi)
            need_pick = max(0, n - mingding_count)
            # Filter out 命定 from player selection
            player_indices = [i for i in indices if (i-1) not in mi]
            if len(player_indices) != need_pick:
                return ("wrong_count", need_pick, mingding_count)
            all_indices = set(indices) | {(i+1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_indices):
                return ("invalid_index",)
            if len(all_indices) != len(set(all_indices)):
                return ("duplicate",)
            values = [self.roll_results[i-1]["value"] for i in sorted(all_indices)]
            total = sum(values)
            # Check 洞穿: all selected == 4
            dongchuan = all(v == 4 for v in values)
            if dongchuan:
                self._pending_dongchuan = True
            bonus = 0
            if dongchuan:
                self.dongchuan_bonus[pid] += 1
            self.atk_value = total
            self.state = self.DEF_ROLL
            return ("ok_atk", values, total, dongchuan)
        elif self.state == self.DEF_SELECT and pid == self.defender:
            card = self._card(pid)
            n = card["def_level"]
            atk_card = self._card(self.attacker)
            if atk_card["skill"] == "穿透":
                n = max(1, n - 1)
            mingding_count = len(mi)
            need_pick = max(0, n - mingding_count)
            player_indices = [i for i in indices if (i-1) not in mi]
            if len(player_indices) != need_pick:
                return ("wrong_count", need_pick, mingding_count)
            all_indices = set(indices) | {(i+1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_indices):
                return ("invalid_index",)
            values = [self.roll_results[i-1]["value"] for i in sorted(all_indices)]
            def_sum = sum(values)
            return self._resolve(pid, values, def_sum)
        return None

    def _resolve(self, def_pid, def_values, def_sum):
        atk_card = self._card(self.attacker)
        def_card = self._card(def_pid)
        # Check if attacker has 洞穿 from this attack
        # 洞穿 is checked in select_dice, stored temporarily
        has_dongchuan = getattr(self, "_pending_dongchuan", False)
        self._pending_dongchuan = False
        if has_dongchuan:
            damage = self.atk_value
        else:
            damage = max(0, self.atk_value - def_sum)
            if def_card["skill"] == "坚守":
                damage = max(0, damage - 2)
        if atk_card["skill"] == "暗影" and self.atk_value > 12 and not has_dongchuan:
            damage *= 2
        old_hp = self._hp(def_pid)
        new_hp = max(0, old_hp - damage)
        self._set_hp(def_pid, new_hp)
        game_over = new_hp <= 0
        if game_over:
            self.state = self.FINISHED
            self.winner = self.attacker
        # 圣光 heal
        heal_info = []
        for pid in [self.p1, self.p2]:
            c = self._card(pid)
            if c["skill"] == "圣光":
                mx = CARDS[self._card_name(pid)]["hp"]
                cur = self._hp(pid)
                if cur > 0 and cur < mx:
                    h = min(3, mx - cur)
                    self._set_hp(pid, cur + h)
                    heal_info.append((pid, h))
        if not game_over:
            self.attacker, self.defender = self.defender, self.attacker
            self.round_num += 1
            self.state = self.ATK_ROLL
        return ("ok_def", def_values, def_sum, damage, old_hp, new_hp, game_over, heal_info, has_dongchuan)

    def use_rainbow(self, pid):
        if self.silenced[pid]: return "silenced"
        if self._rainbow_uses(pid) <= 0: return "no_uses"
        rname = self._rainbow_name(pid)
        if not rname: return "no_dice"
        rdata = RAINBOW_DICE[rname]
        max_round = rdata.get("max_round")
        if max_round and self.round_num > max_round:
            return ("too_late", max_round)
        self._use_rainbow(pid)
        opp = self._other(pid)
        if "faces" in rdata:
            # 真·命运: add 命定 die to next roll
            self.mingding_pending[pid] = rdata
            return ("mingding", rname, rdata)
        return "unknown"

    def surrender(self, pid):
        self.state = self.FINISHED
        self.winner = self._other(pid)


# === Public API ===
def create_challenge(challenger, ctx):
    _pending[ctx] = challenger

def get_pending(ctx):
    return _pending.get(ctx)

def accept_challenge(acceptor, ctx):
    challenger = _pending.pop(ctx, None)
    if not challenger or challenger == acceptor: return None
    gk = (ctx, min(challenger, acceptor), max(challenger, acceptor))
    g = Game(challenger, acceptor, ctx)
    g.accept()
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

def _game_key(p1, p2, ctx):
    return (ctx, min(p1, p2), max(p1, p2))
