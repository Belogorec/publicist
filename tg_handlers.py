import html
import traceback

from flask import request, abort

from config import TG_WEBHOOK_SECRET, ADMIN_IDS
from db import connect
from dialog import (
    MEDIA_CATALOG, get_media, get_format,
    upsert_lead, update_lead,
    save_lead_text, save_lead_file, get_materials_summary, log_moderation,
)
from telegram_api import (
    tg_send_message, tg_answer_callback_query, tg_edit_message_text,
)


def _h(s) -> str:
    return html.escape(str(s or ""), quote=False)


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------

def _kb_main_menu() -> dict:
    return {"inline_keyboard": [
        [
            {"text": "Посмотреть площадки", "callback_data": "menu:media"},
            {"text": "Узнать стоимость",     "callback_data": "menu:prices"},
        ],
        [
            {"text": "Отправить материал",   "callback_data": "menu:material"},
            {"text": "Задать вопрос",         "callback_data": "menu:question"},
        ],
    ]}


def _kb_media_list() -> dict:
    rows = []
    for media_id, media in MEDIA_CATALOG.items():
        rows.append([{"text": media["name"], "callback_data": f"media:{media_id}"}])
    rows.append([{"text": "Сравнить все площадки", "callback_data": "menu:prices"}])
    rows.append([{"text": "◀ Назад",               "callback_data": "menu:back"}])
    return {"inline_keyboard": rows}


def _kb_media_formats(media_id: str) -> dict:
    media = get_media(media_id)
    if not media:
        return {"inline_keyboard": []}
    rows = []
    for fmt in media["formats"]:
        price_str = f"{fmt['price']:,}".replace(",", "\u202f")
        rows.append([{
            "text": f"{fmt['name']} — {price_str} ₽",
            "callback_data": f"format:{media_id}:{fmt['id']}",
        }])
    rows.append([{"text": "◀ Назад к площадкам", "callback_data": "menu:media"}])
    return {"inline_keyboard": rows}


def _kb_after_format() -> dict:
    return {"inline_keyboard": [
        [
            {"text": "Отправить материал",    "callback_data": "action:send_material"},
            {"text": "Требования",             "callback_data": "action:requirements"},
        ],
        [
            {"text": "Задать вопрос",          "callback_data": "menu:question"},
            {"text": "Другой формат",          "callback_data": "menu:media"},
        ],
    ]}


def _kb_material_upload() -> dict:
    return {"inline_keyboard": [
        [{"text": "✅ Завершить отправку", "callback_data": "action:finish_upload"}],
        [{"text": "❌ Отмена",             "callback_data": "action:cancel"}],
    ]}


def _kb_after_reject() -> dict:
    return {"inline_keyboard": [
        [{"text": "Отправить заново",       "callback_data": "action:send_material"}],
        [{"text": "Узнать требования",       "callback_data": "action:requirements"}],
        [{"text": "Связаться с менеджером",  "callback_data": "menu:question"}],
    ]}


def _kb_after_clarify() -> dict:
    return {"inline_keyboard": [
        [{"text": "Отправить уточнение", "callback_data": "action:send_material"}],
    ]}


def _kb_admin_review(lead_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Одобрить",            "callback_data": f"admin:approve:{lead_id}"},
        {"text": "❌ Отклонить",           "callback_data": f"admin:reject:{lead_id}"},
        {"text": "❓ Уточнение",           "callback_data": f"admin:clarify:{lead_id}"},
    ]]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_price(price: int) -> str:
    return f"{price:,}".replace(",", "\u202f") + " ₽"


def _all_prices_text() -> str:
    lines = ["<b>Стоимость размещения по всем площадкам</b>\n"]
    for media in MEDIA_CATALOG.values():
        lines.append(f"<b>{_h(media['name'])}</b>")
        for fmt in media["formats"]:
            lines.append(f"  • {_h(fmt['name'])} — {_fmt_price(fmt['price'])}")
        lines.append("")
    return "\n".join(lines).strip()


