import asyncio
import logging
import os
import random
import sqlite3
import string

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup
)

# ══════════════════════════════════════════
#  CONFIG — apna BOT_TOKEN aur ADMIN_IDS yahan daal do
# ══════════════════════════════════════════

BOT_TOKEN = "8904611562:AAFvj33S_cTF5O8VHSWYMW99GD-ztB2F1-A"   # @BotFather se mila token
ADMIN_IDS = [7515220054]               # @userinfobot se apna ID lo

# ══════════════════════════════════════════
#  DATABASE SETUP
# ══════════════════════════════════════════

DB_PATH = "voucher_bot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER,
            code TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_in_order TEXT,
            FOREIGN KEY(voucher_id) REFERENCES vouchers(id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            voucher_id INTEGER,
            quantity INTEGER,
            total_price REAL,
            status TEXT DEFAULT 'pending',
            screenshot_file_id TEXT,
            txn_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            FOREIGN KEY(voucher_id) REFERENCES vouchers(id)
        );
        CREATE TABLE IF NOT EXISTS order_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            code TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            link TEXT
        );
        INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_message', 'Welcome to Voucher Store!');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('support_username', '@support');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('qr_file_id', '');
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════
#  DATABASE HELPERS
# ══════════════════════════════════════════

def register_user(telegram_id, username, full_name):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
                 (telegram_id, username, full_name))
    conn.commit(); conn.close()


