import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.local_cache import save_quote, load_quote
from .db import get_db
from .engine.real_market import REAL_STOCKS, fetch_all_quotes


def seed_stocks(enable_real=True, enable_virtual=True):
    conn = get_db()
    existing = conn.execute("SELECT code, is_virtual FROM stocks").fetchall()
    existing_codes = {row["code"] for row in existing}
    virtual_codes = {row["code"] for row in existing if row["is_virtual"]}
    real_codes = {row["code"] for row in existing if not row["is_virtual"]}

    if enable_real:
        try:
            quotes = fetch_all_quotes()
        except Exception as e:
            print(f"[Seed] fetch failed: {e}")
            quotes = {}

        for key, code, name in REAL_STOCKS:
            if code in virtual_codes:
                continue
            if code not in existing_codes:
                price = quotes[key]["price"] if key in quotes and quotes[key]["price"] > 0 else 100.0
                conn.execute(
                    "INSERT INTO stocks (code, name, current_price, open_price, high_price, low_price, is_virtual, is_enabled) VALUES (?, ?, ?, ?, ?, ?, 0, 1)",
                    (code, name, price, price, price, price),
                )
            else:
                if key in quotes and quotes[key]["price"] > 0:
                    q = quotes[key]
                    conn.execute(
                        "UPDATE stocks SET name=?, current_price=?, open_price=?, high_price=?, low_price=?, change_pct=? WHERE code=? AND is_virtual=0",
                        (name, q["price"], q["open"], q["high"], q["low"], q["change_pct"], code),
                    )
    else:
        # Disable all real stocks if feature is off
        conn.execute("UPDATE stocks SET is_enabled=0 WHERE is_virtual=0")
        print("[Seed] real stocks disabled", flush=True)

    if not enable_virtual:
        # Disable all virtual stocks if feature is off
        conn.execute("UPDATE stocks SET is_enabled=0 WHERE is_virtual=1")
        print("[Seed] virtual stocks disabled", flush=True)

    conn.commit()
    conn.close()
