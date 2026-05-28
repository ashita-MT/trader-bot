import sys
import os
import random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from core.utils import get_user_id
from ..engine.trading import get_or_create_user
from ..db import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config

NUMBER_RANGE = (1, 1000)


def _get_settings():
    return {
        "ticket_price": bot_config.get("lottery_ticket_price", 100),
        "prize_amount": bot_config.get("lottery_prize_amount", 10000),
        "max_tickets": bot_config.get("lottery_max_tickets", 10),
    }


def get_current_round():
    conn = get_db()
    row = conn.execute("SELECT MAX(round) as r FROM lottery_draws").fetchone()
    conn.close()
    return (row["r"] or 0) + 1


def get_last_draw():
    conn = get_db()
    row = conn.execute("SELECT * FROM lottery_draws ORDER BY round DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def draw_lottery():
    settings = _get_settings()
    current_round = get_current_round()
    winning_number = random.randint(*NUMBER_RANGE)

    conn = get_db()
    conn.execute("INSERT INTO lottery_draws (round, winning_number) VALUES (?, ?)", (current_round, winning_number))

    winners = conn.execute("""
        SELECT t.user_id, u.qq_id, u.balance
        FROM lottery_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.round = ? AND t.number = ?
    """, (current_round, winning_number)).fetchall()

    for w in winners:
        new_balance = round(w["balance"] + settings["prize_amount"], 2)
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, w["user_id"]))

    # Destroy all tickets for this round
    conn.execute("DELETE FROM lottery_tickets WHERE round = ?", (current_round,))

    conn.commit()
    conn.close()
    return {"round": current_round, "winning_number": winning_number, "winners": len(winners)}


async def handle_buy_ticket(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)
    settings = _get_settings()

    if not args:
        await message.reply(content=f"格式: 买彩票 数字\n范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}\n票价: {settings['ticket_price']}\n每人最多: {settings['max_tickets']}张")
        return

    try:
        number = int(args[0])
    except ValueError:
        await message.reply(content="请输入有效数字")
        return

    if number < NUMBER_RANGE[0] or number > NUMBER_RANGE[1]:
        await message.reply(content=f"数字范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}")
        return

    current_round = get_current_round()

    # Check max tickets
    conn = get_db()
    my_count = conn.execute("SELECT COUNT(*) as c FROM lottery_tickets WHERE user_id = ? AND round = ?",
                            (user["id"], current_round)).fetchone()["c"]
    if my_count >= settings["max_tickets"]:
        conn.close()
        await message.reply(content=f"每人每期最多 {settings['max_tickets']} 张，当前已持有 {my_count} 张")
        return

    if user["balance"] < settings["ticket_price"]:
        conn.close()
        await message.reply(content=f"余额不足，票价 {settings['ticket_price']}，当前余额 {user['balance']:.2f}")
        return

    new_balance = round(user["balance"] - settings["ticket_price"], 2)
    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))
    conn.execute("INSERT INTO lottery_tickets (user_id, number, round) VALUES (?, ?, ?)",
                 (user["id"], number, current_round))
    conn.commit()
    conn.close()

    await message.reply(content=f"购买成功！第{current_round}期 号码: {number}\n票价: {settings['ticket_price']}，余额: {new_balance:.2f}")


async def handle_lottery_history(message, args):
    last_draw = get_last_draw()

    if not last_draw or last_draw["winning_number"] is None:
        await message.reply(content="暂无中奖记录")
        return

    await message.reply(content=f"第{last_draw['round']}期 中奖号码: {last_draw['winning_number']}")


async def handle_my_tickets(message, args):
    qq_id = get_user_id(message)
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        await message.reply(content="未开户")
        return

    current_round = get_current_round()
    tickets = conn.execute("SELECT number FROM lottery_tickets WHERE user_id = ? AND round = ?",
                           (user["id"], current_round)).fetchall()
    conn.close()

    if not tickets:
        await message.reply(content=f"第{current_round}期 你还没有彩票")
        return

    nums = ", ".join([str(t["number"]) for t in tickets])
    settings = _get_settings()
    await message.reply(content=f"第{current_round}期 你的号码: {nums}\n共 {len(tickets)}/{settings['max_tickets']} 张")