def _notify_admins(lead, summary: dict) -> None:
    if not ADMIN_IDS:
        return
    media = get_media(lead["selected_media"] or "")
    fmt = get_format(lead["selected_media"] or "", lead["selected_format"] or "")
    media_name = media["name"] if media else (lead["selected_media"] or "—")
    fmt_name = fmt["name"] if fmt else (lead["selected_format"] or "—")
    price = _fmt_price(lead["agreed_price"]) if lead["agreed_price"] else "—"

    name = _h(lead["tg_name"] or "")
    username_line = f"\nTelegram: @{_h(lead['tg_username'])}" if lead["tg_username"] else ""
    text_count = summary["text_count"]
    photos = summary["files"].get("photo", 0)
    docs = summary["files"].get("document", 0)
    preview = _h(summary["text_preview"])

    card = (
        f"<b>📋 Новый материал на рассмотрение</b>\n\n"
        f"Клиент: {name or 'Не указан'}{username_line}\n"
        f"ID: <code>{_h(lead['tg_id'])}</code>\n\n"
        f"Площадка: <b>{_h(media_name)}</b>\n"
        f"Формат: <b>{_h(fmt_name)}</b>\n"
        f"Цена: <b>{price}</b>\n\n"
        f"Что прислал:\n"
        f"  — текст: {'да' if text_count else 'нет'}"
        + (f" ({text_count} сообщ.)" if text_count > 1 else "")
        + f"\n  — фото: {photos}\n  — файлы: {docs}\n\n"
        + (f"Текст:\n<i>{preview}</i>" if preview else "")
    ).strip()

    for admin_id in ADMIN_IDS:
        try:
            tg_send_message(str(admin_id), card, reply_markup=_kb_admin_review(lead["id"]))
        except Exception:
            traceback.print_exc()


def _start_material_upload(chat_id: str, tg_id, conn) -> None:
    update_lead(conn, tg_id, status="awaiting_material")
    tg_send_message(
        chat_id,
        "Отправьте материал в одном из вариантов:\n\n"
        "1. Текстом прямо в чат\n"
        "2. Фото отдельными сообщениями\n"
        "3. Файлом: doc, pdf, txt\n"
        "4. Текст + фото + файл — несколькими сообщениями\n\n"
        "Когда закончите отправку, нажмите кнопку:",
        reply_markup=_kb_material_upload(),
    )


# ---------------------------------------------------------------------------
# /start and message handlers
# ---------------------------------------------------------------------------

def handle_start(chat_id: str, user: dict, conn) -> None:
    upsert_lead(conn, user.get("id"), user.get("username"),
                user.get("first_name"), user.get("last_name"))
    update_lead(conn, user["id"], status="new")

    first_name = _h(user.get("first_name") or "")
    greeting = f"Здравствуйте{', ' + first_name if first_name else ''}."
    text = (
        f"{greeting}\n\n"
        "Вы в боте размещения публикаций в наших медиа.\n\n"
        "Здесь можно:\n"
        "— выбрать площадку для публикации\n"
        "— посмотреть форматы и стоимость\n"
        "— отправить материал на рассмотрение\n"
        "— получить подтверждение после модерации\n\n"
        "Выберите, что вас интересует:"
    )
    tg_send_message(chat_id, text, reply_markup=_kb_main_menu())


