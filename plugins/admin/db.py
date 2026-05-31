"""Admin plugin database layer."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS command_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            command TEXT NOT NULL,
            plugin TEXT DEFAULT '',
            user_id TEXT DEFAULT '',
            context TEXT DEFAULT '',
            context_type TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_logs_ts ON command_logs(ts);
        CREATE INDEX IF NOT EXISTS idx_logs_cmd ON command_logs(command);
        CREATE INDEX IF NOT EXISTS idx_logs_ctx ON command_logs(context);

        CREATE TABLE IF NOT EXISTS command_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context TEXT NOT NULL DEFAULT '*',
            context_type TEXT NOT NULL DEFAULT '*',
            target TEXT NOT NULL,
            target_type TEXT NOT NULL,
            mode TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_rules_ctx ON command_rules(context);

    """)
    conn.close()


def log_command(ts, command, plugin, user_id, context, context_type):
    conn = get_db()
    conn.execute(
        "INSERT INTO command_logs (ts, command, plugin, user_id, context, context_type) VALUES (?,?,?,?,?,?)",
        (ts, command, plugin, user_id, context, context_type),
    )
    conn.commit()
    conn.close()






def query_stats(since=None):
    conn = get_db()
    where = ""
    params = []
    if since:
        where = "WHERE ts >= ?"
        params = [since]
    total = conn.execute(f"SELECT COUNT(*) FROM command_logs {where}", params).fetchone()[0]
    by_cmd = conn.execute(
        f"SELECT command, COUNT(*) as cnt FROM command_logs {where} GROUP BY command ORDER BY cnt DESC", params
    ).fetchall()
    by_ctx = conn.execute(
        f"SELECT context, context_type, COUNT(*) as cnt FROM command_logs {where} GROUP BY context, context_type ORDER BY cnt DESC", params
    ).fetchall()
    by_plugin = conn.execute(
        f"SELECT plugin, COUNT(*) as cnt FROM command_logs {where} GROUP BY plugin ORDER BY cnt DESC", params
    ).fetchall()
    by_hour = conn.execute(
        f"SELECT CAST(ts AS INTEGER) / 3600 as hour_key, COUNT(*) as cnt FROM command_logs {where} GROUP BY hour_key ORDER BY hour_key", params
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "by_command": [dict(r) for r in by_cmd],
        "by_context": [dict(r) for r in by_ctx],
        "by_plugin": [dict(r) for r in by_plugin],
        "by_hour": [dict(r) for r in by_hour],
    }


def query_recent(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM command_logs ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_group_stats():
    conn = get_db()
    rows = conn.execute("""
        SELECT context, context_type,
            COUNT(*) as total,
            COUNT(DISTINCT user_id) as users,
            MIN(ts) as first_seen,
            MAX(ts) as last_seen
        FROM command_logs
        WHERE context != ''
        GROUP BY context, context_type
        ORDER BY total DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_old_logs(keep_days=30):
    import time
    cutoff = time.time() - keep_days * 86400
    conn = get_db()
    conn.execute("DELETE FROM command_logs WHERE ts < ?", (cutoff,))
    conn.commit()
    conn.close()

def add_rule(context, context_type, target, target_type, mode):
    conn = get_db()
    conn.execute(
        "INSERT INTO command_rules (context, context_type, target, target_type, mode) VALUES (?,?,?,?,?)",
        (context, context_type, target, target_type, mode),
    )
    conn.commit()
    conn.close()


def get_rules(context=None):
    conn = get_db()
    if context:
        rows = conn.execute(
            "SELECT * FROM command_rules WHERE context=? OR context='*' ORDER BY context, mode, target_type, target",
            (context,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM command_rules ORDER BY context, mode, target_type, target"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_rule(rule_id):
    conn = get_db()
    conn.execute("DELETE FROM command_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def check_command_allowed(command, plugin_name, context, context_type):
    """Check if a command is allowed in the given context.
    Returns True if allowed, False if blocked."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM command_rules WHERE context=? OR context='*'",
        (context,)
    ).fetchall()
    conn.close()

    if not rows:
        return True

    rules = [dict(r) for r in rows]

    plugin_rules = [r for r in rules if r["target_type"] == "plugin"]
    cmd_rules = [r for r in rules if r["target_type"] == "command"]

    has_plugin_wl = any(r["mode"] == "whitelist" for r in plugin_rules)
    has_cmd_wl = any(r["mode"] == "whitelist" for r in cmd_rules)

    if has_plugin_wl:
        wl_plugins = [r["target"] for r in plugin_rules if r["mode"] == "whitelist"]
        if plugin_name not in wl_plugins:
            return False
    elif plugin_rules:
        bl_plugins = [r["target"] for r in plugin_rules if r["mode"] == "blacklist"]
        if plugin_name in bl_plugins:
            return False

    if has_cmd_wl:
        wl_cmds = [r["target"] for r in cmd_rules if r["mode"] == "whitelist"]
        if command not in wl_cmds:
            return False
    elif cmd_rules:
        bl_cmds = [r["target"] for r in cmd_rules if r["mode"] == "blacklist"]
        if command in bl_cmds:
            return False

    return True
