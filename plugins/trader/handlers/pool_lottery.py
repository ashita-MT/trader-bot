import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from core.utils import get_user_id
from ..engine.trading import get_or_create_user
from ..db import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config


def _get_settings():
    return {
        "ticket_price": bot_config.get("pool_lottery_ticket_price", 100),
        "winners_count": bot_config.get("pool_lottery_winners", 3),
    }


def get_current_round():
    conn = get_db()
    row = conn.execute("SELECT MAX(round) as r FROM pool_lottery_draws").fetchone()
    conn.close()
    return (row["r"] or 0) + 1


def get_pool_amount():
    conn = get_db()
    current_round = get_current_round()
    row = conn.execute("SELECT COUNT(*) as c FROM pool_lottery_tickets WHERE round = ?", (current_round,)).fetchone()
    conn.close()
    settings = _get_settings()
    return row["c"] * settings["ticket_price"]


def get_last_draw():
    conn = get_db()
    row = conn.execute("SELECT * FROM pool_lottery_draws ORDER BY round DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def draw_pool_lottery():
    settings = _get_settings()
    current_round = get_current_round()

    conn = get_db()
    tickets = conn.execute("""
        SELECT t.user_id, u.balance
        FROM pool_lottery_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.round = ?
    """, (current_round,)).fetchall()

    total_pool = len(tickets) * settings["ticket_price"]
    winners_count = min(settings["winners_count"], len(tickets))

    if winners_count == 0 or total_pool == 0:
        conn.execute("INSERT INTO pool_lottery_draws (round, total_pool, winners_count) VALUES (?, 0, 0)",
                     (current_round,))
        conn.execute("DELETE FROM pool_lottery_tickets WHERE round = ?", (current_round,))
        conn.commit()
        conn.close()
        return {"round": current_round, "total_pool": 0, "winners": 0, "prize_each": 0}

    # Randomly select winners
    winner_indices = random.sample(range(len(tickets)), winners_count)
    prize_each = round(total_pool / winners_count, 2)

    conn.execute("INSERT INTO pool_lottery_draws (round, total_pool, winners_count) VALUES (?, ?, ?)",
                 (current_round, total_pool, winners_count))

    for idx in winner_indices:
        w = tickets[idx]
        new_balance = round(w["balance"] + prize_each, 2)
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, w["user_id"]))

    conn.execute("DELETE FROM pool_lottery_tickets WHERE round = ?", (current_round,))
    conn.commit()
    conn.close()
    return {"round": current_round, "total_pool": total_pool, "winners": winners_count, "prize_each": prize_each}


async def handle_buy_pool_ticket(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)
    settings = _get_settings()

    if user["balance"] < settings["ticket_price"]:
        await message.reply(content=f"余额不足，票价 {settings['ticket_price']}，当前余额 {user['balance']:.2f}")
        return

    current_round = get_current_round()
    pool = get_pool_amount()
    new_balance = round(user["balance"] - settings["ticket_price"], 2)

    conn = get_db()
    conn.execute("UPDATE users SET balance = ? WHERE qq_id = ?", (new_balance, qq_id))
    conn.execute("INSERT INTO pool_lottery_tickets (user_id, round) VALUES (?, ?)", (user["id"], current_round))
    conn.commit()
    conn.close()

    new_pool = pool + settings["ticket_price"]
    await message.reply(content=f"购买成功！第{current_round}期 奖池彩\n票价: {settings['ticket_price']}，当前奖池: {new_pool:.2f}\n中奖人数: {settings['winners_count']}，余额: {new_balance:.2f}")


async def handle_pool_lottery_info(message, args):
    current_round = get_current_round()
    pool = get_pool_amount()
    settings = _get_settings()

    conn = get_db()
    ticket_count = conn.execute("SELECT COUNT(*) as c FROM pool_lottery_tickets WHERE round = ?", (current_round,)).fetchone()["c"]
    conn.close()

    lines = [
        f"=== 奖池彩 第{current_round}期 ===",
        f"票价: {settings['ticket_price']}",
        f"奖池: {pool:.2f}",
        f"已售: {ticket_count}张",
        f"中奖人数: {settings['winners_count']}",
    ]

    if ticket_count > 0:
        lines.append(f"每人奖金: {round(pool / settings['winners_count'], 2):.2f}")

    await message.reply(content="\n".join(lines))


async def handle_pool_lottery_history(message, args):
    last_draw = get_last_draw()

    if not last_draw or last_draw["total_pool"] == 0:
        await message.reply(content="暂无开奖记录")
        return

    await message.reply(content=f"第{last_draw['round']}期 奖池: {last_draw['total_pool']:.2f}\n中奖人数: {last_draw['winners_count']}")


async def handle_my_pool_tickets(message, args):
    qq_id = get_user_id(message)
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE qq_id = ?", (qq_id,)).fetchone()
    if not user:
        conn.close()
        await message.reply(content="未开户")
        return

    current_round = get_current_round()
    count = conn.execute("SELECT COUNT(*) as c FROM pool_lottery_tickets WHERE user_id = ? AND round = ?",
                         (user["id"], current_round)).fetchone()["c"]
    conn.close()

    if count == 0:
        await message.reply(content=f"第{current_round}期 你还没有奖池彩彩票")
        return

    await message.reply(content=f"第{current_round}期 你持有 {count} 张奖池彩彩票")
