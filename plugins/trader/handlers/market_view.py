from ..engine.market import get_all_stocks


async def handle_market(message, args):
    stocks = get_all_stocks()
    if not stocks:
        await message.reply(content="暂无股票数据")
        return

    lines = ["=== 行情 ===", ""]
    for s in stocks:
        sign = "+" if s["change_pct"] >= 0 else ""
        lines.append(f"{s['name']}({s['code']})  {s['current_price']:.2f}  {sign}{s['change_pct']:.2f}%")
    await message.reply(content="\n".join(lines))
