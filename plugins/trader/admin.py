import sys
import os

# Plugin root directory
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, PLUGIN_DIR)

import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Trader Admin")

DB_PATH = os.path.join(PLUGIN_DIR, "trader.db")
TEMPLATE_DIR = os.path.join(PLUGIN_DIR, "templates")

# Import config from parent project
sys.path.insert(0, os.path.join(PLUGIN_DIR, "..", ".."))
import config


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(TEMPLATE_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/config")
async def get_config():
    return JSONResponse(config.get())


@app.post("/api/config")
async def set_config(request: Request):
    body = await request.json()
    for k, v in body.items():
        if k in ("interaction_mode", "bot_name", "web_port",
                 "enable_real_stocks", "enable_virtual_stocks",
                 "enable_real_refresh", "enable_virtual_refresh",
                 "real_refresh_interval", "virtual_refresh_interval",
                 "enable_number_lottery", "number_lottery_interval",
                 "number_lottery_ticket_price", "number_lottery_prize_amount",
                 "number_lottery_max_tickets",
                 "enable_pool_lottery", "pool_lottery_interval",
                 "pool_lottery_ticket_price", "pool_lottery_winners_pct", "pool_lottery_max_tickets"):
            config.set(k, v)
    return JSONResponse(config.get())


@app.get("/api/stats")
async def get_stats():
    try:
        conn = get_db()
        stocks = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        holdings = conn.execute("SELECT COUNT(*) FROM holdings WHERE quantity > 0").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()
        return JSONResponse({"stocks": stocks, "users": users, "holdings": holdings, "orders": orders})
    except Exception:
        return JSONResponse({"stocks": 0, "users": 0, "holdings": 0, "orders": 0})


@app.get("/api/stocks")
async def get_stocks():
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM stocks ORDER BY is_virtual DESC, code").fetchall()
        conn.close()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])


@app.get("/api/stocks/real")
async def get_real_stocks():
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM stocks WHERE is_virtual=0 ORDER BY code").fetchall()
        conn.close()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])


@app.get("/api/stocks/virtual")
async def get_virtual_stocks():
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM stocks WHERE is_virtual=1 ORDER BY code").fetchall()
        conn.close()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])


@app.post("/api/stocks/virtual")
async def create_virtual_stock(request: Request):
    try:
        body = await request.json()
        code = body.get("code", "").strip()
        name = body.get("name", "").strip()
        price = float(body.get("price", 0))
        volatility = float(body.get("volatility", 3.0))

        if not code or not name:
            return JSONResponse({"error": "code and name required"}, status_code=400)
        if price <= 0:
            return JSONResponse({"error": "price must be positive"}, status_code=400)
        if volatility > 100:
            volatility = 3.0

        conn = get_db()
        existing = conn.execute("SELECT id FROM stocks WHERE code=?", (code,)).fetchone()
        if existing:
            conn.close()
            return JSONResponse({"error": "stock code already exists"}, status_code=400)

        conn.execute(
            "INSERT INTO stocks (code, name, current_price, open_price, high_price, low_price, is_virtual, is_enabled, volatility) VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)",
            (code, name, price, price, price, price, volatility),
        )
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.put("/api/stocks/virtual/{code}")
async def update_virtual_stock(code: str, request: Request):
    try:
        body = await request.json()
        conn = get_db()
        stock = conn.execute("SELECT * FROM stocks WHERE code=? AND is_virtual=1", (code,)).fetchone()
        if not stock:
            conn.close()
            return JSONResponse({"error": "virtual stock not found"}, status_code=404)

        new_code = str(body.get("code", code)).strip()
        name = str(body.get("name", stock["name"])).strip()
        price = float(body.get("price", stock["current_price"]))
        is_enabled = int(body.get("is_enabled", stock["is_enabled"]))
        volatility = float(body.get("volatility", stock["volatility"]))

        if not new_code or not name:
            return JSONResponse({"error": "code and name required"}, status_code=400)
        if price <= 0:
            return JSONResponse({"error": "price must be positive"}, status_code=400)
        if volatility > 100:
            volatility = 3.0

        if new_code != code:
            existing = conn.execute("SELECT id FROM stocks WHERE code=?", (new_code,)).fetchone()
            if existing:
                conn.close()
                return JSONResponse({"error": f"code {new_code} already exists"}, status_code=400)
            conn.execute("UPDATE holdings SET stock_code=? WHERE stock_code=?", (new_code, code))
            conn.execute("UPDATE orders SET stock_code=? WHERE stock_code=?", (new_code, code))

        conn.execute(
            "UPDATE stocks SET code=?, name=?, current_price=?, open_price=?, high_price=?, low_price=?, is_enabled=?, volatility=? WHERE code=? AND is_virtual=1",
            (new_code, name, price, price, price, price, is_enabled, volatility, code),
        )
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/stocks/virtual/{code}")
async def delete_virtual_stock(code: str):
    try:
        conn = get_db()
        stock = conn.execute("SELECT * FROM stocks WHERE code=? AND is_virtual=1", (code,)).fetchone()
        if not stock:
            conn.close()
            return JSONResponse({"error": "virtual stock not found"}, status_code=404)

        holders = conn.execute("SELECT COUNT(*) FROM holdings WHERE stock_code=? AND quantity>0", (code,)).fetchone()[0]
        if holders > 0:
            conn.close()
            return JSONResponse({"error": f"cannot delete: {holders} users hold this stock"}, status_code=400)

        conn.execute("DELETE FROM stocks WHERE code=? AND is_virtual=1", (code,))
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



