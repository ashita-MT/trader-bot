import json
import os
import threading
import time

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")

_lock = threading.Lock()
_cache = None
_cache_mtime = 0

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
    "enable_number_lottery": True,
    "number_lottery_interval": 86400,
    "number_lottery_ticket_price": 100,
    "number_lottery_prize_amount": 10000,
    "number_lottery_max_tickets": 10,
    "enable_pool_lottery": True,
    "pool_lottery_interval": 86400,
    "pool_lottery_ticket_price": 100,
    "pool_lottery_winners_pct": 10,
    "pool_lottery_max_tickets": 10
}


def _load():
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        mtime = 0
    if _cache is not None and mtime == _cache_mtime:
        return dict(_cache)
    if not os.path.exists(CONFIG_PATH):
        _save(DEFAULT_CONFIG)
        _cache = dict(DEFAULT_CONFIG)
        _cache_mtime = 0
        return dict(_cache)
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    _cache = data
    _cache_mtime = mtime
    return dict(data)


def _save(data):
    global _cache, _cache_mtime
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        _cache_mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        _cache_mtime = 0
    _cache = data


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
