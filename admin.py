import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import config

app = FastAPI(title="Bot Admin")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", "stock_market", "trader.db")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


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
        if k in ("interaction_mode", "bot_name", "web_port", "enable_real_stocks", "enable_virtual_stocks", "enable_real_refresh", "enable_virtual_refresh", "real_refresh_interval", "virtual_refresh_interval"):
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
    except Exception as e:
        print(f"[Admin] /api/stocks error: {e}", flush=True)
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
        print(f"[Admin] create virtual: code={code} name={name} price={price} vol={volatility}", flush=True)

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
        print(f"[Admin] create virtual success: {code}", flush=True)
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"[Admin] create virtual error: {e}", flush=True)
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

        print(f"[Admin] update virtual: {code} -> code={new_code} name={name} price={price} enabled={is_enabled} vol={volatility}", flush=True)

        conn.execute(
            "UPDATE stocks SET code=?, name=?, current_price=?, open_price=?, high_price=?, low_price=?, is_enabled=?, volatility=? WHERE code=? AND is_virtual=1",
            (new_code, name, price, price, price, price, is_enabled, volatility, code),
        )
        conn.commit()
        conn.close()
        print(f"[Admin] update virtual success: {new_code}", flush=True)
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"[Admin] update virtual error: {e}", flush=True)
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
        print(f"[Admin] delete virtual success: {code}", flush=True)
        return JSONResponse({"ok": True})
    except Exception as e:
        print(f"[Admin] delete virtual error: {e}", flush=True)
        return JSONResponse({"error": str(e)}, status_code=500)


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


if __name__ == "__main__":
    import uvicorn
    port = config.get("web_port", 6662)
    print(f"[Admin] http://localhost:{port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)