def handle_message(message: dict, conn) -> None:
    chat_id = str((message.get("chat") or {}).get("id", ""))
    user = message.get("from") or {}
    tg_id = str(user.get("id", ""))
    text = (message.get("text") or "").strip()
    caption = (message.get("caption") or "").strip()
    message_id = message.get("message_id")

    if not chat_id or not tg_id:
        return

    lead = upsert_lead(conn, user.get("id"), user.get("username"),
                       user.get("first_name"), user.get("last_name"))

    if text == "/start":
        handle_start(chat_id, user, conn)
        return

    status = lead["status"]

    # ---- material collection mode ----
    if status in ("awaiting_material", "needs_clarification"):
        if message.get("photo"):
            best = max(message["photo"], key=lambda p: p.get("file_size", 0))
            save_lead_file(conn, lead["id"], "photo", best["file_id"], caption or None)
            if status == "needs_clarification":
                update_lead(conn, tg_id, status="awaiting_material")
            tg_send_message(
                chat_id,
                "Фото получено. Можно отправить ещё материалы или завершить отправку.",
                reply_markup=_kb_material_upload(),
            )
            return

        if message.get("document"):
            doc = message["document"]
            save_lead_file(conn, lead["id"], "document", doc["file_id"],
                           caption=caption or None,
                           original_filename=doc.get("file_name"),
                           mime_type=doc.get("mime_type"))
            if status == "needs_clarification":
                update_lead(conn, tg_id, status="awaiting_material")
            tg_send_message(
                chat_id,
                "Файл получен. Если есть ещё материалы — отправьте их, либо завершите отправку.",
                reply_markup=_kb_material_upload(),
            )
            return

        if text:
            save_lead_text(conn, lead["id"], text, message_id)
            if status == "needs_clarification":
                update_lead(conn, tg_id, status="awaiting_material")
            tg_send_message(
                chat_id,
                "Текст получен. Можете отправить фото или файлы, если они есть.\n"
                "Когда закончите, нажмите «Завершить отправку».",
                reply_markup=_kb_material_upload(),
            )
            return

    # ---- question mode ----
    if status == "asking_question" and text:
        update_lead(conn, tg_id, status="new", manager_comment=text[:1000])
        name = _h(lead["tg_name"] or "")
        username_line = f"\n@{_h(lead['tg_username'])}" if lead["tg_username"] else ""
        admin_text = (
            f"<b>❓ Вопрос от клиента</b>\n\n"
            f"Клиент: {name or 'Не указан'}{username_line}\n"
            f"ID: <code>{tg_id}</code>\n\n"
            f"Текст:\n<i>{_h(text[:800])}</i>"
        )
        for admin_id in ADMIN_IDS:
            try:
                tg_send_message(str(admin_id), admin_text)
            except Exception:
                traceback.print_exc()
        tg_send_message(
            chat_id,
            "Спасибо, ваш вопрос получен.\nМы вернёмся с ответом в ближайшее время.",
            reply_markup=_kb_main_menu(),
        )
        return

    # ---- default: show menu ----
    if text and not text.startswith("/"):
        tg_send_message(chat_id, "Выберите действие:", reply_markup=_kb_main_menu())


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

