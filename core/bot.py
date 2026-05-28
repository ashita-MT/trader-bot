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

    async def on_ready(self):
        print(f"[Bot] on_ready: {self.robot.name}", flush=True)
        await self.plugin_loader.load_all(self)
        self._commands = self.plugin_loader.get_all_commands()
        print(f"[Bot] registered commands: {list(self._commands.keys())}", flush=True)
        self._ready_done = True

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
            try:
                await self._commands[command](message, args)
            except Exception as e:
                print(f"[Cmd] error: {e}", flush=True)
                await message.reply(content=f"执行出错: {e}")
        elif command:
            await message.reply(content=f"未知指令: {command}，发送「帮助」查看可用指令")

    async def on_at_message_create(self, message: Message):
        self._log_msg("at_message", message)
        await self._dispatch(message, require_at=True, mention=True)

    async def on_group_at_message_create(self, message: Message):
        self._log_msg("group_at_message", message)
        await self._dispatch(message, require_at=True, mention=True)

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
            try:
                await self._commands[command](msg, args)
            except Exception as e:
                print(f"[Cmd] error: {e}", flush=True)

    async def close(self):
        await self.plugin_loader.unload_all()
        await super().close()
