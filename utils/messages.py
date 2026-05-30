"""utils/messages.py — Premium message formatters."""

from datetime import datetime

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

FAQ_ANSWERS = {
    "payment": (
        "💸 <b>Payment Issue — Quick Fixes</b>\n\n"
        "1️⃣ Check <b>📦 My Orders</b> → tap your order\n"
        "   → If status is <b>✅ Delivered</b>, codes are shown there\n\n"
        "2️⃣ If status is <b>💰 Payment Detected</b>, wait 2-3 minutes\n"
        "   → Codes are delivered automatically\n\n"
        "3️⃣ Payment not detected? Make sure you paid the\n"
        "   <b>exact decimal amount</b> shown (e.g. ₹149.37)\n\n"
        "4️⃣ Order expired? Place a new order — expired orders\n"
        "   are not charged automatically"
    ),
    "code": (
        "🎫 <b>Code Not Working — Quick Fixes</b>\n\n"
        "1️⃣ Copy the code exactly — tap it to copy\n"
        "   (don't type manually, avoid extra spaces)\n\n"
        "2️⃣ Try in a fresh browser / incognito / new tab\n\n"
        "3️⃣ Check if the code is region-specific\n"
        "   (some codes only work in India)\n\n"
        "4️⃣ Already used codes cannot be replaced\n"
        "   (please test before using elsewhere)"
    ),
    "order": (
        "📦 <b>Order Problem — Quick Fixes</b>\n\n"
        "1️⃣ View all your orders: tap <b>📦 My Orders</b>\n\n"
        "2️⃣ Each order shows full status + your codes\n\n"
        "3️⃣ Order stuck in pending? Either:\n"
        "   • Payment not detected yet (pay exact amount)\n"
        "   • Order may have expired (check expiry)\n\n"
        "4️⃣ Rejected order? Contact support with Order ID"
    ),
    "other": (
        "❓ <b>Need Help?</b>\n\n"
        "Please describe your issue clearly.\n"
        "Include your <b>Order ID</b> if it's order-related.\n\n"
        "Our team will respond as soon as possible!"
    ),
}

CATEGORY_NAMES = {
    "payment": "💸 Payment Issue",
    "code":    "🎫 Code Not Working",
    "order":   "📦 Order Problem",
    "other":   "❓ Other Query",
}


def now_str() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


def success_delivery_msg(voucher_name, codes, amount, order_id, support="@admin"):
    codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
    return (
        f"{DIVIDER}\n  ✅  PAYMENT SUCCESSFUL\n{DIVIDER}\n\n"
        f"🎁 <b>Product:</b> {voucher_name}\n\n"
        f"{codes_block}\n\n"
        f"💰 <b>Amount Paid:</b> ₹{amount:.2f}\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"⏰ <b>Time:</b> {now_str()}\n\n"
        f"{DIVIDER}\n✨ Thank you for shopping with us!\n"
        f"📩 Issues? Contact {support}\n{DIVIDER}"
    )


def admin_sale_receipt(buyer_username, buyer_id, voucher_name, quantity, base_amount, unique_amount, order_id, codes):
    codes_block = "\n".join([f"   🔑 <code>{c}</code>" for c in codes])
    return (
        f"🧾 <b>SALE RECEIPT</b>\n{DIVIDER}\n\n"
        f"👤 <b>Buyer:</b> @{buyer_username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{buyer_id}</code>\n\n"
        f"🎁 <b>Product:</b> {voucher_name} × {quantity}\n"
        f"💵 <b>Base Amount:</b> ₹{base_amount:.0f}\n"
        f"🎯 <b>Paid Amount:</b> ₹{unique_amount:.2f}\n"
        f"💳 <b>Method:</b> UPI Auto-Verified\n\n"
        f"📦 <b>Delivered Codes:</b>\n{codes_block}\n\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"✅ <b>Delivery:</b> Auto-Delivered\n"
        f"⏰ <b>Time:</b> {now_str()}\n{DIVIDER}"
    )