def get_all_vouchers():
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used=0 THEN 1 END) as stock
        FROM vouchers v LEFT JOIN codes c ON c.voucher_id=v.id
        GROUP BY v.id ORDER BY v.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_voucher(vid):
    conn = get_conn()
    row = conn.execute("""
        SELECT v.id, v.name, v.price,
               COUNT(CASE WHEN c.is_used=0 THEN 1 END) as stock
        FROM vouchers v LEFT JOIN codes c ON c.voucher_id=v.id
        WHERE v.id=? GROUP BY v.id
    """, (vid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_active_order(user_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name FROM orders o
        JOIN vouchers v ON v.id=o.voucher_id
        WHERE o.user_id=? AND o.status='pending'
        ORDER BY o.created_at DESC LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_order(user_id, voucher_id, quantity, total_price):
    oid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    conn = get_conn()
    conn.execute("INSERT INTO orders (id,user_id,voucher_id,quantity,total_price,status) VALUES (?,?,?,?,?,'pending')",
                 (oid, user_id, voucher_id, quantity, total_price))
    conn.commit(); conn.close()
    return oid


def save_screenshot(order_id, file_id):
    conn = get_conn()
    conn.execute("UPDATE orders SET screenshot_file_id=? WHERE id=?", (file_id, order_id))
    conn.commit(); conn.close()


def save_txn_id(order_id, txn_id):
    conn = get_conn()
    conn.execute("UPDATE orders SET txn_id=? WHERE id=?", (txn_id, order_id))
    conn.commit(); conn.close()


def get_order(order_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT o.*, v.name as voucher_name FROM orders o
        JOIN vouchers v ON v.id=o.voucher_id WHERE o.id=?
    """, (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name FROM orders o
        JOIN vouchers v ON v.id=o.voucher_id
        WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT 10
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deliver_codes(order_id, voucher_id, quantity):
    conn = get_conn()
    codes = conn.execute("SELECT id,code FROM codes WHERE voucher_id=? AND is_used=0 LIMIT ?",
                         (voucher_id, quantity)).fetchall()
    if len(codes) < quantity:
        conn.close(); return None
    delivered = []
    for c in codes:
        conn.execute("UPDATE codes SET is_used=1, used_in_order=? WHERE id=?", (order_id, c["id"]))
        conn.execute("INSERT INTO order_codes (order_id,code) VALUES (?,?)", (order_id, c["code"]))
        delivered.append(c["code"])
    conn.execute("UPDATE orders SET status='approved', approved_at=CURRENT_TIMESTAMP WHERE id=?", (order_id,))
    conn.commit(); conn.close()
    return delivered


def reject_order(order_id):
    conn = get_conn()
    conn.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
    conn.commit(); conn.close()


def cancel_order(order_id):
    conn = get_conn()
    conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
    conn.commit(); conn.close()


def get_voucher_stock(voucher_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as s FROM codes WHERE voucher_id=? AND is_used=0", (voucher_id,)).fetchone()
    conn.close()
    return row["s"] if row else 0


def add_voucher(name, price):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO vouchers (name,price) VALUES (?,?)", (name, price))
        conn.commit(); conn.close(); return True
    except sqlite3.IntegrityError:
        conn.close(); return False


def delete_voucher(vid):
    conn = get_conn()
    conn.execute("DELETE FROM codes WHERE voucher_id=?", (vid,))
    conn.execute("DELETE FROM vouchers WHERE id=?", (vid,))
    conn.commit(); conn.close()


def update_price(vid, price):
    conn = get_conn()
    conn.execute("UPDATE vouchers SET price=? WHERE id=?", (price, vid))
    conn.commit(); conn.close()


def add_codes_bulk(vid, text):
    codes = [c.strip() for c in text.strip().split("\n") if c.strip()]
    conn = get_conn()
    conn.executemany("INSERT INTO codes (voucher_id,code,is_used) VALUES (?,?,0)",
                     [(vid, code) for code in codes])
    conn.commit(); conn.close()
    return len(codes)


def remove_unused_codes(vid):
    conn = get_conn()
    conn.execute("DELETE FROM codes WHERE voucher_id=? AND is_used=0", (vid,))
    conn.commit(); conn.close()


def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit(); conn.close()


def get_all_channels():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_channel(name, link):
    conn = get_conn()
    conn.execute("INSERT INTO channels (name,link) VALUES (?,?)", (name, link))
    conn.commit(); conn.close()


def remove_channel(cid):
    conn = get_conn()
    conn.execute("DELETE FROM channels WHERE id=?", (cid,))
    conn.commit(); conn.close()


def get_stats():
    conn = get_conn()
    tu = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    to = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status='approved'").fetchone()["c"]
    po = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status='pending' AND screenshot_file_id IS NOT NULL AND screenshot_file_id!=''").fetchone()["c"]
    te = conn.execute("SELECT COALESCE(SUM(total_price),0) as s FROM orders WHERE status='approved'").fetchone()["s"]
    ty = conn.execute("SELECT COALESCE(SUM(total_price),0) as s FROM orders WHERE status='approved' AND DATE(approved_at)=DATE('now')").fetchone()["s"]
    tyo = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status='approved' AND DATE(approved_at)=DATE('now')").fetchone()["c"]
    conn.close()
    return {"total_users": tu, "total_orders": to, "pending_orders": po,
            "total_earnings": te, "today_earnings": ty, "today_orders": tyo}


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    return [r["telegram_id"] for r in rows]


def get_pending_orders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, v.name as voucher_name, u.username, u.full_name
        FROM orders o JOIN vouchers v ON v.id=o.voucher_id JOIN users u ON u.telegram_id=o.user_id
        WHERE o.status='pending' AND o.screenshot_file_id IS NOT NULL AND o.screenshot_file_id!=''
        ORDER BY o.created_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_low_stock(threshold=5):
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, COUNT(CASE WHEN c.is_used=0 THEN 1 END) as stock
        FROM vouchers v LEFT JOIN codes c ON c.voucher_id=v.id
        GROUP BY v.id HAVING stock<=? AND stock>0
    """, (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛍 Buy Vouchers"), KeyboardButton(text="📦 My Orders")],
        [KeyboardButton(text="📜 Disclaimer"), KeyboardButton(text="🆘 Support")],
        [KeyboardButton(text="📢 Our Channels")],
    ], resize_keyboard=True)


def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="📦 View Stock")],
        [KeyboardButton(text="➕ Add Voucher"), KeyboardButton(text="❌ Delete Voucher")],
        [KeyboardButton(text="💰 Set Price"), KeyboardButton(text="📥 Add Codes")],
        [KeyboardButton(text="🗑 Remove Codes"), KeyboardButton(text="📊 Statistics")],
        [KeyboardButton(text="🖼 Upload QR"), KeyboardButton(text="⏳ Pending Orders")],
        [KeyboardButton(text="🆘 Support Settings"), KeyboardButton(text="📢 Manage Channels")],
        [KeyboardButton(text="🏠 Main Menu")],
    ], resize_keyboard=True)


def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Cancel")]], resize_keyboard=True)


def vouchers_kb(vouchers):
    buttons = []
    for v in vouchers:
        if v["stock"] > 0:
            buttons.append([InlineKeyboardButton(
                text=f"🎫 {v['name']} — ₹{v['price']:.0f} ({v['stock']} left)",
                callback_data=f"bv:{v['id']}"
            )])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def quantity_kb(vid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data=f"qty:{vid}:1"),
         InlineKeyboardButton(text="2", callback_data=f"qty:{vid}:2"),
         InlineKeyboardButton(text="3", callback_data=f"qty:{vid}:3")],
        [InlineKeyboardButton(text="5", callback_data=f"qty:{vid}:5"),
         InlineKeyboardButton(text="10", callback_data=f"qty:{vid}:10"),
         InlineKeyboardButton(text="✏️ Custom", callback_data=f"qty:{vid}:custom")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_vouchers")],
    ])


