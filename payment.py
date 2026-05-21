"""payment.py — UPI payment logic: amount fingerprinting, link generation, SMS parsing."""

import random
import re
from urllib.parse import quote
from order_manager import get_pending_order_by_amount, mark_order_paid


def generate_unique_amount(base_price: float, used_amounts: set | None = None) -> float:
    from order_manager import is_amount_taken

    all_decimals = list(range(10, 100))
    random.shuffle(all_decimals)

    for decimal_part in all_decimals:
        amount = round(base_price + decimal_part / 100, 2)
        if used_amounts and amount in used_amounts:
            continue
        if is_amount_taken(amount):
            continue
        return amount

    decimal_part = random.randint(100, 999)
    return round(base_price + decimal_part / 1000, 3)


def generate_upi_link(amount: float, upi_id: str, shop_name: str, api_base_url: str = "") -> str:
    encoded_name = quote(shop_name)
    if api_base_url:
        return (
            f"{api_base_url}/upi?"
            f"pa={quote(upi_id)}&pn={encoded_name}&am={amount:.2f}&cu=INR"
        )
    return generate_raw_upi_link(amount, upi_id, shop_name)


def generate_raw_upi_link(amount: float, upi_id: str, shop_name: str) -> str:
    encoded_name = quote(shop_name)
    return f"upi://pay?pa={upi_id}&pn={encoded_name}&am={amount:.2f}&cu=INR"


SMS_AMOUNT_PATTERNS = [
    r"(?:Rs|INR|₹)\.?\s*([\d,]+\.[\d]{2})",
    r"debited\s+(?:by\s+)?(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"received\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"credited.*?(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"payment\s+of\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"sent\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"transferred\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"paid\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    r"([\d,]+\.[\d]{2})\s*(?:Rs\.?|INR|₹)",
    r"(?:amount|amt)[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+\.[\d]{2})",
    r"upi.*?([\d,]+\.[\d]{2})",
]


def extract_amount_from_sms(sms_text: str) -> float | None:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Parsing SMS for amount: {sms_text[:120]}")

    for pattern in SMS_AMOUNT_PATTERNS:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            try:
                amount_str = match.group(1).replace(",", "")
                amount = float(amount_str)
                logger.info(f"Amount extracted: {amount} (pattern: {pattern[:40]})")
                return amount
            except (ValueError, IndexError):
                continue

    logger.warning(f"No amount found in SMS: {sms_text[:120]}")
    return None


def verify_payment(sms_text: str) -> dict | None:
    amount = extract_amount_from_sms(sms_text)
    if amount is None:
        return None
    order = get_pending_order_by_amount(amount)
    if not order:
        return None
    mark_order_paid(order["id"])
    order["matched_amount"] = amount
    return order
