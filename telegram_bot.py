import json
import logging
import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from utils.calendar_client import create_google_calendar_event


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a scheduling assistant for a Telegram bot.
Extract calendar-event arguments from the user's message.
Return only valid JSON with this exact shape:
{"action":"create_calendar_event","title":"...","start":"ISO-8601 with timezone offset","attendees":["email@example.com"]}
Rules:
- Only return JSON.
- The start value must always include a timezone offset.
- Infer IST as +05:30 when the user says IST.
- If any required field is missing or ambiguous, return:
{"action":"needs_clarification","question":"..."}
"""


@dataclass
class BotConfig:
    telegram_bot_token: str
    telegram_allowed_chat_id: int | None
    gemini_api_key: str
    gemini_model: str


def load_config() -> BotConfig:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    missing = [
        name
        for name, value in [
            ("TELEGRAM_BOT_TOKEN", token),
            ("GEMINI_API_KEY", gemini_api_key),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return BotConfig(
        telegram_bot_token=token,
        telegram_allowed_chat_id=int(chat_id) if chat_id else None,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
    )


def call_gemini_for_event(config: BotConfig, user_message: str) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.gemini_model}:generateContent?key={config.gemini_api_key}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser message:\n{user_message}"}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned an empty response")

    return json.loads(text)


def ensure_authorized(update: Update, config: BotConfig) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    if config.telegram_allowed_chat_id is None:
        return True
    return chat.id == config.telegram_allowed_chat_id


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    await update.effective_message.reply_text(
        "Send me a scheduling message like: schedule Codex Sync at 3pm IST on 2026-04-13 with yash@anthias.xyz"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    message = update.effective_message
    if message is None or not message.text:
        return

    try:
        parsed = call_gemini_for_event(config, message.text)
        action = parsed.get("action")

        if action == "needs_clarification":
            await message.reply_text(parsed.get("question", "I need a bit more detail to schedule that."))
            return

        if action != "create_calendar_event":
            raise ValueError(f"Unexpected Gemini action: {action}")

        event = create_google_calendar_event(
            title=parsed["title"],
            start=parsed["start"],
            attendees=parsed["attendees"],
        )
        await message.reply_text(
            "Scheduled it.\n"
            f"Title: {event['title']}\n"
            f"Start: {event['start']}\n"
            f"Attendees: {event['attendee_count']}\n"
            f"Link: {event['link']}"
        )
    except Exception as exc:
        logger.exception("Failed to handle Telegram message")
        await message.reply_text(f"Could not schedule that yet: {exc}")


def main() -> None:
    config = load_config()
    application = Application.builder().token(config.telegram_bot_token).build()
    application.bot_data["config"] = config
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