@app.get("/api/lottery")
async def get_lottery():
    try:
        conn = get_db()
        nl_tickets = conn.execute("SELECT COUNT(*) FROM number_lottery_tickets t JOIN number_lottery_draws d ON t.round = d.round WHERE d.winning_number IS NULL").fetchone()[0]
        nl_draw = conn.execute("SELECT MAX(round) FROM number_lottery_draws").fetchone()[0] or 0
        nl_last = conn.execute("SELECT winning_number FROM number_lottery_draws WHERE winning_number IS NOT NULL ORDER BY round DESC LIMIT 1").fetchone()
        nl_last_num = nl_last[0] if nl_last else None
        pl_tickets = conn.execute("SELECT COUNT(*) FROM pool_lottery_tickets t JOIN pool_lottery_draws d ON t.round = d.round WHERE d.total_pool = 0").fetchone()[0]
        pl_draw = conn.execute("SELECT MAX(round) FROM pool_lottery_draws").fetchone()[0] or 0
        pl_last = conn.execute("SELECT winners_count, total_pool FROM pool_lottery_draws WHERE total_pool > 0 ORDER BY round DESC LIMIT 1").fetchone()
        conn.close()
        return JSONResponse({
            "nl_enabled": config.get("enable_number_lottery", True),
            "nl_round": nl_draw + 1,
            "nl_tickets": nl_tickets,
            "nl_last": str(nl_last_num) if nl_last_num else None,
            "pl_enabled": config.get("enable_pool_lottery", True),
            "pl_round": pl_draw + 1,
            "pl_tickets": pl_tickets,
            "pl_pool": 0,
            "pl_last": f"{pl_last[0]} winners" if pl_last else None,
            "pl_pct": config.get("pool_lottery_winners_pct", 10),
        })
    except Exception as e:
        return JSONResponse({
            "nl_enabled": config.get("enable_number_lottery", True),
            "nl_round": 1, "nl_tickets": 0, "nl_last": None,
            "pl_enabled": config.get("enable_pool_lottery", True),
            "pl_round": 1, "pl_tickets": 0, "pl_pool": 0, "pl_last": None, "pl_pct": 10,
        })

@app.get("/api/users")
async def get_users():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT u.*, COALESCE(h.cnt, 0) as holding_count
            FROM users u LEFT JOIN (
                SELECT user_id, COUNT(*) as cnt FROM holdings WHERE quantity > 0 GROUP BY user_id
            ) h ON u.id = h.user_id
            ORDER BY u.id
        """).fetchall()
        conn.close()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])


@app.get("/api/users/{qq_id}")
async def get_user_detail(qq_id: str):
    try:
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
        if not user:
            conn.close()
            return JSONResponse({"error": "not found"}, status_code=404)
        holdings = conn.execute("""
            SELECT h.*, s.name, s.current_price
            FROM holdings h JOIN stocks s ON h.stock_code = s.code
            WHERE h.user_id = ? AND h.quantity > 0
        """, (user["id"],)).fetchall()
        conn.close()
        return JSONResponse({"user": dict(user), "holdings": [dict(r) for r in holdings]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
