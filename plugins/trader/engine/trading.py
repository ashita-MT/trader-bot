from ..db import get_db


def resolve_stock(identifier):
    identifier = identifier.strip().upper()
    conn = get_db()
    stock = conn.execute("SELECT * FROM stocks WHERE code = ? AND is_enabled=1", (identifier,)).fetchone()
    if stock:
        conn.close()
        return dict(stock)
    stock = conn.execute("SELECT * FROM stocks WHERE UPPER(name) LIKE ? AND is_enabled=1", (f"%{identifier}%",)).fetchone()
    conn.close()
    if stock:
        return dict(stock)
    return None


def get_or_create_user(qq_id, nickname=""):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users (qq_id, nickname) VALUES (?, ?)", (qq_id, nickname))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    conn.close()
    return dict(user)


def get_balance(qq_id):
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    conn.close()
    return user["balance"] if user else 0.0


def buy_stock(qq_id, identifier, quantity):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        return {"success": False, "msg": "未开户，发送「开户」创建账户"}

    stock = conn.execute("SELECT * FROM stocks WHERE (UPPER(name) LIKE ? OR code = ?) AND is_enabled=1",
                         (f"%{identifier.upper()}%", identifier.upper())).fetchone()
    if not stock:
        conn.close()
        return {"success": False, "msg": f"股票 {identifier} 不存在或未启用"}

    total_cost = stock["current_price"] * quantity
    if user["balance"] < total_cost:
        conn.close()
        return {"success": False, "msg": f"余额不足，需要 {total_cost:.2f}，当前余额 {user['balance']:.2f}"}

    new_balance = user["balance"] - total_cost
    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))

    holding = conn.execute(
        "SELECT * FROM holdings WHERE user_id = ? AND stock_code = ?",
        (user["id"], stock["code"]),
    ).fetchone()

    if holding:
        new_qty = holding["quantity"] + quantity
        new_avg = (holding["avg_cost"] * holding["quantity"] + total_cost) / new_qty
        conn.execute(
            "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE id = ?",
            (new_qty, round(new_avg, 4), holding["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO holdings (user_id, stock_code, quantity, avg_cost) VALUES (?, ?, ?, ?)",
            (user["id"], stock["code"], quantity, stock["current_price"]),
        )

    conn.execute(
        "INSERT INTO orders (user_id, stock_code, order_type, quantity, price) VALUES (?, ?, 'buy', ?, ?)",
        (user["id"], stock["code"], quantity, stock["current_price"]),
    )

    conn.commit()
    conn.close()
    return {
        "success": True,
        "msg": f"买入 {stock['name']}({stock['code']}) x{quantity}，花费 {total_cost:.2f}，剩余余额 {new_balance:.2f}",
    }


def sell_stock(qq_id, identifier, quantity):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        return {"success": False, "msg": "未开户，发送「开户」创建账户"}

    stock = conn.execute("SELECT * FROM stocks WHERE (UPPER(name) LIKE ? OR code = ?) AND is_enabled=1",
                         (f"%{identifier.upper()}%", identifier.upper())).fetchone()
    if not stock:
        conn.close()
        return {"success": False, "msg": f"股票 {identifier} 不存在或未启用"}

    holding = conn.execute(
        "SELECT * FROM holdings WHERE user_id = ? AND stock_code = ?",
        (user["id"], stock["code"]),
    ).fetchone()

    if not holding or holding["quantity"] < quantity:
        current = holding["quantity"] if holding else 0
        conn.close()
        return {"success": False, "msg": f"持仓不足，当前持有 {stock['code']} {current} 股"}

    total_income = stock["current_price"] * quantity
    new_balance = user["balance"] + total_income
    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))

    new_qty = holding["quantity"] - quantity
    if new_qty == 0:
        conn.execute("DELETE FROM holdings WHERE id = ?", (holding["id"],))
    else:
        conn.execute("UPDATE holdings SET quantity = ? WHERE id = ?", (new_qty, holding["id"]))

    conn.execute(
        "INSERT INTO orders (user_id, stock_code, order_type, quantity, price) VALUES (?, ?, 'sell', ?, ?)",
        (user["id"], stock["code"], quantity, stock["current_price"]),
    )

    conn.commit()
    conn.close()
    return {
        "success": True,
        "msg": f"卖出 {stock['name']}({stock['code']}) x{quantity}，收入 {total_income:.2f}，当前余额 {new_balance:.2f}",
    }


def get_holdings(qq_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        return []

    rows = conn.execute(
        """SELECT h.*, s.name, s.current_price
           FROM holdings h JOIN stocks s ON h.stock_code = s.code
           WHERE h.user_id = ? AND h.quantity > 0""",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
