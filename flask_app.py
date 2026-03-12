from flask import Flask, abort, request

from db import connect, run_migrations
from tg_handlers import tg_webhook_impl
from dialog import get_lead_snapshot
from crm_sync import send_event, crm_sync_enabled
from config import TG_WEBHOOK_SECRET

app = Flask(__name__)


def bootstrap_schema():
    conn = connect()
    try:
        run_migrations(conn)
    finally:
        conn.close()


bootstrap_schema()


@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    return tg_webhook_impl()


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


@app.route("/api/migrate-to-crm", methods=["POST"])
def migrate_to_crm():
    # Protected by the same webhook secret
    secret = request.headers.get("X-Migrate-Secret", "")
    if TG_WEBHOOK_SECRET and secret != TG_WEBHOOK_SECRET:
        abort(403)

    if not crm_sync_enabled():
        return {"ok": False, "error": "CRM_API_URL not set"}, 503

    conn = connect()
    try:
        leads = conn.execute("SELECT id FROM leads ORDER BY id").fetchall()
        ok = 0
        fail = 0
        for row in leads:
            snapshot = get_lead_snapshot(conn, row["id"])
            if not snapshot:
                continue
            result = send_event("lead.migrated", snapshot, {"actor_tg_id": "migration"})
            if result:
                ok += 1
            else:
                fail += 1
    finally:
        conn.close()

    return {"ok": True, "synced": ok, "failed": fail}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
