import sys, os
from core.utils import get_user_id
from ..engine.trading import buy_stock, sell_stock, get_holdings, get_balance


async def handle_buy(message, args):
    if len(args) < 2:
        await message.reply(content="格式: 买入 股票代码 数量\n示例: 买入 00700 100")
        return

    stock_code = args[0].upper()
    try:
        quantity = int(args[1])
    except ValueError:
        await message.reply(content="数量必须是整数")
        return

    if quantity <= 0:
        await message.reply(content="数量必须大于0")
        return

    result = buy_stock(get_user_id(message), stock_code, quantity)
    await message.reply(content=result["msg"])


async def handle_sell(message, args):
    if len(args) < 2:
        await message.reply(content="格式: 卖出 股票代码 数量\n示例: 卖出 00700 50")
        return

    stock_code = args[0].upper()
    try:
        quantity = int(args[1])
    except ValueError:
        await message.reply(content="数量必须是整数")
        return

    if quantity <= 0:
        await message.reply(content="数量必须大于0")
        return

    result = sell_stock(get_user_id(message), stock_code, quantity)
    await message.reply(content=result["msg"])


async def handle_holdings(message, args):
    qq_id = get_user_id(message)
    balance = get_balance(qq_id)
    if balance == 0.0:
        await message.reply(content="未开户，发送「开户」创建账户")
        return

    holdings = get_holdings(qq_id)
    if not holdings:
        await message.reply(content=f"当前无持仓\n余额: {balance:.2f}")
        return

    total_value = balance
    lines = ["=== 我的持仓 ===", f"余额: {balance:.2f}", ""]
    for h in holdings:
        market_value = h["current_price"] * h["quantity"]
        profit = (h["current_price"] - h["avg_cost"]) * h["quantity"]
        profit_pct = (h["current_price"] / h["avg_cost"] - 1) * 100 if h["avg_cost"] > 0 else 0
        total_value += market_value
        sign = "+" if profit >= 0 else ""
        lines.append(f"{h['name']}({h['stock_code']})")
        lines.append(f"  持仓: {h['quantity']}股 | 成本: {h['avg_cost']:.2f} | 现价: {h['current_price']:.2f}")
        lines.append(f"  盈亏: {sign}{profit:.2f} ({sign}{profit_pct:.2f}%)")
        lines.append("")

    lines.append(f"总资产: {total_value:.2f}")
    await message.reply(content="\n".join(lines))
