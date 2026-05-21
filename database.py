"""
database.py — Unified DB connection for SQLite (local) and PostgreSQL (Railway).
"""

import os
import re
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = os.getenv("DB_PATH", "voucher_bot.db")
IS_POSTGRES = bool(DATABASE_URL)


class Row(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


def _pg_sql(sql: str) -> str:
    sql = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINSERT\s+OR\s+REPLACE\s+INTO\b', 'INSERT INTO', sql, flags=re.IGNORECASE)
    sql = re.sub(r"DATE\('now'\)", 'CURRENT_DATE', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bDATE\((\w+)\)', r'(\1)::date', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\?', '%s', sql)
    return sql


class UnifiedConn:
    def __init__(self):
        if IS_POSTGRES:
            import psycopg2
            import psycopg2.extras
            self._conn = psycopg2.connect(DATABASE_URL)
            self._backend = "pg"
        else:
            self._conn = sqlite3.connect(DB_PATH)
            self._conn.row_factory = sqlite3.Row
            self._backend = "sqlite"

    def _cursor(self):
        if self._backend == "pg":
            import psycopg2.extras
            return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self._conn.cursor()

    def _to_row(self, row):
        if row is None:
            return None
        return Row(dict(row))

    def _prep(self, sql, params):
        if self._backend == "pg":
            return _pg_sql(sql), params or ()
        return sql, params or ()

    def execute(self, sql, params=None):
        sql, params = self._prep(sql, params)
        cur = self._cursor()
        cur.execute(sql, params)
        return _CursorResult(cur, self._backend)

    def executemany(self, sql, params_list):
        sql, _ = self._prep(sql, None)
        cur = self._cursor()
        if self._backend == "pg":
            import psycopg2.extras
            psycopg2.extras.execute_batch(cur, sql, params_list)
        else:
            cur.executemany(sql, params_list)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.commit()
        self.close()


class _CursorResult:
    def __init__(self, cur, backend):
        self._cur = cur
        self._backend = backend

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return Row(dict(row))

    def fetchall(self):
        rows = self._cur.fetchall()
        return [Row(dict(r)) for r in rows]


def get_conn() -> UnifiedConn:
    return UnifiedConn()


def _safe_migrate(conn: UnifiedConn, sql: str):
    """Run a migration query — silently rollback on failure (e.g. column already exists)."""
    try:
        conn.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()


def init_db():
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    if IS_POSTGRES:
        _safe_migrate(conn, "CREATE SEQUENCE IF NOT EXISTS users_id_seq")
        _safe_migrate(conn, "ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price REAL,
            disclaimer TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    _safe_migrate(conn, "ALTER TABLE vouchers ADD COLUMN disclaimer TEXT DEFAULT NULL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER,
            code TEXT,
            is_used INTEGER DEFAULT 0,
            used_in_order TEXT,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id BIGINT,
            voucher_id INTEGER,
            quantity INTEGER,
            total_price REAL,
            unique_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_at TIMESTAMP,
            approved_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            code TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            link TEXT
        )
    """)

    conn.executemany(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO NOTHING""",
        [
            ("support_username", "@admin"),
            ("welcome_message", "Welcome! Buy vouchers here."),
            ("maintenance_mode", "0"),
            ("maintenance_msg", "🔧 <b>BOT UNDER MAINTENANCE</b>\n\nHum filhal bot ko update kar rahe hain.\nThodi der mein wapas aayein. Shukriya! 🙏"),
        ]
    )

    conn.commit()
    conn.close()
