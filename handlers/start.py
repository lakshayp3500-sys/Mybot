"""
handlers/start.py — Start, welcome, disclaimer, support, channels.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart

from config import ADMIN_IDS, BOT_NAME
from utils.db_helpers import register_user, get_setting, get_all_channels
from utils.messages import welcome_msg, new_user_alert
from keyboards.reply import main_menu
import asyncio

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    username = user.username or ""
    full_name = user.full_name or user.first_name or "User"

    is_new = register_user(user.id, username, full_name)

    await message.bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(0.8)

    support = get_setting("support_username") or "@admin"

    await message.answer(
        welcome_msg(user.first_name or "there", BOT_NAME, support),
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    if is_new:
        alert = new_user_alert(username, user.id, full_name)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, alert, parse_mode="HTML")
            except Exception:
                pass


@router.message(F.text == "📜 Disclaimer")
async def disclaimer(message: Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(0.7)
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
    await message.bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(0.7)
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
    await message.bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(0.7)
    channels = get_all_channels()
    if not channels:
        await message.answer(
            "📢 No channels added yet.\nCheck back soon!",
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
