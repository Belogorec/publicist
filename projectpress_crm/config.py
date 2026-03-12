import os

from dotenv import load_dotenv

load_dotenv()

CRM_INGEST_API_KEY = os.getenv("CRM_INGEST_API_KEY", "").strip()
CRM_DB_PATH = os.getenv(
    "CRM_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "projectpress_crm.db"),
).strip()
CRM_DEFAULT_MANAGER = os.getenv("CRM_DEFAULT_MANAGER", "").strip() or None
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Telegram authentication
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# Session configuration
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production").strip()
AUTH_TOKEN_LIFETIME = int(os.getenv("AUTH_TOKEN_LIFETIME", "86400").strip() or "86400")  # 1 day

# Authenticate via Telegram
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# Session config
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production").strip()
AUTH_TOKEN_LIFETIME = int(os.getenv("AUTH_TOKEN_LIFETIME", "86400").strip() or "86400")  # 1 day
