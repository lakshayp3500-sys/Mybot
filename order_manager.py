"""order_manager.py — Order lifecycle: create, fetch, expire."""

import uuid
from datetime import datetime, timedelta
from database import get_conn, IS_POSTGRES


def create_order(user_id, voucher_id, quantity, total_price, unique_amount, expiry_minutes=5):
    order_id = str(uuid.uuid4()).replace("-", "").upper()[:12]
    created_at = datetime.now()
    expiry_at = created_at + timedelta(minutes=expiry_minutes)
    conn = get_conn()
    conn.execute(
        """INSERT INTO orders
           (id, user_id, voucher_id, quantity, total_price, unique_amount,
            status, created_at, expiry_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (order_id, user_id, voucher_id, quantity, total_price,
         unique_amount, created_at, expiry_at)
    )
    conn.commit()
    conn.close()
    return order_id


def is_amount_taken(amount: float) -> bool:
    now = datetime.now()
    conn = get_conn()
    if IS_POSTGRES:
        row = conn.execute("""
            SELECT id FROM orders
            WHERE ABS(unique_amount - ?) < 0.001
              AND status = 'pending'
              AND expiry_at > ?
            LIMIT 1
        """, (amount, now)).fetchone()
    else:
        row = conn.execute("""
            SELECT id FROM orders
            WHERE unique_amount = ?
              AND status = 'pending'
              AND expiry_at > ?
            LIMIT 1
        """, (amount, now)).fetchone()
    conn.close()
    return row is not None


def get_pending_order_by_amount(amount: float) -> dict | None:
    now = datetime.now()
    conn = get_conn()
    if IS_POSTGRES:
        row = conn.execute("""
            SELECT o.*, v.name as voucher_name, v.price as voucher_price
            FROM orders o
            JOIN vouchers v ON v.id = o.voucher_id
            WHERE ABS(o.unique_amount - ?) < 0.001
              AND o.status = 'pending'
              AND o.expiry_at > ?
            ORDER BY o.created_at DESC
            LIMIT 1
        """, (amount, now)).fetchone()
    else:
        row = conn.execute("""
            SELECT o.*, v.name as voucher_name, v.price as voucher_price
            FROM orders o
            JOIN vouchers v ON v.id = o.voucher_id
            WHERE o.unique_amount = ?
              AND o.status = 'pending'
              AND o.expiry_at > ?
            ORDER BY o.created_at DESC
            LIMIT 1
        """, (amount, now)).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_order_paid(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'paid' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def expire_orders() -> list[dict]:
    now = datetime.now()
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.status = 'pending' AND o.expiry_at <= ?
    """, (now,)).fetchall()
    expired = [dict(r) for r in rows]
    if expired:
        ids = tuple(r["id"] for r in expired)
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE orders SET status = 'expired' WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    conn.close()
    return expired


def get_order_by_id(order_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name, v.price as voucher_price
        FROM orders o
        JOIN vouchers v ON v.id = o.voucher_id
        WHERE o.id = ?
    """, (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