def admin_manual_sale_receipt(buyer_username, buyer_id, voucher_name, quantity, base_amount, order_id, codes):
    codes_block = "\n".join([f"   🔑 <code>{c}</code>" for c in codes])
    return (
        f"🧾 <b>SALE RECEIPT</b>\n{DIVIDER}\n\n"
        f"👤 <b>Buyer:</b> @{buyer_username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{buyer_id}</code>\n\n"
        f"🎁 <b>Product:</b> {voucher_name} × {quantity}\n"
        f"💵 <b>Amount:</b> ₹{base_amount:.0f}\n"
        f"💳 <b>Method:</b> Manual Approval\n\n"
        f"📦 <b>Delivered Codes:</b>\n{codes_block}\n\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"✅ <b>Delivery:</b> Manually Approved\n"
        f"⏰ <b>Time:</b> {now_str()}\n{DIVIDER}"
    )


def new_user_alert(username, user_id, full_name):
    return (
        f"🆕 <b>NEW USER JOINED BOT</b>\n{DIVIDER}\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"🔗 <b>Username:</b> @{username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📅 <b>Joined:</b> {now_str()}\n{DIVIDER}"
    )


def welcome_msg(first_name, bot_name="Proxy Shop", support="@admin"):
    return (
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"{DIVIDER}\n  🏪  {bot_name.upper()}\n{DIVIDER}\n\n"
        f"🎫 Premium digital vouchers & codes\n"
        f"⚡ Instant auto-delivery after payment\n"
        f"🔒 Safe & trusted UPI payments\n\n"
        f"<b>Quick Actions:</b>\n"
        f"🛍 <b>Buy Vouchers</b> — Browse products\n"
        f"📦 <b>My Orders</b> — View your orders\n"
        f"🆘 <b>Support</b> — Get help\n\n"
        f"<i>Tap a button below to get started!</i>"
    )


def payment_waiting_msg(order_id, voucher_name, quantity, base_total, unique_amount, expiry_minutes, shop_name):
    return (
        f"{DIVIDER}\n  🧾  ORDER CREATED\n{DIVIDER}\n\n"
        f"🆔 Order ID: <code>#{order_id}</code>\n"
        f"🎁 Product: <b>{voucher_name} × {quantity}</b>\n"
        f"💰 Base Price: ₹{base_total:.0f}\n\n"
        f"{DIVIDER}\n  💳  PAY EXACTLY THIS AMOUNT\n{DIVIDER}\n"
        f"     <b>₹{unique_amount:.2f}</b>\n{DIVIDER}\n\n"
        f"📲 Scan QR above with any UPI app\n"
        f"   PhonePe  •  GPay  •  Paytm  •  BHIM\n\n"
        f"⚠️ Pay the <b>EXACT decimal amount</b> shown.\n"
        f"   It auto-identifies your payment.\n\n"
        f"⏳ Order expires in <b>{expiry_minutes} minutes</b>\n"
        f"✅ Codes are delivered automatically!\n\n"
        f"<i>🏪 {shop_name}</i>"
    )


def order_detail_msg(order, codes):
    status_map = {
        "pending":   "⏳ Awaiting Payment",
        "paid":      "💰 Payment Detected",
        "approved":  "✅ Delivered",
        "rejected":  "❌ Rejected",
        "cancelled": "🚫 Cancelled",
        "expired":   "⌛ Expired",
    }
    unique_amount = order.get("unique_amount") or order["total_price"]
    text = (
        f"{DIVIDER}\n  📋  ORDER DETAILS\n{DIVIDER}\n\n"
        f"🎁 <b>Product:</b> {order['voucher_name']}\n"
        f"🔢 <b>Quantity:</b> {order['quantity']}\n"
        f"💵 <b>Paid:</b> ₹{unique_amount:.2f}\n"
        f"🆔 <b>Order ID:</b> <code>#{order['id']}</code>\n"
        f"📅 <b>Date:</b> {str(order['created_at'])[:16]}\n"
        f"📌 <b>Status:</b> {status_map.get(order['status'], order['status'])}\n"
    )
    if codes:
        codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
        text += f"\n{DIVIDER}\n🎁 <b>Your Codes:</b>\n{codes_block}\n{DIVIDER}"
    elif order["status"] in ("approved", "paid"):
        text += f"\n\n<i>Codes were delivered. Contact support if missing.</i>"
    return text


def disclaimer_msg(voucher_name, disclaimer_text):
    return (
        f"📋 <b>DISCLAIMER</b>\n{DIVIDER}\n\n"
        f"🎁 <b>Product:</b> {voucher_name}\n\n"
        f"{disclaimer_text}\n\n{DIVIDER}\n"
        f"<i>Tap <b>✅ Accept &amp; Continue</b> to proceed\nor <b>❌ Cancel</b> to go back.</i>"
    )


# ── TICKET MESSAGES ───────────────────────────────────────────────────────────

def support_menu_msg() -> str:
    return (
        f"🆘 <b>SUPPORT CENTER</b>\n{DIVIDER}\n\n"
        f"Select your issue type and we'll try to solve it instantly.\n"
        f"If the quick fix doesn't help, you can raise a ticket.\n\n"
        f"<b>What's your issue?</b>"
    )


def faq_msg(category: str, faq_text: str) -> str:
    from utils.messages import CATEGORY_NAMES
    cat_name = CATEGORY_NAMES.get(category, category)
    return (
        f"{cat_name}\n{DIVIDER}\n\n"
        f"{faq_text}\n\n{DIVIDER}\n"
        f"<i>Did this solve your problem?</i>"
    )


def ticket_created_msg(ticket_id: str, category: str) -> str:
    from utils.messages import CATEGORY_NAMES
    cat_name = CATEGORY_NAMES.get(category, category)
    return (
        f"✅ <b>TICKET CREATED</b>\n{DIVIDER}\n\n"
        f"🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>\n"
        f"📂 <b>Category:</b> {cat_name}\n"
        f"⏰ <b>Created:</b> {now_str()}\n\n"
        f"Our team will reply soon.\n"
        f"You'll get a notification when we respond.\n\n"
        f"📋 Track via <b>My Tickets</b>"
    )


def ticket_detail_msg(ticket: dict, replies: list) -> str:
    from utils.messages import CATEGORY_NAMES
    cat_name = CATEGORY_NAMES.get(ticket["category"], ticket["category"])
    status_icon = "🟢 Open" if ticket["status"] == "open" else "🔴 Closed"
    text = (
        f"🎫 <b>TICKET {ticket['id']}</b>\n{DIVIDER}\n\n"
        f"📂 <b>Category:</b> {cat_name}\n"
        f"📌 <b>Status:</b> {status_icon}\n"
        f"📅 <b>Created:</b> {str(ticket['created_at'])[:16]}\n\n"
        f"{DIVIDER}\n"
        f"<b>Your Message:</b>\n{ticket['message']}\n"
    )
    if replies:
        text += f"\n{DIVIDER}\n<b>Conversation:</b>\n"
        for r in replies:
            sender = "🔧 <b>Support</b>" if r["from_admin"] else "👤 <b>You</b>"
            text += f"\n{sender} — {str(r['created_at'])[:16]}\n{r['message']}\n"
    return text


def admin_new_ticket_msg(ticket_id, user_id, username, full_name, category, message) -> str:
    from utils.messages import CATEGORY_NAMES
    cat_name = CATEGORY_NAMES.get(category, category)
    return (
        f"📩 <b>NEW SUPPORT TICKET</b>\n{DIVIDER}\n\n"
        f"🎫 <b>Ticket:</b> <code>{ticket_id}</code>\n"
        f"📂 <b>Category:</b> {cat_name}\n"
        f"👤 <b>User:</b> {full_name} (@{username or 'N/A'})\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"⏰ <b>Time:</b> {now_str()}\n\n"
        f"{DIVIDER}\n"
        f"<b>Message:</b>\n{message}\n{DIVIDER}"
    )


def admin_ticket_detail_msg(ticket: dict, replies: list) -> str:
    from utils.messages import CATEGORY_NAMES
    cat_name = CATEGORY_NAMES.get(ticket["category"], ticket["category"])
    status_icon = "🟢 Open" if ticket["status"] == "open" else "🔴 Closed"
    uname = ticket.get("username") or "N/A"
    fname = ticket.get("full_name") or str(ticket["user_id"])
    text = (
        f"🎫 <b>TICKET {ticket['id']}</b>\n{DIVIDER}\n\n"
        f"👤 {fname} (@{uname})\n"
        f"🆔 <code>{ticket['user_id']}</code>\n"
        f"📂 {cat_name}  •  {status_icon}\n"
        f"📅 {str(ticket['created_at'])[:16]}\n\n"
        f"{DIVIDER}\n<b>User Message:</b>\n{ticket['message']}\n"
    )
    if replies:
        text += f"\n{DIVIDER}\n<b>Conversation:</b>\n"
        for r in replies:
            sender = "🔧 Support" if r["from_admin"] else "👤 User"
            text += f"\n<b>{sender}</b> — {str(r['created_at'])[:16]}\n{r['message']}\n"
    return text
