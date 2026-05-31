import botpy
from botpy.message import Message
from .plugin_loader import PluginLoader
from .command_parser import CommandParser
from .utils import get_user_id, MentionMessage
from .adapter import InteractionMessage


class PluginBot(botpy.Client):
    def __init__(self, intents, plugins_dir="plugins", **kwargs):
        super().__init__(intents=intents, **kwargs)
        self.plugin_loader = PluginLoader(plugins_dir)
        self.command_parser = CommandParser()
        self._commands = {}
        self._ready_done = False
        self._command_hooks = []
        self._cmd_plugin_map = {}

    async def on_ready(self):
        print(f"[Bot] on_ready: {self.robot.name}", flush=True)
        await self.plugin_loader.load_all(self)
        self._commands = self.plugin_loader.get_all_commands()
        self._cmd_plugin_map = {}
        for plugin in self.plugin_loader.plugins:
            for cmd in plugin.get_commands():
                self._cmd_plugin_map[cmd] = plugin.name
        print(f"[Bot] registered commands: {list(self._commands.keys())}", flush=True)
        # Populate admin panel command/plugin registry
        try:
            from plugins.admin.plugin import populate_command_registry
            populate_command_registry(self)
        except Exception as e:
            print(f"[Bot] Failed to populate admin registry: {e}", flush=True)
        self._ready_done = True

    def _get_context(self, message):
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
        return "*"

    def _get_context_type(self, message):
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
        return "*"

    def register_command_hook(self, hook):
        self._command_hooks.append(hook)

    async def _ensure_commands(self):
        if not self._ready_done:
            await self.plugin_loader.load_all(self)
            self._commands = self.plugin_loader.get_all_commands()
            self._ready_done = True

    def _log_msg(self, event, message):
        uid = get_user_id(message)
        print(f"[Event] {event} | user={uid} | content={message.content}", flush=True)

    async def _dispatch(self, message, require_at=True, mention=False):
        await self._ensure_commands()
        content = message.content

        if require_at:
            command, args = self.command_parser.parse_with_at(content)
        else:
            command, args = self.command_parser.parse_raw(content)

        print(f"[Cmd] '{command}' args={args}", flush=True)

        # Wrap message with @mention for group/channel
        if mention:
            uid = get_user_id(message)
            message = MentionMessage(message, uid)

        if command in self._commands:
            # Check if plugin is enabled
            plugin_name = self._cmd_plugin_map.get(command, "")
            if plugin_name:
                import sys, os
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                import config as _cfg
                if not _cfg.get(f"enable_{plugin_name}", True):
                    await message.reply(content=f"「{plugin_name}」插件已关闭")
                    return
                # Check command rules
                try:
                    from plugins.admin.db import check_command_allowed
                    ctx = self._get_context(message)
                    ctx_type = self._get_context_type(message)
                    if not check_command_allowed(command, plugin_name, ctx, ctx_type):
                        return
                except Exception:
                    pass
            try:
                await self._commands[command](message, args)
                for hook in self._command_hooks:
                    try:
                        await hook(command, args, message)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Cmd] error: {e}", flush=True)
                await message.reply(content=f"执行出错: {e}")
        elif command:
            await message.reply(content=f"未知指令: {command}，发送「帮助」查看可用指令")

    async def on_at_message_create(self, message: Message):
        self._log_msg("at_message", message)
        await self._dispatch(message, require_at=True, mention=False)

    async def on_group_at_message_create(self, message: Message):
        self._log_msg("group_at_message", message)
        await self._dispatch(message, require_at=True, mention=False)

    async def on_c2c_message_create(self, message: Message):
        self._log_msg("c2c_message", message)
        await self._dispatch(message, require_at=False, mention=False)

    async def on_direct_message_create(self, message: Message):
        self._log_msg("direct_message", message)
        await self._dispatch(message, require_at=False, mention=False)

    async def on_message_create(self, message: Message):
        self._log_msg("message", message)

    async def on_interaction_create(self, interaction):
        await self._ensure_commands()
        btn_data = ""
        if interaction.data and interaction.data.resolved:
            btn_data = interaction.data.resolved.button_data or ""
        uid = interaction.user_openid or interaction.group_member_openid or interaction.group_openid or "?"
        print(f"[Event] interaction | user={uid} | button_data={btn_data}", flush=True)

        if not btn_data:
            return

        msg = InteractionMessage(interaction, self.api)
        command, args = self.command_parser.parse_raw(btn_data)
        print(f"[Cmd] '{command}' args={args}", flush=True)
        if command in self._commands:
            plugin_name = self._cmd_plugin_map.get(command, "")
            if plugin_name:
                import sys as _sys, os as _os
                _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
                import config as _cfg
                if not _cfg.get(f"enable_{plugin_name}", True):
                    return
            try:
                await self._commands[command](msg, args)
                for hook in self._command_hooks:
                    try:
                        await hook(command, args, msg)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Cmd] error: {e}", flush=True)

    async def close(self):
        await self.plugin_loader.unload_all()
        await super().close()
