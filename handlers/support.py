"""
handlers/support.py — Complete in-bot support ticket system.

User Flow:
  🆘 Support → Select Category → Auto-FAQ shown
    → ✅ Solved? Close.
    → 📝 Still need help? Write message → Ticket created → Admin notified

Admin Flow:
  📩 Tickets → View all open tickets → Reply / Close
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from states.states import SupportStates, AdminStates
from utils.db_helpers import (
    create_ticket, get_ticket, get_user_tickets,
    get_open_tickets, close_ticket,
    add_ticket_reply, get_ticket_replies,
    get_user, get_open_ticket_count
)
from utils.messages import (
    support_menu_msg, faq_msg, FAQ_ANSWERS, CATEGORY_NAMES,
    ticket_created_msg, ticket_detail_msg,
    admin_new_ticket_msg, admin_ticket_detail_msg, DIVIDER
)
from keyboards.inline import (
    support_menu_keyboard, support_faq_keyboard,
    ticket_created_keyboard, my_tickets_keyboard,
    ticket_detail_keyboard, admin_ticket_keyboard,
    admin_tickets_list_keyboard
)
from keyboards.reply import cancel_keyboard, admin_menu, main_menu

router = Router()


# ─── USER: CATEGORY SELECTION ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("support_cat:"))
async def support_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    faq_text = FAQ_ANSWERS.get(category, FAQ_ANSWERS["other"])

    await callback.message.edit_text(
        faq_msg(category, faq_text),
        reply_markup=support_faq_keyboard(category),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── USER: PROBLEM SOLVED ─────────────────────────────────────────────────────

@router.callback_query(F.data == "support_solved")
async def support_solved(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Great! Glad it helped.</b>\n\n"
        f"If you need anything else, tap <b>🆘 Support</b> anytime.",
        parse_mode="HTML"
    )
    await callback.answer("Problem solved! 👍")


# ─── USER: STILL NEED HELP → WRITE TICKET ────────────────────────────────────

@router.callback_query(F.data.startswith("support_write:"))
async def support_write(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    await state.update_data(ticket_category=category)
    cat_name = CATEGORY_NAMES.get(category, category)

    await callback.message.edit_text(
        f"📝 <b>CREATE TICKET</b>\n{DIVIDER}\n\n"
        f"📂 <b>Category:</b> {cat_name}\n\n"
        f"Describe your issue in detail.\n"
        f"Include your <b>Order ID</b> if order-related.\n\n"
        f"<i>Type your message below:</i>",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "✍️ Write your message (or tap Cancel):",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(SupportStates.write_message)
    await callback.answer()


@router.message(SupportStates.write_message)
async def write_ticket_message(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=main_menu())
        return

    if not message.text or len(message.text.strip()) < 10:
        await message.answer(
            "⚠️ Message too short. Please describe your issue in more detail (min 10 chars):"
        )
        return

    data = await state.get_data()
    category = data.get("ticket_category", "other")
    msg_text = message.text.strip()

    # Subject = first 50 chars of message
    subject = msg_text[:50] + ("..." if len(msg_text) > 50 else "")

    ticket_id = create_ticket(
        user_id=message.from_user.id,
        category=category,
        subject=subject,
        message=msg_text
    )
    await state.clear()

    # Confirm to user
    await message.answer(
        ticket_created_msg(ticket_id, category),
        reply_markup=ticket_created_keyboard(ticket_id),
        parse_mode="HTML"
    )
    await message.answer("← Back to main menu", reply_markup=main_menu())

    # Notify admins
    user_info = get_user(message.from_user.id) or {}
    uname = user_info.get("username") or ""
    fname = user_info.get("full_name") or message.from_user.full_name or "User"

    notif = admin_new_ticket_msg(
        ticket_id=ticket_id,
        user_id=message.from_user.id,
        username=uname,
        full_name=fname,
        category=category,
        message=msg_text
    )
    from keyboards.inline import admin_ticket_keyboard as atk
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, notif,
                reply_markup=atk(ticket_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


# ─── USER: MY TICKETS ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_tickets")
async def my_tickets(callback: CallbackQuery):
    tickets = get_user_tickets(callback.from_user.id)
    if not tickets:
        await callback.message.edit_text(
            f"📋 <b>MY TICKETS</b>\n{DIVIDER}\n\n"
            f"You haven't raised any support tickets yet.\n\n"
            f"Tap a category to get help!",
            reply_markup=support_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    open_c = sum(1 for t in tickets if t["status"] == "open")
    closed_c = sum(1 for t in tickets if t["status"] == "closed")

    await callback.message.edit_text(
        f"📋 <b>MY TICKETS</b>\n{DIVIDER}\n\n"
        f"🟢 Open: <b>{open_c}</b>  •  🔴 Closed: <b>{closed_c}</b>\n\n"
        f"Tap a ticket to view details:",
        reply_markup=my_tickets_keyboard(tickets),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_ticket:"))
async def view_ticket(callback: CallbackQuery):
    ticket_id = callback.data.split(":")[1]
    ticket = get_ticket(ticket_id)

    if not ticket or int(ticket["user_id"]) != int(callback.from_user.id):
        await callback.answer("Ticket not found!", show_alert=True)
        return

    replies = get_ticket_replies(ticket_id)
    text = ticket_detail_msg(ticket, replies)

    await callback.message.edit_text(
        text,
        reply_markup=ticket_detail_keyboard(ticket_id, ticket["status"]),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── USER: ADD REPLY TO TICKET ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_reply:"))
async def user_reply_start(callback: CallbackQuery, state: FSMContext):
    ticket_id = callback.data.split(":")[1]
    ticket = get_ticket(ticket_id)
    if not ticket or ticket["status"] == "closed":
        await callback.answer("This ticket is closed.", show_alert=True)
        return

    await state.update_data(reply_ticket_id=ticket_id)
    await callback.message.answer(
        f"💬 Reply to <code>{ticket_id}</code>:\n(type your message below)",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(SupportStates.write_message)
    # Reuse write_message but mark it as a reply
    await state.update_data(ticket_category="__reply__")
    await callback.answer()


# ─── BACK TO SUPPORT MENU ─────────────────────────────────────────────────────

@router.callback_query(F.data == "support_back")
async def support_back(callback: CallbackQuery):
    await callback.message.edit_text(
        support_menu_msg(),
        reply_markup=support_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── ADMIN: VIEW ALL OPEN TICKETS ─────────────────────────────────────────────

@router.message(F.text == "📩 Tickets")
async def admin_tickets(message: Message):
    from config import ADMIN_IDS
    if message.from_user.id not in ADMIN_IDS:
        return

    tickets = get_open_tickets()
    if not tickets:
        await message.answer(
            f"📩 <b>OPEN TICKETS</b>\n{DIVIDER}\n\n"
            f"✅ No open support tickets right now!\n"
            f"All queries are resolved.",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"📩 <b>OPEN TICKETS</b>\n{DIVIDER}\n\n"
        f"🟢 <b>{len(tickets)}</b> ticket(s) need attention:\n\n"
        f"Tap to view details:",
        reply_markup=admin_tickets_list_keyboard(tickets),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_view_ticket:"))
async def admin_view_ticket(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied!", show_alert=True)
        return

    ticket_id = callback.data.split(":")[1]
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True)
        return

    # Get user info
    user_info = get_user(ticket["user_id"]) or {}
    ticket_with_user = dict(ticket)
    ticket_with_user["username"] = user_info.get("username", "N/A")
    ticket_with_user["full_name"] = user_info.get("full_name", str(ticket["user_id"]))

    replies = get_ticket_replies(ticket_id)
    text = admin_ticket_detail_msg(ticket_with_user, replies)

    await callback.message.edit_text(
        text,
        reply_markup=admin_ticket_keyboard(ticket_id) if ticket["status"] == "open" else None,
        parse_mode="HTML"
    )
    await callback.answer()


# ─── ADMIN: REPLY TO TICKET ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied!", show_alert=True)
        return

    ticket_id = callback.data.split(":")[1]
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True)
        return

    await state.update_data(admin_reply_ticket_id=ticket_id, admin_reply_user_id=ticket["user_id"])
    await callback.message.answer(
        f"💬 <b>Replying to {ticket_id}</b>\n\nType your reply (or Cancel):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.reply_ticket)
    await callback.answer()


@router.message(AdminStates.reply_ticket)
async def admin_reply_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return

    data = await state.get_data()
    ticket_id = data["admin_reply_ticket_id"]
    user_id = data["admin_reply_user_id"]

    reply_text = message.text.strip() if message.text else ""
    if not reply_text:
        await message.answer("⚠️ Enter a reply message:")
        return

    add_ticket_reply(ticket_id, reply_text, from_admin=True)

    # Notify user
    try:
        await bot.send_message(
            user_id,
            f"📩 <b>SUPPORT REPLY</b>\n{DIVIDER}\n\n"
            f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
            f"🔧 <b>Support Team:</b>\n{reply_text}\n\n{DIVIDER}\n"
            f"<i>Tap 📋 My Tickets to view full conversation.</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ <b>Reply sent</b> to ticket <code>{ticket_id}</code>!",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await state.clear()


# ─── ADMIN: CLOSE TICKET ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("close_ticket:"))
async def close_ticket_cb(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied!", show_alert=True)
        return

    ticket_id = callback.data.split(":")[1]
    ticket = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True)
        return

    close_ticket(ticket_id)

    # Notify user
    try:
        await bot.send_message(
            ticket["user_id"],
            f"✅ <b>TICKET RESOLVED</b>\n{DIVIDER}\n\n"
            f"🎫 Ticket <code>{ticket_id}</code> has been marked as resolved.\n\n"
            f"If your issue persists, tap <b>🆘 Support</b> to raise a new ticket.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            (callback.message.text or "") + f"\n\n✅ <b>TICKET CLOSED</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("✅ Ticket closed & user notified!", show_alert=True)
