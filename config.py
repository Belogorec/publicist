import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TG_WEBHOOK_SECRET = os.getenv("TG_WEBHOOK_SECRET", "").strip()

if BOT_TOKEN:
    TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
else:
    TG_API = ""

# Comma-separated list of admin Telegram user IDs, e.g. "123456789,987654321"
_admin_raw = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]
