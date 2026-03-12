# Telegram Authentication for projectpress_crm

## Overview

The CRM now supports authentication via Telegram with admin status verification. Only Telegram users in the `ADMIN_IDS` list can log in.

## How It Works

### 1. Authentication Flow

1. User visits CRM at `https://crm.example.com/` (or configured URL)
2. User is redirected to login page (`/login`)
3. User clicks "Получить код для входа" (Get login code)
4. Server generates a unique code (e.g., `AUTH-ABC123`) valid for 10 minutes
5. User opens the bot and sends: `/auth AUTH-ABC123`
6. Bot verifies that the user is an admin and confirms the code via CRM API
7. User returns to CRM and clicks "Проверить и войти" (Verify and log in)
8. CRM creates a session and user is logged in
9. Session lasts for 24 hours (configurable via `AUTH_TOKEN_LIFETIME`)

### 2. Bot Command

The bot recognizes the `/auth <code>` command:
- Checks if the user is in `ADMIN_IDS`
- Calls CRM API endpoint `/api/auth/confirm-code` with the code
- Sends feedback to the user

### 3. Configuration

Add these environment variables:

```bash
# Comma-separated list of admin Telegram user IDs
ADMIN_IDS=123456789,987654321

# Session configuration
SESSION_SECRET_KEY=your-secret-key-here  # Change this in production!
AUTH_TOKEN_LIFETIME=86400                # Session lifetime in seconds (1 day)

# For bot to call CRM
CRM_API_URL=https://crm.example.com      # CRM base URL
BOT_TOKEN=...                             # Already configured
```

## Database Tables

### `auth_codes`
Stores pending authentication codes:
- `code` - Unique code like "AUTH-ABC123"
- `telegram_id` - Telegram ID after code is confirmed
- `confirmed` - 0 = pending, 1 = confirmed by bot
- `expires_at` - When code expires (10 minutes)

### `auth_sessions`
Stores active user sessions:
- `session_id` - Secure random session ID (stored in HTTP-only cookie)
- `telegram_id` - Telegram user ID
- `username` - Telegram username
- `full_name` - User's full name
- `expires_at` - Session expiration time

## API Endpoints

### `GET /login`
Login page. Shows code request form or code confirmation form.

### `POST /request-auth-code`
Generate a new authentication code.
- Returns: Redirect to `/login?code=AUTH-XXXXXX`

### `POST /confirm-auth-code`
Validate code and create session.
- Body: `code` (form parameter)
- Returns: Redirect to `/` if success, or back to `/login` with error

### `GET /logout`
Destroy session and redirect to login.

### `POST /api/auth/confirm-code`
**Internal API** - Called by bot to confirm authentication code.
- Method: `POST`
- Auth: `bot_token` parameter must match `BOT_TOKEN`
- Body (JSON):
  ```json
  {
    "code": "AUTH-ABC123",
    "telegram_id": 123456789,
    "bot_token": "..."
  }
  ```
- Response (success):
  ```json
  {
    "ok": true
  }
  ```
- Response (error):
  ```json
  {
    "ok": false,
    "error": "invalid_or_expired_code"
  }
  ```

## User Experience

### For Admin Users

1. Open the CRM
2. See login page with "Получить код для входа" button
3. Click button → get code like `AUTH-ABC123`
4. Open Telegram bot
5. Send: `/auth AUTH-ABC123`
6. Bot responds: "✅ Код подтвержден!"
7. Return to CRM
8. Click "Проверить и войти"
9. Logged in! See username and "Выход" button in sidebar

### For Non-Admin Users

1. Open CRM
2. See login page
3. Click button → get code
4. Send code to bot
5. Bot responds: "❌ У вас нет доступа к CRM"
6. Cannot access CRM

## Security Features

- **Session cookies**: HTTP-only, Secure, SameSite=Strict
- **Code expiration**: Codes valid for 10 minutes only
- **API authentication**: Bot token required for code confirmation
- **Admin check**: Only users in `ADMIN_IDS` can authenticate
- **Session timeout**: Sessions expire after configured time (default 24h)

## Cleanup

Old auth codes and sessions are automatically cleaned up when they expire. You can manually trigger cleanup by calling the internal `cleanup_expired()` function.

## Troubleshooting

### "Код не подтвёрден ботом или истёк"
- Code might have expired (10 minute limit)
- User might not be in `ADMIN_IDS`
- Bot API call might have failed

### "У вас нет доступа к CRM"
- User's Telegram ID is not in `ADMIN_IDS` config
- Check the ID matches exactly

### Session not persisting
- Check `SESSION_SECRET_KEY` is set
- Check cookies are enabled in browser
- Check `SECURE` flag if using HTTPS

## Development Notes

- Auth logic is in `auth_service.py`
- Login UI is in `templates/login.html`
- Flask app integration in `flask_app.py` (routes and decorator)
- Bot integration in `tg_handlers.py` (handle_auth function)
- DB tables created automatically on app startup
