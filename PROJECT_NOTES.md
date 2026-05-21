# Telegram Voucher Bot — Project Notes

## Bot Info
- **Bot:** @CouponStoreByProxy_bot
- **Bot Token:** (set in Railway env vars as BOT_TOKEN)
- **Admin Telegram ID:** 7515220054
- **GitHub Repo:** https://github.com/lakshayp3500-sys/Mybot

## What This Bot Does
Premium Telegram voucher-selling bot with UPI auto-payment verification.
- Customers buy digital voucher/coupon codes via Telegram
- Payment via UPI (fingerprinted unique amounts for auto-detection)
- SMS forwarder on admin's phone forwards UPI credit SMS to bot
- Bot auto-detects payment and delivers codes instantly
- Full admin panel inside Telegram

## Live Deployment (Railway)
- **Platform:** Railway (railway.app)
- **Bot URL (SMS):** https://worker-production-e44a.up.railway.app/sms
- **Bot URL (UPI):** https://worker-production-e44a.up.railway.app/upi
- **Database:** PostgreSQL (Railway plugin — permanent data)
- **Auto-deploy:** Yes — push to GitHub → Railway redeploys automatically

## Railway Environment Variables (set these in Railway dashboard)
```
BOT_TOKEN=<telegram bot token>
ADMIN_IDS=7515220054
UPI_ID=bimlesh.01@ptyes
SHOP_NAME=Proxy codes shop
BOT_NAME=Proxy codes shop
ORDER_EXPIRY_MINUTES=5
RAILWAY_PUBLIC_DOMAIN=worker-production-e44a.up.railway.app
DATABASE_URL=<auto-set by Railway PostgreSQL plugin>
```

## SMS Forwarder App Setup
- App on admin's Android phone forwards UPI credit SMS
- URL: https://worker-production-e44a.up.railway.app/sms
- Method: POST
- Body: {"sms": "{msg}"}

## Bot Commands
### Customer Commands
- /start — Main menu
- Buy Vouchers — Browse and buy
- My Orders — View order history with codes

### Admin Commands
- /admin — Admin panel
- Add Voucher — Create new voucher type with price
- Add Codes — Bulk add codes to a voucher
- Live Orders — See pending orders
- Stats — Revenue and user stats
- /broadcast — Send message to all users
- /pay <SMS text> — Manual payment verify (paste SMS text)

## Tech Stack
- **Language:** Python 3.11
- **Bot Framework:** aiogram 3.13.1
- **Web Server:** aiohttp (for SMS + UPI endpoints)
- **Database:** SQLite (local) / PostgreSQL (Railway)
- **DB Driver:** psycopg2-binary (PostgreSQL)

## Key Files
```
main.py          — Bot entry point, aiohttp server (/sms and /upi routes)
config.py        — All env var loading
database.py      — Unified SQLite/PostgreSQL connection layer
payment.py       — UPI fingerprinting + SMS amount parsing
order_manager.py — Order create/fetch/expire logic
handlers/
  start.py       — /start, main menu
  buy.py         — Voucher browsing and order creation
  orders.py      — My Orders, order status
  admin.py       — Full admin panel
utils/
  db_helpers.py  — All database operations
  messages.py    — Message templates
```

## How UPI Payment Works
1. Customer selects voucher → bot generates unique amount (e.g. ₹100.47)
2. Customer clicks "Pay with UPI" → opens /upi page → UPI app opens
3. Customer pays exact amount
4. UPI credit SMS arrives on admin's phone
5. SMS Forwarder app → POST to /sms
6. Bot extracts amount, matches pending order, delivers codes
7. Customer gets codes, admin gets sale receipt

## Security Features
- Collision detection: two orders can NEVER have same amount
- Idempotent delivery: codes can't be delivered twice for same order
- Order expiry: unpaid orders expire after ORDER_EXPIRY_MINUTES

## Known Fixes Applied
1. Double-code delivery bug fixed (idempotent deliver_codes)
2. PostgreSQL datetime comparison fix (use datetime objects not strings)
3. PostgreSQL float comparison uses ABS tolerance (0.001)
4. SMS regex patterns: 12 patterns for all Indian bank formats
5. Collision detection for unique payment amounts
6. /upi route added to aiohttp server for Railway

## Future Plans / Next Features
- /addadmin command for multi-admin support
- Migrate to Koyeb + Supabase when Railway free tier expires (30 days)
- Koyeb: koyeb.com (free forever, no credit card)
- Supabase: supabase.com (free PostgreSQL, 500MB)

## Pushing Code Updates to GitHub (from Replit)
Since git commands are restricted, use Python API script:
- Script is in PROJECT_NOTES.md for reference
- GitHub Token: (stored in conversation, regenerate if expired)
- Username: lakshayp3500-sys

## When Migrating from Railway to Koyeb
1. Export PostgreSQL data from Railway
2. Create Supabase project → get new DATABASE_URL
3. Import data to Supabase
4. Deploy to Koyeb from GitHub
5. Set all env vars in Koyeb
6. Update SMS forwarder URL to new Koyeb URL
7. Add RAILWAY_PUBLIC_DOMAIN → KOYEB_PUBLIC_DOMAIN env var
