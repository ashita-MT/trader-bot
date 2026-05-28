import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trader.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qq_id TEXT UNIQUE NOT NULL,
            nickname TEXT DEFAULT '',
            balance REAL DEFAULT 100000.0,
            last_work TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            current_price REAL NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            change_pct REAL DEFAULT 0.0,
            is_virtual INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            volatility REAL DEFAULT 3.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            avg_cost REAL DEFAULT 0.0,
            UNIQUE(user_id, stock_code),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            order_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            price REAL NOT NULL,
            volume INTEGER DEFAULT 0,
            date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lottery_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round INTEGER UNIQUE NOT NULL,
            winning_number INTEGER,
            drawn_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lottery_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            round INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    for col, dtype, default in [
        ("is_virtual", "INTEGER", "0"),
        ("is_enabled", "INTEGER", "1"),
        ("volatility", "REAL", "3.0"),
        ("last_work", "TEXT", "NULL"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM stocks LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute(f"ALTER TABLE stocks ADD COLUMN {col} {dtype} DEFAULT {default}")
                print(f"[DB] added {col} column")
            except sqlite3.OperationalError:
                pass

    try:
        conn.execute("SELECT last_work FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_work TEXT DEFAULT NULL")
            print("[DB] added last_work column to users")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    print("[DB] database initialized")
