"""
utils/db_helpers.py — All database helper functions.

IMPORTANT: deliver_codes() is IDEMPOTENT — calling it multiple times
for the same order returns the SAME codes without assigning new ones.
This prevents the double-delivery bug.

Works with both SQLite (local) and PostgreSQL (Railway).
"""

from database import get_conn


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────

def register_user(telegram_id: int, username: str, full_name: str):
    """Register or update a user. Returns True if newly registered."""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE telegram_id = ?",
            (username, full_name, telegram_id)
        )
        conn.commit()
        conn.close()
        return False
    conn.execute(
        "INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
        (telegram_id, username, full_name)
    )
    conn.commit()
    conn.close()
    return True


def get_user(telegram_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# VOUCHERS
# ─────────────────────────────────────────────

def get_all_vouchers_with_stock() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id, v.name, v.price
        ORDER BY v.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_voucher(voucher_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        WHERE v.id = ?
        GROUP BY v.id, v.name, v.price
    """, (voucher_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_voucher(name: str, price: float) -> bool:
    conn = get_conn()
    try:
        conn.execute("INSERT INTO vouchers (name, price) VALUES (?, ?)", (name, price))
        conn.commit()
        result = True
    except Exception:
        result = False
    conn.close()
    return result


def delete_voucher(voucher_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM codes WHERE voucher_id = ?", (voucher_id,))
    conn.execute("DELETE FROM vouchers WHERE id = ?", (voucher_id,))
    conn.commit()
    conn.close()


def update_price(voucher_id: int, price: float):
    conn = get_conn()
    conn.execute("UPDATE vouchers SET price = ? WHERE id = ?", (price, voucher_id))
    conn.commit()
    conn.close()


def get_voucher_stock(voucher_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as stock FROM codes WHERE voucher_id = ? AND is_used = 0",
        (voucher_id,)
    ).fetchone()
    conn.close()
    return row["stock"] if row else 0


def add_codes_bulk(voucher_id: int, codes_text: str) -> int:
    codes = [c.strip() for c in codes_text.strip().split("\n") if c.strip()]
    conn = get_conn()
    conn.executemany(
        "INSERT INTO codes (voucher_id, code, is_used) VALUES (?, ?, 0)",
        [(voucher_id, code) for code in codes]
    )
    conn.commit()
    conn.close()
    return len(codes)


def remove_all_codes(voucher_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM codes WHERE voucher_id = ? AND is_used = 0", (voucher_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────────

def get_order(order_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name, v.price as voucher_price
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.id = ?
    """, (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
        LIMIT 20
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_order_codes(order_id: str) -> list[str]:
    """Return all codes already delivered for this order."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ? ORDER BY id",
        (order_id,)
    ).fetchall()
    conn.close()
    return [r["code"] for r in rows]


def get_user_active_order(user_id: int) -> dict | None:
    """Return the user's currently pending order, if any."""
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.user_id = ? AND o.status = 'pending'
        ORDER BY o.created_at DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def cancel_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def reject_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def deliver_codes(order_id: str, voucher_id: int, quantity: int) -> list[str] | None:
    """
    Deliver codes for an order. IDEMPOTENT — if codes are already
    assigned to this order, returns the SAME codes without creating new ones.

    Returns:
        List of code strings on success.
        None if not enough stock.
    """
    conn = get_conn()

    # ── IDEMPOTENCY CHECK ─────────────────────────────────────────────────────
    existing = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ? ORDER BY id",
        (order_id,)
    ).fetchall()
    if existing:
        conn.close()
        return [r["code"] for r in existing]

    # ── ASSIGN NEW CODES ──────────────────────────────────────────────────────
    available = conn.execute(
        "SELECT id, code FROM codes WHERE voucher_id = ? AND is_used = 0 LIMIT ?",
        (voucher_id, quantity)
    ).fetchall()

    if len(available) < quantity:
        conn.close()
        return None

    delivered = []
    for c in available:
        conn.execute(
            "UPDATE codes SET is_used = 1, used_in_order = ? WHERE id = ?",
            (order_id, c["id"])
        )
        conn.execute(
            "INSERT INTO order_codes (order_id, code) VALUES (?, ?)",
            (order_id, c["code"])
        )
        delivered.append(c["code"])

    conn.execute(
        "UPDATE orders SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,)
    )
    conn.commit()
    conn.close()
    return delivered


# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────

def get_setting(key: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    # ON CONFLICT syntax works in both SQLite 3.24+ and PostgreSQL
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# CHANNELS
# ─────────────────────────────────────────────

def get_all_channels() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_channel(name: str, link: str):
    conn = get_conn()
    conn.execute("INSERT INTO channels (name, link) VALUES (?, ?)", (name, link))
    conn.commit()
    conn.close()


def remove_channel(channel_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# STATISTICS
# ─────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_conn()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_orders = conn.execute(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'approved'"
    ).fetchone()["c"]
    pending_orders = conn.execute(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'pending'"
    ).fetchone()["c"]
    total_earnings = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) as s FROM orders WHERE status = 'approved'"
    ).fetchone()["s"]
    today_earnings = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) as s FROM orders "
        "WHERE status = 'approved' AND DATE(approved_at) = CURRENT_DATE"
    ).fetchone()["s"]
    today_orders = conn.execute(
        "SELECT COUNT(*) as c FROM orders "
        "WHERE status = 'approved' AND DATE(approved_at) = CURRENT_DATE"
    ).fetchone()["c"]
    conn.close()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_earnings": float(total_earnings or 0),
        "today_earnings": float(today_earnings or 0),
        "today_orders": today_orders,
    }


def get_all_users() -> list[int]:
    conn = get_conn()
    rows = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    return [r["telegram_id"] for r in rows]


def get_pending_orders() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name, u.username, u.full_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        JOIN users u ON u.telegram_id = o.user_id
        WHERE o.status = 'pending'
        ORDER BY o.created_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_low_stock_vouchers(threshold: int = 5) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id, v.name, v.price
        HAVING COUNT(CASE WHEN c.is_used = 0 THEN 1 END) <= ?
           AND COUNT(CASE WHEN c.is_used = 0 THEN 1 END) > 0
        ORDER BY stock ASC
    """, (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_out_of_stock_vouchers() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id, v.name
        HAVING COUNT(CASE WHEN c.is_used = 0 THEN 1 END) = 0
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
