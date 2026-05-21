"""
utils/db_helpers.py — All database helper functions.

deliver_codes() is IDEMPOTENT — calling it multiple times for the same order
returns the SAME codes without assigning new ones. Prevents double-delivery.
"""

from database import get_conn


def register_user(telegram_id: int, username: str, full_name: str) -> bool:
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
    row = conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_vouchers_with_stock() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id
        ORDER BY v.created_at ASC
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
        GROUP BY v.id
    """, (voucher_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_voucher_stock(voucher_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM codes WHERE voucher_id = ? AND is_used = 0",
        (voucher_id,)
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def add_voucher(name: str, price: float) -> bool:
    conn = get_conn()
    existing = conn.execute("SELECT id FROM vouchers WHERE name = ?", (name,)).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute("INSERT INTO vouchers (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    conn.close()
    return True


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


def add_codes_bulk(voucher_id: int, raw_text: str) -> int:
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    if not lines:
        return 0
    conn = get_conn()
    conn.executemany(
        "INSERT INTO codes (voucher_id, code, is_used) VALUES (?, ?, 0)",
        [(voucher_id, code) for code in lines]
    )
    conn.commit()
    conn.close()
    return len(lines)


def remove_all_codes(voucher_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM codes WHERE voucher_id = ? AND is_used = 0", (voucher_id,))
    conn.commit()
    conn.close()


def deliver_codes(order_id: str, voucher_id: int, quantity: int) -> list[str] | None:
    conn = get_conn()

    already = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ?", (order_id,)
    ).fetchall()
    if already:
        conn.close()
        return [r["code"] for r in already]

    available = conn.execute(
        "SELECT id, code FROM codes WHERE voucher_id = ? AND is_used = 0 LIMIT ?",
        (voucher_id, quantity)
    ).fetchall()

    if len(available) < quantity:
        conn.close()
        return None

    codes = [r["code"] for r in available]
    ids = [r["id"] for r in available]

    for cid in ids:
        conn.execute(
            "UPDATE codes SET is_used = 1, used_in_order = ? WHERE id = ?",
            (order_id, cid)
        )

    conn.executemany(
        "INSERT INTO order_codes (order_id, code) VALUES (?, ?)",
        [(order_id, code) for code in codes]
    )

    conn.execute(
        "UPDATE orders SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,)
    )

    conn.commit()
    conn.close()
    return codes


def get_order_codes(order_id: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ?", (order_id,)
    ).fetchall()
    conn.close()
    return [r["code"] for r in rows]


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


def cancel_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (order_id,))
    conn.commit()
    conn.close()


def reject_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def get_user_orders(telegram_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
        LIMIT 20
    """, (telegram_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_active_order(telegram_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.user_id = ? AND o.status = 'pending'
        ORDER BY o.created_at DESC
        LIMIT 1
    """, (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


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


def get_stats() -> dict:
    conn = get_conn()
    tu  = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    to_ = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'approved'").fetchone()["c"]
    po  = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'pending'").fetchone()["c"]
    te  = conn.execute("SELECT COALESCE(SUM(total_price), 0) as s FROM orders WHERE status = 'approved'").fetchone()["s"]
    ty  = conn.execute("SELECT COALESCE(SUM(total_price), 0) as s FROM orders WHERE status = 'approved' AND DATE(approved_at) = DATE('now')").fetchone()["s"]
    tyo = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'approved' AND DATE(approved_at) = DATE('now')").fetchone()["c"]
    conn.close()
    return {
        "total_users":    int(tu  or 0),
        "total_orders":   int(to_ or 0),
        "pending_orders": int(po  or 0),
        "total_earnings": float(te  or 0),
        "today_earnings": float(ty  or 0),
        "today_orders":   int(tyo or 0),
    }


def get_all_users() -> list[int]:
    conn = get_conn()
    rows = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    return [r["telegram_id"] for r in rows]


def get_low_stock_vouchers(threshold: int = 5) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id
        HAVING stock <= ? AND stock > 0
    """, (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_out_of_stock_vouchers() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, COUNT(CASE WHEN c.is_used = 0 THEN 1 END) as stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id
        HAVING stock = 0
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_voucher_disclaimer(voucher_id: int) -> str:
    conn = get_conn()
    row = conn.execute("SELECT disclaimer FROM vouchers WHERE id = ?", (voucher_id,)).fetchone()
    conn.close()
    return row["disclaimer"] if row and row["disclaimer"] else ""


def set_voucher_disclaimer(voucher_id: int, text: str):
    conn = get_conn()
    conn.execute("UPDATE vouchers SET disclaimer = ? WHERE id = ?", (text, voucher_id))
    conn.commit()
    conn.close()


def get_setting(key: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def is_maintenance() -> bool:
    return get_setting("maintenance_mode") == "1"


def set_maintenance(on: bool):
    set_setting("maintenance_mode", "1" if on else "0")


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
