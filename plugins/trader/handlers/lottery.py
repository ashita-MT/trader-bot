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


def _get_number_lottery_settings():
    return {
        "ticket_price": bot_config.get("lottery_ticket_price", 100),
        "prize_amount": bot_config.get("lottery_prize_amount", 10000),
        "max_tickets": bot_config.get("lottery_max_tickets", 10),
    }


def _get_pool_lottery_settings():
    return {
        "ticket_price": bot_config.get("pool_ticket_price", 100),
        "winner_count": bot_config.get("pool_winner_count", 3),
        "max_tickets": bot_config.get("pool_max_tickets", 10),
    }


# ========== 号码彩 ==========

def get_number_round():
    conn = get_db()
    row = conn.execute("SELECT MAX(round) as r FROM lottery_draws").fetchone()
    conn.close()
    return (row["r"] or 0) + 1


def get_last_number_draw():
    conn = get_db()
    row = conn.execute("SELECT * FROM lottery_draws ORDER BY round DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def draw_number_lottery():
    settings = _get_number_lottery_settings()
    current_round = get_number_round()
    winning_number = random.randint(*NUMBER_RANGE)

    conn = get_db()
    conn.execute("INSERT INTO lottery_draws (round, winning_number) VALUES (?, ?)", (current_round, winning_number))

    winners = conn.execute("""
        SELECT t.user_id, u.balance
        FROM lottery_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.round = ? AND t.number = ?
    """, (current_round, winning_number)).fetchall()

    for w in winners:
        new_balance = round(w["balance"] + settings["prize_amount"], 2)
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, w["user_id"]))

    conn.execute("DELETE FROM lottery_tickets WHERE round = ?", (current_round,))
    conn.commit()
    conn.close()
    return {"round": current_round, "winning_number": winning_number, "winners": len(winners)}


# ========== 奖池彩 ==========

def get_pool_round():
    conn = get_db()
    row = conn.execute("SELECT MAX(round) as r FROM pool_draws").fetchone()
    conn.close()
    return (row["r"] or 0) + 1


def get_last_pool_draw():
    conn = get_db()
    row = conn.execute("SELECT * FROM pool_draws ORDER BY round DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_pool_tickets_count(round_num):
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as c FROM pool_tickets WHERE round = ?", (round_num,)).fetchone()
    conn.close()
    return row["c"]


def draw_pool_lottery():
    settings = _get_pool_lottery_settings()
    current_round = get_pool_round()

    conn = get_db()
    tickets = conn.execute("""
        SELECT t.id, t.user_id, u.balance
        FROM pool_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.round = ?
    """, (current_round,)).fetchall()

    total_pool = len(tickets) * settings["ticket_price"]
    winner_count = min(settings["winner_count"], len(tickets))

    winners = []
    if tickets and winner_count > 0:
        winner_tickets = random.sample(list(tickets), winner_count)
        prize_each = round(total_pool / winner_count, 2)

        for w in winner_tickets:
            new_balance = round(w["balance"] + prize_each, 2)
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, w["user_id"]))
            winners.append(w["user_id"])

    conn.execute("INSERT INTO pool_draws (round, total_pool, winner_count) VALUES (?, ?, ?)",
                 (current_round, total_pool, len(winners)))
    conn.execute("DELETE FROM pool_tickets WHERE round = ?", (current_round,))
    conn.commit()
    conn.close()
    return {"round": current_round, "total_pool": total_pool, "winners": len(winners), "winner_count": winner_count}


# ========== 号码彩指令 ==========

async def handle_buy_number_ticket(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)
    settings = _get_number_lottery_settings()

    if not args:
        await message.reply(content=f"格式: 买号码彩 数字\n范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}\n票价: {settings['ticket_price']}\n奖金: {settings['prize_amount']}\n每人最多: {settings['max_tickets']}张")
        return

    try:
        number = int(args[0])
    except ValueError:
        await message.reply(content="请输入有效数字")
        return

    if number < NUMBER_RANGE[0] or number > NUMBER_RANGE[1]:
        await message.reply(content=f"数字范围: {NUMBER_RANGE[0]}-{NUMBER_RANGE[1]}")
        return

    current_round = get_number_round()

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

    await message.reply(content=f"号码彩购买成功！第{current_round}期 号码: {number}\n票价: {settings['ticket_price']}，余额: {new_balance:.2f}")


