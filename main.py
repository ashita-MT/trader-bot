import sys
import os
import threading
import socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import botpy
from core.bot import PluginBot
import config


def find_available_port(start_port, max_tries=20):
    for i in range(max_tries):
        port = start_port + i
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    return None


def run_admin():
    import uvicorn
    preferred = config.get("web_port", 6662)
    port = find_available_port(preferred)
    if port is None:
        print(f"[Admin] ERROR: no available port found starting from {preferred}", flush=True)
        return
    if port != preferred:
        print(f"[Admin] port {preferred} occupied, using {port}", flush=True)
    print(f"[Admin] http://localhost:{port}", flush=True)
    uvicorn.run("plugins.trader.admin:app", host="0.0.0.0", port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    appid = config.get("appid", "")
    secret = config.get("secret", "")

    if not appid or not secret:
        print("[Bot] ERROR: appid and secret not configured in bot_config.json", flush=True)
        print("[Bot] Copy bot_config.example.json to bot_config.json and fill in your credentials", flush=True)
        sys.exit(1)

    admin_thread = threading.Thread(target=run_admin, daemon=True)
    admin_thread.start()

    intents = botpy.Intents(
        public_guild_messages=True,
        public_messages=True,
        direct_message=True,
        interaction=True,
    )
    client = PluginBot(intents=intents)
    client.run(appid=appid, secret=secret)
