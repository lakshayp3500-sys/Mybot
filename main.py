"""
main.py — Bot entry point.

Runs Telegram polling + aiohttp webhook server on port 5001.
SMS auto-verify: POST /api/sms from SMS forwarder app.
Admin command: /pay <SMS text>
"""

import asyncio
import logging
import sys
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, ORDER_EXPIRY_MINUTES, SMS_WEBHOOK_PORT
from database import init_db
from order_manager import expire_orders
from handlers import start, buy, orders, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Global bot instance (set in main())
_bot: Bot | None = None

# ─── Aiohttp SMS webhook handler ──────────────────────────────────────────────

async def sms_webhook(request: web.Request) -> web.Response:
    """
    Receives forwarded SMS from Express /api/sms proxy.
    Extracts payment amount, matches pending order, delivers codes.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid JSON"}, status=400)

    sms_text: str = (
        data.get("message") or data.get("sms") or
        data.get("text") or data.get("msg") or ""
    )

    if not sms_text:
        return web.json_response({"status": "error", "error": "No SMS text"}, status=400)

    logger.info(f"SMS received via webhook: {sms_text[:80]}")

    from payment import verify_payment
    from utils.db_helpers import deliver_codes, get_voucher_stock, get_setting, get_user
    from utils.messages import success_delivery_msg, admin_sale_receipt

    order = verify_payment(sms_text)
    if not order:
        return web.json_response({"status": "no_match"})

    order_id = order["id"]
    codes = deliver_codes(order_id, order["voucher_id"], order["quantity"])

    if codes is None:
        return web.json_response({"status": "error", "error": "Not enough stock"})

    matched_amount = order.get("matched_amount", order.get("unique_amount", 0))
    support = get_setting("support_username") or "@admin"

    # Notify user
    if _bot:
        user_msg = success_delivery_msg(
            voucher_name=order["voucher_name"],
            codes=codes,
            amount=matched_amount,
            order_id=order_id,
            support=support
        )
        try:
            await _bot.send_message(order["user_id"], user_msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not notify user {order['user_id']}: {e}")

        # Notify admin with sale receipt
        try:
            user_info = get_user(order["user_id"]) or {}
            buyer_username = user_info.get("username", "N/A")
        except Exception:
            buyer_username = "N/A"

        remaining = get_voucher_stock(order["voucher_id"])
        stock_note = ""
        if remaining == 0:
            stock_note = "\n\n🚨 <b>STOCK EMPTY! Add more codes.</b>"
        elif remaining <= 5:
            stock_note = f"\n\n⚠️ Only <b>{remaining}</b> codes left!"

        receipt = admin_sale_receipt(
            buyer_username=buyer_username,
            buyer_id=order["user_id"],
            voucher_name=order["voucher_name"],
            quantity=order["quantity"],
            base_amount=order["total_price"],
            unique_amount=matched_amount,
            order_id=order_id,
            codes=codes
        )
        for admin_id in ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, receipt + stock_note, parse_mode="HTML")
            except Exception:
                pass

    logger.info(f"Auto-delivered order {order_id} via webhook")
    return web.json_response({"status": "delivered", "order_id": order_id})


async def start_webhook_server():
    """Start aiohttp server on port 5001 for SMS webhook."""
    app = web.Application()
    app.router.add_post("/sms", sms_webhook)
    app.router.add_get("/health", lambda r: web.json_response({"status": "ok"}))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", SMS_WEBHOOK_PORT)
    await site.start()
    logger.info(f"SMS webhook server running on port {SMS_WEBHOOK_PORT}")
    return runner


# ─── Background expiry loop ───────────────────────────────────────────────────

async def _expiry_loop(bot: Bot):
    while True:
        await asyncio.sleep(60)
        try:
            expired = expire_orders()
            for order in expired:
                try:
                    await bot.send_message(
                        order["user_id"],
                        f"⏰ <b>ORDER EXPIRED</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🆔 Order <code>#{order['id']}</code>\n"
                        f"🎁 {order['voucher_name']}\n\n"
                        f"No payment detected within {ORDER_EXPIRY_MINUTES} minutes.\n"
                        f"Tap <b>🛍 Buy Vouchers</b> to place a new order.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Expiry loop error: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global _bot

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)

    init_db()
    logger.info("Database initialised.")

    _bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)

    await _bot.delete_webhook(drop_pending_updates=True)

    # Start SMS webhook server + background tasks
    runner = await start_webhook_server()
    asyncio.create_task(_expiry_loop(_bot))

    logger.info("Bot started — polling active, SMS webhook on :5001")

    try:
        await dp.start_polling(_bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down...")
        await runner.cleanup()
        await dp.storage.close()
        await _bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
