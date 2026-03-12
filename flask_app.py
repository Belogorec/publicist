from flask import Flask

from db import connect, run_migrations
from tg_handlers import tg_webhook_impl

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