def confirm_order_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I've Paid", callback_data=f"paid:{order_id}")],
        [InlineKeyboardButton(text="❌ Cancel Order", callback_data=f"cancel_order:{order_id}")],
    ])


def admin_approve_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{order_id}"),
         InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{order_id}")],
    ])


def channels_kb(channels):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["link"])] for ch in channels
    ])


# ══════════════════════════════════════════
#  STATES
# ══════════════════════════════════════════

class BuyStates(StatesGroup):
    select_voucher = State()
    select_quantity = State()
    custom_quantity = State()
    waiting_screenshot = State()
    waiting_txn_id = State()


class AdminStates(StatesGroup):
    add_voucher_name = State()
    add_voucher_price = State()
    add_codes_voucher = State()
    add_codes_input = State()
    remove_voucher = State()
    set_price_voucher = State()
    set_price_value = State()
    upload_qr = State()
    broadcast_message = State()
    set_support = State()
    add_channel_name = State()
    add_channel_link = State()
    remove_channel = State()
    reject_reason = State()


# ══════════════════════════════════════════
#  ROUTER & HELPERS
# ══════════════════════════════════════════

router = Router()
TIMEOUT = 15 * 60


def is_admin(uid):
    return uid in ADMIN_IDS


def stock_msg(vouchers):
    lines = [f"▪️ {v['name']} : {v['stock']} Left (₹{v['price']:.0f})" if v['stock'] > 0
             else f"▪️ {v['name']} : ❌ Out of Stock" for v in vouchers]
    return ("📦 <b>Current Stock</b>\n\n" + "\n".join(lines) if lines
            else "⚠️ No vouchers available.") + "\n\n⚡ <i>Instant Auto Delivery</i>"


async def payment_timeout(bot: Bot, user_id, order_id, state: FSMContext):
    await asyncio.sleep(TIMEOUT)
    order = get_order(order_id)
    if not order or order["status"] != "pending" or order.get("screenshot_file_id"):
        return
    cancel_order(order_id)
    try:
        await bot.send_message(user_id,
            f"⏰ <b>Order Expired</b>\n\n<code>{order_id}</code> cancelled — no payment in 15 min.\n\nTap 🛍 Buy Vouchers to try again.",
            parse_mode="HTML", reply_markup=main_menu())
    except Exception:
        pass


# ══════════════════════════════════════════
#  USER HANDLERS
# ══════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    vouchers = get_all_vouchers()
    welcome = get_setting("welcome_message")
    await message.answer(f"👋 <b>{welcome}</b>\n\n{stock_msg(vouchers)}",
                         reply_markup=main_menu(), parse_mode="HTML")


@router.message(F.text == "📦 My Orders")
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("📦 <b>My Orders</b>\n\nNo orders yet!", parse_mode="HTML")
        return
    sm = {"pending": "⏳ Under Review", "approved": "✅ Delivered",
          "rejected": "❌ Rejected", "cancelled": "🚫 Cancelled"}
    lines = [f"🆔 <code>{o['id']}</code>\n   🎫 {o['voucher_name']} × {o['quantity']} | ₹{o['total_price']:.0f}\n   {sm.get(o['status'], o['status'])} | {o['created_at'][:10]}"
             for o in orders]
    await message.answer("📦 <b>My Orders</b>\n\n" + "\n\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📜 Disclaimer")
async def disclaimer(message: Message):
    await message.answer("📜 <b>Disclaimer</b>\n\n• All sales are <b>final</b>\n• No refunds after delivery\n• Digital products only\n• Use codes at your own risk\n\n✅ By purchasing you agree to these terms.", parse_mode="HTML")


@router.message(F.text == "🆘 Support")
async def support(message: Message):
    su = get_setting("support_username")
    await message.answer(f"🆘 <b>Support</b>\n\nContact: {su}", parse_mode="HTML")


@router.message(F.text == "📢 Our Channels")
async def our_channels(message: Message):
    channels = get_all_channels()
    if not channels:
        await message.answer("No channels yet.")
        return
    await message.answer("📢 <b>Our Channels</b>", reply_markup=channels_kb(channels), parse_mode="HTML")


# ── BUY FLOW ──

