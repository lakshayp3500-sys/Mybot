"""
handlers/buy.py — User purchase flow (UPI semi-auto payment).
"""

import asyncio
import io

import asyncio as _asyncio
from aiogram import Router, F, Bot
from aiogram.enums import ChatAction
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from states.states import BuyStates
from utils.db_helpers import (
    get_all_vouchers_with_stock, get_voucher,
    get_order, cancel_order, deliver_codes,
    get_user_active_order, get_order_codes,
    get_voucher_disclaimer
)
from utils.messages import success_delivery_msg, payment_waiting_msg, disclaimer_msg, DIVIDER
from order_manager import create_order, get_order_by_id
from payment import generate_unique_amount, generate_upi_link, generate_raw_upi_link
from qr_generator import generate_qr_with_label
from keyboards.reply import main_menu, cancel_keyboard
from keyboards.inline import vouchers_keyboard, quantity_keyboard, payment_keyboard, disclaimer_keyboard
from config import ADMIN_IDS, UPI_ID, SHOP_NAME, ORDER_EXPIRY_MINUTES, API_BASE_URL

router = Router()


@router.message(F.text == "🛍 Buy Vouchers")
async def buy_vouchers(message: Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await _asyncio.sleep(0.4)
    await state.clear()

    active = get_user_active_order(message.from_user.id)
    if active:
        unique_amount = active.get("unique_amount", active["total_price"])
        await message.answer(
            f"⚠️ <b>ACTIVE ORDER EXISTS</b>\n"
            f"{DIVIDER}\n\n"
            f"🆔 Order: <code>#{active['id']}</code>\n"
            f"🎁 {active['voucher_name']} × {active['quantity']}\n"
            f"💳 Pay Exactly: <b>₹{unique_amount:.2f}</b>\n\n"
            f"⏳ Please wait for payment or let it expire.\n"
            f"Check <b>📦 My Orders</b> for details.",
            parse_mode="HTML"
        )
        return

    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer(
            "⚠️ <b>No Products Available</b>\n\n"
            "We're restocking soon. Check back later!",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"🛍 <b>AVAILABLE PRODUCTS</b>\n"
        f"{DIVIDER}\n\n"
        f"Select a product to purchase:",
        reply_markup=vouchers_keyboard(vouchers),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_voucher)


@router.callback_query(F.data.startswith("buy_voucher:"))
async def select_voucher(callback: CallbackQuery, state: FSMContext):
    voucher_id = int(callback.data.split(":")[1])
    voucher = get_voucher(voucher_id)

    if not voucher:
        await callback.answer("❌ Product not found!", show_alert=True)
        return
    if voucher["stock"] == 0:
        await callback.answer("❌ Out of Stock!", show_alert=True)
        return

    await state.update_data(
        voucher_id=voucher_id,
        voucher_name=voucher["name"],
        price=voucher["price"]
    )
    await callback.message.edit_text(
        f"🎁 <b>{voucher['name']}</b>\n"
        f"{DIVIDER}\n\n"
        f"💰 Price: <b>₹{voucher['price']:.0f}</b> per code\n"
        f"📦 In Stock: {voucher['stock']} available\n\n"
        f"How many codes do you want?",
        reply_markup=quantity_keyboard(voucher_id),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_quantity)
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    voucher_id = int(parts[1])
    qty_str = parts[2]
    data = await state.get_data()

    voucher = get_voucher(voucher_id)
    if not voucher or voucher["stock"] == 0:
        await callback.answer("❌ Out of Stock!", show_alert=True)
        return

    price = data.get("price", voucher["price"])
    voucher_name = data.get("voucher_name", voucher["name"])
    await state.update_data(voucher_id=voucher_id, voucher_name=voucher_name, price=price)

    if qty_str == "custom":
        await callback.message.edit_text(
            f"✏️ <b>Custom Quantity</b>\n"
            f"{DIVIDER}\n\n"
            f"Enter how many codes you want:\n"
            f"(Max available: {voucher['stock']})",
            parse_mode="HTML"
        )
        await state.set_state(BuyStates.custom_quantity)
        await callback.answer()
        return

    quantity = int(qty_str)
    if quantity > voucher["stock"]:
        await callback.answer(f"❌ Only {voucher['stock']} available!", show_alert=True)
        return

    total = quantity * price
    await state.update_data(quantity=quantity, total=total)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _check_disclaimer_and_proceed(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        state=state,
        user_id=callback.from_user.id,
        voucher_id=voucher_id,
        voucher_name=voucher_name,
        quantity=quantity,
        price=price,
        total=total
    )
    await callback.answer()


@router.message(BuyStates.custom_quantity)
async def handle_custom_quantity(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=main_menu())
        return

    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("⚠️ Please enter a valid number (e.g. 2):")
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    voucher = get_voucher(data["voucher_id"])

    if not voucher:
        await message.answer("❌ Product not found!", reply_markup=main_menu())
        return
    if quantity > voucher["stock"]:
        await message.answer(f"❌ Only {voucher['stock']} codes available. Enter a smaller number:")
        return

    price = data.get("price", voucher["price"])
    voucher_name = data.get("voucher_name", voucher["name"])
    total = quantity * price
    await state.update_data(quantity=quantity, total=total)

    await _check_disclaimer_and_proceed(
        bot=message.bot,
        chat_id=message.from_user.id,
        state=state,
        user_id=message.from_user.id,
        voucher_id=data["voucher_id"],
        voucher_name=voucher_name,
        quantity=quantity,
        price=price,
        total=total
    )


async def _check_disclaimer_and_proceed(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    user_id: int,
    voucher_id: int,
    voucher_name: str,
    quantity: int,
    price: float,
    total: float
):
    """Check if voucher has a disclaimer. If yes, show it first. If no, go straight to QR."""
    disclaimer = get_voucher_disclaimer(voucher_id)
    if disclaimer:
        await state.update_data(
            pending_voucher_id=voucher_id,
            pending_voucher_name=voucher_name,
            pending_quantity=quantity,
            pending_price=price,
            pending_total=total,
            pending_user_id=user_id
        )
        await bot.send_message(
            chat_id,
            disclaimer_msg(voucher_name, disclaimer),
            parse_mode="HTML",
            reply_markup=disclaimer_keyboard()
        )
        await state.set_state(BuyStates.disclaimer_confirm)
    else:
        await _send_payment_qr(
            bot=bot,
            chat_id=chat_id,
            state=state,
            user_id=user_id,
            voucher_id=voucher_id,
            voucher_name=voucher_name,
            quantity=quantity,
            price=price,
            total=total
        )


@router.callback_query(F.data == "disclaimer_accept")
async def disclaimer_accepted(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_payment_qr(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        state=state,
        user_id=callback.from_user.id,
        voucher_id=data["pending_voucher_id"],
        voucher_name=data["pending_voucher_name"],
        quantity=data["pending_quantity"],
        price=data["pending_price"],
        total=data["pending_total"]
    )
    await callback.answer()


@router.callback_query(F.data == "disclaimer_cancel")
async def disclaimer_cancelled(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "❌ <b>Cancelled.</b>\n\nReturning to main menu.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await callback.answer("Cancelled.")


async def _send_payment_qr(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    user_id: int,
    voucher_id: int,
    voucher_name: str,
    quantity: int,
    price: float,
    total: float
):
    unique_amount = generate_unique_amount(total)

    order_id = create_order(
        user_id=user_id,
        voucher_id=voucher_id,
        quantity=quantity,
        total_price=total,
        unique_amount=unique_amount,
        expiry_minutes=ORDER_EXPIRY_MINUTES
    )
    await state.update_data(order_id=order_id)

    raw_upi_link = generate_raw_upi_link(unique_amount, UPI_ID, SHOP_NAME)
    https_upi_link = generate_upi_link(unique_amount, UPI_ID, SHOP_NAME, API_BASE_URL)

    qr_buffer: io.BytesIO = generate_qr_with_label(raw_upi_link, unique_amount, SHOP_NAME)

    caption = payment_waiting_msg(
        order_id=order_id,
        voucher_name=voucher_name,
        quantity=quantity,
        base_total=total,
        unique_amount=unique_amount,
        expiry_minutes=ORDER_EXPIRY_MINUTES,
        shop_name=SHOP_NAME
    )

    await bot.send_photo(
        chat_id=chat_id,
        photo=BufferedInputFile(qr_buffer.read(), filename="payment_qr.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=payment_keyboard(order_id, https_upi_link)
    )

    await state.set_state(BuyStates.waiting_payment)
    asyncio.create_task(_expiry_notify(bot, user_id, order_id))


async def _expiry_notify(bot: Bot, user_id: int, order_id: str):
    await asyncio.sleep(ORDER_EXPIRY_MINUTES * 60)
    order = get_order_by_id(order_id)
    if not order or order["status"] != "pending":
        return
    try:
        await bot.send_message(
            user_id,
            f"⏰ <b>ORDER EXPIRED</b>\n"
            f"{DIVIDER}\n\n"
            f"🆔 Order <code>#{order_id}</code> expired after {ORDER_EXPIRY_MINUTES} minutes.\n\n"
            f"No payment was detected. Tap <b>🛍 Buy Vouchers</b> to try again.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("i_paid:"))
async def i_paid_callback(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]
    order = get_order(order_id)

    if not order:
        await callback.answer("❌ Order not found!", show_alert=True)
        return

    status = order["status"]

    if status == "approved":
        codes = get_order_codes(order_id)
        support = "@admin"
        try:
            from utils.db_helpers import get_setting as _gs
            support = _gs("support_username") or "@admin"
        except Exception:
            pass

        unique_amount = order.get("unique_amount") or order["total_price"]
        await callback.message.answer(
            success_delivery_msg(
                voucher_name=order["voucher_name"],
                codes=codes,
                amount=unique_amount,
                order_id=order_id,
                support=support
            ),
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        await state.clear()
        await callback.answer()
        return

    if status == "expired":
        await callback.answer("❌ This order has expired. Please place a new order.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            f"⏰ <b>Order Expired.</b>\n\nTap <b>🛍 Buy Vouchers</b> to place a new order.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        await state.clear()
        return

    if status == "cancelled":
        await callback.answer("❌ This order was cancelled.", show_alert=True)
        return

    if status == "rejected":
        await callback.answer("❌ This order was rejected. Contact support.", show_alert=True)
        return

    unique_amount = order.get("unique_amount") or order["total_price"]
    await callback.answer(
        f"⏳ Payment not detected yet!\n\nPay EXACTLY ₹{unique_amount:.2f}\nThen tap this button again.",
        show_alert=True
    )


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_cb(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]
    cancel_order(order_id)
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        f"❌ <b>Order Cancelled</b>\n\n"
        f"Order <code>#{order_id}</code> has been cancelled.\n"
        f"Tap <b>🛍 Buy Vouchers</b> to start over.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await callback.answer("Order cancelled.")


@router.callback_query(F.data == "back_vouchers")
async def back_to_vouchers(callback: CallbackQuery, state: FSMContext):
    vouchers = get_all_vouchers_with_stock()
    await callback.message.edit_text(
        f"🛍 <b>AVAILABLE PRODUCTS</b>\n"
        f"{DIVIDER}\n\n"
        f"Select a product to purchase:",
        reply_markup=vouchers_keyboard(vouchers),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_voucher)
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()
