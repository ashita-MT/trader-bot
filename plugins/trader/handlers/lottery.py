import sys
import os
import random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from core.utils import get_user_id
from ..engine.trading import get_or_create_user
from ..db import get_db

TICKET_PRICE = 100
PRIZE_AMOUNT = 10000
NUMBER_RANGE = (1, 1000)


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
        new_balance = round(w["balance"] + PRIZE_AMOUNT, 2)
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, w["user_id"]))

    conn.commit()
    conn.close()
    return {"round": current_round, "winning_number": winning_number, "winners": len(winners)}


async def handle_buy_ticket(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)

    if not args:
        await message.reply(content=f"格式: 买彩票 数字\n范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}\n票价: {TICKET_PRICE}")
        return

    try:
        number = int(args[0])
    except ValueError:
        await message.reply(content="请输入有效数字")
        return

    if number < NUMBER_RANGE[0] or number > NUMBER_RANGE[1]:
        await message.reply(content=f"数字范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}")
        return

    if user["balance"] < TICKET_PRICE:
        await message.reply(content=f"余额不足，票价 {TICKET_PRICE}，当前余额 {user['balance']:.2f}")
        return

    current_round = get_current_round()
    new_balance = round(user["balance"] - TICKET_PRICE, 2)

    conn = get_db()
    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))
    conn.execute("INSERT INTO lottery_tickets (user_id, number, round) VALUES (?, ?, ?)",
                 (user["id"], number, current_round))
    conn.commit()
    conn.close()

    await message.reply(content=f"购买成功！第{current_round}期 号码: {number}\n票价: {TICKET_PRICE}，余额: {new_balance:.2f}")


async def handle_lottery_info(message, args):
    last_draw = get_last_draw()
    current_round = get_current_round()

    if last_draw:
        lines = [
            f"=== lottery ===",
            f"第{last_draw['round']}期 中奖号码: {last_draw['winning_number']}",
            f"当前期: 第{current_round}期",
            f"票价: {TICKET_PRICE}",
            f"奖金: {PRIZE_AMOUNT}",
            f"范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}",
        ]
    else:
        lines = [
            f"=== lottery ===",
            f"尚未开奖",
            f"当前期: 第{current_round}期",
            f"票价: {TICKET_PRICE}",
            f"奖金: {PRIZE_AMOUNT}",
            f"范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}",
        ]

    # Show user tickets for current round
    qq_id = get_user_id(message)
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if user:
        tickets = conn.execute("SELECT number FROM lottery_tickets WHERE user_id = ? AND round = ?",
                               (user["id"], current_round)).fetchall()
        if tickets:
            nums = ", ".join([str(t["number"]) for t in tickets])
            lines.append(f"你的号码: {nums}")
    conn.close()

    await message.reply(content="\n".join(lines))


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
    await message.reply(content=f"第{current_round}期 你的号码: {nums}\n共 {len(tickets)} 张")
