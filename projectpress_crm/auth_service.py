import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple

from config import AUTH_TOKEN_LIFETIME, ADMIN_IDS
from db import connect


def _format_code(code_str: str) -> str:
    """Format a code string as AUTH-XXXXXX"""
    return f"AUTH-{code_str[:6].upper()}"


def _generate_code() -> str:
    """Generate a random 6-digit code"""
    code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return code


def _generate_session_id() -> str:
    """Generate a secure session ID"""
    return secrets.token_urlsafe(32)


def create_auth_code() -> str:
    """Create a new authentication code and store it in DB"""
    conn = connect()
    try:
        code = _generate_code()
        formatted = _format_code(code)
        expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

        conn.execute(
            """
            INSERT INTO auth_codes (code, confirmed, expires_at)
            VALUES (?, 0, ?)
            """,
            (formatted, expires_at),
        )
        conn.commit()
        return formatted
    finally:
        conn.close()


def confirm_auth_code(code: str, telegram_id: int) -> bool:
    """Confirm an auth code with a telegram_id (called by the bot when user sends /auth code)"""
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, expires_at FROM auth_codes
            WHERE code = ? AND confirmed = 0
            """,
            (code,),
        ).fetchone()

        if not row:
            return False

        # Check if not expired
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires_at:
            return False

        # Mark as confirmed
        conn.execute(
            "UPDATE auth_codes SET telegram_id = ?, confirmed = 1 WHERE id = ?",
            (str(telegram_id), row["id"]),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def validate_and_create_session(code: str, admin_ids_list: list) -> Optional[str]:
    """
    Validate the code was confirmed by bot, check if telegram_id is admin,
    and create a session. Returns session_id or None.
    """
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT telegram_id, expires_at FROM auth_codes
            WHERE code = ? AND confirmed = 1
            """,
            (code,),
        ).fetchone()

        if not row:
            return None

        # Check if not expired
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires_at:
            return None

        telegram_id = int(row["telegram_id"])

        # Check if user is admin
        if telegram_id not in admin_ids_list:
            return None

        # Get user info from users table
        user_row = conn.execute(
            "SELECT username, full_name FROM users WHERE telegram_id = ?",
            (str(telegram_id),),
        ).fetchone()

        username = (user_row["username"] or "") if user_row else str(telegram_id)
        full_name = (user_row["full_name"] or "") if user_row else ""

        # Create session
        session_id = _generate_session_id()
        session_expires = (datetime.utcnow() + timedelta(seconds=AUTH_TOKEN_LIFETIME)).isoformat()

        conn.execute(
            """
            INSERT INTO auth_sessions (session_id, telegram_id, username, full_name, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, str(telegram_id), username, full_name, session_expires),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_session_user(session_id: str) -> Optional[dict]:
    """Get user info from a valid session ID"""
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT telegram_id, username, full_name, expires_at
            FROM auth_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        if not row:
            return None

        # Check if not expired
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires_at:
            # Delete expired session
            conn.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return None

        return {
            "telegram_id": row["telegram_id"],
            "username": row["username"],
            "full_name": row["full_name"],
        }
    finally:
        conn.close()


def invalidate_session(session_id: str) -> None:
    """Delete a session (logout)"""
    conn = connect()
    try:
        conn.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def cleanup_expired() -> None:
    """Clean up expired auth codes and sessions"""
    conn = connect()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute("DELETE FROM auth_codes WHERE expires_at < ?", (now,))
        conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
        conn.commit()
    finally:
        conn.close()
