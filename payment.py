"""payment.py — UPI payment logic: amount fingerprinting, link generation, SMS parsing."""

import random
import re
from urllib.parse import quote
from order_manager import get_pending_order_by_amount, mark_order_paid


def generate_unique_amount(base_price: float, used_amounts: set | None = None) -> float:
    """
    Append random 2-digit decimal to fingerprint the payment.
    Retries up to 90 times to avoid collision with currently pending orders.
    used_amounts: set of floats already taken by live pending orders.
    """
    from order_manager import is_amount_taken

    tried: set[int] = set()
    all_decimals = list(range(10, 100))  # .10 to .99 → 90 slots

    random.shuffle(all_decimals)

    for decimal_part in all_decimals:
        amount = round(base_price + decimal_part / 100, 2)
        # Check in-memory set first (fast), then DB (authoritative)
        if used_amounts and amount in used_amounts:
            continue
        if is_amount_taken(amount):
            continue
        return amount

    # All 90 slots taken (extremely unlikely — only if 90 simultaneous pending orders exist)
    # Fall back to expanding to 3-decimal range as last resort
    decimal_part = random.randint(100, 999)
    return round(base_price + decimal_part / 1000, 3)


def generate_upi_link(amount: float, upi_id: str, shop_name: str, api_base_url: str = "") -> str:
    """HTTPS redirect URL for Telegram inline button."""
    encoded_name = quote(shop_name)
    if api_base_url:
        return (
            f"{api_base_url}/upi?"
            f"pa={quote(upi_id)}&pn={encoded_name}&am={amount:.2f}&cu=INR"
        )
    return generate_raw_upi_link(amount, upi_id, shop_name)


def generate_raw_upi_link(amount: float, upi_id: str, shop_name: str) -> str:
    """Raw upi:// link — for QR code only."""
    encoded_name = quote(shop_name)
    return f"upi://pay?pa={upi_id}&pn={encoded_name}&am={amount:.2f}&cu=INR"


SMS_AMOUNT_PATTERNS = [
    # ₹100.47 or Rs100.47 or INR100.47 (no space)
    r"(?:Rs|INR|₹)\.?\s*([\d,]+\.[\d]{2})",
    # debited by 100.47
    r"debited\s+(?:by\s+)?(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # received Rs 100.47
    r"received\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # credited with Rs 100.47
    r"credited.*?(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # payment of Rs 100.47
    r"payment\s+of\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # sent Rs 100.47
    r"sent\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # transferred Rs 100.47
    r"transferred\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # paid Rs 100.47
    r"paid\s+(?:Rs\.?|INR|₹)\s*([\d,]+\.[\d]{2})",
    # 100.47 Rs/INR/₹ (amount before symbol)
    r"([\d,]+\.[\d]{2})\s*(?:Rs\.?|INR|₹)",
    # Amount:100.47 or Amt:100.47
    r"(?:amount|amt)[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+\.[\d]{2})",
    # UPI: 100.47 (some apps)
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
                # Remove commas (e.g. 1,000.47 → 1000.47)
                amount_str = match.group(1).replace(",", "")
                amount = float(amount_str)
                logger.info(f"Amount extracted: {amount} (pattern: {pattern[:40]})")
                return amount
            except (ValueError, IndexError):
                continue

    logger.warning(f"No amount found in SMS: {sms_text[:120]}")
    return None


def verify_payment(sms_text: str) -> dict | None:
    """Extract amount from SMS, match to pending order, mark as paid."""
    amount = extract_amount_from_sms(sms_text)
    if amount is None:
        return None
    order = get_pending_order_by_amount(amount)
    if not order:
        return None
    mark_order_paid(order["id"])
    order["matched_amount"] = amount
    return order
