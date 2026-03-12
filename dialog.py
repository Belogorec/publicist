"""
dialog.py — media catalog data and DB helper functions for the lead funnel.
"""
import sqlite3
from typing import Optional

# ---------------------------------------------------------------------------
# Media catalog
# ---------------------------------------------------------------------------

MEDIA_CATALOG: dict = {
    "journal_1": {
        "name": "Журнал №1",
        "desc": "Городское lifestyle-медиа: рестораны, события, люди, тренды",
        "formats": [
            {"id": "short_news",    "name": "Короткая новость",      "price": 5000},
            {"id": "standard_post", "name": "Стандартная публикация", "price": 7000},
            {"id": "extended_post", "name": "Расширенная публикация", "price": 10000},
            {"id": "announce_post", "name": "Анонс + публикация",     "price": 9000},
        ],
    },
    "journal_2": {
        "name": "Журнал №2",
        "desc": "Гастрономическое и культурное медиа: открытия, авторские проекты, шефы, напитки",
        "formats": [
            {"id": "news",         "name": "Новость / инфоповод",                    "price": 6000},
            {"id": "project_post", "name": "Публикация о проекте / меню / запуске",  "price": 8000},
            {"id": "author_post",  "name": "Авторский материал / интервью",          "price": 10000},
        ],
    },
    "journal_3": {
        "name": "Журнал №3",
        "desc": "Бизнес- и PR-формат: анонсы, кейсы, запуски, интервью, партнёрские публикации",
        "formats": [
            {"id": "pr_note",       "name": "PR-заметка",                 "price": 5000},
            {"id": "business_post", "name": "Бизнес-материал / кейс",     "price": 8000},
            {"id": "interview",     "name": "Интервью / разбор / колонка", "price": 10000},
        ],
    },
}


def get_media(media_id: str) -> Optional[dict]:
    return MEDIA_CATALOG.get(media_id)


def get_format(media_id: str, format_id: str) -> Optional[dict]:
    media = MEDIA_CATALOG.get(media_id)
    if not media:
        return None
    return next((f for f in media["formats"] if f["id"] == format_id), None)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_lead(
    conn: sqlite3.Connection,
    tg_id,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> sqlite3.Row:
    tg_id = str(tg_id)
    name = " ".join(filter(None, [first_name or "", last_name or ""])).strip() or None
    conn.execute(
        """
        INSERT INTO leads (tg_id, tg_username, tg_name, first_contact_at, last_activity_at, status)
        VALUES (?, ?, ?, datetime('now'), datetime('now'), 'new')
        ON CONFLICT(tg_id) DO UPDATE SET
            tg_username      = excluded.tg_username,
            tg_name          = excluded.tg_name,
            last_activity_at = datetime('now')
        """,
        (tg_id, username, name),
    )
    conn.commit()
    return conn.execute("SELECT * FROM leads WHERE tg_id = ?", (tg_id,)).fetchone()


def get_lead(conn: sqlite3.Connection, tg_id) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM leads WHERE tg_id = ?", (str(tg_id),)
    ).fetchone()


def update_lead(conn: sqlite3.Connection, tg_id, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [str(tg_id)]
    conn.execute(
        f"UPDATE leads SET {set_clause}, last_activity_at = datetime('now') WHERE tg_id = ?",
        values,
    )
    conn.commit()


def save_lead_text(
    conn: sqlite3.Connection, lead_id: int, text: str, tg_message_id: Optional[int]
) -> None:
    conn.execute(
        """
        INSERT INTO lead_messages (lead_id, message_type, text, tg_message_id, created_at)
        VALUES (?, 'text', ?, ?, datetime('now'))
        """,
        (lead_id, text, tg_message_id),
    )
    conn.commit()


def save_lead_file(
    conn: sqlite3.Connection,
    lead_id: int,
    file_type: str,
    tg_file_id: str,
    caption: Optional[str] = None,
    original_filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO lead_files (lead_id, file_type, tg_file_id, caption,
                                original_filename, mime_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (lead_id, file_type, tg_file_id, caption, original_filename, mime_type),
    )
    conn.commit()


def get_materials_summary(conn: sqlite3.Connection, lead_id: int) -> dict:
    txt = conn.execute(
        "SELECT COUNT(*) AS cnt, GROUP_CONCAT(SUBSTR(text, 1, 300), '\n') AS preview "
        "FROM lead_messages WHERE lead_id = ? AND message_type = 'text'",
        (lead_id,),
    ).fetchone()
    files = conn.execute(
        "SELECT file_type, COUNT(*) AS cnt FROM lead_files WHERE lead_id = ? GROUP BY file_type",
        (lead_id,),
    ).fetchall()
    return {
        "text_count": txt["cnt"] if txt else 0,
        "text_preview": (txt["preview"] or "")[:600] if txt else "",
        "files": {row["file_type"]: row["cnt"] for row in (files or [])},
    }


def log_moderation(
    conn: sqlite3.Connection,
    lead_id: int,
    action: str,
    admin_tg_id,
    comment: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO moderation_log (lead_id, action, admin_tg_id, comment, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (lead_id, action, str(admin_tg_id), comment),
    )
    conn.commit()
