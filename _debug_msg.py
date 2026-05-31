import pathlib
p = pathlib.Path("core/bot.py")
c = p.read_text(encoding="utf-8")

old = """    async def on_message_create(self, message: Message):
        self._log_msg("message", message)"""

new = """    async def on_message_create(self, message: Message):
        self._log_msg("message", message)
        # Debug: check message attributes
        _gid = getattr(message, "group_openid", None)
        _cid = getattr(message, "channel_id", None)
        _content = getattr(message, "content", "")
        print(f"[ChatDebug] group_openid={_gid} channel_id={_cid} content={_content[:50]!r}", flush=True)"""

c = c.replace(old, new)
p.write_text(c, encoding="utf-8")
print("Debug added")
