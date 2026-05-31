"""Effect system for arena battles.
All 22 effects defined with categories, timing, and persistence rules."""

# Effect keys (short English identifiers)
HEAL = "heal"
COMBO = "combo"
STRENGTH = "strength"
TOUGHNESS = "toughness"
INSTANT = "instant"
ASCEND = "ascend"
HACK = "hack"
POISON = "poison"
LIFESTEAL = "lifesteal"
COUNTER = "counter"
UPGRADE = "upgrade"
PIERCE = "pierce"
REFLECT = "reflect"
TOXIC = "toxic"
THORNS = "thorns"
UNYIELDING = "unyielding"
DISRUPT = "disrupt"
FORCEFIELD = "forcefield"
FATED = "fated"
OVERLOAD = "overload"
DESPERATION = "desperation"
LUCKY = "lucky"

# Timing categories
TIMING_PRE_ROLL = "pre_roll"        # Before dice are rolled
TIMING_POST_ROLL = "post_roll"      # After dice are rolled, before selection
TIMING_PRE_RESOLVE = "pre_resolve"  # After selection, before damage calc
TIMING_ATK = "atk"                  # During attack calculation
TIMING_DEF = "def"                  # During defense calculation
TIMING_POST_COMBAT = "post_combat"  # After damage resolution
TIMING_INSTANT = "instant"          # Immediate, no resolution needed

# Expiry categories
EXPIRE_NEVER = "never"              # Persists indefinitely
EXPIRE_TURN = "turn"                # Expires at end of current turn
EXPIRE_ATTACK = "attack"            # Expires after one attack
EXPIRE_USE = "use"                  # Single use, removed on trigger

# Effect definitions: key -> {name, timing, expiry, stackable, desc}
EFFECTS = {
    HEAL: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_USE,
        "stackable": True,
        "desc": "???????????????????"
    },
    COMBO: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_USE,
        "stackable": True,
        "desc": "??????????????????????????????"
    },
    STRENGTH: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "????????????????????"
    },
    TOUGHNESS: {
        "name": "??", "timing": TIMING_DEF, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "????????????????????"
    },
    INSTANT: {
        "name": "??", "timing": TIMING_INSTANT, "expiry": EXPIRE_USE,
        "stackable": True,
        "desc": "?????????????????"
    },
    ASCEND: {
        "name": "??", "timing": TIMING_PRE_RESOLVE, "expiry": EXPIRE_USE,
        "stackable": False,
        "desc": "???????????????????????????????????"
    },
    HACK: {
        "name": "??", "timing": TIMING_PRE_RESOLVE, "expiry": EXPIRE_USE,
        "stackable": False,
        "desc": "????????????????????2?????????"
    },
    POISON: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "???????????????????-1"
    },
    LIFESTEAL: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "???????????????????"
    },
    COUNTER: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_NEVER,
        "stackable": False,
        "desc": "?????????????????????????"
    },
    UPGRADE: {
        "name": "??", "timing": TIMING_POST_ROLL, "expiry": EXPIRE_USE,
        "stackable": True,
        "desc": "???????????????????12?"
    },
    PIERCE: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_ATTACK,
        "stackable": False,
        "desc": "?????????????????"
    },
    REFLECT: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "??????????????????????"
    },
    TOXIC: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_NEVER,
        "stackable": False,
        "desc": "??????????????????????"
    },
    THORNS: {
        "name": "??", "timing": TIMING_PRE_ROLL, "expiry": EXPIRE_TURN,
        "stackable": True,
        "desc": "????????????????????"
    },
    UNYIELDING: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_TURN,
        "stackable": False,
        "desc": "????????1????????????"
    },
    DISRUPT: {
        "name": "??", "timing": TIMING_PRE_ROLL, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "??????????????"
    },
    FORCEFIELD: {
        "name": "??", "timing": TIMING_POST_COMBAT, "expiry": EXPIRE_TURN,
        "stackable": False,
        "desc": "????????????????????"
    },
    FATED: {
        "name": "??", "timing": TIMING_POST_ROLL, "expiry": EXPIRE_USE,
        "stackable": False,
        "desc": "?????????????"
    },
    OVERLOAD: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_NEVER,
        "stackable": True,
        "desc": "?????????????????????????50%???"
    },
    DESPERATION: {
        "name": "??", "timing": TIMING_ATK, "expiry": EXPIRE_ATTACK,
        "stackable": False,
        "desc": "????????1????????????????"
    },
    LUCKY: {
        "name": "??", "timing": TIMING_PRE_ROLL, "expiry": EXPIRE_NEVER,
        "stackable": False,
        "desc": "?????????????????"
    },
}


def new_effects():
    """Create a fresh effects dict with all keys at 0/False."""
    out = {}
    for key, edef in EFFECTS.items():
        if edef["stackable"]:
            out[key] = 0
        else:
            out[key] = False
    return out


def add_effect(effects, key, stacks=1):
    """Add stacks (or set True for non-stackable). Returns message."""
    edef = EFFECTS[key]
    if edef["stackable"]:
        effects[key] += stacks
        return edef["name"] + " +" + str(stacks) + " (??" + str(effects[key]) + "?)"
    else:
        effects[key] = True
        return edef["name"] + " ???"


def remove_effect(effects, key):
    """Remove an effect entirely."""
    edef = EFFECTS[key]
    if edef["stackable"]:
        effects[key] = 0
    else:
        effects[key] = False


def has_effect(effects, key):
    """Check if effect is active."""
    val = effects.get(key)
    if isinstance(val, bool): return val
    return val > 0


def get_stacks(effects, key):
    """Get stack count (0 if inactive)."""
    val = effects.get(key, 0)
    if isinstance(val, bool): return 1 if val else 0
    return val


def clear_expired(effects, expiry_type):
    """Clear all effects of a given expiry type."""
    for key, edef in EFFECTS.items():
        if edef["expiry"] == expiry_type:
            remove_effect(effects, key)


def get_active_text(effects):
    """Format active effects as display text."""
    parts = []
    for key, edef in EFFECTS.items():
        val = effects.get(key)
        if isinstance(val, bool):
            if val:
                parts.append(edef["name"])
        elif val > 0:
            parts.append(edef["name"] + " x" + str(val))
    return " ".join(parts) if parts else "?"
