import subprocess
import sys
import os
import config

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("[Start] starting bot and admin panel...")

bot_proc = subprocess.Popen([sys.executable, "main.py"])
admin_port = config.get("web_port", 8080)
admin_proc = subprocess.Popen([sys.executable, "admin.py"])

print(f"[Start] bot: running")
print(f"[Start] admin: http://localhost:{admin_port}")

try:
    bot_proc.wait()
except KeyboardInterrupt:
    bot_proc.terminate()
    admin_proc.terminate()
