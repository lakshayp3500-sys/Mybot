"""
handlers/admin.py — Full admin panel with premium UI, live orders, sale receipts, SMS verify.
"""

from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, ORDER_EXPIRY_MINUTES
from states.states import AdminStates
from utils.db_helpers import (
    get_all_vouchers_with_stock, get_voucher, get_voucher_stock,
    get_order, deliver_codes, reject_order, cancel_order,
    add_voucher, delete_voucher, update_price,
    add_codes_bulk, remove_all_codes,
    get_setting, set_setting,
    get_all_channels, add_channel, remove_channel,
    get_stats, get_all_users, get_pending_orders,
    get_low_stock_vouchers, get_out_of_stock_vouchers, get_order_codes,
    get_voucher_disclaimer, set_voucher_disclaimer,
    is_maintenance, set_maintenance
)
from utils.messages import (
    admin_sale_receipt, admin_manual_sale_receipt, DIVIDER
)
from order_manager import expire_orders
from payment import verify_payment
from keyboards.reply import admin_menu, main_menu, cancel_keyboard
from keyboards.inline import admin_approve_keyboard

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access Denied.")
        return
    stats = get_stats()
    await message.answer(
        f"🔐 <b>ADMIN PANEL</b>\n"
        f"{DIVIDER}\n\n"
        f"👥 Users: <b>{stats['total_users']}</b>  •  "
        f"✅ Orders: <b>{stats['total_orders']}</b>\n"
        f"💰 Today: <b>₹{stats['today_earnings']:.0f}</b>  •  "
        f"⏳ Pending: <b>{stats['pending_orders']}</b>\n"
        f"{DIVIDER}",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

# ─── SMS AUTO-VERIFY (/pay command) ───────────────────────────────────────────
@router.message(Command("pay"))
async def pay_via_sms(message: Message, command: CommandObject, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer(
            "📲 <b>SMS Verify Usage:</b>\n\n"
            "<code>/pay &lt;full SMS text&gt;</code>\n\n"
            "Example:\n"
            "<code>/pay Rs.149.37 received from UPI</code>",
            parse_mode="HTML"
        )
        return
    await _process_sms(message, bot, command.args.strip())

@router.message(Command("sms"))
async def sms_alias(message: Message, command: CommandObject, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer("Usage: <code>/sms &lt;SMS text&gt;</code>", parse_mode="HTML")
        return
    await _process_sms(message, bot, command.args.strip())

async def _process_sms(message: Message, bot: Bot, sms_text: str):
    processing = await message.answer("🔄 <b>Processing payment...</b>", parse_mode="HTML")

    order = verify_payment(sms_text)

    if not order:
        await processing.edit_text(
            f"❌ <b>No Matching Order Found</b>\n\n"
            f"No pending order matched the amount in:\n"
            f"<i>{sms_text[:100]}</i>",
            parse_mode="HTML"
        )
        return

    order_id = order["id"]
    codes = deliver_codes(order_id, order["voucher_id"], order["quantity"])

    if codes is None:
        await processing.edit_text(
            f"⚠️ <b>Stock Error</b>\n\n"
            f"Order <code>#{order_id}</code> matched but not enough codes in stock!",
            parse_mode="HTML"
        )
        return

    matched_amount = order.get("matched_amount", order.get("unique_amount", 0))
    support = get_setting("support_username") or "@admin"
    from utils.messages import success_delivery_msg
    user_msg = success_delivery_msg(
        voucher_name=order["voucher_name"],
        codes=codes,
        amount=matched_amount,
        order_id=order_id,
        support=support
    )

    try:
        await bot.send_message(order["user_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    remaining = get_voucher_stock(order["voucher_id"])
    stock_note = ""
    if remaining == 0:
        stock_note = "\n\n🚨 <b>STOCK EMPTY! Add more codes immediately.</b>"
    elif remaining <= 5:
        stock_note = f"\n\n⚠️ Low stock: only <b>{remaining}</b> codes left!"

    try:
        from utils.db_helpers import get_user
        user_info = get_user(order["user_id"]) or {}
        buyer_username = user_info.get("username", "N/A")
    except Exception:
        buyer_username = "N/A"

    receipt = admin_sale_receipt(
        buyer_username=buyer_username,
        buyer_id=order["user_id"],
        voucher_name=order["voucher_name"],
        quantity=order["quantity"],
        base_amount=order["total_price"],
        unique_amount=matched_amount,
        order_id=order_id,
        codes=codes
    )
    await processing.edit_text(receipt + stock_note, parse_mode="HTML")

# ─── LIVE ORDERS ──────────────────────────────────────────────────────────────
@router.message(F.text == "📡 Live Orders")
async def live_orders(message: Message):
    if not is_admin(message.from_user.id):
        return

    orders = get_pending_orders()
    now = datetime.now()

    active = []
    for o in orders:
        try:
            expiry = datetime.fromisoformat(str(o["expiry_at"]))
            if expiry > now:
                remaining_secs = int((expiry - now).total_seconds())
                o["_remaining"] = remaining_secs
                active.append(o)
        except Exception:
            pass

    if not active:
        await message.answer(
            f"📡 <b>LIVE ORDERS</b>\n"
            f"{DIVIDER}\n\n"
            f"✅ No active pending orders right now.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"📡 <b>LIVE ORDERS</b>\n"
        f"{DIVIDER}\n\n"
        f"🔴 <b>{len(active)}</b> order(s) waiting for payment:",
        parse_mode="HTML"
    )

    for o in active:
        remaining = o["_remaining"]
        mins = remaining // 60
        secs = remaining % 60
        unique_amount = o.get("unique_amount") or o["total_price"]

        text = (
            f"⏳ <b>PENDING ORDER</b>\n"
            f"{DIVIDER}\n\n"
            f"👤 @{o.get('username') or 'N/A'}  •  ID: <code>{o['user_id']}</code>\n"
            f"🎁 <b>{o['voucher_name']}</b> × {o['quantity']}\n"
            f"💳 Pay: <b>₹{unique_amount:.2f}</b>\n"
            f"⏱ Expires in: <b>{mins:02d}m {secs:02d}s</b>\n"
            f"🆔 <code>#{o['id']}</code>"
        )
        await message.answer(text, reply_markup=admin_approve_keyboard(o["id"]), parse_mode="HTML")

# ─── PENDING ORDERS ───────────────────────────────────────────────────────────
@router.message(F.text == "⏳ Pending Orders")
async def pending_orders_btn(message: Message):
    if not is_admin(message.from_user.id):
        return
    orders = get_pending_orders()
    if not orders:
        await message.answer("✅ <b>No Pending Orders</b>", parse_mode="HTML")
        return

    await message.answer(
        f"⏳ <b>{len(orders)} PENDING ORDER(S)</b>\n"
        f"{DIVIDER}\n"
        f"<i>Use /pay &lt;SMS text&gt; to auto-verify</i>",
        parse_mode="HTML"
    )
    for order in orders:
        unique_amount = order.get("unique_amount") or order["total_price"]
        text = (
            f"⏳ <b>Pending Order</b>\n"
            f"{DIVIDER}\n\n"
            f"🆔 <code>#{order['id']}</code>\n"
            f"👤 {order['full_name']} (@{order.get('username') or 'N/A'})\n"
            f"🎁 {order['voucher_name']} × {order['quantity']}\n"
            f"💵 Base: ₹{order['total_price']:.0f}\n"
            f"🎯 Unique: <b>₹{unique_amount:.2f}</b>\n"
            f"📅 {str(order['created_at'])[:16]}"
        )
        await message.answer(text, reply_markup=admin_approve_keyboard(order["id"]), parse_mode="HTML")

# ─── MANUAL APPROVE ───────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access Denied!", show_alert=True)
        return
    order_id = callback.data.split(":")[1]
    order = get_order(order_id)
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    if order["status"] not in ("pending", "paid"):
        await callback.answer(f"Order is already {order['status']}!", show_alert=True)
        return

    codes = deliver_codes(order_id, order["voucher_id"], order["quantity"])
    if codes is None:
        await callback.answer("❌ Not enough stock to deliver!", show_alert=True)
        return

    support = get_setting("support_username") or "@admin"
    from utils.messages import success_delivery_msg
    unique_amount = order.get("unique_amount") or order["total_price"]
    user_msg = success_delivery_msg(
        voucher_name=order["voucher_name"],
        codes=codes,
        amount=unique_amount,
        order_id=order_id,
        support=support
    )
    try:
        await bot.send_message(order["user_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    try:
        edit_text = (callback.message.text or "") + "\n\n✅ <b>APPROVED & DELIVERED</b>"
        await callback.message.edit_text(edit_text, reply_markup=None, parse_mode="HTML")
    except Exception:
        pass

    try:
        from utils.db_helpers import get_user
        user_info = get_user(order["user_id"]) or {}
        buyer_username = user_info.get("username", "N/A")
    except Exception:
        buyer_username = "N/A"

    remaining = get_voucher_stock(order["voucher_id"])
    stock_note = ""
    if remaining == 0:
        stock_note = "\n\n🚨 <b>STOCK EMPTY! Add more codes.</b>"
    elif remaining <= 5:
        stock_note = f"\n\n⚠️ Only <b>{remaining}</b> codes left!"

    receipt = admin_manual_sale_receipt(
        buyer_username=buyer_username,
        buyer_id=order["user_id"],
        voucher_name=order["voucher_name"],
        quantity=order["quantity"],
        base_amount=order["total_price"],
        order_id=order_id,
        codes=codes
    )
    await callback.message.answer(receipt + stock_note, parse_mode="HTML")
    await callback.answer("✅ Approved! Codes sent.", show_alert=True)

# ─── MANUAL REJECT ────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("reject:"))
async def reject_order_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access Denied!", show_alert=True)
        return
    order_id = callback.data.split(":")[1]
    order = get_order(order_id)
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    if order["status"] not in ("pending", "paid"):
        await callback.answer(f"Order is already {order['status']}!", show_alert=True)
        return
    await state.update_data(reject_order_id=order_id)
    await callback.message.answer(
        "📝 <b>Rejection Reason</b>\n\n"
        "Enter the reason (sent to user), or type <code>skip</code> for default:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.reject_reason)
    await callback.answer()

@router.message(AdminStates.reject_reason)
async def reject_order_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data["reject_order_id"]
    order = get_order(order_id)
    reason = (
        message.text
        if message.text and message.text.lower() != "skip"
        else "Payment could not be verified. Please contact support."
    )

    reject_order(order_id)

    try:
        await bot.send_message(
            order["user_id"],
            f"❌ <b>ORDER REJECTED</b>\n"
            f"{DIVIDER}\n\n"
            f"🆔 Order: <code>#{order_id}</code>\n"
            f"🎁 {order['voucher_name']} × {order['quantity']}\n\n"
            f"📝 <b>Reason:</b> {reason}\n\n"
            f"Contact support if you believe this is a mistake.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"❌ <b>Order Rejected</b>\n\n<code>#{order_id}</code> rejected. User notified.",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )
    await state.clear()

# ─── STATISTICS ───────────────────────────────────────────────────────────────
@router.message(F.text == "📊 Statistics")
async def view_statistics(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = get_stats()
    low_stock = get_low_stock_vouchers(5)
    out_of_stock = get_out_of_stock_vouchers()

    text = (
        f"📊 <b>STATISTICS</b>\n"
        f"{DIVIDER}\n\n"
        f"👥 Total Users: <b>{stats['total_users']}</b>\n"
        f"✅ Completed Orders: <b>{stats['total_orders']}</b>\n"
        f"⏳ Pending Orders: <b>{stats['pending_orders']}</b>\n"
        f"💰 Total Earnings: <b>₹{stats['total_earnings']:.0f}</b>\n\n"
        f"📅 <b>TODAY</b>\n"
        f"   📦 Orders: <b>{stats['today_orders']}</b>\n"
        f"   💵 Earnings: <b>₹{stats['today_earnings']:.0f}</b>"
    )
    if low_stock:
        names = ", ".join([v["name"] for v in low_stock])
        text += f"\n\n⚠️ <b>Low Stock:</b> {names}"
    if out_of_stock:
        names = ", ".join([v["name"] for v in out_of_stock])
        text += f"\n\n🚨 <b>Out of Stock:</b> {names}"

    await message.answer(text, parse_mode="HTML")

# ─── VIEW STOCK ───────────────────────────────────────────────────────────────
@router.message(F.text == "📦 View Stock")
async def view_stock(message: Message):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer("⚠️ No vouchers found.")
        return
    lines = []
    for v in vouchers:
        if v["stock"] == 0:
            lines.append(f"🔴 {v['name']} — OUT OF STOCK (₹{v['price']:.0f})")
        elif v["stock"] <= 5:
            lines.append(f"🟡 {v['name']} — {v['stock']} codes (₹{v['price']:.0f}) ⚠️ LOW")
        else:
            lines.append(f"🟢 {v['name']} — {v['stock']} codes (₹{v['price']:.0f})")

    await message.answer(
        f"📦 <b>CURRENT STOCK</b>\n{DIVIDER}\n\n" + "\n".join(lines),
        parse_mode="HTML"
    )

# ─── ADD VOUCHER ──────────────────────────────────────────────────────────────
@router.message(F.text == "➕ Add Voucher")
async def add_voucher_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📝 Enter the voucher name:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.add_voucher_name)

@router.message(AdminStates.add_voucher_name)
async def add_voucher_name_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    await state.update_data(voucher_name=message.text.strip())
    await message.answer("💰 Enter price per code (₹):")
    await state.set_state(AdminStates.add_voucher_price)

@router.message(AdminStates.add_voucher_price)
async def add_voucher_price_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid number (e.g. 149):")
        return
    data = await state.get_data()
    success = add_voucher(data["voucher_name"], price)
    if success:
        await message.answer(
            f"✅ <b>Voucher Added!</b>\n\n"
            f"🎁 Name: <b>{data['voucher_name']}</b>\n"
            f"💰 Price: ₹{price:.0f}\n\n"
            f"Now use <b>📥 Add Codes</b> to upload codes.",
            reply_markup=admin_menu(), parse_mode="HTML"
        )
    else:
        await message.answer("❌ A voucher with this name already exists!", reply_markup=admin_menu())
    await state.clear()

# ─── DELETE VOUCHER ───────────────────────────────────────────────────────────
@router.message(F.text == "❌ Delete Voucher")
async def delete_voucher_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer("No vouchers found.")
        return
    lines = [f"<b>{v['id']}</b>. {v['name']} ({v['stock']} codes)" for v in vouchers]
    await message.answer(
        f"🗑 <b>DELETE VOUCHER</b>\n{DIVIDER}\n\n"
        + "\n".join(lines)
        + "\n\nSend the voucher <b>ID number</b> to delete it:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.remove_voucher)

@router.message(AdminStates.remove_voucher)
async def delete_voucher_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid ID number!")
        return
    voucher = get_voucher(vid)
    if not voucher:
        await message.answer("❌ Voucher not found!")
        return
    delete_voucher(vid)
    await message.answer(
        f"✅ <b>{voucher['name']}</b> and all its codes deleted!",
        reply_markup=admin_menu(), parse_mode="HTML"
    )
    await state.clear()

# ─── SET PRICE ────────────────────────────────────────────────────────────────
@router.message(F.text == "💰 Set Price")
async def set_price_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    lines = [f"<b>{v['id']}</b>. {v['name']} (₹{v['price']:.0f})" for v in vouchers]
    await message.answer(
        f"💰 <b>SET PRICE</b>\n{DIVIDER}\n\n" + "\n".join(lines) + "\n\nSend voucher ID:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.set_price_voucher)

@router.message(AdminStates.set_price_voucher)
async def set_price_voucher_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid ID!")
        return
    voucher = get_voucher(vid)
    if not voucher:
        await message.answer("❌ Voucher not found!")
        return
    await state.update_data(voucher_id=vid, voucher_name=voucher["name"])
    await message.answer(f"Enter new price for <b>{voucher['name']}</b> (₹):", parse_mode="HTML")
    await state.set_state(AdminStates.set_price_value)

@router.message(AdminStates.set_price_value)
async def set_price_value_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid number!")
        return
    data = await state.get_data()
    update_price(data["voucher_id"], price)
    await message.answer(
        f"✅ Price updated to <b>₹{price:.0f}</b> for {data['voucher_name']}!",
        reply_markup=admin_menu(), parse_mode="HTML"
    )
    await state.clear()

# ─── SET DISCLAIMER ───────────────────────────────────────────────────────────
@router.message(F.text == "📋 Set Disclaimer")
async def set_disclaimer_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer("⚠️ No vouchers found.", reply_markup=admin_menu())
        return
    lines = []
    for v in vouchers:
        disc = get_voucher_disclaimer(v["id"])
        tag = " ✅" if disc else " ➖"
        lines.append(f"<b>{v['id']}</b>. {v['name']}{tag}")
    await message.answer(
        f"📋 <b>SET DISCLAIMER</b>\n"
        f"{DIVIDER}\n\n"
        + "\n".join(lines)
        + f"\n\n✅ = Disclaimer set  •  ➖ = Not set\n\n"
        f"Send voucher <b>ID</b> to edit its disclaimer:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.set_disclaimer_voucher)

@router.message(AdminStates.set_disclaimer_voucher)
async def set_disclaimer_voucher_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid ID number!")
        return
    voucher = get_voucher(vid)
    if not voucher:
        await message.answer("❌ Voucher not found!")
        return
    existing = get_voucher_disclaimer(vid)
    await state.update_data(disclaimer_voucher_id=vid, disclaimer_voucher_name=voucher["name"])

    if existing:
        preview = existing[:150] + ("..." if len(existing) > 150 else "")
        existing_block = f"\n\n📋 <b>Current Disclaimer:</b>\n<i>{preview}</i>"
    else:
        existing_block = "\n\n<i>No disclaimer set for this voucher.</i>"

    await message.answer(
        f"📋 <b>Disclaimer for: {voucher['name']}</b>"
        f"{existing_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Type the new disclaimer text below.\n"
        f"(Send <code>clear</code> to remove existing disclaimer)",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.set_disclaimer_text)

@router.message(AdminStates.set_disclaimer_text)
async def set_disclaimer_text_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    vid = data["disclaimer_voucher_id"]
    name = data["disclaimer_voucher_name"]

    if message.text.strip().lower() == "clear":
        set_voucher_disclaimer(vid, "")
        await message.answer(
            f"🗑 <b>Disclaimer Removed</b>\n\n"
            f"No disclaimer will be shown for <b>{name}</b>.",
            reply_markup=admin_menu(), parse_mode="HTML"
        )
    else:
        set_voucher_disclaimer(vid, message.text.strip())
        await message.answer(
            f"✅ <b>Disclaimer Saved!</b>\n"
            f"{DIVIDER}\n\n"
            f"🎁 <b>Voucher:</b> {name}\n\n"
            f"📋 <b>Disclaimer:</b>\n"
            f"<i>{message.text.strip()[:200]}</i>\n\n"
            f"{DIVIDER}\n"
            f"Users will see this before paying for <b>{name}</b>.",
            reply_markup=admin_menu(), parse_mode="HTML"
        )
    await state.clear()

# ─── ADD CODES ────────────────────────────────────────────────────────────────
@router.message(F.text == "📥 Add Codes")
async def add_codes_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    lines = [f"<b>{v['id']}</b>. {v['name']} ({v['stock']} codes)" for v in vouchers]
    await message.answer(
        f"📥 <b>ADD CODES</b>\n{DIVIDER}\n\n" + "\n".join(lines) + "\n\nSend voucher ID:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_codes_voucher)

@router.message(AdminStates.add_codes_voucher)
async def add_codes_select_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        vid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Enter a valid ID!")
        return
    voucher = get_voucher(vid)
    if not voucher:
        await message.answer("❌ Voucher not found!")
        return
    await state.update_data(voucher_id=vid, voucher_name=voucher["name"])
    await message.answer(
        f"📥 Paste codes for <b>{voucher['name']}</b>\n\n"
        f"One code per line:\n"
        f"<code>ABC123\nXYZ999\nTEST777</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_codes_input)

@router.message(AdminStates.add_codes_input)
async def add_codes_input_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    count = add_codes_bulk(data["voucher_id"], message.text)
    voucher = get_voucher(data["voucher_id"])
    await message.answer(
        f"✅ <b>Codes Added!</b>\n\n"
        f"🎁 {data['voucher_name']}\n"
        f"➕ Added: <b>{count} codes</b>\n"
        f"📦 Total stock: <b>{voucher['stock']} codes</b>",
        reply_markup=admin_menu(), parse_mode="HTML"
    )
    await state.clear()

# ─── REMOVE CODES ─────────────────────────────────────────────────────────────
@router.message(F.text == "🗑 Remove Codes")
async def remove_codes_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    lines = [f"<b>{v['id']}</b>. {v['name']} ({v['stock']} unused codes)" for v in vouchers]
    await message.answer(
        f"🗑 <b>REMOVE CODES</b>\n{DIVIDER}\n\n" + "\n".join(lines) +
        "\n\nSend voucher ID to remove ALL unused codes:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.remove_codes_voucher)

  @router.message(AdminStates.remove_codes_voucher)
  async def remove_codes_voucher_h(message: Message, state: FSMContext):
      if message.text == "❌ Cancel":
          await state.clear()
          await message.answer("Cancelled.", reply_markup=admin_menu())
          return
      try:
          vid = int(message.text.strip())
      except ValueError:
          await message.answer("⚠️ Enter a valid ID number!")
          return
      voucher = get_voucher(vid)
      if not voucher:
          await message.answer("❌ Voucher not found!")
          return
      remove_all_codes(vid)
      await message.answer(
          f"✅ <b>All unused codes removed!</b>\n\n"
          f"🎁 {voucher['name']} — stock is now 0.",
          reply_markup=admin_menu(), parse_mode="HTML"
      )
      await state.clear()

  # ─── BROADCAST ────────────────────────────────────────────────────────────────
@router.message(F.text == "📢 Broadcast")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"📢 <b>BROADCAST</b>\n{DIVIDER}\n\n"
        f"Enter message to send to all users.\n"
        f"<i>(HTML supported: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;)</i>",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.broadcast_message)

@router.message(AdminStates.broadcast_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    users = get_all_users()
    sent = failed = 0
    status_msg = await message.answer(f"📤 <b>Sending to {len(users)} users...</b>", parse_mode="HTML")
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>ANNOUNCEMENT</b>\n{DIVIDER}\n\n{message.text}", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n✓ Sent: {sent}\n✗ Failed: {failed}",
        parse_mode="HTML"
    )
    await message.answer("Done.", reply_markup=admin_menu())
    await state.clear()

# ─── MAINTENANCE MODE ─────────────────────────────────────────────────────────
@router.message(F.text == "🔧 Maintenance")
async def maintenance_toggle(message: Message):
    if not is_admin(message.from_user.id):
        return
    current = is_maintenance()
    status_text = "🔴 ON (Bot is closed for users)" if current else "🟢 OFF (Bot is open)"
    await message.answer(
        f"🔧 <b>MAINTENANCE MODE</b>\n"
        f"{DIVIDER}\n\n"
        f"Current Status: <b>{status_text}</b>\n\n"
        f"When ON — all users see maintenance message.\n"
        f"You (admin) can still use the bot normally.\n\n"
        f"{DIVIDER}\n"
        f"Press button below to toggle:",
        reply_markup=_maintenance_keyboard(current),
        parse_mode="HTML"
    )

def _maintenance_keyboard(is_on: bool):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if is_on:
        builder.button(text="✅ Turn OFF — Open Bot", callback_data="maintenance:off")
    else:
        builder.button(text="🔴 Turn ON — Close Bot", callback_data="maintenance:on")
    builder.adjust(1)
    return builder.as_markup()

@router.callback_query(F.data.startswith("maintenance:"))
async def maintenance_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access Denied!", show_alert=True)
        return
    action = callback.data.split(":")[1]
    if action == "on":
        set_maintenance(True)
        await callback.message.edit_text(
            f"🔧 <b>MAINTENANCE MODE</b>\n"
            f"{DIVIDER}\n\n"
            f"Current Status: <b>🔴 ON (Bot is closed for users)</b>\n\n"
            f"✅ <b>Maintenance ON kar diya!</b>\n"
            f"Users ko ab maintenance message aayega.\n"
            f"Aap (admin) normally use kar sakte ho.\n\n"
            f"{DIVIDER}\n"
            f"Press button below to toggle:",
            reply_markup=_maintenance_keyboard(True),
            parse_mode="HTML"
        )
        await callback.answer("🔴 Maintenance ON!", show_alert=True)
    else:
        set_maintenance(False)
        await callback.message.edit_text(
            f"🔧 <b>MAINTENANCE MODE</b>\n"
            f"{DIVIDER}\n\n"
            f"Current Status: <b>🟢 OFF (Bot is open)</b>\n\n"
            f"✅ <b>Maintenance OFF kar diya!</b>\n"
            f"Bot ab sabke liye open hai.\n\n"
            f"{DIVIDER}\n"
            f"Press button below to toggle:",
            reply_markup=_maintenance_keyboard(False),
            parse_mode="HTML"
        )
        await callback.answer("🟢 Maintenance OFF!", show_alert=True)

# ─── SUPPORT SETTINGS ─────────────────────────────────────────────────────────
@router.message(F.text == "🆘 Support Settings")
async def support_settings(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    current = get_setting("support_username")
    await message.answer(
        f"🆘 <b>SUPPORT SETTINGS</b>\n{DIVIDER}\n\nCurrent: <b>{current}</b>\n\n"
        f"Enter new support username (e.g. @yourusername):",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.set_support)

@router.message(AdminStates.set_support)
async def set_support_h(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    set_setting("support_username", message.text.strip())
    await message.answer(
        f"✅ Support updated to <b>{message.text.strip()}</b>!",
        reply_markup=admin_menu(), parse_mode="HTML"
    )
    await state.clear()

# ─── MANAGE CHANNELS ──────────────────────────────────────────────────────────
@router.message(F.text == "📢 Manage Channels")
async def manage_channels(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    channels = get_all_channels()
    lines = (
        [f"<b>{ch['id']}</b>. {ch['name']} — {ch['link']}" for ch in channels]
        or ["No channels yet."]
    )
    await message.answer(
        f"📢 <b>MANAGE CHANNELS</b>\n{DIVIDER}\n\n" + "\n".join(lines) +
        "\n\nType <b>add</b> to add new, or send channel <b>ID</b> to remove:",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.remove_channel)

@router.message(AdminStates.remove_channel)
async def channels_action(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Done.", reply_markup=admin_menu())
        return
    if message.text.lower() == "add":
        await message.answer("Enter channel name:")
        await state.set_state(AdminStates.add_channel_name)
        return
    try:
        cid = int(message.text.strip())
        remove_channel(cid)
        await message.answer("✅ Channel removed!", reply_markup=admin_menu())
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Enter a valid channel ID or 'add'.")

@router.message(AdminStates.add_channel_name)
async def add_ch_name(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    await state.update_data(ch_name=message.text.strip())
    await message.answer("Enter channel link (e.g. https://t.me/mychannel):")
    await state.set_state(AdminStates.add_channel_link)

@router.message(AdminStates.add_channel_link)
async def add_ch_link(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    add_channel(data["ch_name"], message.text.strip())
    await message.answer(
        f"✅ Channel '<b>{data['ch_name']}</b>' added!",
        reply_markup=admin_menu(), parse_mode="HTML"
    )
    await state.clear()

# ─── EXPIRE ORDERS — Manual ───────────────────────────────────────────────────
@router.message(Command("expire"))
async def manual_expire(message: Message):
    if not is_admin(message.from_user.id):
        return
    expired = expire_orders()
    if not expired:
        await message.answer("✅ No expired orders to clean up.")
        return
    await message.answer(
        f"🗑 <b>Expired {len(expired)} order(s)</b>\n\n" +
        "\n".join([f"• <code>#{o['id']}</code> — {o['voucher_name']}" for o in expired]),
        parse_mode="HTML"
    )

# ─── ORDER SEARCH ─────────────────────────────────────────────────────────────
@router.message(Command("order"))
async def search_order(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer("Usage: <code>/order &lt;ORDER_ID&gt;</code>", parse_mode="HTML")
        return
    order_id = command.args.strip().upper()
    order = get_order(order_id)
    if not order:
        await message.answer(f"❌ Order <code>#{order_id}</code> not found.", parse_mode="HTML")
        return

    status_map = {
        "pending": "⏳ Pending", "paid": "💰 Payment Detected",
        "approved": "✅ Delivered", "rejected": "❌ Rejected",
        "cancelled": "🚫 Cancelled", "expired": "⌛ Expired",
    }
    unique_amount = order.get("unique_amount") or order["total_price"]
    codes = get_order_codes(order_id)

    text = (
        f"🔍 <b>ORDER LOOKUP</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order['id']}</code>\n"
        f"👤 User: <code>{order['user_id']}</code>\n"
        f"🎁 {order['voucher_name']} × {order['quantity']}\n"
        f"💵 Base: ₹{order['total_price']:.0f}\n"
        f"🎯 Unique: ₹{unique_amount:.2f}\n"
        f"📊 Status: {status_map.get(order['status'], order['status'])}\n"
        f"📅 Created: {str(order['created_at'])[:16]}"
    )
    if codes:
        codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
        text += f"\n\n📦 <b>Codes:</b>\n{codes_block}"

    markup = admin_approve_keyboard(order_id) if order["status"] in ("pending", "paid") else None
    await message.answer(text, parse_mode="HTML", reply_markup=markup)

# ─── MAIN MENU ────────────────────────────────────────────────────────────────
@router.message(F.text == "🏠 Main Menu")
async def go_main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Main Menu", reply_markup=main_menu())
