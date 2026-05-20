"""
utils/messages.py — Premium message formatters for consistent UI across the bot.
All messages use HTML parse mode.
"""

from datetime import datetime


DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


def now_str() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


def success_delivery_msg(
    voucher_name: str,
    codes: list[str],
    amount: float,
    order_id: str,
    support: str = "@admin"
) -> str:
    codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
    return (
        f"{DIVIDER}\n"
        f"  ✅  PAYMENT SUCCESSFUL\n"
        f"{DIVIDER}\n\n"
        f"🎁 <b>Product:</b> {voucher_name}\n\n"
        f"{codes_block}\n\n"
        f"💰 <b>Amount Paid:</b> ₹{amount:.2f}\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"⏰ <b>Time:</b> {now_str()}\n\n"
        f"{DIVIDER}\n"
        f"✨ Thank you for shopping with us!\n"
        f"📩 Issues? Contact {support}\n"
        f"{DIVIDER}"
    )


def admin_sale_receipt(
    buyer_username: str,
    buyer_id: int,
    voucher_name: str,
    quantity: int,
    base_amount: float,
    unique_amount: float,
    order_id: str,
    codes: list[str]
) -> str:
    codes_block = "\n".join([f"   🔑 <code>{c}</code>" for c in codes])
    return (
        f"🧾 <b>SALE RECEIPT</b>\n"
        f"{DIVIDER}\n\n"
        f"👤 <b>Buyer:</b> @{buyer_username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{buyer_id}</code>\n\n"
        f"🎁 <b>Product:</b> {voucher_name} × {quantity}\n"
        f"💵 <b>Base Amount:</b> ₹{base_amount:.0f}\n"
        f"🎯 <b>Paid Amount:</b> ₹{unique_amount:.2f}\n"
        f"💳 <b>Method:</b> UPI Auto-Verified\n\n"
        f"📦 <b>Delivered Codes:</b>\n{codes_block}\n\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"✅ <b>Delivery:</b> Auto-Delivered\n"
        f"⏰ <b>Time:</b> {now_str()}\n"
        f"{DIVIDER}"
    )


def admin_manual_sale_receipt(
    buyer_username: str,
    buyer_id: int,
    voucher_name: str,
    quantity: int,
    base_amount: float,
    order_id: str,
    codes: list[str]
) -> str:
    codes_block = "\n".join([f"   🔑 <code>{c}</code>" for c in codes])
    return (
        f"🧾 <b>SALE RECEIPT</b>\n"
        f"{DIVIDER}\n\n"
        f"👤 <b>Buyer:</b> @{buyer_username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{buyer_id}</code>\n\n"
        f"🎁 <b>Product:</b> {voucher_name} × {quantity}\n"
        f"💵 <b>Amount:</b> ₹{base_amount:.0f}\n"
        f"💳 <b>Method:</b> Manual Approval\n\n"
        f"📦 <b>Delivered Codes:</b>\n{codes_block}\n\n"
        f"🆔 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"✅ <b>Delivery:</b> Manually Approved\n"
        f"⏰ <b>Time:</b> {now_str()}\n"
        f"{DIVIDER}"
    )


def new_user_alert(username: str, user_id: int, full_name: str) -> str:
    return (
        f"🆕 <b>NEW USER JOINED BOT</b>\n"
        f"{DIVIDER}\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"🔗 <b>Username:</b> @{username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📅 <b>Joined:</b> {now_str()}\n"
        f"{DIVIDER}"
    )


def welcome_msg(first_name: str, bot_name: str = "Proxy Shop", support: str = "@admin") -> str:
    return (
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"{DIVIDER}\n"
        f"  🏪  {bot_name.upper()}\n"
        f"{DIVIDER}\n\n"
        f"🎫 Premium digital vouchers & codes\n"
        f"⚡ Instant auto-delivery after payment\n"
        f"🔒 Safe & trusted UPI payments\n\n"
        f"<b>Quick Actions:</b>\n"
        f"🛍 <b>Buy Vouchers</b> — Browse products\n"
        f"📦 <b>My Orders</b> — View your orders\n"
        f"🆘 <b>Support</b> — Get help\n\n"
        f"<i>Tap a button below to get started!</i>"
    )


def payment_waiting_msg(
    order_id: str,
    voucher_name: str,
    quantity: int,
    base_total: float,
    unique_amount: float,
    expiry_minutes: int,
    shop_name: str
) -> str:
    return (
        f"{DIVIDER}\n"
        f"  🧾  ORDER CREATED\n"
        f"{DIVIDER}\n\n"
        f"🆔 Order ID: <code>#{order_id}</code>\n"
        f"🎁 Product: <b>{voucher_name} × {quantity}</b>\n"
        f"💰 Base Price: ₹{base_total:.0f}\n\n"
        f"{DIVIDER}\n"
        f"  💳  PAY EXACTLY THIS AMOUNT\n"
        f"{DIVIDER}\n"
        f"     <b>₹{unique_amount:.2f}</b>\n"
        f"{DIVIDER}\n\n"
        f"📲 Scan QR above with any UPI app\n"
        f"   PhonePe  •  GPay  •  Paytm  •  BHIM\n\n"
        f"⚠️ Pay the <b>EXACT decimal amount</b> shown.\n"
        f"   It auto-identifies your payment.\n\n"
        f"⏳ Order expires in <b>{expiry_minutes} minutes</b>\n"
        f"✅ Codes are delivered automatically!\n\n"
        f"<i>🏪 {shop_name}</i>"
    )


def order_expired_msg(order_id: str, voucher_name: str, expiry_minutes: int) -> str:
    return (
        f"⏰ <b>ORDER EXPIRED</b>\n"
        f"{DIVIDER}\n\n"
        f"🆔 Order <code>#{order_id}</code>\n"
        f"🎁 {voucher_name}\n\n"
        f"No payment detected within {expiry_minutes} minutes.\n\n"
        f"💡 Tap <b>🛍 Buy Vouchers</b> to place a new order."
    )


def order_detail_msg(order: dict, codes: list[str]) -> str:
    status_map = {
        "pending":   "⏳ Awaiting Payment",
        "paid":      "💰 Payment Detected",
        "approved":  "✅ Delivered",
        "rejected":  "❌ Rejected",
        "cancelled": "🚫 Cancelled",
        "expired":   "⌛ Expired",
    }
    status_emoji = status_map.get(order["status"], order["status"])
    unique_amount = order.get("unique_amount") or order["total_price"]

    text = (
        f"{DIVIDER}\n"
        f"  📋  ORDER DETAILS\n"
        f"{DIVIDER}\n\n"
        f"🎁 <b>Product:</b> {order['voucher_name']}\n"
        f"🔢 <b>Quantity:</b> {order['quantity']}\n"
        f"💵 <b>Paid:</b> ₹{unique_amount:.2f}\n"
        f"🆔 <b>Order ID:</b> <code>#{order['id']}</code>\n"
        f"📅 <b>Date:</b> {order['created_at'][:16]}\n"
        f"📌 <b>Status:</b> {status_emoji}\n"
    )

    if codes:
        codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
        text += f"\n{DIVIDER}\n🎁 <b>Your Codes:</b>\n{codes_block}\n{DIVIDER}"
    elif order["status"] == "approved":
        text += f"\n\n<i>Codes were delivered. Contact support if missing.</i>"

    return text