async def handle_number_lottery_history(message, args):
    last_draw = get_last_number_draw()
    if not last_draw or last_draw["winning_number"] is None:
        await message.reply(content="号码彩暂无中奖记录")
        return
    await message.reply(content=f"号码彩第{last_draw['round']}期 中奖号码: {last_draw['winning_number']}")


async def handle_my_number_tickets(message, args):
    qq_id = get_user_id(message)
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        await message.reply(content="未开户")
        return

    current_round = get_number_round()
    tickets = conn.execute("SELECT number FROM lottery_tickets WHERE user_id = ? AND round = ?",
                           (user["id"], current_round)).fetchall()
    conn.close()

    if not tickets:
        await message.reply(content=f"号码彩第{current_round}期 你还没有彩票")
        return

    nums = ", ".join([str(t["number"]) for t in tickets])
    settings = _get_number_lottery_settings()
    await message.reply(content=f"号码彩第{current_round}期 你的号码: {nums}\n共 {len(tickets)}/{settings['max_tickets']} 张")


# ========== 奖池彩指令 ==========

async def handle_buy_pool_ticket(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)
    settings = _get_pool_lottery_settings()

    current_round = get_pool_round()

    conn = get_db()
    my_count = conn.execute("SELECT COUNT(*) as c FROM pool_tickets WHERE user_id = ? AND round = ?",
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
    total_tickets = get_pool_tickets_count(current_round) + 1
    total_pool = total_tickets * settings["ticket_price"]

    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))
    conn.execute("INSERT INTO pool_tickets (user_id, round) VALUES (?, ?)", (user["id"], current_round))
    conn.commit()
    conn.close()

    await message.reply(content=f"奖池彩购买成功！第{current_round}期\n票价: {settings['ticket_price']}，当前奖池: {total_pool}\n中奖人数: {settings['winner_count']}，余额: {new_balance:.2f}")


async def handle_pool_info(message, args):
    settings = _get_pool_lottery_settings()
    current_round = get_pool_round()
    total_tickets = get_pool_tickets_count(current_round)
    total_pool = total_tickets * settings["ticket_price"]

    last_draw = get_last_pool_draw()

    lines = [
        f"=== 奖池彩 ===",
        f"第{current_round}期",
        f"票价: {settings['ticket_price']}",
        f"当前奖池: {total_pool}",
        f"当前票数: {total_tickets}",
        f"中奖人数: {settings['winner_count']}",
        f"每人最多: {settings['max_tickets']}张",
    ]

    if last_draw:
        lines.append(f"上期奖池: {last_draw['total_pool']}，中奖人数: {last_draw['winner_count']}")

    await message.reply(content="\n".join(lines))


async def handle_pool_lottery_history(message, args):
    last_draw = get_last_pool_draw()
    if not last_draw:
        await message.reply(content="奖池彩暂无开奖记录")
        return
    await message.reply(content=f"奖池彩第{last_draw['round']}期 奖池: {last_draw['total_pool']}，中奖人数: {last_draw['winner_count']}")


async def handle_my_pool_tickets(message, args):
    qq_id = get_user_id(message)
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        await message.reply(content="未开户")
        return

    current_round = get_pool_round()
    my_count = conn.execute("SELECT COUNT(*) as c FROM pool_tickets WHERE user_id = ? AND round = ?",
                            (user["id"], current_round)).fetchone()["c"]
    conn.close()

    settings = _get_pool_lottery_settings()
    await message.reply(content=f"奖池彩第{current_round}期 你持有 {my_count}/{settings['max_tickets']} 张")
