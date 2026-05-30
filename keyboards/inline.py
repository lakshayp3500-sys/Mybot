"""keyboards/inline.py — Inline keyboard layouts."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def vouchers_keyboard(vouchers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vouchers:
        stock = v["stock"]
        label = (
            f"✅ {v['name']}  •  ₹{v['price']:.0f}  •  {stock} in stock"
            if stock > 0
            else f"❌ {v['name']}  •  OUT OF STOCK"
        )
        builder.button(text=label, callback_data=f"buy_voucher:{v['id']}")
    builder.button(text="🔙 Back", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def quantity_keyboard(voucher_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 Code", callback_data=f"qty:{voucher_id}:1")
    builder.button(text="5 Codes", callback_data=f"qty:{voucher_id}:5")
    builder.button(text="10 Codes", callback_data=f"qty:{voucher_id}:10")
    builder.button(text="✏️ Custom Amount", callback_data=f"qty:{voucher_id}:custom")
    builder.button(text="🔙 Back to Products", callback_data="back_vouchers")
    builder.adjust(3, 1, 1)
    return builder.as_markup()


def disclaimer_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accept & Continue", callback_data="disclaimer_accept")
    builder.button(text="❌ Cancel", callback_data="disclaimer_cancel")
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(order_id: str, upi_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📲 Open UPI App to Pay", url=upi_link)
    builder.button(text="✅ I Have Paid", callback_data=f"i_paid:{order_id}")
    builder.button(text="❌ Cancel Order", callback_data=f"cancel_order:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_approve_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve & Deliver", callback_data=f"approve:{order_id}")
    builder.button(text="❌ Reject", callback_data=f"reject:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def orders_keyboard(orders: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_emoji = {
        "pending":   "⏳",
        "approved":  "✅",
        "rejected":  "❌",
        "cancelled": "🚫",
        "expired":   "⌛",
        "paid":      "💰",
    }
    for o in orders:
        emoji = status_emoji.get(o["status"], "❓")
        builder.button(
            text=f"{emoji} {o['voucher_name']}  •  #{o['id'][:8]}",
            callback_data=f"view_order:{o['id']}"
        )
    builder.button(text="🔙 Back", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def order_detail_keyboard(order_id: str, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "pending":
        builder.button(text="✅ I Have Paid", callback_data=f"i_paid:{order_id}")
        builder.button(text="❌ Cancel Order", callback_data=f"cancel_order:{order_id}")
    builder.button(text="🔙 Back to Orders", callback_data="back_orders")
    builder.adjust(1)
    return builder.as_markup()


# ── SUPPORT TICKET KEYBOARDS ──────────────────────────────────────────────────

def support_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Payment Issue",        callback_data="support_cat:payment")
    builder.button(text="🎫 Code Not Working",     callback_data="support_cat:code")
    builder.button(text="📦 Order Problem",        callback_data="support_cat:order")
    builder.button(text="❓ Other Query",           callback_data="support_cat:other")
    builder.button(text="📋 My Tickets",           callback_data="my_tickets")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def support_faq_keyboard(category: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Problem Solved!", callback_data="support_solved")
    builder.button(text="📝 Still Need Help", callback_data=f"support_write:{category}")
    builder.adjust(1)
    return builder.as_markup()


def ticket_created_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 View My Tickets", callback_data="my_tickets")
    builder.adjust(1)
    return builder.as_markup()


def my_tickets_keyboard(tickets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_icon = {"open": "🟢", "closed": "🔴"}
    for t in tickets:
        icon = status_icon.get(t["status"], "⚪")
        builder.button(
            text=f"{icon} #{t['id'][:10]}  •  {t['subject'][:20]}",
            callback_data=f"view_ticket:{t['id']}"
        )
    builder.button(text="🔙 Back", callback_data="support_back")
    builder.adjust(1)
    return builder.as_markup()


def ticket_detail_keyboard(ticket_id: str, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "open":
        builder.button(text="💬 Add Reply", callback_data=f"user_reply:{ticket_id}")
    builder.button(text="🔙 My Tickets", callback_data="my_tickets")
    builder.adjust(1)
    return builder.as_markup()


def admin_ticket_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Reply to User",  callback_data=f"admin_reply:{ticket_id}")
    builder.button(text="✅ Close Ticket",   callback_data=f"close_ticket:{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()


def admin_tickets_list_keyboard(tickets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    cat_icon = {"payment": "💸", "code": "🎫", "order": "📦", "other": "❓"}
    for t in tickets:
        icon = cat_icon.get(t["category"], "📩")
        builder.button(
            text=f"{icon} #{t['id'][:10]}  •  {str(t['created_at'])[:10]}",
            callback_data=f"admin_view_ticket:{t['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()
