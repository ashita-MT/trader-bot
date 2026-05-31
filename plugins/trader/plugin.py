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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from plugins.admin.admin import register_plugin


# Command registry: (command, description, tag, keyboard_label, keyboard_data, keyboard_id)
COMMAND_REGISTRY = [
    ("开户",   "开户          - 开通账户",       "core",   "开户",   "开户",   "btn_register"),
    ("查余额", "查余额        - 查看余额",       "core",   "查余额", "查余额", "btn_balance"),
    ("买入",   "买入 股票 数量  - 买入指定数量的股票", "core", None, None, None),
    ("卖出",   "卖出 股票 数量  - 卖出指定数量的股票", "core", None, None, None),
    ("持仓",   "持仓          - 查看持仓",       "core",   "持仓",   "持仓",   "btn_hold"),
    ("打工",   "打工          - 每日打工 (1000-10000)", "work", None, None, None),
    ("行情",   "行情          - 查看所有股票",     "market", "行情", "行情", "btn_market"),
    ("买号码彩", "买号码彩 号码  - 购买号码彩票",   "number_lottery", None, None, None),
    ("号码彩历史", "号码彩历史    - 查看上次中奖号码", "number_lottery", "号码彩", "号码彩历史", "btn_number_lottery"),
    ("我的号码彩", "我的号码彩    - 查看我的号码彩",  "number_lottery", None, None, None),
    ("买奖池彩", "买奖池彩      - 购买奖池彩票",   "pool_lottery", None, None, None),
    ("奖池彩",   "奖池彩        - 查看奖池信息",   "pool_lottery", "奖池彩", "奖池彩", "btn_pool_lottery"),
    ("奖池彩历史", "奖池彩历史    - 查看上次开奖结果", "pool_lottery", None, None, None),
    ("我的奖池彩", "我的奖池彩    - 查看我的奖池彩",  "pool_lottery", None, None, None),
    ("帮助",   "帮助          - 显示帮助",       "core", None, None, None),
]

TAG_TITLES = {
    "core": None,
    "work": None,
    "market": "--- 股市 ---",
    "number_lottery": "--- 号码彩 ---",
    "pool_lottery": "--- 奖池彩 ---",
}


def _is_tag_enabled(tag):
    if tag == "core":
        return True
    if tag == "work":
        return True
    if tag == "market":
        return bot_config.get("enable_real_stocks", True) or bot_config.get("enable_virtual_stocks", True)
    if tag == "number_lottery":
        return bot_config.get("enable_number_lottery", True)
    if tag == "pool_lottery":
        return bot_config.get("enable_pool_lottery", True)
    return True


def build_help_text():
    lines = ["=== 交易员 ===", ""]
    current_tag = None
    for cmd, desc, tag, *_ in COMMAND_REGISTRY:
        if not _is_tag_enabled(tag):
            continue
        if tag != current_tag:
            title = TAG_TITLES.get(tag)
            if title:
                if current_tag is not None:
                    lines.append("")
                lines.append(title)
            current_tag = tag
        lines.append(desc)
    lines.append("")
    return "\n".join(lines)


def build_help_keyboard():
    buttons = []
    for cmd, desc, tag, label, data, btn_id in COMMAND_REGISTRY:
        if not _is_tag_enabled(tag):
            continue
        if label and data and btn_id:
            buttons.append([{"id": btn_id, "label": label, "data": data, "style": 1}])
    return build_keyboard(buttons)


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

        register_plugin("trader", "QQ \u865a\u62df\u80a1\u5e02 + \u5f69\u7968\u7cfb\u7edf", {
            "_enabled": {"type": "boolean", "label": "\u542f\u7528\u63d2\u4ef6", "default": True},
            "enable_real_stocks": {"type": "boolean", "label": "\u542f\u7528\u73b0\u5b9e\u80a1\u7968", "default": True},
            "enable_virtual_stocks": {"type": "boolean", "label": "\u542f\u7528\u865a\u62df\u80a1\u5e02", "default": True},
            "enable_real_refresh": {"type": "boolean", "label": "\u73b0\u5b9e\u80a1\u7968\u81ea\u52a8\u5237\u65b0", "default": True, "depends_on": "enable_real_stocks"},
            "enable_virtual_refresh": {"type": "boolean", "label": "\u865a\u62df\u80a1\u7968\u81ea\u52a8\u5237\u65b0", "default": True, "depends_on": "enable_virtual_stocks"},
            "real_refresh_interval": {"type": "number", "label": "\u73b0\u5b9e\u5237\u65b0\u95f4\u9694(\u79d2)", "default": 300},
            "virtual_refresh_interval": {"type": "number", "label": "\u865a\u62df\u5237\u65b0\u95f4\u9694(\u79d2)", "default": 300},
            "enable_number_lottery": {"type": "boolean", "label": "\u542f\u7528\u53f7\u7801\u5f69", "default": True},
            "number_lottery_interval": {"type": "number", "label": "\u53f7\u7801\u5f69\u95f4\u9694(\u79d2)", "default": 86400},
            "number_lottery_ticket_price": {"type": "number", "label": "\u53f7\u7801\u5f69\u7968\u4ef7", "default": 100},
            "number_lottery_prize_amount": {"type": "number", "label": "\u53f7\u7801\u5f69\u5956\u91d1", "default": 10000},
            "number_lottery_max_tickets": {"type": "number", "label": "\u53f7\u7801\u5f69\u6bcf\u4eba\u9650\u8d2d", "default": 10},
            "enable_pool_lottery": {"type": "boolean", "label": "\u542f\u7528\u5956\u6c60\u5f69", "default": True},
            "pool_lottery_interval": {"type": "number", "label": "\u5956\u6c60\u5f69\u95f4\u9694(\u79d2)", "default": 86400},
            "pool_lottery_ticket_price": {"type": "number", "label": "\u5956\u6c60\u5f69\u7968\u4ef7", "default": 100},
            "pool_lottery_winners_pct": {"type": "number", "label": "\u5956\u6c60\u5f69\u4e2d\u5956\u6bd4\u4f8b(%)", "default": 10},
            "pool_lottery_max_tickets": {"type": "number", "label": "\u5956\u6c60\u5f69\u6bcf\u4eba\u9650\u8d2d", "default": 10},
        })

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
        help_text = build_help_text()
        mode = bot_config.get_mode()
        is_interaction = hasattr(message, "_interaction")

        if is_interaction:
            await message.reply(content=help_text)
            return

        if mode == "button":
            has_keyboard = hasattr(message, "_api") and hasattr(message, "channel_id")
            if has_keyboard and message.channel_id:
                try:
                    keyboard = build_help_keyboard()
                    await message.reply(content=help_text, keyboard=json.dumps(keyboard))
                    return
                except Exception:
                    pass

        await message.reply(content=help_text)
