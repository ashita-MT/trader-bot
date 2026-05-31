"""Admin plugin — entry point."""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from core.base import BasePlugin
from core.utils import get_user_id
from .db import init_db, log_command
from .admin import register_plugin, _command_registry, _plugin_registry


def _detect_plugin(command, bot):
    """Try to find which plugin owns a command."""
    for plugin in bot.plugin_loader.plugins:
        cmds = plugin.get_commands()
        if command in cmds:
            return plugin.name
    return ""


def _context_type(message):
    if hasattr(message, "group_openid") and message.group_openid:
        return "group"
    if hasattr(message, "channel_id") and message.channel_id:
        return "channel"
    if hasattr(message, "_message"):
        m = message._message
        if hasattr(m, "group_openid") and m.group_openid:
            return "group"
        if hasattr(m, "channel_id") and m.channel_id:
            return "channel"
    aid = getattr(getattr(message, "author", None), "user_openid", None)
    if aid:
        return "c2c"
    return "direct"


def _context_id(message):
    if hasattr(message, "group_openid") and message.group_openid:
        return message.group_openid
    if hasattr(message, "channel_id") and message.channel_id:
        return message.channel_id
    if hasattr(message, "_message"):
        m = message._message
        if hasattr(m, "group_openid") and m.group_openid:
            return m.group_openid
        if hasattr(m, "channel_id") and m.channel_id:
            return m.channel_id
    return ""


def populate_command_registry(bot):
    """Scan all loaded plugins and populate the command + plugin registry."""
    _command_registry.clear()
    for plugin in bot.plugin_loader.plugins:
        cmds = plugin.get_commands()
        for cmd_name in cmds:
            _command_registry.append({
                "name": cmd_name,
                "plugin": plugin.name,
                "description": ""
            })
    print(f"[Admin] Registry populated: {len(_command_registry)} commands, {len(_plugin_registry)} plugins", flush=True)


class Plugin(BasePlugin):
    name = "admin"
    version = "1.1.0"
    description = "Bot 后台管理面板"

    async def setup(self, bot):
        init_db()

        async def command_hook(command, args, message):
            uid = get_user_id(message)
            ctx = _context_id(message)
            ctx_type = _context_type(message)
            plugin_name = _detect_plugin(command, bot)
            log_command(time.time(), command, plugin_name, uid, ctx, ctx_type)

        bot.register_command_hook(command_hook)
        print("[Admin] Plugin loaded, command hook registered.", flush=True)

    async def teardown(self):
        pass

    def get_commands(self):
        return {}
