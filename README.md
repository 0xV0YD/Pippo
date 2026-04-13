# Google Calendar MCP Setup

Place your default Google OAuth desktop client JSON at:

`credentials/google_oauth_client_default.json`

The first successful `create_calendar_event(...)` call will open a browser for Google sign-in and then save the token at:

`credentials/google_token_default.json`

For multiple accounts, use named aliases and separate client and token files:

- `credentials/google_oauth_client_default.json`
- `credentials/google_oauth_client_work.json`
- `credentials/google_oauth_client_personal.json`
- `credentials/google_token_default.json`
- `credentials/google_token_work.json`
- `credentials/google_token_personal.json`

You can connect an additional account by authenticating a named alias such as `work` or `personal`, then pass that alias to `create_calendar_event(..., account="work")`.

# Telegram Bot Setup

Copy `.env.example` to `.env` and fill in:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_ID`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (optional, defaults to `gemini-2.5-flash`)

Then run:

`uv run python telegram_bot.py`

The bot now shows account-selection buttons and remembers the active calendar per chat:

- `Personal Yash` maps to account alias `default`
- `Pro Yash` maps to account alias `work`

Use `/start` or `/accounts` to switch the active account before sending a scheduling request.

# Docker Setup

Run the Telegram bot with Docker:

`make up`

Stop it:

`make down`

See logs:

`make logs`

Notes:

- Fill in `.env` before starting.
- Keep your `credentials/google_oauth_client_<alias>.json` files present on the host.
- `credentials/google_token_<alias>.json` files are persisted through the mounted `credentials/` folder.
