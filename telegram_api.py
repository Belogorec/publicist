import json
from typing import Optional

import requests

from config import TG_API

session = requests.Session()


def tg_post(method: str, data: dict) -> dict:
    if not TG_API:
        raise RuntimeError("BOT_TOKEN не задан")

    r = session.post(f"{TG_API}/{method}", data=data, timeout=25)
    r.raise_for_status()

    try:
        payload = r.json()
    except Exception as e:
        raise RuntimeError(f"Telegram API вернул не-JSON ответ для {method}: {e}")

    if not payload.get("ok", False):
        description = payload.get("description") or "Unknown Telegram API error"
        error_code = payload.get("error_code")
        raise RuntimeError(
            f"Telegram API ошибка в {method}: "
            f"error_code={error_code}, description={description}"
        )

    return payload


def tg_send_message(
    chat_id: str,
    text: str,
    reply_markup: Optional[dict] = None,
    parse_mode: str = "HTML",
) -> Optional[int]:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    data = tg_post("sendMessage", payload)
    return (data.get("result") or {}).get("message_id")
