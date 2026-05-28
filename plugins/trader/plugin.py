import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config as bot_config
from core.base import BasePlugin
from core.keyboard import build_keyboard
from .db import init_db
from .seed import seed_stocks
from .engine.scheduler import MarketScheduler
from .handlers.account import handle_register, handle_balance
from .handlers.trade import handle_buy, handle_sell, handle_holdings
from .handlers.market_view import handle_market
from .handlers.work import handle_work
from .handlers.number_lottery import handle_buy_number_lottery, handle_number_lottery_history, handle_my_number_tickets
from .handlers.pool_lottery import handle_buy_pool_ticket, handle_pool_lottery_info, handle_pool_lottery_history, handle_my_pool_tickets


HELP_TEXT = (
    "=== trader ===\n\n"
    "开户          - create account\n"
    "查余额        - check balance\n"
    "买入 X N      - buy N shares of X\n"
    "卖出 X N      - sell N shares of X\n"
    "持仓          - view holdings\n"
    "行情          - view all stocks\n"
    "打工          - work once per day (1000-10000)\n\n"
    "--- 号码彩 ---\n"
    "买号码彩 N    - buy number lottery ticket\n"
    "号码彩历史    - last winning number\n"
    "我的号码彩    - my number tickets\n\n"
    "--- 奖池彩 ---\n"
    "买奖池彩      - buy pool lottery ticket\n"
    "奖池彩        - pool lottery info\n"
    "奖池彩历史    - last draw result\n"
    "我的奖池彩    - my pool tickets\n\n"
    "帮助          - show help\n"
)

HELP_KEYBOARD = build_keyboard([
    [
        {"id": "btn_register", "label": "开户", "data": "开户", "style": 1},
        {"id": "btn_balance", "label": "查余额", "data": "查余额", "style": 1},
    ],
    [
        {"id": "btn_market", "label": "行情", "data": "行情", "style": 1},
        {"id": "btn_hold", "label": "持仓", "data": "持仓", "style": 1},
    ],
    [
        {"id": "btn_number_lottery", "label": "号码彩", "data": "号码彩历史", "style": 1},
        {"id": "btn_pool_lottery", "label": "奖池彩", "data": "奖池彩", "style": 1},
    ],
])


class Plugin(BasePlugin):
    name = "trader"
    version = "1.8.0"
    description = "QQ virtual stock trading plugin with lottery"

    def __init__(self):
        self.scheduler = MarketScheduler()

    async def setup(self, bot):
        init_db()
        enable_real = bot_config.get("enable_real_stocks", True)
        enable_virtual = bot_config.get("enable_virtual_stocks", True)
        enable_real_refresh = bot_config.get("enable_real_refresh", True)
        enable_virtual_refresh = bot_config.get("enable_virtual_refresh", True)
        enable_number_lottery = bot_config.get("enable_number_lottery", True)
        enable_pool_lottery = bot_config.get("enable_pool_lottery", True)
        real_interval = bot_config.get("real_refresh_interval", 300)
        virtual_interval = bot_config.get("virtual_refresh_interval", 300)
        number_lottery_interval = bot_config.get("number_lottery_interval", 86400)
        pool_lottery_interval = bot_config.get("pool_lottery_interval", 86400)

        if enable_real or enable_virtual:
            seed_stocks(enable_real=enable_real, enable_virtual=enable_virtual)

        started = False
        if enable_real and enable_real_refresh:
            self.scheduler.start_real(interval=real_interval)
            started = True

        if enable_virtual and enable_virtual_refresh:
            self.scheduler.start_virtual(interval=virtual_interval)
            started = True

        if enable_number_lottery:
            self.scheduler.start_number_lottery(interval=number_lottery_interval)
            started = True

        if enable_pool_lottery:
            self.scheduler.start_pool_lottery(interval=pool_lottery_interval)
            started = True

        if started:
            self.scheduler.start()
        else:
            print("[Trader] all refresh disabled", flush=True)

    async def teardown(self):
        self.scheduler.stop()

    def get_commands(self):
        return {
            "开户": handle_register,
            "查余额": handle_balance,
            "余额": handle_balance,
            "买入": handle_buy,
            "卖出": handle_sell,
            "持仓": handle_holdings,
            "行情": handle_market,
            "打工": handle_work,
            "买号码彩": handle_buy_number_lottery,
            "号码彩历史": handle_number_lottery_history,
            "我的号码彩": handle_my_number_tickets,
            "买奖池彩": handle_buy_pool_ticket,
            "奖池彩": handle_pool_lottery_info,
            "奖池彩历史": handle_pool_lottery_history,
            "我的奖池彩": handle_my_pool_tickets,
            "帮助": self._handle_help,
        }

    async def _handle_help(self, message, args):
        import json
        mode = bot_config.get_mode()
        is_interaction = hasattr(message, "_interaction")

        if is_interaction:
            await message.reply(content=HELP_TEXT)
            return

        if mode == "button":
            has_keyboard = hasattr(message, "_api") and hasattr(message, "channel_id")
            if has_keyboard and message.channel_id:
                try:
                    await message.reply(content=HELP_TEXT, keyboard=json.dumps(HELP_KEYBOARD))
                    return
                except Exception:
                    pass

        await message.reply(content=HELP_TEXT)
