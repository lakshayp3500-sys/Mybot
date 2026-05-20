"""states/states.py — FSM states for the bot."""

from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    select_voucher = State()
    select_quantity = State()
    custom_quantity = State()
    waiting_payment = State()


class AdminStates(StatesGroup):
    # Voucher management
    add_voucher_name = State()
    add_voucher_price = State()
    remove_voucher = State()
    set_price_voucher = State()
    set_price_value = State()

    # Codes
    add_codes_voucher = State()
    add_codes_input = State()

    # Orders
    reject_reason = State()

    # Channels
    remove_channel = State()
    add_channel_name = State()
    add_channel_link = State()

    # Settings
    set_support = State()
    broadcast_message = State()
