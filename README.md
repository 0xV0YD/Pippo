# Google Calendar MCP Setup

Place your Google OAuth desktop client JSON at:

`credentials/google_oauth_client.json`

The first successful `create_calendar_event(...)` call will open a browser for Google sign-in and then save the token at:

`credentials/google_token.json`

# Telegram Bot Setup

Copy `.env.example` to `.env` and fill in:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_ID`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (optional, defaults to `gemini-2.5-flash`)

Then run:

`uv run python telegram_bot.py`

# Docker Setup

Run the Telegram bot with Docker:

`make up`

Stop it:

`make down`

See logs:

`make logs`

Notes:

- Fill in `.env` before starting.
- Keep `credentials/google_oauth_client.json` present on the host.
- `credentials/google_token.json` is persisted through the mounted `credentials/` folder.
