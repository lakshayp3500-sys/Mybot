from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    select_voucher = State()
    select_quantity = State()
    custom_quantity = State()
    disclaimer_confirm = State()
    waiting_payment = State()


class AdminStates(StatesGroup):
    add_voucher_name = State()
    add_voucher_price = State()
    remove_voucher = State()
    set_price_voucher = State()
    set_price_value = State()
    add_codes_voucher = State()
    add_codes_input = State()
    reject_reason = State()
    remove_channel = State()
    add_channel_name = State()
    add_channel_link = State()
    set_support = State()
    broadcast_message = State()
    set_disclaimer_voucher = State()
    set_disclaimer_text = State()
