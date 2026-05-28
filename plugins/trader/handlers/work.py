import sys
import os
import random
from datetime import datetime

from core.utils import get_user_id
from ..engine.trading import get_or_create_user
from ..db import get_db


async def handle_work(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)

    today = datetime.now().strftime("%Y-%m-%d")
    if user.get("last_work") == today:
        await message.reply(content="今天已经打过工了，明天再来吧")
        return

    amount = random.randint(1000, 10000)
    new_balance = user["balance"] + amount

    conn = get_db()
    conn.execute("UPDATE users SET balance=?, last_work=? WHERE qq_id=?", (new_balance, today, qq_id))
    conn.commit()
    conn.close()

    await message.reply(content=f"打工成功，获得 {amount}，当前余额 {new_balance:.2f}")
