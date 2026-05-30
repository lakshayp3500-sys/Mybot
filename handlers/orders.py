"""
handlers/orders.py — "My Orders" section with full details including delivered codes.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from utils.db_helpers import get_user_orders, get_order, get_order_codes
from utils.messages import order_detail_msg, DIVIDER
from keyboards.reply import main_menu
from keyboards.inline import orders_keyboard, order_detail_keyboard

router = Router()


@router.message(F.text == "📦 My Orders")
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(
            f"📦 <b>MY ORDERS</b>\n"
            f"{DIVIDER}\n\n"
            f"You haven't placed any orders yet.\n\n"
            f"Tap <b>🛍 Buy Vouchers</b> to get started!",
            parse_mode="HTML"
        )
        return

    status_summary = {
        "approved": sum(1 for o in orders if o["status"] == "approved"),
        "pending": sum(1 for o in orders if o["status"] == "pending"),
    }

    await message.answer(
        f"📦 <b>MY ORDERS</b>\n"
        f"{DIVIDER}\n\n"
        f"📊 Total: {len(orders)}  •  "
        f"✅ Delivered: {status_summary['approved']}  •  "
        f"⏳ Pending: {status_summary['pending']}\n\n"
        f"Tap any order to view details:",
        reply_markup=orders_keyboard(orders),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("view_order:"))
async def view_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    order = get_order(order_id)

    # Safe int comparison — guards against type mismatch between DB and Telegram
    if not order or int(order["user_id"]) != int(callback.from_user.id):
        await callback.answer("Order not found!", show_alert=True)
        return

    # Fetch codes for approved or paid orders
    codes = get_order_codes(order_id) if order["status"] in ("approved", "paid") else []

    text = order_detail_msg(order, codes)

    await callback.message.edit_text(
        text,
        reply_markup=order_detail_keyboard(order_id, order["status"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_orders")
async def back_orders(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    if not orders:
        await callback.message.edit_text(
            f"📦 <b>MY ORDERS</b>\n\nNo orders found.",
            parse_mode="HTML"
        )
        return

    status_summary = {
        "approved": sum(1 for o in orders if o["status"] == "approved"),
        "pending": sum(1 for o in orders if o["status"] == "pending"),
    }

    await callback.message.edit_text(
        f"📦 <b>MY ORDERS</b>\n"
        f"{DIVIDER}\n\n"
        f"📊 Total: {len(orders)}  •  "
        f"✅ Delivered: {status_summary['approved']}  •  "
        f"⏳ Pending: {status_summary['pending']}\n\n"
        f"Tap any order to view:",
        reply_markup=orders_keyboard(orders),
        parse_mode="HTML"
    )
    await callback.answer()
