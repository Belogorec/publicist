## Quick Start - Telegram Auth

### 1️⃣ Set Environment Variables

Add to `.env`:
```bash
ADMIN_IDS=your_telegram_id,other_admin_ids
SESSION_SECRET_KEY=generate-random-32-char-string
CRM_API_URL=http://localhost:5002
```

Get your Telegram ID: Send `/start` to bot, it shows in messages as `<code>123456789</code>`

### 2️⃣ Initialize Database

```bash
cd projectpress/projectpress_crm
python init_db.py
```

### 3️⃣ Start Services

**Terminal 1 - CRM:**
```bash
cd projectpress/projectpress_crm
python flask_app.py
```

**Terminal 2 - Bot:**
```bash
cd projectpress
python flask_app.py
```

### 4️⃣ Test Login

1. Open `http://localhost:5002`
2. Click "Получить код для входа" → Copy code
3. Send to bot: `/auth AUTH-XXXXXX`
4. Bot replies: "✅ Код подтвережен!"
5. Click "Проверить и войти"
6. ✅ You're in!

### ✨ That's it!

The CRM is now protected - only admins with valid codes can log in via Telegram.

**All routes protected:**
- `/` - Applications list
- `/applications/*` - Details, edit, download
- Everything except API endpoints

**Autologout:**
- Sessions expire after 24h
- Click "Выход" to logout anytime
- Expired codes/sessions auto-deleted

### 🔒 Security Checklist

- [ ] `ADMIN_IDS` contains your Telegram ID
- [ ] `SESSION_SECRET_KEY` is set to randomvalue (not default)
- [ ] `CRM_API_URL` matches your bot/CRM domains
- [ ] In production: Use HTTPS and strong secret key
- [ ] In production: Use long session timeout

### 📚 Full Docs

See `projectpress/projectpress_crm/AUTH.md` for complete documentation.
