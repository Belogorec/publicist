import os
import sqlite3

# Локально: ./data/projectpress.db
# На Railway: задайте DB_PATH=/data/projectpress.db (volume смонтирован в /data)
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "projectpress.db"))


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id               TEXT    NOT NULL UNIQUE,
            tg_username         TEXT,
            tg_name             TEXT,
            first_contact_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            last_activity_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            status              TEXT    NOT NULL DEFAULT 'new',
            selected_media      TEXT,
            selected_format     TEXT,
            agreed_price        INTEGER,
            source              TEXT,
            manager_comment     TEXT
        );

        CREATE TABLE IF NOT EXISTS lead_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER NOT NULL REFERENCES leads(id),
            message_type    TEXT    NOT NULL DEFAULT 'text',
            text            TEXT,
            tg_message_id   INTEGER,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lead_files (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id             INTEGER NOT NULL REFERENCES leads(id),
            file_type           TEXT    NOT NULL,
            tg_file_id          TEXT,
            original_filename   TEXT,
            mime_type           TEXT,
            caption             TEXT,
            storage_path        TEXT,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS moderation_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER NOT NULL REFERENCES leads(id),
            action          TEXT    NOT NULL,
            admin_tg_id     TEXT,
            comment         TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
