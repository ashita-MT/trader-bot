"""Game state machine v4 - unified effect system."""
import random, string
from .data import CARDS, RAINBOW_DICE
from .effects import (
    EFFECTS, new_effects, add_effect, remove_effect,
    has_effect, get_stacks, clear_expired, get_active_text,
    HEAL, COMBO, STRENGTH, TOUGHNESS, INSTANT, ASCEND, HACK,
    POISON, LIFESTEAL, COUNTER, UPGRADE, PIERCE, REFLECT,
    TOXIC, THORNS, UNYIELDING, DISRUPT, FORCEFIELD, FATED,
    OVERLOAD, DESPERATION, LUCKY,
    EXPIRE_TURN, EXPIRE_ATTACK,
)

_pending = {}   # {ctx: {"player": challenger, "code": "XXXX"}}
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
        self.pending_dongchuan = False
        self.pending_magic_bullet = {p1: False, p2: False}
        # Unified effects dict per player
        self.effects = {p1: new_effects(), p2: new_effects()}
        # Rainbow dice tracking
        self.damage_taken = {p1: 0, p2: 0}       # cumulative damage taken
        self.ones_rolled = {p1: 0, p2: 0}         # cumulative 1-point dice selected
        self.fours_selected = {p1: 0, p2: 0}      # cumulative 4-point dice selected
        # Per-activation tracking for limited-trigger dice
        self.special_triggers = {p1: {}, p2: {}}  # {effect_key: {value: count}}
        self.pending_value_effects = {p1: [], p2: []}  # effects to apply on next select
        self.def_bonus = {p1: 0, p2: 0}             # DEF bonus (for 遐蝶)
        self.rainbow_special_count = {p1: 0, p2: 0}  # cumulative rainbow special triggers
        # New card tracking
        self.dh_def_restore = {p1: False, p2: False}       # 丹恒: restore def after defense
        self.dh_counter_restore = {p1: False, p2: False}    # 丹恒: restore counter
        self.yg_extra_rerolls = {p1: 0, p2: 0}              # 爻光: extra rerolls granted
        self.yg_rerolls_this_turn = {p1: 0, p2: 0}          # 爻光: rerolls used this turn
        self.xl_accum = {p1: 0, p2: 0}                      # 昔涟: accumulated atk+def value
        self.xl_promoted = {p1: False, p2: False}            # 昔涟: promoted to atk 5
        self.be_unyielding_used = {p1: False, p2: False}     # 白厄: unyielding used flag
        self.fj_atk_value = {p1: 0, p2: 0}                  # 风堇: last ATK value for strength calc
        # Message context for sending to both players
        self.msg_ctx = {p1: None, p2: None}  # stored by plugin when players interact (大黑塔)

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

    def _use_rainbow_count(self, pid):
        if pid == self.p1: self.p1_rainbow_uses -= 1
        else: self.p2_rainbow_uses -= 1

    def _effective_atk(self, pid):
        """ATK level for dice count selection (does NOT include strength)."""
        base = self._card(pid)["atk_level"]
        bonus = self.dongchuan_bonus[pid]
        return base + bonus

    def _effective_def(self, pid):
        """DEF level for dice count selection (does NOT include toughness)."""
        base = self._card(pid)["def_level"]
        return base + self.def_bonus[pid]

    def _roll_dice(self, pid):
        card = self._card(pid)
        eff = self.effects[pid]
        results = []
        for spec in card["dice"]:
            for _ in range(spec["count"]):
                sides = spec["type"]
                val = random.randint(1, sides)
                # ??: all dice roll max
                if has_effect(eff, LUCKY):
                    val = sides
                results.append({"value": val, "type": sides, "mingding": False, "label": "", "rainbow": False})
        # Append rainbow die if pending
        rdata = self.mingding_pending.get(pid)
        if rdata:
            faces = rdata["faces"]
            val = random.choice(faces)
            md = rdata.get("mingding", False)
            label = "??" if md else ""
            results.append({"value": val, "type": 0, "mingding": md, "label": label, "rainbow_val": val, "rainbow": True})
            self._apply_rainbow_effect(pid, rdata, val)
            self.mingding_pending[pid] = None
        return results

    def _count_pairs(self, values):
        """Count how many pairs of matching values exist."""
        from collections import Counter
        counts = Counter(values)
        pairs = sum(v // 2 for v in counts.values())
        return pairs

    def _has_two_pairs(self, values):
        """Check if values contain at least two pairs."""
        return self._count_pairs(values) >= 2

    def _has_pair(self, values):
        """Check if values contain at least one pair."""
        return self._count_pairs(values) >= 1

    def _unique_values(self, values):
        """Count unique values."""
        return len(set(values))

    def _apply_rainbow_effect(self, pid, rdata, val):
        """Record rainbow die roll value. Effects trigger only when SELECTED."""
        self.rainbow_roll_info = getattr(self, 'rainbow_roll_info', {})
        self.rainbow_roll_info[pid] = {'rdata': rdata, 'value': val}
        return []

    def _apply_turn_start(self, pid):
        """Apply effects at the start of a player's turn (pre-roll).
        No-op: poison and thorns both trigger in _apply_round_effects.
        """
        return []

    def _apply_rainbow_on_select(self, pid, rainbow_val):
        """Apply rainbow die effect when the die is SELECTED in attack/defense.
        This is the single entry point for ALL rainbow effects."""
        rinfo = getattr(self, "rainbow_roll_info", {}).get(pid)
        if not rinfo:
            return []
        rdata = rinfo["rdata"]
        val = rinfo["value"]
        effect = rdata.get("effect", "none")
        eff = self.effects[pid]
        msgs = []

        # === Instant effects (trigger once on select, based on rolled value) ===
        if effect == "evolution":
            if val == 2:
                add_effect(eff, ASCEND)
                msgs.append("\u771f\u00b7\u8fdb\u5316\u89e6\u53d1\uff01\u83b7\u5f97\u8dc3\u5347")
        elif effect == "heal":
            add_effect(eff, HEAL, val)
            msgs.append("\u771f\u00b7\u533b\u5631\uff1a\u83b7\u5f97" + str(val) + "\u5c42\u6cbb\u6108")
        elif effect == "overload":
            add_effect(eff, OVERLOAD, val)
            msgs.append("\u771f\u00b7\u8d37\u6b3e\uff1a\u83b7\u5f97" + str(val) + "\u5c42\u8d85\u8f7d")
        elif effect == "hack":
            triggered = False
            if val == 6:
                triggered = True
            elif val == 4:
                triggered = random.random() < 0.25
            if triggered:
                add_effect(eff, HACK)
                msgs.append("\u771f\u00b7\u5947\u672f\u5e08\u89e6\u53d1\uff01\u83b7\u5f97\u9a87\u5165")
        elif effect == "heartbeat":
            if val == 9:
                if pid == self.p1: self.p1_rainbow_uses += 1
                else: self.p2_rainbow_uses += 1
                msgs.append("\u771f\u00b7\u5fc3\u8df3\u89e6\u53d1\uff01+1\u66dc\u5f69\u9ab0\u6b21\u6570")
        elif effect == "thorns":
            if val == 8:
                add_effect(eff, THORNS, 2)
                msgs.append("\u771f\u00b7\u6218\u72c2\uff1a+2\u8346\u68d8")
            elif val == 12:
                add_effect(eff, THORNS, 3)
                msgs.append("\u771f\u00b7\u6218\u72c2\uff1a+3\u8346\u68d8")
        elif effect == "magic_bullet":
            self.pending_magic_bullet[pid] = True
            msgs.append("\u771f\u00b7\u9b54\u5f39\u5f85\u53d1")
        elif effect == "cactus":
            add_effect(eff, COUNTER)
            msgs.append("\u771f\u00b7\u4ed9\u4eba\u7403\uff1a\u83b7\u5f97\u53cd\u51fb")
        elif effect == "red_button":
            add_effect(eff, DESPERATION)
            msgs.append("\u771f\u00b7\u5927\u7ea2\u6309\u94ae\uff1a\u83b7\u5f97\u80cc\u6c34")

        # === Value-based effects (check special_values) ===
        sv = rdata.get("special_values")
        if sv:
            val_key = str(val)
            if val_key in sv:
                triggered, _ = self._check_value_trigger(pid, rdata, val)
                if triggered:
                    if effect == "evolution" and val == 2:
                        # Already handled above as instant
                        pass
                    elif effect == "last_words":
                        # Double attack/def value - handled via pending_value_effects
                        self.pending_value_effects[pid].append({"type": "double", "msg": "\u9057\u8bed\u89e6\u53d1\uff01" + str(val) + "\u70b9\u7ffb\u500d"})
                        msgs.append("\u9057\u8bed\u89e6\u53d1\uff01" + str(val) + "\u70b9\u7ffb\u500d")
                    elif effect == "repeat" and val == 4:
                        self.pending_value_effects[pid].append({"type": "combo", "msg": "\u590d\u8bfb\u89e6\u53d1\uff01+1\u8fde\u51fb"})
                        msgs.append("\u590d\u8bfb\u89e6\u53d1\uff01+1\u8fde\u51fb")
                    elif effect == "star_shield" and val == 1:
                        self.pending_value_effects[pid].append({"type": "forcefield", "msg": "\u661f\u76fe\u89e6\u53d1\uff01\u529b\u573a"})
                        msgs.append("\u661f\u76fe\u89e6\u53d1\uff01\u529b\u573a")
                    elif effect == "oath" and val in (4, 6):
                        self.pending_value_effects[pid].append({"type": "unyielding", "msg": "\u8a93\u8a00\u89e6\u53d1\uff01\u4e0d\u5c48"})
                        msgs.append("\u8a93\u8a00\u89e6\u53d1\uff01\u4e0d\u5c48")

        # Track special triggers for 大黑塔
        if msgs:
            self.rainbow_special_count[pid] = self.rainbow_special_count.get(pid, 0) + 1

        # Clear the roll info after processing
        if hasattr(self, "rainbow_roll_info"):
            self.rainbow_roll_info.pop(pid, None)
        return msgs

    def _apply_round_effects(self, pid):
        """Apply round effects before damage resolution.
        Called for both attacker and defender before resolve.
        Triggers: thorns, then poison.
        """
        eff = self.effects[pid]
        msgs = []
        # Thorns
        thorns = get_stacks(eff, THORNS)
        if thorns > 0:
            old_hp = self._hp(pid)
            self._set_hp(pid, max(0, old_hp - thorns))
            msgs.append("\u8346\u68d8\u4f24\u5bb3 -" + str(thorns) + "HP")
            if self._hp(pid) <= 0:
                msgs.append("GAME_OVER")
                return msgs
        # Poison
        poison = get_stacks(eff, POISON)
        if poison > 0:
            dmg = poison
            if has_effect(eff, TOXIC):
                dmg *= 2
            old_hp = self._hp(pid)
            self._set_hp(pid, max(0, old_hp - dmg))
            eff[POISON] -= 1
            if eff[POISON] <= 0:
                eff[POISON] = 0
            msgs.append("\u4e2d\u6bd2\u4f24\u5bb3 -" + str(dmg) + "HP (\u5269\u4f59" + str(eff[POISON]) + "\u5c42)")
            if self._hp(pid) <= 0:
                msgs.append("GAME_OVER")
                return msgs
        return msgs

    def _check_rainbow_condition(self, pid, rdata):
        """Check if a rainbow die meets its use condition."""
        cond = rdata.get("condition")
        if not cond:
            return True
        if cond == "damage_taken_25":
            return self.damage_taken[pid] >= 25
        if cond == "two_4s_selected":
            return self.fours_selected[pid] >= 2
        if cond == "nine_1s_selected":
            return self.ones_rolled[pid] >= 9
        if cond == "round_5_plus":
            return self.round_num >= 5
        # HP-based condition
        if cond.startswith("hp_le_"):
            threshold = int(cond.split("_")[-1])
            return self._hp(pid) <= threshold
        return True

    def _can_use_rainbow_phase(self, pid, rdata):
        """Check if rainbow die can be used in current phase."""
        phase = rdata.get("use_phase")
        if not phase:
            return True  # no phase restriction
        if phase == "atk":
            return pid == self.attacker
        if phase == "def":
            return pid == self.defender
        return True

    def _init_special_triggers(self, pid, rdata):
        """Initialize special trigger tracking for a rainbow die."""
        sv = rdata.get("special_values")
        if sv:
            effect_key = rdata["effect"]
            if effect_key not in self.special_triggers[pid]:
                self.special_triggers[pid][effect_key] = {}

    def _check_value_trigger(self, pid, rdata, value):
        """Check if selecting a specific value triggers a rainbow effect.
        Returns (triggered: bool, effect_info: dict or None)"""
        sv = rdata.get("special_values")
        if not sv:
            return False, None
        val_key = str(value)
        if val_key not in sv:
            return False, None
        effect_key = rdata["effect"]
        triggers = self.special_triggers[pid].get(effect_key, {})
        current = triggers.get(val_key, 0)
        max_t = sv[val_key]["max_triggers"]
        if current >= max_t:
            return False, None
        # Increment trigger count
        if effect_key not in self.special_triggers[pid]:
            self.special_triggers[pid][effect_key] = {}
        self.special_triggers[pid][effect_key][val_key] = current + 1
        return True, sv[val_key]

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
        if random.random() < 0.5:
            self.attacker, self.defender = self.p1, self.p2
        else:
            self.attacker, self.defender = self.p2, self.p1
        self.round_num = 1
        self.state = self.ATK_ROLL

    def roll(self, pid):
        if self.state == self.ATK_ROLL and pid == self.attacker:
            # Apply turn-start effects
            start_msgs = self._apply_turn_start(pid)
            if "GAME_OVER" in start_msgs:
                self.state = self.FINISHED
                self.winner = self.defender
                return ("game_over_thorns", start_msgs)
            # Card skill check for rerolls
            cn = self._card_name(pid)
            base_rerolls = 4 if cn == '爻光' else 2
            self.yg_rerolls_this_turn[pid] = 0
            disrupt = get_stacks(self.effects[pid], DISRUPT)
            self.max_rerolls = max(0, base_rerolls - disrupt)
            self.rerolls_used = 0
            self.roll_results = self._roll_dice(pid)
            self.state = self.ATK_SELECT
            return ("rolled", self.roll_results, start_msgs)
        elif self.state == self.DEF_ROLL and pid == self.defender:
            # Apply turn-start effects (?? + clear expired) for defender
            start_msgs = self._apply_turn_start(pid)
            if "GAME_OVER" in start_msgs:
                self.state = self.FINISHED
                self.winner = self.attacker
                return ("game_over_turn", start_msgs)
            card = self._card(pid)
            self.max_rerolls = 0
            self.rerolls_used = 0
            self.roll_results = self._roll_dice(pid)
            self.state = self.DEF_SELECT
            return ("rolled", self.roll_results, start_msgs)
        return None

    def reroll(self, pid):
        can = False
        if self.state == self.ATK_SELECT and pid == self.attacker: can = True
        elif self.state == self.DEF_SELECT and pid == self.defender: can = True
        if not can: return None
        if self.rerolls_used >= self.max_rerolls: return "no_rerolls"
        self.roll_results = self._roll_dice(pid)
        self.rerolls_used += 1
        # 爻光(星轨): after 2 rerolls, each extra gives 2 thorns
        if self._card_name(pid) == '爻光':
            self.yg_rerolls_this_turn[pid] = self.rerolls_used
            if self.rerolls_used > 2:
                add_effect(self.effects[pid], THORNS, 2)
        return self.roll_results

    def _mingding_indices(self):
        return {i for i, r in enumerate(self.roll_results) if r["mingding"]}

    def _apply_hack(self):
        """Change opponent's highest non-rainbow die to 2."""
        eff = self.effects[self.defender]
        if not has_effect(eff, HACK): return None
        best_idx = -1; best_val = -1
        for i, r in enumerate(self.roll_results):
            if not r.get("rainbow") and r["value"] > best_val:
                best_val = r["value"]; best_idx = i
        remove_effect(eff, HACK)
        if best_idx >= 0 and best_val > 2:
            self.roll_results[best_idx]["value"] = 2
            return (best_idx + 1, best_val)
        return None

    def _apply_ascend(self, selected_indices):
        """Randomly change one selected non-rainbow die to its max value."""
        eff = self.effects[self.attacker]
        if not has_effect(eff, ASCEND): return None
        remove_effect(eff, ASCEND)
        # Find eligible dice (non-rainbow)
        eligible = [i for i in selected_indices if not self.roll_results[i].get("rainbow")]
        if not eligible: return None
        target = random.choice(eligible)
        die_type = self.roll_results[target]["type"]
        old_val = self.roll_results[target]["value"]
        self.roll_results[target]["value"] = die_type
        return (target + 1, old_val, die_type)

    def _consume_heal(self, pid):
        eff = self.effects[pid]
        hs = get_stacks(eff, HEAL)
        msgs = []
        if hs > 0:
            mx = CARDS[self._card_name(pid)]["hp"]
            cur = self._hp(pid)
            healed = min(hs, mx - cur)
            if healed > 0:
                self._set_hp(pid, cur + healed)
                msgs.append("????" + str(healed) + "HP")
            remove_effect(eff, HEAL)
        return msgs

    def select_dice(self, pid, indices):
        mi = self._mingding_indices()
        eff_pid = self.effects[pid]

        if self.state == self.ATK_SELECT and pid == self.attacker:
            n = self._effective_atk(pid)
            mc = len(mi)
            need = max(0, n - mc)
            pi = [i for i in indices if (i - 1) not in mi]
            if len(pi) != need: return ("wrong_count", need, mc)
            all_idx = set(indices) | {(i + 1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_idx):
                return ("invalid_index",)

            # Get selected values
            zero_based = [i - 1 for i in sorted(all_idx)]
            values = [self.roll_results[i]["value"] for i in zero_based]
            total = sum(values)

            # ?? card check (all 4s)
            dongchuan = all(v == 4 for v in values)
            if dongchuan:
                self.dongchuan_bonus[pid] += 1
                add_effect(eff_pid, PIERCE)
                self.pending_dongchuan = True

            # ??: change smallest non-rainbow to max
            ascend_result = self._apply_ascend(zero_based)
            if ascend_result:
                # Recalculate total
                values = [self.roll_results[i]["value"] for i in zero_based]
                total = sum(values)

            # ??: consume heal stacks
            heal_msgs = self._consume_heal(pid)

            # ??: add strength bonus (already in _effective_atk, but for display)
            strength = get_stacks(eff_pid, STRENGTH)

            # ??: add overload to attack
            overload = get_stacks(eff_pid, OVERLOAD)
            if overload > 0:
                total += overload

            # ??: set HP to 1, add difference as bonus
            desperation_bonus = 0
            if has_effect(eff_pid, DESPERATION):
                cur_hp = self._hp(pid)
                if cur_hp > 1:
                    desperation_bonus = cur_hp - 1
                    self._set_hp(pid, 1)
                    total += desperation_bonus
                    remove_effect(eff_pid, DESPERATION)

            # Apply rainbow effect if rainbow die is selected
            rainbow_in_selection = any(self.roll_results[i].get("rainbow") for i in zero_based)
            rainbow_msgs = []
            if rainbow_in_selection:
                rainbow_val = None
                for i in zero_based:
                    if self.roll_results[i].get("rainbow"):
                        rainbow_val = self.roll_results[i].get("rainbow_val")
                        break
                if rainbow_val is not None:
                    rainbow_msgs = self._apply_rainbow_on_select(pid, rainbow_val)
                    if rainbow_val == 1: self.ones_rolled[pid] += 1
                    if rainbow_val == 4: self.fours_selected[pid] += 1

            # Track 1s and 4s for rainbow conditions (non-rainbow dice)
            for i in zero_based:
                r = self.roll_results[i]
                if not r.get("rainbow"):
                    v = r["value"]
                    if v == 1: self.ones_rolled[pid] += 1
                    if v == 4: self.fours_selected[pid] += 1

            # Process pending value-based effects from rainbow dice
            value_effect_msgs = []
            for ve in self.pending_value_effects[pid]:
                ve_type = ve.get("type")
                if ve_type == "double":
                    total *= 2
                    value_effect_msgs.append(ve.get("msg", "\u7ffb\u500d\u6548\u679c\u89e6\u53d1\uff01"))
                elif ve_type == "combo":
                    add_effect(eff_pid, COMBO, 1)
                    value_effect_msgs.append(ve.get("msg", "\u8fde\u51fb\u89e6\u53d1\uff01"))
                elif ve_type == "desperation":
                    cur_hp = self._hp(pid)
                    if cur_hp > 1:
                        bonus = cur_hp - 1
                        self._set_hp(pid, 1)
                        total += bonus
                        value_effect_msgs.append("\u80cc\u6c34\uff01HP\u964d\u4e3a1\uff0c\u83b7\u5f97+" + str(bonus) + "\u653b\u51fb")
            self.pending_value_effects[pid] = []

            # Card skills (ATK phase)
            card_skill_msgs = []
            card = self._card(pid)
            card_name = self._card_name(pid)

            # 流萤(炽翼): two pairs -> combo; full HP -> +5
            if card_name == '流萤':
                if self._has_two_pairs(values):
                    add_effect(eff_pid, COMBO, 1)
                    card_skill_msgs.append('炽翼触发！两组相同点数，获得连击')
                max_hp = card['hp']
                if self._hp(pid) >= max_hp:
                    total += 5
                    card_skill_msgs.append('炽翼触发！满血+5攻击')

            # 知更鸟(和弦): all even -> upgrade selected dice
            if card_name == '知更鸟':
                if all(v % 2 == 0 for v in values):
                    upgraded = []
                    for idx in zero_based:
                        die = self.roll_results[idx]
                        if not die.get('rainbow') and die['type'] < 12:
                            old_type = die['type']
                            die['type'] = min(12, die['type'] * 2)
                            die['value'] = random.randint(1, die['type'])
                            upgraded.append(str(old_type) + '→' + str(die['type']))
                    if upgraded:
                        values = [self.roll_results[i]['value'] for i in zero_based]
                        total = sum(values)
                        card_skill_msgs.append('和弦触发！升级 ' + ' '.join(upgraded))

            # 卡芙卡(影蚀): each unique value -> 1 poison on opponent
            if card_name == '卡芙卡':
                uv = self._unique_values(values)
                if uv > 0:
                    opp = self._other(pid)
                    add_effect(self.effects[opp], POISON, uv)
                    card_skill_msgs.append('影蚀触发！' + str(uv) + '个不同点数，中毒对方' + str(uv) + '层')

            # 三月七(春风): one pair -> 3 instant damage (ATK)
            if card_name == '三月七':
                if self._has_pair(values):
                    opp = self._other(pid)
                    old_ohp = self._hp(opp)
                    self._set_hp(opp, max(0, old_ohp - 3))
                    card_skill_msgs.append('春风触发！造成3点眩伤')
                    if self._hp(opp) <= 0:
                        self.state = self.FINISHED
                        self.winner = pid


            # 丹恒·腾荒(破风): ATK>=18 -> next DEF+3 and counter
            if card_name == '丹恒·腾荒':
                if total >= 18:
                    self.def_bonus[pid] += 3
                    add_effect(eff_pid, COUNTER)
                    self.dh_def_restore[pid] = True
                    card_skill_msgs.append('破风触发！下次防御+3并获得反击')

            # 爻光(星轨): ATK>=18 -> remove all thorns + 1 rainbow use
            if card_name == '爻光':
                if total >= 18:
                    remove_effect(eff_pid, THORNS)
                    if pid == self.p1:
                        self.p1_rainbow_uses += 1
                    else:
                        self.p2_rainbow_uses += 1
                    card_skill_msgs.append('星轨触发！清除荆棘+1曜彩骰次数')

            # 昔涟(潮汐): accumulate ATK value, >24 -> ATK 5 + ascend
            if card_name == '昔涟':
                self.xl_accum[pid] += total
                if not self.xl_promoted[pid] and self.xl_accum[pid] > 24:
                    self.xl_promoted[pid] = True
                    self.dongchuan_bonus[pid] += (5 - card['atk_level'])
                    card_skill_msgs.append('潮汐触发！攻击等级提升至5')
                elif self.xl_promoted[pid]:
                    add_effect(eff_pid, ASCEND)
                    card_skill_msgs.append('潮汐：获得跃升')

            # 白厄(吞噬): lifesteal 50% of ATK value (floor)
            if card_name == '白厄':
                heal_amt = total // 2
                if heal_amt > 0:
                    mx = card['hp']
                    cur = self._hp(pid)
                    actual = min(heal_amt, mx - cur)
                    if actual > 0:
                        self._set_hp(pid, cur + actual)
                        card_skill_msgs.append('吞噬触发！虹吸恢复' + str(actual) + 'HP')

            # 风堇(葱岑): set strength to 50% ATK (floor); all 6s -> 100% + heal 6
            if card_name == '风堇':
                all_six = all(v == 6 for v in values)
                if all_six:
                    strength_set = total
                else:
                    strength_set = total // 2
                eff_pid[STRENGTH] = strength_set
                card_skill_msgs.append('葱岑触发！力量设为' + str(strength_set))
                if all_six:
                    mx = card['hp']
                    cur = self._hp(pid)
                    actual = min(6, mx - cur)
                    if actual > 0:
                        self._set_hp(pid, cur + actual)
                        card_skill_msgs.append('葱岑：全6点！治愈' + str(actual) + 'HP')

            self.atk_value = total
            self.state = self.DEF_ROLL
            return ("ok_atk", values, total, dongchuan, heal_msgs, strength, overload, desperation_bonus, ascend_result, value_effect_msgs + rainbow_msgs + card_skill_msgs)

        elif self.state == self.DEF_SELECT and pid == self.defender:
            card = self._card(pid)
            n = self._effective_def(pid)
            atk_card = self._card(self.attacker)
            if atk_card.get("skill", "") == "??": n = max(1, n - 1)
            mc = len(mi)
            need = max(0, n - mc)
            pi = [i for i in indices if (i - 1) not in mi]
            if len(pi) != need: return ("wrong_count", need, mc)
            all_idx = set(indices) | {(i + 1) for i in mi}
            if any(i < 1 or i > len(self.roll_results) for i in all_idx):
                return ("invalid_index",)

            zero_based = [i - 1 for i in sorted(all_idx)]

            # ??: change defender's highest non-rainbow die to 2
            hack_result = self._apply_hack()

            # Read values AFTER hack may have modified roll_results
            values = [self.roll_results[i]["value"] for i in zero_based]
            def_sum = sum(values)

            # ??: consume heal stacks
            heal_msgs = self._consume_heal(pid)

            # ?? bonus (already in _effective_def)
            toughness = get_stacks(self.effects[pid], TOUGHNESS)
            if toughness > 0:
                def_sum += toughness

            # ?? defense self-damage
            eff_pid = self.effects[pid]
            overload = get_stacks(eff_pid, OVERLOAD)
            ov_self_dmg = overload // 2 if overload > 0 else 0

            # Apply rainbow effect if rainbow die is selected
            rainbow_in_selection = any(self.roll_results[i].get('rainbow') for i in zero_based)
            rainbow_msgs = []
            if rainbow_in_selection:
                rainbow_val = None
                for i in zero_based:
                    if self.roll_results[i].get('rainbow'):
                        rainbow_val = self.roll_results[i].get('rainbow_val')
                        break
                if rainbow_val is not None:
                    rainbow_msgs = self._apply_rainbow_on_select(pid, rainbow_val)
                    if rainbow_val == 1: self.ones_rolled[pid] += 1
                    if rainbow_val == 4: self.fours_selected[pid] += 1

            # Track 1s and 4s (non-rainbow dice)
            for i in zero_based:
                r = self.roll_results[i]
                if not r.get('rainbow'):
                    v = r['value']
                    if v == 1: self.ones_rolled[pid] += 1
                    if v == 4: self.fours_selected[pid] += 1

            # Process pending value-based effects
            value_effect_msgs = []
            for ve in self.pending_value_effects[pid]:
                ve_type = ve.get('type')
                if ve_type == 'double':
                    def_sum *= 2
                    value_effect_msgs.append(ve.get('msg', '翻倍效果触发！'))
                elif ve_type == 'counter':
                    add_effect(self.effects[pid], COUNTER)
                    value_effect_msgs.append('反击效果触发！')
                elif ve_type == 'forcefield':
                    add_effect(self.effects[pid], FORCEFIELD)
                    value_effect_msgs.append('力场效果触发！')
                elif ve_type == 'unyielding':
                    add_effect(self.effects[pid], UNYIELDING)
                    value_effect_msgs.append('不屈效果触发！')
            self.pending_value_effects[pid] = []

            # Card skills (DEF phase)
            card = self._card(pid)
            card_name = self._card_name(pid)
            card_skill_msgs = []

            # 三月七(春风): one pair -> 3 instant damage (DEF)
            if card_name == '三月七':
                if self._has_pair(values):
                    opp = self._other(pid)
                    old_ohp = self._hp(opp)
                    self._set_hp(opp, max(0, old_ohp - 3))
                    card_skill_msgs.append('春风触发！造成3点眩伤')
                    if self._hp(opp) <= 0:
                        self.state = self.FINISHED
                        self.winner = pid


            # 白厄(吞噬): DEF all same value -> unyielding (once per game)
            if card_name == '白厄' and not self.be_unyielding_used.get(pid, False):
                if len(values) > 0 and all(v == values[0] for v in values):
                    add_effect(self.effects[pid], UNYIELDING)
                    self.be_unyielding_used[pid] = True
                    card_skill_msgs.append('吞噬触发！全同点数，获得不屈')

            # 昔涟(潮汐): accumulate DEF value too
            if card_name == '昔涟':
                self.xl_accum[pid] += def_sum
                if not self.xl_promoted.get(pid, False) and self.xl_accum[pid] > 24:
                    self.xl_promoted[pid] = True
                    card_atk = self._card(pid)['atk_level']
                    self.dongchuan_bonus[pid] += (5 - card_atk)
                    card_skill_msgs.append('潮汐触发！攻击等级提升至5')
                elif self.xl_promoted.get(pid, False):
                    add_effect(self.effects[pid], ASCEND)
                    card_skill_msgs.append('潮汐：获得跃升')

            def_round_msgs = self._apply_round_effects(pid)

            return self._resolve(pid, values, def_sum, hack_result, heal_msgs, toughness, ov_self_dmg, def_round_msgs, value_effect_msgs + rainbow_msgs + card_skill_msgs)
        return None

    def _resolve(self, def_pid, def_values, def_sum, hack_result, heal_msgs, toughness, ov_self_dmg, def_round_msgs=None, def_value_msgs=None):
        atk_eff = self.effects[self.attacker]
        def_eff = self.effects[def_pid]
        atk_card = self._card(self.attacker)
        def_card = self._card(def_pid)

        # Apply round effects (??) to attacker before damage resolution
        atk_round_msgs = self._apply_round_effects(self.attacker)

        has_dongchuan = self.pending_dongchuan
        self.pending_dongchuan = False

        # ??: ignore damage if active
        forcefield_active = has_effect(def_eff, FORCEFIELD)

        if has_dongchuan:
            # ??: bypass defense and forcefield
            damage = self.atk_value
            forcefield_active = False
        else:
            damage = max(0, self.atk_value - def_sum)
            if def_card.get("skill", "") == "??":
                damage = max(0, damage - 2)

        if atk_card.get("skill", "") == "??" and self.atk_value > 12 and not has_dongchuan:
            damage *= 2

        # Apply ?? (blocks regular damage)
        if forcefield_active and damage > 0:
            damage = 0

        # ??: magic bullet
        mb_dmg = 0
        if self.pending_magic_bullet.get(self.attacker):
            mb_dmg = 3
            self.pending_magic_bullet[self.attacker] = False

        # ??: heal based on damage dealt
        lifesteal_msgs = []
        ls_stacks = get_stacks(atk_eff, LIFESTEAL)
        if ls_stacks > 0 and damage > 0:
            heal_amount = damage * ls_stacks // 10  # Each stack = 10% of damage
            if heal_amount > 0:
                mx = CARDS[self._card_name(self.attacker)]["hp"]
                cur = self._hp(self.attacker)
                actual_heal = min(heal_amount, mx - cur)
                if actual_heal > 0:
                    self._set_hp(self.attacker, cur + actual_heal)
                    lifesteal_msgs.append("????" + str(actual_heal) + "HP")

        total_damage = damage + mb_dmg

        # ?? defense self-damage
        if ov_self_dmg > 0:
            old_self = self._hp(def_pid)
            self._set_hp(def_pid, max(0, old_self - ov_self_dmg))

        # Apply damage to defender
        old_hp = self._hp(def_pid)
        new_hp = max(0, old_hp - total_damage)
        # ??: keep at least 1 HP
        if has_effect(def_eff, UNYIELDING) and new_hp <= 0:
            new_hp = 1
        self._set_hp(def_pid, new_hp)
        # Track damage taken for rainbow conditions
        actual_dmg = old_hp - new_hp
        if actual_dmg > 0:
            self.damage_taken[def_pid] += actual_dmg
        game_over = new_hp <= 0

        # ??: if def_sum > attack value, deal difference to attacker
        counter_msgs = []
        if has_effect(def_eff, COUNTER) and def_sum > self.atk_value:
            counter_dmg = def_sum - self.atk_value
            old_atk_hp = self._hp(self.attacker)
            self._set_hp(self.attacker, max(0, old_atk_hp - counter_dmg))
            self.damage_taken[self.attacker] += counter_dmg
            counter_msgs.append("????" + str(counter_dmg) + "??")
            if self._hp(self.attacker) <= 0:
                game_over = True
                self.winner = def_pid

        # ??: deal % of def_sum as instant damage
        reflect_msgs = []
        reflect_stacks = get_stacks(def_eff, REFLECT)
        if reflect_stacks > 0 and total_damage > 0:
            reflect_dmg = def_sum * reflect_stacks // 10  # Each stack = 10%
            if reflect_dmg > 0:
                old_atk_hp = self._hp(self.attacker)
                self._set_hp(self.attacker, max(0, old_atk_hp - reflect_dmg))
                self.damage_taken[self.attacker] += reflect_dmg
                reflect_msgs.append("????" + str(reflect_dmg) + "??")
                if self._hp(self.attacker) <= 0:
                    game_over = True
                    self.winner = def_pid

        # ?? heal
        # Post-damage card skills
        def_card_name = self._card_name(def_pid) if self._card(def_pid) else ''

        # 遐蝶(蝴蝶): DEF - damage>=8 atk/def+1, damage<=5 deal 3 instant
        if def_card_name == '遐蝶' and actual_dmg > 0:
            if actual_dmg >= 8:
                self.dongchuan_bonus[def_pid] += 1
                self.def_bonus[def_pid] += 1
            elif actual_dmg <= 5:
                old_atk_hp2 = self._hp(self.attacker)
                self._set_hp(self.attacker, max(0, old_atk_hp2 - 3))
                if not game_over and self._hp(self.attacker) <= 0:
                    game_over = True
                    self.winner = def_pid

        # 卡芙卡(影蚀): DEF fail - remove 1 poison from attacker
        if def_card_name == '卡芙卡' and actual_dmg > 0:
            atk_poison = get_stacks(self.effects[self.attacker], POISON)
            if atk_poison > 0:
                self.effects[self.attacker][POISON] -= 1

        # 大黑塔(智慧): round end - +1 rainbow uses; 4+ specials -> ascend
        for pid_ck in [self.p1, self.p2]:
            c = self._card(pid_ck)
            if c and c.get('name') == '大黑塔':
                if pid_ck == self.p1:
                    self.p1_rainbow_uses += 1
                else:
                    self.p2_rainbow_uses += 1
                if self.rainbow_special_count.get(pid_ck, 0) >= 4:
                    add_effect(self.effects[pid_ck], ASCEND)

        saint_heal = []
        for pid in [self.p1, self.p2]:
            c = self._card(pid)
            if c.get("skill", "") == "??":
                mx = CARDS[self._card_name(pid)]["hp"]
                cur = self._hp(pid)
                if cur > 0 and cur < mx:
                    h = min(3, mx - cur)
                    self._set_hp(pid, cur + h)
                    saint_heal.append((pid, h))

        # Clear attack-expiry effects for attacker
        clear_expired(atk_eff, EXPIRE_ATTACK)

        # Post-round card restores
        for pid_ck in [self.p1, self.p2]:
            c = self._card(pid_ck)
            if not c: continue
            cn = c.get('name', '')
            # 丹恒(破风): restore def_bonus and counter after defense
            if cn == '丹恒·腾荒' and self.dh_def_restore.get(pid_ck):
                self.def_bonus[pid_ck] = 0
                remove_effect(self.effects[pid_ck], COUNTER)
                self.dh_def_restore[pid_ck] = False
            # 爻光(星轨): reset turn reroll counter
            if cn == '爻光':
                self.yg_rerolls_this_turn[pid_ck] = 0

        if not game_over:
            self.attacker, self.defender = self.defender, self.attacker
            self.round_num += 1
            self.state = self.ATK_ROLL
        else:
            self.state = self.FINISHED
            if not self.winner:
                self.winner = self.attacker

        # Clear turn-expiry effects AFTER all effects have been applied
        for pid in [self.p1, self.p2]:
            if self._hp(pid) > 0:
                clear_expired(self.effects[pid], EXPIRE_TURN)


        round_msgs = (atk_round_msgs or []) + (def_round_msgs or []) + (def_value_msgs or [])
        return ("ok_def", def_values, def_sum, damage, old_hp, new_hp, game_over,
                saint_heal, has_dongchuan, hack_result, heal_msgs, mb_dmg, ov_self_dmg,
                lifesteal_msgs, counter_msgs, reflect_msgs, forcefield_active, round_msgs)

    def use_rainbow(self, pid):
        eff = self.effects[pid]
        if self._rainbow_uses(pid) <= 0: return "no_uses"
        rname = self._rainbow_name(pid)
        if not rname: return "no_dice"
        rdata = RAINBOW_DICE[rname]
        max_round = rdata.get("max_round")
        if max_round and self.round_num > max_round:
            return ("too_late", max_round)
        # Phase check
        if not self._can_use_rainbow_phase(pid, rdata):
            phase = rdata.get("use_phase", "")
            return ("wrong_phase", phase)
        # Condition check
        if not self._check_rainbow_condition(pid, rdata):
            cond = rdata.get("condition", "")
            return ("condition_not_met", cond)
        self._use_rainbow_count(pid)
        self._init_special_triggers(pid, rdata)
        if "faces" in rdata:
            self.mingding_pending[pid] = rdata
            return ("activated", rname, rdata)
        return "unknown"

    def surrender(self, pid):
        self.state = self.FINISHED
        self.winner = self._other(pid)

    def get_effects_text(self, pid):
        """Get formatted active effects for a player."""
        return get_active_text(self.effects[pid])


def _gen_room_code():
    """Generate a 4-character room code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def create_challenge(challenger, ctx):
    code = _gen_room_code()
    _pending[ctx] = {"player": challenger, "code": code}
    return code


def get_pending(ctx):
    """Return list of (challenger, code) for all pending challenges in context."""
    info = _pending.get(ctx)
    if info:
        return [(info["player"], info["code"])]
    return []


def find_pending_by_code(ctx, code):
    """Find a pending challenge by room code."""
    info = _pending.get(ctx)
    if info and info["code"].upper() == code.upper():
        return info["player"]
    return None

def get_pending_count(ctx):
    """Check if there's a pending challenge."""
    return 1 if ctx in _pending else 0

def accept_challenge(acceptor, ctx, code=None):
    info = _pending.get(ctx)
    if not info: return None
    challenger = info["player"]
    if code:
        if info["code"].upper() != code.upper():
            return "wrong_code"
    if challenger == acceptor:
        _pending.pop(ctx, None)
        return None
    _pending.pop(ctx, None)
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
