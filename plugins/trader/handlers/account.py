import sys, os
from core.utils import get_user_id
from ..engine.trading import get_or_create_user, get_balance


async def handle_register(message, args):
    qq_id = get_user_id(message)
    nickname = getattr(message.author, "username", "") or ""
    user = get_or_create_user(qq_id, nickname)
    await message.reply(
        content=f"开户成功！\n"
                f"账户ID: {user['id']}\n"
                f"初始余额: {user['balance']:.2f}"
    )


async def handle_balance(message, args):
    qq_id = get_user_id(message)
    balance = get_balance(qq_id)
    if balance == 0.0:
        await message.reply(content="未开户，发送「开户」创建账户")
        return
    await message.reply(content=f"当前余额: {balance:.2f}")
