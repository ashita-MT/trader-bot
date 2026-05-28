import re
import urllib.request
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.local_cache import load_quote, save_quote, load_history

TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={}"
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{days},qfq"

REAL_STOCKS = [
    ("hk00700", "00700", "腾讯控股"),
    ("hk09988", "09988", "阿里巴巴"),
    ("hk09618", "09618", "京东集团"),
    ("hk09626", "09626", "哔哩哔哩"),
    ("hk03690", "03690", "美团"),
    ("sh600036", "600036", "招商银行"),
    ("sh600519", "600519", "贵州茅台"),
    ("sz000858", "000858", "五粮液"),
]


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("gbk")


def _parse_quote(raw):
    match = re.search(r'"(.+?)"', raw)
    if not match:
        return None
    fields = match.group(1).split("~")
    if len(fields) < 35:
        return None
    return {
        "name": fields[1],
        "code": fields[2],
        "price": float(fields[3]) if fields[3] else 0.0,
        "open": float(fields[5]) if fields[5] else 0.0,
        "volume": int(float(fields[6])) if fields[6] else 0,
        "change_pct": float(fields[32]) if fields[32] else 0.0,
        "high": float(fields[33]) if fields[33] else 0.0,
        "low": float(fields[34]) if fields[34] else 0.0,
    }


def fetch_all_quotes():
    results = {}
    need_fetch = []
    for key, code, name in REAL_STOCKS:
        cached = load_quote(code)
        if cached:
            cached["stock_key"] = key
            results[key] = cached
        else:
            need_fetch.append((key, code, name))

    if need_fetch:
        codes = ",".join([s[0] for s in need_fetch])
        try:
            raw = _fetch(TENCENT_QUOTE_URL.format(codes))
            for line in raw.strip().split(";"):
                line = line.strip()
                if not line:
                    continue
                quote = _parse_quote(line)
                if quote and quote["price"] > 0:
                    for key, code, name in need_fetch:
                        if quote["code"] == code:
                            quote["stock_key"] = key
                            quote["date"] = quote.get("saved_at", "")
                            save_quote(code, quote)
                            results[key] = quote
                            break
        except Exception as e:
            print(f"[RealMarket] fetch failed: {e}")

    return results


def get_history(code, days=10):
    return load_history(code, days)
