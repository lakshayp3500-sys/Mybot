"""keyboards/reply.py — Reply keyboard layouts."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Buy Vouchers"), KeyboardButton(text="📦 My Orders")],
            [KeyboardButton(text="📜 Disclaimer"), KeyboardButton(text="🆘 Support")],
            [KeyboardButton(text="📢 Our Channels")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📡 Live Orders"), KeyboardButton(text="⏳ Pending Orders")],
            [KeyboardButton(text="📦 View Stock"), KeyboardButton(text="📊 Statistics")],
            [KeyboardButton(text="➕ Add Voucher"), KeyboardButton(text="❌ Delete Voucher")],
            [KeyboardButton(text="💰 Set Price"), KeyboardButton(text="📥 Add Codes")],
            [KeyboardButton(text="🗑 Remove Codes"), KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="📢 Manage Channels"), KeyboardButton(text="🆘 Support Settings")],
            [KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
