import html
import traceback

from flask import request, abort

from config import TG_WEBHOOK_SECRET
from telegram_api import tg_send_message


def _h(s: str) -> str:
    return html.escape(s or "", quote=False)


def _get_message(update: dict) -> dict:
    return update.get("message") or {}


def handle_start(chat_id: str, user: dict) -> None:
    first_name = _h(user.get("first_name") or "")
    text = (
        f"Привет{', ' + first_name if first_name else ''}! 👋\n\n"
        "Я помогу вам разместить публикацию.\n\n"
        "Напишите, что вам нужно, и мы начнём."
    )
    tg_send_message(chat_id, text)


def tg_webhook_impl() -> tuple:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if TG_WEBHOOK_SECRET and secret != TG_WEBHOOK_SECRET:
        abort(403)

    try:
        update = request.get_json(force=True, silent=True) or {}
    except Exception:
        return "", 400

    try:
        message = _get_message(update)
        if not message:
            return "", 200

        chat_id = str((message.get("chat") or {}).get("id", ""))
        user = message.get("from") or {}
        text = (message.get("text") or "").strip()

        if text == "/start":
            handle_start(chat_id, user)

    except Exception:
        traceback.print_exc()

    return "", 200
