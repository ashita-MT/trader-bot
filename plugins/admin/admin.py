"""Admin panel — FastAPI backend."""
import sys, os, time, json

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.insert(0, os.path.join(PLUGIN_DIR, "..", ".."))
import config

from db import init_db, query_stats, query_recent, query_group_stats, add_rule, get_rules, delete_rule

app = FastAPI(title="Bot Admin")

TEMPLATE_DIR = os.path.join(PLUGIN_DIR, "templates")

START_TIME = time.time()

# ── Plugin registry (populated by plugin.py at startup) ──
_plugin_registry = {}

# ── Command registry (populated by plugin.py at startup) ──
_command_registry = []
_bot_ref = None


def register_plugin(name, description, config_schema=None):
    """Called by each plugin during setup to register itself with the admin panel."""
    _plugin_registry[name] = {
        "name": name,
        "description": description,
        "config_schema": config_schema or {},
    }


def get_registered_plugins():
    return _plugin_registry


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(TEMPLATE_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Bot info ──
@app.get("/api/bot")
async def get_bot_info():
    cfg = config.get()
    uptime = int(time.time() - START_TIME)
    days = uptime // 86400
    hours = (uptime % 86400) // 3600
    mins = (uptime % 3600) // 60
    uptime_str = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m"
    return JSONResponse({
        "name": cfg.get("bot_name", "Bot"),
        "mode": cfg.get("interaction_mode", "text"),
        "web_port": cfg.get("web_port", 6662),
        "uptime": uptime_str,
        "uptime_seconds": uptime,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(START_TIME)),
    })


# ── Command stats ──
@app.get("/api/stats")
async def get_stats():
    today_start = int(time.time()) - (int(time.time()) % 86400)
    today_stats = query_stats(since=today_start)
    all_stats = query_stats()
    return JSONResponse({"today": today_stats, "all": all_stats})


@app.get("/api/stats/recent")
async def get_recent(limit: int = 50):
    return JSONResponse(query_recent(limit))


# ── Group stats ──
@app.get("/api/groups")
async def get_groups():
    return JSONResponse(query_group_stats())


# ── Config ──
@app.get("/api/config")
async def get_config():
    return JSONResponse(config.get())


@app.post("/api/config")
async def set_config(request: Request):
    body = await request.json()
    for k, v in body.items():
        config.set(k, v)
    return JSONResponse(config.get())


# ── Plugin management ──
@app.get("/api/plugins")
async def get_plugins():
    plugins = []
    for name, info in get_registered_plugins().items():
        cfg = {k: config.get(k, v.get("default")) for k, v in info["config_schema"].items()}
        cfg["enable_" + name] = config.get("enable_" + name, True)
        plugins.append({
            "name": name,
            "description": info["description"],
            "config_schema": info["config_schema"],
            "config": cfg,
        })
    return JSONResponse(plugins)


@app.post("/api/plugins/{name}/config")
async def set_plugin_config(name: str, request: Request):
    body = await request.json()
    plugin = get_registered_plugins().get(name)
    if not plugin:
        return JSONResponse({"error": "plugin not found"}, status_code=404)
    schema = plugin["config_schema"]
    for k, v in body.items():
        if k in schema or k == "enable_" + name:
            config.set(k, v)
    return JSONResponse({"ok": True})

# ── Command & plugin list for rules dropdown ──
@app.get("/api/commands")
async def list_commands():
    return JSONResponse(_command_registry)


# ── Command rules ──
@app.get("/api/rules")
async def list_rules(context: str = None):
    return JSONResponse(get_rules(context))


@app.post("/api/rules")
async def create_rule(request: Request):
    body = await request.json()
    ctx = body.get("context", "*")
    ctx_type = body.get("context_type", "*")
    target = body.get("target", "").strip()
    target_type = body.get("target_type", "command")
    mode = body.get("mode", "blacklist")

    if not target:
        return JSONResponse({"error": "target required"}, status_code=400)
    if target_type not in ("command", "plugin"):
        return JSONResponse({"error": "target_type must be command or plugin"}, status_code=400)
    if mode not in ("blacklist", "whitelist"):
        return JSONResponse({"error": "mode must be blacklist or whitelist"}, status_code=400)

    add_rule(ctx, ctx_type, target, target_type, mode)
    return JSONResponse({"ok": True})


@app.delete("/api/rules/{rule_id}")
async def remove_rule(rule_id: int):
    delete_rule(rule_id)
    return JSONResponse({"ok": True})