def handle_callback_query(callback_query: dict, conn) -> None:
    cq_id = callback_query.get("id", "")
    user = callback_query.get("from") or {}
    tg_id = str(user.get("id", ""))
    cb_message = callback_query.get("message") or {}
    chat_id = str((cb_message.get("chat") or {}).get("id", ""))
    msg_id = cb_message.get("message_id")
    data = (callback_query.get("data") or "").strip()

    if not chat_id or not tg_id or not data:
        tg_answer_callback_query(cq_id)
        return

    lead = upsert_lead(conn, user.get("id"), user.get("username"),
                       user.get("first_name"), user.get("last_name"))

    parts = data.split(":", 2)
    prefix = parts[0]

    # ---- menu actions ----
    if prefix == "menu":
        action = parts[1] if len(parts) > 1 else ""
        tg_answer_callback_query(cq_id)

        if action == "media":
            update_lead(conn, tg_id, status="browsing_formats")
            tg_send_message(chat_id, "Доступны следующие площадки:", reply_markup=_kb_media_list())

        elif action == "prices":
            tg_send_message(chat_id, _all_prices_text(), reply_markup=_kb_main_menu())

        elif action == "material":
            if not lead["selected_media"] or not lead["selected_format"]:
                tg_send_message(
                    chat_id,
                    "Сначала выберите площадку и формат размещения:",
                    reply_markup=_kb_media_list(),
                )
            else:
                _start_material_upload(chat_id, tg_id, conn)

        elif action == "question":
            update_lead(conn, tg_id, status="asking_question")
            tg_send_message(
                chat_id,
                "Напишите ваш вопрос одним сообщением.\n"
                "Мы зафиксируем его и передадим менеджеру.",
            )

        elif action == "back":
            tg_send_message(chat_id, "Выберите действие:", reply_markup=_kb_main_menu())

        return

    # ---- media selection ----
    if prefix == "media":
        media_id = parts[1] if len(parts) > 1 else ""
        media = get_media(media_id)
        tg_answer_callback_query(cq_id)

        if not media:
            tg_send_message(chat_id, "Площадка не найдена.", reply_markup=_kb_media_list())
            return

        update_lead(conn, tg_id, selected_media=media_id, status="browsing_formats")

        lines = [
            f"<b>{_h(media['name'])}</b>",
            f"{_h(media['desc'])}\n",
            "Доступные форматы:\n",
        ]
        for i, fmt in enumerate(media["formats"], 1):
            lines.append(f"{i}. <b>{_h(fmt['name'])}</b> — {_fmt_price(fmt['price'])}")

        tg_send_message(chat_id, "\n".join(lines), reply_markup=_kb_media_formats(media_id))
        return

    # ---- format selection ----
    if prefix == "format":
        media_id = parts[1] if len(parts) > 1 else ""
        format_id = parts[2] if len(parts) > 2 else ""
        media = get_media(media_id)
        fmt = get_format(media_id, format_id)
        tg_answer_callback_query(cq_id)

        if not media or not fmt:
            tg_send_message(chat_id, "Формат не найден.", reply_markup=_kb_media_list())
            return

        update_lead(conn, tg_id,
                    selected_media=media_id,
                    selected_format=format_id,
                    agreed_price=fmt["price"],
                    status="selected_format")

        text = (
            f"Вы выбрали:\n\n"
            f"<b>{_h(media['name'])}</b>\n"
            f"<b>Формат:</b> {_h(fmt['name'])}\n"
            f"<b>Стоимость:</b> {_fmt_price(fmt['price'])}\n\n"
            f"Дальше можно:\n"
            f"1. Сразу отправить материал\n"
            f"2. Посмотреть требования к материалу\n"
            f"3. Задать вопрос менеджеру"
        )
        tg_send_message(chat_id, text, reply_markup=_kb_after_format())
        return

    # ---- user actions ----
    if prefix == "action":
        action = parts[1] if len(parts) > 1 else ""
        tg_answer_callback_query(cq_id)

        if action == "send_material":
            if not lead["selected_media"] or not lead["selected_format"]:
                tg_send_message(
                    chat_id, "Сначала выберите площадку и формат:",
                    reply_markup=_kb_media_list(),
                )
                return
            _start_material_upload(chat_id, tg_id, conn)

        elif action == "requirements":
            tg_send_message(
                chat_id,
                "Чтобы мы быстрее рассмотрели публикацию, отправьте:\n\n"
                "— текст материала или описание\n"
                "— фото / файлы, если есть\n"
                "— название проекта / компании\n"
                "— желаемую дату публикации\n"
                "— контакт для связи\n\n"
                "Если текста ещё нет, можно отправить информацию в свободной форме —\n"
                "мы уточним детали.",
                reply_markup={"inline_keyboard": [
                    [{"text": "Отправить материал", "callback_data": "action:send_material"}],
                    [{"text": "◀ Назад",             "callback_data": "menu:back"}],
                ]},
            )

        elif action == "finish_upload":
            summary = get_materials_summary(conn, lead["id"])
            has_material = summary["text_count"] > 0 or bool(summary["files"])
            if not has_material:
                tg_send_message(
                    chat_id,
                    "Пока что материал не получен.\n"
                    "Отправьте текст, фото или файл, а затем нажмите «Завершить отправку».",
                    reply_markup=_kb_material_upload(),
                )
                return
            update_lead(conn, tg_id, status="under_review")
            fresh_lead = conn.execute("SELECT * FROM leads WHERE tg_id = ?", (tg_id,)).fetchone()
            _notify_admins(fresh_lead, summary)
            tg_send_message(
                chat_id,
                "Спасибо, материал получен и отправлен на рассмотрение редакции.\n\n"
                "Что будет дальше:\n"
                "— мы проверим комплектность\n"
                "— администратор рассмотрит материал\n"
                "— после одобрения вы получите подтверждение и дальнейшие шаги\n\n"
                "<b>Статус: На модерации</b>",
            )

        elif action == "cancel":
            update_lead(conn, tg_id, status="new")
            tg_send_message(chat_id, "Отправка отменена. Выберите действие:",
                            reply_markup=_kb_main_menu())

        return

    # ---- admin actions ----
    if prefix == "admin":
        # Security: only registered admins can use these callbacks
        try:
            caller_id = int(tg_id)
        except ValueError:
            tg_answer_callback_query(cq_id, "Нет доступа")
            return
        if caller_id not in ADMIN_IDS:
            tg_answer_callback_query(cq_id, "Нет доступа")
            return

        action = parts[1] if len(parts) > 1 else ""
        try:
            target_lead_id = int(parts[2]) if len(parts) > 2 else None
        except (ValueError, IndexError):
            tg_answer_callback_query(cq_id)
            return

        if not target_lead_id:
            tg_answer_callback_query(cq_id)
            return

        target_lead = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (target_lead_id,)
        ).fetchone()
        if not target_lead:
            tg_answer_callback_query(cq_id, "Заявка не найдена")
            return

        client_chat_id = target_lead["tg_id"]
        admin_name = _h(user.get("first_name") or tg_id)
        client_name = _h(target_lead["tg_name"] or target_lead["tg_id"])

        if action == "approve":
            update_lead(conn, client_chat_id, status="approved")
            log_moderation(conn, target_lead_id, "approved", tg_id)
            tg_answer_callback_query(cq_id, "✅ Одобрено")
            if msg_id:
                tg_edit_message_text(
                    chat_id, msg_id,
                    f"✅ <b>Одобрено</b>\nКлиент: {client_name}\nРешение: {admin_name}\n"
                    f"Заявка #{target_lead_id}",
                )
            tg_send_message(
                client_chat_id,
                "Ваш материал одобрен. ✅\n\n"
                "С вами свяжется менеджер для завершения размещения.",
                reply_markup=_kb_main_menu(),
            )

        elif action == "reject":
            update_lead(conn, client_chat_id, status="rejected")
            log_moderation(conn, target_lead_id, "rejected", tg_id)
            tg_answer_callback_query(cq_id, "❌ Отклонено")
            if msg_id:
                tg_edit_message_text(
                    chat_id, msg_id,
                    f"❌ <b>Отклонено</b>\nКлиент: {client_name}\nРешение: {admin_name}\n"
                    f"Заявка #{target_lead_id}",
                )
            tg_send_message(
                client_chat_id,
                "Спасибо, материал рассмотрен.\n\n"
                "На текущем этапе мы не можем принять его в публикацию в текущем виде.\n"
                "Вы можете отправить обновлённую версию или уточнить требования.",
                reply_markup=_kb_after_reject(),
            )

        elif action == "clarify":
            update_lead(conn, client_chat_id, status="needs_clarification")
            log_moderation(conn, target_lead_id, "needs_clarification", tg_id)
            tg_answer_callback_query(cq_id, "❓ Запрошено уточнение")
            if msg_id:
                tg_edit_message_text(
                    chat_id, msg_id,
                    f"❓ <b>Запрошено уточнение</b>\nКлиент: {client_name}\n"
                    f"Решение: {admin_name}\nЗаявка #{target_lead_id}",
                )
            tg_send_message(
                client_chat_id,
                "Редакции нужны уточнения по вашему материалу.\n\n"
                "Пожалуйста, пришлите:\n"
                "— более полный текст / описание\n"
                "— дополнительные фотографии\n"
                "— уточнение по дате / бренду / контактам\n\n"
                "После этого материал снова уйдёт на рассмотрение.",
                reply_markup=_kb_after_clarify(),
            )

        return

    tg_answer_callback_query(cq_id)


# ---------------------------------------------------------------------------
# Main webhook dispatcher
# ---------------------------------------------------------------------------

def tg_webhook_impl() -> tuple:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if TG_WEBHOOK_SECRET and secret != TG_WEBHOOK_SECRET:
        abort(403)

    try:
        update = request.get_json(force=True, silent=True) or {}
    except Exception:
        return "", 400

    try:
        conn = connect()
        try:
            if "callback_query" in update:
                handle_callback_query(update["callback_query"], conn)
            elif "message" in update:
                handle_message(update["message"], conn)
        finally:
            conn.close()
    except Exception:
        traceback.print_exc()

    return "", 200
