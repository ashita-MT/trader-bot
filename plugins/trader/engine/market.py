import time
import hashlib
from datetime import date
from ..db import get_db
from .real_market import fetch_all_quotes, get_history, REAL_STOCKS


def refresh_prices():
    conn = get_db()
    try:
        quotes = fetch_all_quotes()
        for key, code, name in REAL_STOCKS:
            if key in quotes and quotes[key]["price"] > 0:
                q = quotes[key]
                conn.execute(
                    "UPDATE stocks SET name=?, current_price=?, open_price=?, high_price=?, low_price=?, change_pct=?, updated_at=CURRENT_TIMESTAMP WHERE code=? AND is_virtual=0",
                    (name, q["price"], q["open"], q["high"], q["low"], q["change_pct"], code),
                )
        conn.commit()
    except Exception as e:
        print(f"[Market] sync failed: {e}")
    finally:
        conn.close()


def refresh_virtual_prices():
    conn = get_db()
    try:
        stocks = conn.execute(
            "SELECT code, current_price, high_price, low_price, volatility FROM stocks WHERE is_virtual=1 AND is_enabled=1"
        ).fetchall()

        if not stocks:
            return

        timestamp = int(time.time())

        for s in stocks:
            key = f"{s['code']}_{timestamp}"
            h = hashlib.md5(key.encode()).hexdigest()
            num = int(h[:8], 16)
            vol = s["volatility"] if s["volatility"] is not None else 3.0
            if vol == 0:
                continue
            # Map to [-vol%, +vol%]
            change_pct = (num / 0xFFFFFFFF - 0.5) * 2 * vol

            old_price = s["current_price"]
            new_price = round(old_price * (1 + change_pct / 100), 2)
            if new_price < 0.01:
                new_price = 0.01

            new_high = max(s["high_price"], new_price)
            new_low = min(s["low_price"], new_price)

            conn.execute(
                "UPDATE stocks SET current_price=?, high_price=?, low_price=?, change_pct=?, updated_at=CURRENT_TIMESTAMP WHERE code=? AND is_virtual=1",
                (new_price, new_high, new_low, round(change_pct, 2), s["code"]),
            )

        conn.commit()
        print(f"[Market] virtual refreshed {len(stocks)} stocks", flush=True)
    except Exception as e:
        print(f"[Market] virtual refresh failed: {e}", flush=True)
    finally:
        conn.close()


def get_all_stocks():
    conn = get_db()
    stocks = conn.execute("SELECT * FROM stocks WHERE is_enabled=1 ORDER BY is_virtual DESC, code").fetchall()
    conn.close()
    return stocks


def get_stock(code):
    conn = get_db()
    stock = conn.execute("SELECT * FROM stocks WHERE code = ? AND is_enabled=1", (code.upper(),)).fetchone()
    conn.close()
    return stock


def get_price_history(code, days=10):
    return get_history(code.upper(), days)


