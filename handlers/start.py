"""
handlers/start.py — Start, welcome, disclaimer, support, channels.
Sends new-user alert to admin on first join.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart

from config import ADMIN_IDS, BOT_NAME
from utils.db_helpers import register_user, get_setting, get_all_channels
from utils.messages import welcome_msg, new_user_alert
from keyboards.reply import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    username = user.username or ""
    full_name = user.full_name or user.first_name or "User"

    # Register user — returns True if brand new
    is_new = register_user(user.id, username, full_name)

    support = get_setting("support_username") or "@admin"

    await message.answer(
        welcome_msg(user.first_name or "there", BOT_NAME, support),
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    # Alert admins about new user
    if is_new:
        alert = new_user_alert(username, user.id, full_name)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, alert, parse_mode="HTML")
            except Exception:
                pass


@router.message(F.text == "📜 Disclaimer")
async def disclaimer(message: Message):
    await message.answer(
        "📜 <b>DISCLAIMER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ All vouchers and codes sold here are digital products.\n\n"
        "• No refunds once codes are delivered\n"
        "• Codes are valid at time of delivery\n"
        "• We are not responsible for misuse\n"
        "• Payment issues? Contact support\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>By purchasing, you agree to these terms.</i>",
        parse_mode="HTML"
    )


@router.message(F.text == "🆘 Support")
async def support(message: Message):
    support_username = get_setting("support_username") or "@admin"
    await message.answer(
        f"🆘 <b>SUPPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Need help? Contact us:\n\n"
        f"👤 <b>{support_username}</b>\n\n"
        f"⏰ Response time: Usually within 1 hour\n"
        f"📋 Include your Order ID for faster support\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )


@router.message(F.text == "📢 Our Channels")
async def our_channels(message: Message):
    channels = get_all_channels()
    if not channels:
        await message.answer(
            "📢 No channels added yet.\n"
            "Check back soon!",
            parse_mode="HTML"
        )
        return

    lines = [f"🔗 <a href='{ch['link']}'>{ch['name']}</a>" for ch in channels]
    await message.answer(
        f"📢 <b>OUR CHANNELS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Join to stay updated with latest deals!</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