@router.message(F.text == "🛍 Buy Vouchers")
async def buy_vouchers(message: Message, state: FSMContext):
    await state.clear()
    active = get_user_active_order(message.from_user.id)
    if active:
        await message.answer(
            f"⚠️ You have a pending order!\n\n🆔 <code>{active['id']}</code>\n🎫 {active['voucher_name']} × {active['quantity']}\n💵 ₹{active['total_price']:.0f}\n\nWait for it to be reviewed first.",
            parse_mode="HTML")
        return
    vouchers = [v for v in get_all_vouchers() if v["stock"] > 0]
    if not vouchers:
        await message.answer("⚠️ No vouchers in stock right now!")
        return
    await message.answer("🛍 <b>Select a Voucher:</b>", reply_markup=vouchers_kb(vouchers), parse_mode="HTML")
    await state.set_state(BuyStates.select_voucher)


@router.callback_query(F.data.startswith("bv:"))
async def select_voucher(callback: CallbackQuery, state: FSMContext):
    vid = int(callback.data.split(":")[1])
    v = get_voucher(vid)
    if not v or v["stock"] == 0:
        await callback.answer("❌ Out of stock!", show_alert=True); return
    await state.update_data(voucher_id=vid, voucher_name=v["name"], price=v["price"])
    await callback.message.edit_text(
        f"🎫 <b>{v['name']}</b>\n\n💰 ₹{v['price']:.0f} per code\n📦 {v['stock']} available\n\nSelect quantity:",
        reply_markup=quantity_kb(vid), parse_mode="HTML")
    await state.set_state(BuyStates.select_quantity)
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    vid, qty_str = int(parts[1]), parts[2]
    v = get_voucher(vid)
    if not v or v["stock"] == 0:
        await callback.answer("❌ Out of stock!", show_alert=True); return
    data = await state.get_data()
    price = data.get("price", v["price"])
    vname = data.get("voucher_name", v["name"])
    await state.update_data(voucher_id=vid, voucher_name=vname, price=price)
    if qty_str == "custom":
        await callback.message.edit_text("✏️ How many codes do you want?", parse_mode="HTML")
        await state.set_state(BuyStates.custom_quantity)
        await callback.answer(); return
    qty = int(qty_str)
    if qty > v["stock"]:
        await callback.answer(f"❌ Only {v['stock']} available!", show_alert=True); return
    total = qty * price
    await state.update_data(quantity=qty, total=total)
    await show_qr(callback, state, vid, vname, qty, price, total, callback.from_user.id)
    await callback.answer()


