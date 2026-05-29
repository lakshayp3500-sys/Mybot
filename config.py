import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_NAME = os.getenv("BOT_NAME", "Proxy Shop")

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = list(map(int, ADMIN_IDS_RAW.split(","))) if ADMIN_IDS_RAW.strip() else []

DB_PATH = "voucher_bot.db"

UPI_ID = os.getenv("UPI_ID", "yourname@upi")
SHOP_NAME = os.getenv("SHOP_NAME", "MyShop")
ORDER_EXPIRY_MINUTES = int(os.getenv("ORDER_EXPIRY_MINUTES", "5"))

SMS_WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("BOT_PORT", "5001")))

_replit_domain = os.getenv("REPLIT_DEV_DOMAIN", "")
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")

if _railway_domain:
    API_BASE_URL = f"https://{_railway_domain}"
elif _replit_domain:
    API_BASE_URL = f"https://{_replit_domain}/api"
else:
    API_BASE_URL = ""
