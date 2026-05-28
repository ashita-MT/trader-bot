import json
import os
import time

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PLUGIN_DIR, "data", "stocks")
QUOTE_TTL = 300


def _stock_dir(code):
    d = os.path.join(CACHE_DIR, code)
    os.makedirs(d, exist_ok=True)
    return d


def save_quote(code, data):
    d = _stock_dir(code)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(d, f"{ts}.json")
    data["saved_at"] = ts
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cleanup_old(d, max_files=2880)


def load_quote(code):
    d = _stock_dir(code)
    files = sorted(os.listdir(d), reverse=True)
    if not files:
        return None
    newest = os.path.join(d, files[0])
    with open(newest, "r", encoding="utf-8") as f:
        data = json.load(f)
    saved_at = data.get("saved_at", "")
    try:
        ts_str = saved_at.replace("_", "").replace("-", "")
        saved_ts = time.mktime(time.strptime(ts_str, "%Y%m%d%H%M%S"))
    except Exception:
        return None
    if time.time() - saved_ts > QUOTE_TTL:
        return None
    return data


def load_history(code, days=10):
    d = _stock_dir(code)
    if not os.path.isdir(d):
        return []
    cutoff = time.time() - days * 86400
    results = []
    for fname in sorted(os.listdir(d), reverse=True):
        path = os.path.join(d, fname)
        try:
            ts_str = fname.replace(".json", "").replace("_", "").replace("-", "")
            file_ts = time.mktime(time.strptime(ts_str, "%Y%m%d%H%M%S"))
            if file_ts < cutoff:
                continue
            with open(path, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            continue
    return results


def _cleanup_old(d, max_files=2880):
    files = sorted(os.listdir(d))
    if len(files) > max_files:
        for f in files[: len(files) - max_files]:
            try:
                os.remove(os.path.join(d, f))
            except Exception:
                pass