@router.message(BuyStates.custom_quantity)
async def custom_qty(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("❌ Cancelled.", reply_markup=main_menu()); return
    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("⚠️ Enter a valid number!"); return
    qty = int(message.text.strip())
    data = await state.get_data()
    v = get_voucher(data["voucher_id"])
    if not v or qty > v["stock"]:
        await message.answer(f"❌ Only {v['stock'] if v else 0} available!"); return
    price = data.get("price", v["price"])
    vname = data.get("voucher_name", v["name"])
    total = qty * price
    oid = create_order(message.from_user.id, data["voucher_id"], qty, total)
    await state.update_data(order_id=oid, quantity=qty, total=total)
    qr = get_setting("qr_file_id")
    text = f"🧾 <b>Order Summary</b>\n\n🆔 <code>{oid}</code>\n🎫 {vname}\n🔢 {qty} codes\n💵 ₹{total:.0f}"
    if qr:
        await message.answer_photo(qr, caption=text + "\n\n💳 Scan QR & click below:", reply_markup=confirm_order_kb(oid), parse_mode="HTML")
    else:
        await message.answer(text + "\n\n📌 Click below after paying:", reply_markup=confirm_order_kb(oid), parse_mode="HTML")
    asyncio.create_task(payment_timeout(message.bot, message.from_user.id, oid, state))
    await state.set_state(BuyStates.waiting_screenshot)


async def show_qr(callback, state, vid, vname, qty, price, total, user_id):
    oid = create_order(user_id, vid, qty, total)
    await state.update_data(order_id=oid)
    qr = get_setting("qr_file_id")
    text = f"🧾 <b>Order Summary</b>\n\n🆔 <code>{oid}</code>\n🎫 {vname}\n🔢 {qty} codes\n💰 ₹{price:.0f} × {qty}\n💵 <b>Total: ₹{total:.0f}</b>"
    try:
        await callback.message.delete()
    except Exception:
        pass
    if qr:
        await callback.message.answer_photo(qr, caption=text + "\n\n💳 Scan QR & click below:", reply_markup=confirm_order_kb(oid), parse_mode="HTML")
    else:
        await callback.message.answer(text + "\n\n📌 Click below after paying:", reply_markup=confirm_order_kb(oid), parse_mode="HTML")
    asyncio.create_task(payment_timeout(callback.bot, user_id, oid, state))
    await state.set_state(BuyStates.waiting_screenshot)


@router.callback_query(F.data.startswith("paid:"))
async def user_paid(callback: CallbackQuery, state: FSMContext):
    oid = callback.data.split(":")[1]
    order = get_order(oid)
    if not order or order["status"] != "pending":
        await callback.answer("❌ Order already processed!", show_alert=True); return
    await state.update_data(order_id=oid)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"📸 <b>Step 1/2 — Send Screenshot</b>\n\n🆔 <code>{oid}</code>\n💵 ₹{order['total_price']:.0f}\n\nSend your payment screenshot 👇",
        parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(BuyStates.waiting_screenshot)
    await callback.answer()


@router.message(BuyStates.waiting_screenshot, F.photo)
async def recv_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    oid = data.get("order_id")
    if not oid:
        await message.answer("⚠️ Session expired. Start new order.", reply_markup=main_menu())
        await state.clear(); return
    file_id = message.photo[-1].file_id
    save_screenshot(oid, file_id)
    await state.update_data(screenshot_file_id=file_id)
    await message.answer(
        "✅ Screenshot received!\n\n📝 <b>Step 2/2 — Enter Transaction ID</b>\n\nEnter 10-16 digit UTR/TXN ID from your payment app:",
        parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(BuyStates.waiting_txn_id)


@router.message(BuyStates.waiting_screenshot)
async def screenshot_invalid(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        data = await state.get_data()
        if data.get("order_id"):
            cancel_order(data["order_id"])
        await state.clear(); await message.answer("❌ Cancelled.", reply_markup=main_menu()); return
    await message.answer("📸 Please send a <b>photo</b> of your payment!", parse_mode="HTML")


@router.message(BuyStates.waiting_txn_id)
async def recv_txn(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        data = await state.get_data()
        if data.get("order_id"):
            cancel_order(data["order_id"])
        await state.clear(); await message.answer("❌ Cancelled.", reply_markup=main_menu()); return
    txn = message.text.strip() if message.text else ""
    if not txn.isdigit() or not (10 <= len(txn) <= 16):
        await message.answer("⚠️ Invalid! Enter a <b>10-16 digit</b> Transaction ID.", parse_mode="HTML"); return
    data = await state.get_data()
    oid = data.get("order_id")
    if not oid:
        await message.answer("⚠️ Session expired.", reply_markup=main_menu())
        await state.clear(); return
    order = get_order(oid)
    if not order or order["status"] != "pending":
        await message.answer("⚠️ Order no longer active.", reply_markup=main_menu())
        await state.clear(); return
    save_txn_id(oid, txn)
    await message.answer(
        f"🎉 <b>Submitted!</b>\n\n🆔 <code>{oid}</code>\n🎫 {order['voucher_name']} × {order['quantity']}\n💵 ₹{order['total_price']:.0f}\n🔖 TXN: <code>{txn}</code>\n\n⏳ Admin will verify shortly. You'll get codes once approved! ✅",
        reply_markup=main_menu(), parse_mode="HTML")
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"🔔 <b>New Payment — Action Required</b>\n\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {message.from_user.full_name} (@{message.from_user.username or 'N/A'}) [<code>{message.from_user.id}</code>]\n"
                f"🎫 {order['voucher_name']} × {order['quantity']}\n"
                f"💵 ₹{order['total_price']:.0f}\n"
                f"🔖 TXN: <code>{txn}</code>"
            )
            scr = data.get("screenshot_file_id")
            if scr:
                await bot.send_photo(admin_id, photo=scr, caption=caption,
                                     reply_markup=admin_approve_kb(oid), parse_mode="HTML")
            else:
                await bot.send_message(admin_id, caption, reply_markup=admin_approve_kb(oid), parse_mode="HTML")
        except Exception:
            pass
    await state.clear()


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_cb(callback: CallbackQuery, state: FSMContext):
    cancel_order(callback.data.split(":")[1])
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("❌ Order cancelled.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "back_vouchers")
async def back_vouchers(callback: CallbackQuery, state: FSMContext):
    vouchers = [v for v in get_all_vouchers() if v["stock"] > 0]
    await callback.message.edit_text("🛍 <b>Select a Voucher:</b>", reply_markup=vouchers_kb(vouchers), parse_mode="HTML")
    await state.set_state(BuyStates.select_voucher)
    await callback.answer()


# ══════════════════════════════════════════
#  ADMIN HANDLERS
# ══════════════════════════════════════════

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access Denied."); return
    await state.clear()
    stats = get_stats()
    pending = stats["pending_orders"]
    low = get_low_stock(5)
    alerts = []
    if pending > 0:
        alerts.append(f"🔔 <b>{pending} order(s) waiting review!</b>")
    for v in low:
        alerts.append(f"⚠️ Low stock: {v['name']} ({v['stock']} left)")
    alert_text = "\n".join(alerts) + "\n\n" if alerts else ""
    await message.answer(
        f"🔐 <b>Admin Panel</b>\n\n{alert_text}"
        f"👥 Users: <b>{stats['total_users']}</b> | ✅ Orders: <b>{stats['total_orders']}</b> | 💰 ₹<b>{stats['total_earnings']:.0f}</b>\n"
        f"📅 Today: <b>{stats['today_orders']} orders</b> | <b>₹{stats['today_earnings']:.0f}</b>",
        reply_markup=admin_menu(), parse_mode="HTML")


@router.message(Command("order"))
async def search_order(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.answer("Usage: /order <ORDER_ID>"); return
    order = get_order(command.args.strip().upper())
    if not order:
        await message.answer("❌ Order not found."); return
    sm = {"pending": "⏳ Pending", "approved": "✅ Approved", "rejected": "❌ Rejected", "cancelled": "🚫 Cancelled"}
    text = (f"🔍 <b>Order</b>\n\n🆔 <code>{order['id']}</code>\n👤 User: <code>{order['user_id']}</code>\n"
            f"🎫 {order['voucher_name']} × {order['quantity']}\n💵 ₹{order['total_price']:.0f}\n"
            f"🔖 TXN: <code>{order.get('txn_id') or 'N/A'}</code>\n📊 {sm.get(order['status'], order['status'])}")
    kb = admin_approve_kb(order["id"]) if order["status"] == "pending" else None
    if order.get("screenshot_file_id") and order["status"] == "pending":
        await message.answer_photo(order["screenshot_file_id"], caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏠 Main Menu")
async def go_main(message: Message, state: FSMContext):
    await state.clear(); await message.answer("🏠 Main Menu", reply_markup=main_menu())


@router.message(F.text == "📊 Statistics")
async def view_stats(message: Message):
    if not is_admin(message.from_user.id): return
    s = get_stats()
    low = get_low_stock(5)
    text = (f"📊 <b>Statistics</b>\n\n👥 Users: <b>{s['total_users']}</b>\n✅ Orders: <b>{s['total_orders']}</b>\n"
            f"⏳ Pending: <b>{s['pending_orders']}</b>\n💰 Earnings: <b>₹{s['total_earnings']:.0f}</b>\n\n"
            f"📅 Today: <b>{s['today_orders']} orders</b> | <b>₹{s['today_earnings']:.0f}</b>")
    if low:
        text += "\n\n⚠️ <b>Low Stock:</b>\n" + "\n".join([f"   {v['name']}: {v['stock']} left" for v in low])
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📦 View Stock")
async def view_stock(message: Message):
    if not is_admin(message.from_user.id): return
    vouchers = get_all_vouchers()
    if not vouchers:
        await message.answer("No vouchers."); return
    lines = [f"{'❌' if v['stock']==0 else '⚠️' if v['stock']<=5 else '✅'} {v['name']} — {v['stock']} codes (₹{v['price']:.0f})" for v in vouchers]
    await message.answer("📦 <b>Stock</b>\n\n" + "\n".join(lines), parse_mode="HTML")


@router.message(F.text == "➕ Add Voucher")
async def add_v_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📝 Enter voucher name:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.add_voucher_name)


@router.message(AdminStates.add_voucher_name)
async def add_v_name(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    await state.update_data(voucher_name=message.text.strip())
    await message.answer("💰 Enter price per code (₹):")
    await state.set_state(AdminStates.add_voucher_price)


@router.message(AdminStates.add_voucher_price)
async def add_v_price(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid number!"); return
    data = await state.get_data()
    ok = add_voucher(data["voucher_name"], price)
    await message.answer(
        f"✅ '<b>{data['voucher_name']}</b>' added at ₹{price:.0f}!\nNow use 📥 Add Codes to upload codes." if ok
        else "❌ Voucher name already exists!", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


@router.message(F.text == "❌ Delete Voucher")
async def del_v_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    vouchers = get_all_vouchers()
    lines = [f"{v['id']}. {v['name']} ({v['stock']} codes)" for v in vouchers]
    await message.answer("🗑 Send voucher ID to delete:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(AdminStates.remove_voucher)


@router.message(AdminStates.remove_voucher)
async def del_v_handler(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter valid ID!"); return
    v = get_voucher(vid)
    if not v:
        await message.answer("❌ Not found!"); return
    delete_voucher(vid)
    await message.answer(f"✅ '<b>{v['name']}</b>' deleted!", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


@router.message(F.text == "💰 Set Price")
async def set_p_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    vouchers = get_all_vouchers()
    lines = [f"{v['id']}. {v['name']} (₹{v['price']:.0f})" for v in vouchers]
    await message.answer("💰 Send voucher ID:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(AdminStates.set_price_voucher)


@router.message(AdminStates.set_price_voucher)
async def set_p_voucher(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter valid ID!"); return
    v = get_voucher(vid)
    if not v:
        await message.answer("❌ Not found!"); return
    await state.update_data(voucher_id=vid, voucher_name=v["name"])
    await message.answer(f"Enter new price for <b>{v['name']}</b> (₹):", parse_mode="HTML")
    await state.set_state(AdminStates.set_price_value)


@router.message(AdminStates.set_price_value)
async def set_p_value(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter valid number!"); return
    data = await state.get_data()
    update_price(data["voucher_id"], price)
    await message.answer(f"✅ Price → ₹{price:.0f} for <b>{data['voucher_name']}</b>!", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


@router.message(F.text == "📥 Add Codes")
async def add_c_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    vouchers = get_all_vouchers()
    lines = [f"{v['id']}. {v['name']} ({v['stock']} codes)" for v in vouchers]
    await message.answer("📥 Send voucher ID:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(AdminStates.add_codes_voucher)


@router.message(AdminStates.add_codes_voucher)
async def add_c_select(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter valid ID!"); return
    v = get_voucher(vid)
    if not v:
        await message.answer("❌ Not found!"); return
    await state.update_data(voucher_id=vid, voucher_name=v["name"])
    await message.answer(f"📥 Paste codes for <b>{v['name']}</b>\n\nOne code per line:", parse_mode="HTML")
    await state.set_state(AdminStates.add_codes_input)


@router.message(AdminStates.add_codes_input)
async def add_c_input(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    data = await state.get_data()
    count = add_codes_bulk(data["voucher_id"], message.text)
    v = get_voucher(data["voucher_id"])
    await message.answer(f"✅ Added <b>{count} codes</b> to {data['voucher_name']}!\nTotal stock: <b>{v['stock']}</b>",
                         reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


@router.message(F.text == "🗑 Remove Codes")
async def rem_c_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    vouchers = get_all_vouchers()
    lines = [f"{v['id']}. {v['name']} ({v['stock']} unused)" for v in vouchers]
    await message.answer("🗑 Send voucher ID to remove ALL unused codes:\n\n" + "\n".join(lines), reply_markup=cancel_kb())
    await state.set_state(AdminStates.add_codes_voucher)


@router.message(F.text == "🖼 Upload QR")
async def upload_qr_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("🖼 Send your payment QR code photo:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.upload_qr)


@router.message(AdminStates.upload_qr, F.photo)
async def recv_qr(message: Message, state: FSMContext):
    set_setting("qr_file_id", message.photo[-1].file_id)
    await message.answer("✅ QR updated!", reply_markup=admin_menu())
    await state.clear()


@router.message(AdminStates.upload_qr)
async def qr_invalid(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    await message.answer("📷 Send a <b>photo</b>!", parse_mode="HTML")


@router.message(F.text == "⏳ Pending Orders")
async def pending_orders(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    orders = get_pending_orders()
    if not orders:
        await message.answer("✅ No pending orders!"); return
    await message.answer(f"⏳ <b>{len(orders)} Pending Order(s)</b>", parse_mode="HTML")
    for o in orders:
        caption = (f"🔔 <b>Pending</b>\n\n🆔 <code>{o['id']}</code>\n👤 {o['full_name']} (@{o['username'] or 'N/A'})\n"
                   f"🎫 {o['voucher_name']} × {o['quantity']}\n💵 ₹{o['total_price']:.0f}\n🔖 TXN: <code>{o.get('txn_id') or 'N/A'}</code>")
        if o["screenshot_file_id"]:
            await bot.send_photo(message.from_user.id, o["screenshot_file_id"], caption=caption,
                                 reply_markup=admin_approve_kb(o["id"]), parse_mode="HTML")
        else:
            await message.answer(caption + "\n\n⚠️ No screenshot.", parse_mode="HTML")


@router.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access Denied!", show_alert=True); return
    oid = callback.data.split(":")[1]
    order = get_order(oid)
    if not order:
        await callback.answer("Not found!", show_alert=True); return
    if order["status"] != "pending":
        await callback.answer(f"Already {order['status']}!", show_alert=True); return
    codes = deliver_codes(oid, order["voucher_id"], order["quantity"])
    if codes is None:
        await callback.answer("❌ Not enough stock!", show_alert=True); return
    codes_text = "\n".join([f"<code>{c}</code>" for c in codes])
    try:
        await bot.send_message(order["user_id"],
            f"🎉 <b>Payment Approved!</b>\n\n🆔 <code>{oid}</code>\n🎫 {order['voucher_name']} × {order['quantity']}\n\n🎁 <b>Your Codes:</b>\n{codes_text}\n\nThank you! 🙏",
            parse_mode="HTML")
    except Exception:
        pass
    try:
        if callback.message.caption:
            await callback.message.edit_caption(callback.message.caption + "\n\n✅ <b>APPROVED</b>", reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(callback.message.text + "\n\n✅ <b>APPROVED</b>", reply_markup=None, parse_mode="HTML")
    except Exception:
        pass
    remaining = get_voucher_stock(order["voucher_id"])
    note = "\n\n🚨 <b>Stock EMPTY! Add more codes.</b>" if remaining == 0 else f"\n\n⚠️ Only {remaining} codes left!" if remaining <= 5 else ""
    await callback.message.answer(
        f"✅ <b>Approved!</b>\n\n🆔 <code>{oid}</code>\n🎫 {order['voucher_name']} × {order['quantity']}\n💵 ₹{order['total_price']:.0f}\n📦 {len(codes)} code(s) sent.{note}",
        parse_mode="HTML")
    await callback.answer("✅ Approved!", show_alert=True)


@router.callback_query(F.data.startswith("reject:"))
async def reject_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access Denied!", show_alert=True); return
    oid = callback.data.split(":")[1]
    order = get_order(oid)
    if not order or order["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return
    await state.update_data(reject_order_id=oid)
    await callback.message.answer(
        "📝 Enter rejection reason (or type <code>skip</code> for default):",
        parse_mode="HTML")
    await state.set_state(AdminStates.reject_reason)
    await callback.answer()


@router.message(AdminStates.reject_reason)
async def reject_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data["reject_order_id"]
    order = get_order(oid)
    reason = message.text if message.text.lower() != "skip" else "Payment could not be verified. Please contact support."
    reject_order(oid)
    try:
        await bot.send_message(order["user_id"],
            f"❌ <b>Order Rejected</b>\n\n🆔 <code>{oid}</code>\n🎫 {order['voucher_name']} × {order['quantity']}\n\n📝 Reason: {reason}\n\nContact support if you think this is a mistake.",
            parse_mode="HTML")
    except Exception:
        pass
    await message.answer(f"❌ Order <code>{oid}</code> rejected. User notified.", parse_mode="HTML", reply_markup=admin_menu())
    await state.clear()


@router.message(F.text == "📢 Broadcast")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📢 Enter broadcast message:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.broadcast_message)


@router.message(AdminStates.broadcast_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>Announcement</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Sent to {sent}/{len(users)} users.", reply_markup=admin_menu())
    await state.clear()


@router.message(F.text == "🆘 Support Settings")
async def support_settings(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer(f"Current: <b>{get_setting('support_username')}</b>\n\nEnter new support username:", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AdminStates.set_support)


@router.message(AdminStates.set_support)
async def set_support(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    set_setting("support_username", message.text.strip())
    await message.answer(f"✅ Support updated to <b>{message.text.strip()}</b>!", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


@router.message(F.text == "📢 Manage Channels")
async def manage_channels(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    channels = get_all_channels()
    lines = [f"{ch['id']}. {ch['name']} — {ch['link']}" for ch in channels] or ["None yet."]
    await message.answer("📢 <b>Channels</b>\n\n" + "\n".join(lines) + "\n\nType <b>add</b> to add, or send ID to remove:",
                         reply_markup=cancel_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.remove_channel)


@router.message(AdminStates.remove_channel)
async def manage_ch_action(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Done.", reply_markup=admin_menu()); return
    if message.text.lower() == "add":
        await message.answer("Enter channel name:")
        await state.set_state(AdminStates.add_channel_name); return
    try:
        remove_channel(int(message.text.strip()))
        await message.answer("✅ Removed!", reply_markup=admin_menu())
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Enter valid ID or 'add'.")


@router.message(AdminStates.add_channel_name)
async def add_ch_name(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    await state.update_data(ch_name=message.text.strip())
    await message.answer("Enter channel link (https://t.me/...):")
    await state.set_state(AdminStates.add_channel_link)


@router.message(AdminStates.add_channel_link)
async def add_ch_link(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear(); await message.answer("Cancelled.", reply_markup=admin_menu()); return
    data = await state.get_data()
    add_channel(data["ch_name"], message.text.strip())
    await message.answer(f"✅ Channel '<b>{data['ch_name']}</b>' added!", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print("✅ Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
