import json
import os
import time
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "stocks")
CACHE_TTL = 300  # 5 minutes
MAX_DAYS = 10


def _ensure_dir(code):
    d = os.path.join(DATA_DIR, code)
    os.makedirs(d, exist_ok=True)
    return d


def _latest_file(code):
    d = os.path.join(DATA_DIR, code)
    if not os.path.isdir(d):
        return None
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")], reverse=True)
    return os.path.join(d, files[0]) if files else None


def load_quote(code):
    path = _latest_file(code)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("timestamp", 0)
        if time.time() - ts > CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def save_quote(code, quote):
    d = _ensure_dir(code)
    now = datetime.now()
    filename = now.strftime("%Y%m%d_%H%M%S") + ".json"
    path = os.path.join(d, filename)
    quote["timestamp"] = time.time()
    quote["saved_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(quote, f, ensure_ascii=False, indent=2)
    _cleanup(code)


def _cleanup(code):
    d = os.path.join(DATA_DIR, code)
    if not os.path.isdir(d):
        return
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")])
    cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime("%Y%m%d")
    for f in files:
        if f[:8] < cutoff:
            os.remove(os.path.join(d, f))
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")])
    while len(files) > MAX_DAYS * 288:
        os.remove(os.path.join(d, files.pop(0)))


def load_history(code, days=10):
    d = os.path.join(DATA_DIR, code)
    if not os.path.isdir(d):
        return []
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")])
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    result = []
    seen_dates = set()
    for f in files:
        if f[:8] < cutoff:
            continue
        try:
            with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            date_str = data.get("date", "")
            if date_str and date_str not in seen_dates:
                seen_dates.add(date_str)
                result.append(data)
        except Exception:
            continue
    return result
