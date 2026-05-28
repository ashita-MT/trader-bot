import json
import os
import threading

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")

_lock = threading.Lock()

DEFAULT_CONFIG = {
    "interaction_mode": "text",
    "bot_name": "virtual stock market",
    "admin_password": "admin123",
    "web_port": 6662,
    "enable_real_stocks": True,
    "enable_virtual_stocks": True,
    "enable_real_refresh": True,
    "enable_virtual_refresh": True,
    "real_refresh_interval": 300,
    "virtual_refresh_interval": 300,
    "enable_number_lottery": true,
    "number_lottery_interval": 86400,
    "number_lottery_ticket_price": 100,
    "number_lottery_prize_amount": 10000,
    "number_lottery_max_tickets": 10,
    "enable_pool_lottery": true,
    "pool_lottery_interval": 86400,
    "pool_lottery_ticket_price": 100,
    "pool_lottery_winners": 3
}


def _load():
    if not os.path.exists(CONFIG_PATH):
        _save(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    return data


def _save(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key=None, default=None):
    with _lock:
        cfg = _load()
    if key is None:
        return cfg
    return cfg.get(key, default)


def set(key, value):
    with _lock:
        cfg = _load()
        cfg[key] = value
        _save(cfg)
    return cfg


def get_mode():
    return get("interaction_mode", "text")
