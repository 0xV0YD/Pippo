import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from utils.calendar_client import (
    create_google_calendar_event,
    find_google_calendar_free_slots,
    list_google_calendar_events_for_day,
)
from utils.contact_store import (
    add_contact,
    add_group,
    contacts_prompt_block,
    find_group,
    find_contact,
    groups_prompt_block,
    load_contacts,
    load_groups,
    remove_contact,
    remove_group,
)
from utils.linear_client import (
    add_linear_issue_labels,
    assign_linear_issue,
    create_linear_issue,
    filter_linear_issues,
    format_linear_issues_readable,
    get_linear_issue,
    list_linear_labels,
    list_linear_projects,
    get_linear_team_by_key,
    get_linear_viewer,
    list_linear_team_issues,
    list_linear_teams,
    list_my_linear_issues,
    remove_linear_issue_labels,
    update_linear_issue_labels,
    update_linear_issue_project,
    update_linear_issue_state,
)


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ACCOUNT_LABELS = {
    "default": "Personal Yash",
    "work": "Pro Yash",
}


HELP_TEXT = """Pippo quick guide

Calendar
- /start
- /accounts
- list today's meetings
- find free slots today
- find free slots on 2026-04-14 for 30 minutes
- schedule a sync with infra tomorrow at 4pm IST named Infra Sync

Members and groups
- /members
- /showmember akshat
- /addmember Harsh harsh@anthias.xyz harsh
- /removemember harsh
- /groups
- /addgroup infra vasu akshat vansh
- /removegroup infra

Linear
- show my linear orgs
- show my linear issues
- my in progress issues in ANT
- create a linear issue in ANT titled Fix dashboard issue
- assign ANT-147 to akshat
- move ANT-147 to in progress
- add label bug to ANT-147
- remove label bug from ANT-147
- add ANT-147 to project Monitoring

Safety
- risky actions ask for Confirm / Cancel buttons before they run

Tip
- you can use saved member names and group names instead of typing emails every time"""


SYSTEM_PROMPT = """You are an assistant for a Telegram bot that can help with Google Calendar and Linear.
Return only valid JSON.
Supported JSON shapes:
{"action":"create_calendar_event","title":"...","start":"ISO-8601 with timezone offset","attendees":["email@example.com"]}
{"action":"list_linear_orgs"}
{"action":"list_my_linear_assigned_issues","limit":20}
{"action":"list_linear_issues","team_key":"ENG","limit":20}
{"action":"create_linear_issue","team_key":"ENG","title":"...","description":"...","assign_to_me":true}
{"action":"update_linear_issue_state","issue_id":"ANT-147","state_name":"In Progress"}
{"action":"list_linear_projects"}
{"action":"list_linear_labels"}
{"action":"update_linear_issue_labels","issue_id":"ANT-147","label_names":["Bug","Urgent"]}
{"action":"update_linear_issue_project","issue_id":"ANT-147","project_name":"Monitoring"}
{"action":"add_linear_issue_labels","issue_id":"ANT-147","label_names":["Bug"]}
{"action":"remove_linear_issue_labels","issue_id":"ANT-147","label_names":["Bug"]}
{"action":"assign_linear_issue","issue_id":"ANT-147","assignee":"akshat@anthias.xyz"}
{"action":"list_todays_meetings"}
{"action":"find_free_slots","day":"2026-04-13","duration_minutes":60}
Rules:
- Only return JSON.
- The start value must always include a timezone offset.
- Infer IST as +05:30 when the user says IST.
- For "my orgs", "my linear orgs", or "show teams", use action "list_linear_orgs".
- For "my issues" in Linear, use action "list_my_linear_assigned_issues".
- For "list issues in ORG" use action "list_linear_issues" and extract the team key.
- For "create a linear issue" use action "create_linear_issue".
- For "move ANT-147 to In Progress" or "change ANT-147 to Done" use action "update_linear_issue_state".
- For "show linear projects" use action "list_linear_projects".
- For "show linear labels" use action "list_linear_labels".
- For "add label Bug to ANT-147" use action "update_linear_issue_labels".
- For "remove label Bug from ANT-147" use action "remove_linear_issue_labels".
- For "add ANT-147 to project Monitoring" use action "update_linear_issue_project".
- For "assign ANT-147 to Akshat" use action "assign_linear_issue".
- For "list today's meetings" use action "list_todays_meetings".
- For "find free slots today" use action "find_free_slots".
- If limit is not specified for Linear list actions, use 20.
- If any required field is missing or ambiguous, return:
{"action":"needs_clarification","question":"..."}
"""


@dataclass
class BotConfig:
    telegram_bot_token: str
    telegram_allowed_chat_id: int | None
    telegram_allowed_username: str
    ai_provider: str
    gemini_api_key: str
    gemini_model: str
    openai_api_key: str
    openai_model: str


LINEAR_STATE_ALIASES = {
    "todo": "Todo",
    "backlog": "Backlog",
    "in progress": "In Progress",
    "progress": "In Progress",
    "in review": "In Review",
    "review": "In Review",
    "done": "Done",
    "canceled": "Canceled",
    "cancelled": "Canceled",
}


def get_account_selector_markup(selected_account: str | None = None) -> InlineKeyboardMarkup:
    keyboard = []
    for alias, label in ACCOUNT_LABELS.items():
        prefix = "Active: " if alias == selected_account else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"select_account:{alias}")])
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_markup(action_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Confirm", callback_data=f"confirm_action:{action_id}"),
                InlineKeyboardButton("Cancel", callback_data=f"cancel_action:{action_id}"),
            ]
        ]
    )


def get_selected_account(context: ContextTypes.DEFAULT_TYPE, chat_id: int | None) -> str:
    if chat_id is None:
        return "default"
    selected_accounts = context.application.bot_data.setdefault("selected_accounts", {})
    return selected_accounts.get(chat_id, "default")


def set_selected_account(context: ContextTypes.DEFAULT_TYPE, chat_id: int, account: str) -> None:
    selected_accounts = context.application.bot_data.setdefault("selected_accounts", {})
    selected_accounts[chat_id] = account


def get_last_linear_issue_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int | None) -> str | None:
    if chat_id is None:
        return None
    last_issue_ids = context.application.bot_data.setdefault("last_linear_issue_ids", {})
    return last_issue_ids.get(chat_id)


def set_last_linear_issue_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int | None, issue_id: str) -> None:
    if chat_id is None:
        return
    last_issue_ids = context.application.bot_data.setdefault("last_linear_issue_ids", {})
    last_issue_ids[chat_id] = issue_id


def get_pending_actions(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.application.bot_data.setdefault("pending_actions", {})


def load_config() -> BotConfig:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    allowed_username = os.getenv("TELEGRAM_ALLOWED_USERNAME", "OxVoyd").strip().lstrip("@")
    ai_provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    missing = [
        name
        for name, value in [
            ("TELEGRAM_BOT_TOKEN", token),
        ]
        if not value
    ]
    if ai_provider == "gemini" and not gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if ai_provider == "openai" and not openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return BotConfig(
        telegram_bot_token=token,
        telegram_allowed_chat_id=int(chat_id) if chat_id else None,
        telegram_allowed_username=allowed_username,
        ai_provider=ai_provider,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
    )


def call_gemini_for_action(config: BotConfig, user_message: str) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.gemini_model}:generateContent?key={config.gemini_api_key}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{contacts_prompt_block()}\n{groups_prompt_block()}\n\nUser message:\n{user_message}"}],
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


def raise_for_status_with_body(response: requests.Response, provider_name: str) -> None:
    if response.ok:
        return
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    raise ValueError(f"{provider_name} API error ({response.status_code}): {payload}")


def extract_openai_text(payload: dict) -> str:
    if payload.get("output_text"):
        return payload["output_text"]

    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    return "".join(parts).strip()


def call_openai_for_action(config: BotConfig, user_message: str) -> dict:
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {config.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.openai_model,
            "instructions": SYSTEM_PROMPT,
            "input": f"Return JSON only.\n{contacts_prompt_block()}\n{groups_prompt_block()}\n\nUser message:\n{user_message}",
            "text": {
                "format": {
                    "type": "json_object"
                }
            },
        },
        timeout=60,
    )
    raise_for_status_with_body(response, "OpenAI")
    payload = response.json()
    text = extract_openai_text(payload)
    if not text:
        raise ValueError("OpenAI returned an empty response")
    return json.loads(text)


def call_ai_for_action(config: BotConfig, user_message: str) -> dict:
    if config.ai_provider == "openai":
        try:
            return call_openai_for_action(config, user_message)
        except Exception as exc:
            if config.gemini_api_key and any(
                marker in str(exc).lower()
                for marker in ["429", "insufficient_quota", "rate limit", "quota"]
            ):
                logger.warning("OpenAI failed, falling back to Gemini: %s", exc)
                return call_gemini_for_action(config, user_message)
            raise
    if config.ai_provider == "gemini":
        return call_gemini_for_action(config, user_message)
    raise ValueError(f"Unsupported AI_PROVIDER: {config.ai_provider}")


def parse_linear_filters(user_message: str, last_issue_id: str | None = None) -> dict | None:
    text = user_message.strip()
    lowered = text.lower()

    if any(phrase in lowered for phrase in ["today's meetings", "todays meetings", "list today's meetings", "list todays meetings"]):
        return {"action": "list_todays_meetings"}

    if "free slot" in lowered or "free time" in lowered:
        day_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        duration_match = re.search(r"\b(\d+)\s*(minute|min|minutes|mins|hour|hours)\b", lowered)
        duration_minutes = 60
        if duration_match:
            quantity = int(duration_match.group(1))
            unit = duration_match.group(2)
            duration_minutes = quantity * 60 if "hour" in unit else quantity
        return {
            "action": "find_free_slots",
            "day": day_match.group(1) if day_match else "",
            "duration_minutes": duration_minutes,
        }

    if re.search(r"\b[A-Z]{2,10}-\d+\b", text):
        has_linear_signal = True
    else:
        has_linear_signal = False

    if (
        "linear" not in lowered
        and "issue" not in lowered
        and "issues" not in lowered
        and "org" not in lowered
        and not has_linear_signal
    ):
        return None

    if any(phrase in lowered for phrase in ["my linear orgs", "show my linear orgs", "show linear orgs", "linear orgs"]):
        return {"action": "list_linear_orgs"}

    if any(phrase in lowered for phrase in ["linear projects", "show projects", "list projects"]):
        return {"action": "list_linear_projects"}

    if any(phrase in lowered for phrase in ["linear labels", "show labels", "list labels"]):
        return {"action": "list_linear_labels"}

    team_key = None
    try:
        teams = list_linear_teams()
    except Exception:
        teams = []

    for team in teams:
        team_name = team["name"].strip().lower()
        team_alias = team["key"].strip().lower()
        if re.search(rf"\b{re.escape(team_alias)}\b", lowered) or team_name in lowered:
            team_key = team["key"].upper()
            break

    limit_match = re.search(r"\b(\d+)\s+(?:issues|tickets)\b", lowered)
    limit = int(limit_match.group(1)) if limit_match else 20

    state_filters = []
    for alias, canonical in LINEAR_STATE_ALIASES.items():
        if alias in lowered and canonical not in state_filters:
            state_filters.append(canonical)

    issue_id_match = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
    issue_id = issue_id_match.group(1).upper() if issue_id_match else None
    if issue_id is None and "this issue" in lowered:
        issue_id = last_issue_id

    only_mine = any(phrase in lowered for phrase in ["only my", "only mine", "my issues", "assigned to me", "mine"])

    if issue_id and state_filters and any(word in lowered for word in ["change", "move", "update", "set", "label", "status", "state"]):
        target_state = state_filters[0]
        to_match = re.search(r"\bto\s+([a-z ]+)$", lowered)
        if to_match:
            to_segment = to_match.group(1).strip()
            for alias, canonical in LINEAR_STATE_ALIASES.items():
                if alias in to_segment:
                    target_state = canonical
                    break
        return {
            "action": "update_linear_issue_state",
            "issue_id": issue_id,
            "state_name": target_state,
        }

    if issue_id and any(word in lowered for word in ["label", "labels"]):
        label_match = re.search(r"\blabels?\s+(.+?)(?:\s+(?:to|for|on)\s+|$)", text, re.IGNORECASE)
        if label_match:
            raw_labels = label_match.group(1)
            label_names = [part.strip().strip('"').strip("'") for part in re.split(r",| and ", raw_labels) if part.strip()]
            if label_names:
                action_name = "update_linear_issue_labels"
                if "remove label" in lowered or "remove labels" in lowered:
                    action_name = "remove_linear_issue_labels"
                elif "add label" in lowered or "add labels" in lowered:
                    action_name = "add_linear_issue_labels"
                return {
                    "action": action_name,
                    "issue_id": issue_id,
                    "label_names": label_names,
                }

    if issue_id and any(word in lowered for word in ["assign", "assignee"]):
        assignee_match = re.search(r"\bassign(?:\s+(?:it|issue))?\s+(?:to\s+)?(.+)$", text, re.IGNORECASE)
        if assignee_match:
            return {
                "action": "assign_linear_issue",
                "issue_id": issue_id,
                "assignee": assignee_match.group(1).strip().strip('"').strip("'"),
            }

    if issue_id and "project" in lowered:
        project_match = re.search(r"\bproject\s+(.+)$", text, re.IGNORECASE)
        if project_match:
            return {
                "action": "update_linear_issue_project",
                "issue_id": issue_id,
                "project_name": project_match.group(1).strip().strip('"').strip("'"),
            }

    if "create" in lowered and "issue" in lowered:
        title_match = (
            re.search(r'\b(?:heading|title)\s+"([^"]+)"', text, re.IGNORECASE)
            or re.search(r"\b(?:heading|title)\s+'([^']+)'", text, re.IGNORECASE)
            or re.search(r"\b(?:heading|title)\s+(.+?)(?:\s+and\s+|\s+description\s+|$)", text, re.IGNORECASE)
            or re.search(r"\bissue\s+(?:called|named)\s+(.+?)(?:\s+and\s+|\s+description\s+|$)", text, re.IGNORECASE)
        )
        description_match = re.search(r"\bdescription\s+(.+)$", text, re.IGNORECASE)
        assign_to_me = "assign it to me" in lowered or "assign to me" in lowered or "for me" in lowered
        if team_key and title_match:
            return {
                "action": "create_linear_issue",
                "team_key": team_key,
                "title": title_match.group(1).strip().strip('"').strip("'"),
                "description": description_match.group(1).strip() if description_match else "",
                "assign_to_me": assign_to_me,
            }
        return {
            "action": "needs_clarification",
            "question": "I can create that Linear issue, but I need both the team and the issue title. Example: create a linear issue in ANT titled Fix dashboard issue",
        }

    if (
        "my issues" in lowered
        or "assigned to me" in lowered
        or "only my" in lowered
        or "only mine" in lowered
        or ("my" in lowered and "issues" in lowered)
    ):
        return {
            "action": "list_my_linear_assigned_issues",
            "team_key": team_key,
            "limit": limit,
            "state_filters": state_filters,
        }

    if (
        "list issues" in lowered
        or "show issues" in lowered
        or "team issues" in lowered
        or "tickets" in lowered
        or "issues in" in lowered
    ):
        if team_key:
            return {
                "action": "list_linear_issues",
                "team_key": team_key,
                "limit": limit,
                "state_filters": state_filters,
                "only_mine": only_mine,
            }

    return None


def ensure_authorized(update: Update, config: BotConfig) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat is None:
        return False
    if user is None:
        return False

    username = (user.username or "").strip().lstrip("@").lower()
    allowed_username = config.telegram_allowed_username.strip().lstrip("@").lower()
    if allowed_username and username != allowed_username:
        return False

    if config.telegram_allowed_chat_id is not None and chat.id != config.telegram_allowed_chat_id:
        return False

    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    chat_id = update.effective_chat.id if update.effective_chat else None
    selected_account = get_selected_account(context, chat_id)
    await update.effective_message.reply_text(
        "Choose which calendar account should be active for upcoming tasks, then send a scheduling message.",
        reply_markup=get_account_selector_markup(selected_account),
    )
    await update.effective_message.reply_text(
        f"Current account: {ACCOUNT_LABELS[selected_account]}\n"
        "Example: schedule Codex Sync at 3pm IST on 2026-04-13 with yash@anthias.xyz"
    )


async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    chat_id = update.effective_chat.id if update.effective_chat else None
    selected_account = get_selected_account(context, chat_id)
    await update.effective_message.reply_text(
        "Select the calendar account to use for upcoming tasks:",
        reply_markup=get_account_selector_markup(selected_account),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return
    await update.effective_message.reply_text(HELP_TEXT)


async def members_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    contacts = load_contacts()
    if not contacts:
        await update.effective_message.reply_text("No members saved yet.")
        return

    lines = ["Saved members:"]
    for contact in contacts:
        aliases = ", ".join(contact.get("aliases", []))
        lines.append(f"- {contact['name']} <{contact['email']}> aliases: {aliases}")
    await update.effective_message.reply_text("\n".join(lines))


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    groups = load_groups()
    if not groups:
        await update.effective_message.reply_text("No groups saved yet.")
        return

    lines = ["Saved groups:"]
    for group in groups:
        members = ", ".join(group.get("members", []))
        lines.append(f"- {group['name']}: {members}")
    await update.effective_message.reply_text("\n".join(lines))


async def show_member_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /showmember alias_or_email")
        return

    contact = find_contact(context.args[0])
    if not contact:
        await update.effective_message.reply_text(f"Member '{context.args[0]}' not found.")
        return

    aliases = ", ".join(contact.get("aliases", [])) or "none"
    await update.effective_message.reply_text(
        f"Member: {contact['name']}\nEmail: {contact['email']}\nAliases: {aliases}"
    )


async def add_member_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    args = context.args
    if len(args) < 2:
        await update.effective_message.reply_text("Usage: /addmember Name email@example.com [alias1,alias2]")
        return

    name = args[0]
    email = args[1]
    aliases = args[2].split(",") if len(args) > 2 else [name.lower()]
    try:
        contact = add_contact(name=name, email=email, aliases=aliases)
        await update.effective_message.reply_text(
            f"Added member {contact['name']} <{contact['email']}> aliases: {', '.join(contact['aliases'])}"
        )
    except Exception as exc:
        await update.effective_message.reply_text(str(exc))


async def remove_member_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /removemember email_or_alias")
        return

    try:
        contact = remove_contact(context.args[0])
        await update.effective_message.reply_text(f"Removed member {contact['name']} <{contact['email']}>")
    except Exception as exc:
        await update.effective_message.reply_text(str(exc))


async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /addgroup group_name member1 member2 member3")
        return

    group_name = context.args[0]
    members = [member.strip() for member in re.split(r"[,\s]+", " ".join(context.args[1:])) if member.strip()]
    try:
        group = add_group(group_name, members)
        await update.effective_message.reply_text(f"Added group {group['name']}: {', '.join(group['members'])}")
    except Exception as exc:
        await update.effective_message.reply_text(str(exc))


async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /removegroup group_name")
        return

    try:
        group = remove_group(context.args[0])
        await update.effective_message.reply_text(f"Removed group {group['name']}")
    except Exception as exc:
        await update.effective_message.reply_text(str(exc))


async def account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await query.answer("This bot is not authorized for this chat.", show_alert=True)
        return

    data = query.data or ""
    if not data.startswith("select_account:"):
        await query.answer()
        return

    selected_account = data.split(":", 1)[1]
    chat_id = query.message.chat_id if query.message else None
    if chat_id is None or selected_account not in ACCOUNT_LABELS:
        await query.answer("Unknown account.", show_alert=True)
        return

    set_selected_account(context, chat_id, selected_account)
    await query.answer(f"Using {ACCOUNT_LABELS[selected_account]}")
    await query.edit_message_text(
        f"Selected account: {ACCOUNT_LABELS[selected_account]}",
        reply_markup=get_account_selector_markup(selected_account),
    )


async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    data = query.data or ""
    if not (data.startswith("confirm_action:") or data.startswith("cancel_action:")):
        await query.answer()
        return

    action_id = data.split(":", 1)[1]
    pending_actions = get_pending_actions(context)
    spec = pending_actions.get(action_id)
    if not spec:
        await query.answer("This action expired.", show_alert=True)
        return

    if data.startswith("cancel_action:"):
        pending_actions.pop(action_id, None)
        await query.answer("Cancelled")
        await query.edit_message_text("Cancelled.")
        return

    try:
        chat_id = query.message.chat_id if query.message else None
        if chat_id is None:
            raise ValueError("Missing chat for confirmation")
        result_text = await execute_pending_action(context, chat_id, spec)
        pending_actions.pop(action_id, None)
        await query.answer("Done")
        await query.edit_message_text(f"{query.message.text}\n\nConfirmed.")
        await context.bot.send_message(chat_id=chat_id, text=result_text)
    except Exception as exc:
        pending_actions.pop(action_id, None)
        await query.answer("Failed", show_alert=True)
        if query.message:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Action failed: {exc}")


def format_linear_teams(teams: list[dict]) -> str:
    if not teams:
        return "No Linear teams found."
    return "Linear teams:\n" + "\n".join(
        f"- {team['key']}: {team['name']} (id: {team['id']})" for team in teams
    )


def format_calendar_events_readable(events: list[dict], heading: str) -> str:
    if not events:
        return f"{heading}\nNo meetings found."
    lines = [heading]
    for event in events:
        lines.append(f"- {event['title']}")
        lines.append(f"  {event['start']} -> {event['end']}")
        if event.get("attendees"):
            lines.append(f"  Attendees: {', '.join(event['attendees'])}")
        if event.get("meet_link"):
            lines.append(f"  Meet: {event['meet_link']}")
    return "\n".join(lines)


def resolve_attendee_tokens(attendees: list[str]) -> list[str]:
    resolved = []
    seen = set()
    for attendee in attendees:
        token = attendee.strip()
        if not token:
            continue
        group = find_group(token)
        if group:
            for email in group["members"]:
                if email not in seen:
                    seen.add(email)
                    resolved.append(email)
            continue
        contact = find_contact(token)
        if contact:
            if contact["email"] not in seen:
                seen.add(contact["email"])
                resolved.append(contact["email"])
            continue
        if "@" in token and token not in seen:
            seen.add(token)
            resolved.append(token)
    return resolved


def create_pending_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int | None, spec: dict) -> str:
    if chat_id is None:
        raise ValueError("Chat is required for pending actions")
    action_id = f"{chat_id}:{len(get_pending_actions(context)) + 1}:{int(datetime.now().timestamp())}"
    get_pending_actions(context)[action_id] = spec
    return action_id


def build_confirmation_text(spec: dict) -> str:
    action = spec["action"]
    payload = spec["payload"]
    if action == "create_calendar_event":
        return (
            "Confirm meeting creation?\n"
            f"Account: {ACCOUNT_LABELS.get(payload['account'], payload['account'])}\n"
            f"Title: {payload['title']}\n"
            f"Start: {payload['start']}\n"
            f"Attendees: {', '.join(payload['attendees'])}"
        )
    if action == "create_linear_issue":
        return f"Confirm Linear issue creation?\nTeam: {payload['team_key']}\nTitle: {payload['title']}"
    if action == "update_linear_issue_state":
        return f"Confirm moving {payload['issue_id']} to {payload['state_name']}?"
    if action in {"update_linear_issue_labels", "add_linear_issue_labels", "remove_linear_issue_labels"}:
        verb = {
            "update_linear_issue_labels": "replace labels on",
            "add_linear_issue_labels": "add labels to",
            "remove_linear_issue_labels": "remove labels from",
        }[action]
        return f"Confirm {verb} {payload['issue_id']}?\nLabels: {', '.join(payload['label_names'])}"
    if action == "update_linear_issue_project":
        return f"Confirm adding {payload['issue_id']} to project {payload['project_name']}?"
    if action == "assign_linear_issue":
        return f"Confirm assigning {payload['issue_id']} to {payload['assignee']}?"
    return "Confirm this action?"


async def execute_pending_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int, spec: dict) -> str:
    action = spec["action"]
    payload = spec["payload"]
    if action == "create_calendar_event":
        event = create_google_calendar_event(
            title=payload["title"],
            start=payload["start"],
            attendees=payload["attendees"],
            account=payload["account"],
        )
        return (
            "Scheduled it.\n"
            f"Account: {ACCOUNT_LABELS.get(event['account'], event['account'])}\n"
            f"Title: {event['title']}\n"
            f"Start: {event['start']}\n"
            f"Attendees: {event['attendee_count']}\n"
            f"Calendar Link: {event['link']}\n"
            f"Meet Link: {event['meet_link']}"
        )
    if action == "create_linear_issue":
        team = get_linear_team_by_key(payload["team_key"])
        viewer = get_linear_viewer()
        issue = create_linear_issue(
            team_id=team["id"],
            title=payload["title"],
            description=payload.get("description", ""),
            assignee_id=viewer["id"] if payload.get("assign_to_me") else None,
        )
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Created Linear issue {issue['identifier']} in {team['key']}.\nTitle: {issue['title']}\nLink: {issue['url']}"
    if action == "update_linear_issue_state":
        issue = update_linear_issue_state(issue_id=payload["issue_id"], state_name=payload["state_name"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Updated {issue['identifier']} to {issue['state']['name']}.\nTitle: {issue['title']}\nLink: {issue['url']}"
    if action == "update_linear_issue_labels":
        issue = update_linear_issue_labels(issue_id=payload["issue_id"], label_names=payload["label_names"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Updated labels for {issue['identifier']}.\nLabels: {', '.join(label['name'] for label in issue['labels']['nodes']) or 'no labels'}\nLink: {issue['url']}"
    if action == "add_linear_issue_labels":
        issue = add_linear_issue_labels(issue_id=payload["issue_id"], label_names=payload["label_names"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Added labels for {issue['identifier']}.\nLabels: {', '.join(label['name'] for label in issue['labels']['nodes']) or 'no labels'}\nLink: {issue['url']}"
    if action == "remove_linear_issue_labels":
        issue = remove_linear_issue_labels(issue_id=payload["issue_id"], label_names=payload["label_names"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Removed labels for {issue['identifier']}.\nLabels: {', '.join(label['name'] for label in issue['labels']['nodes']) or 'no labels'}\nLink: {issue['url']}"
    if action == "update_linear_issue_project":
        issue = update_linear_issue_project(issue_id=payload["issue_id"], project_name=payload["project_name"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Updated project for {issue['identifier']}.\nProject: {(issue.get('project') or {}).get('name', 'No project')}\nLink: {issue['url']}"
    if action == "assign_linear_issue":
        issue = assign_linear_issue(issue_id=payload["issue_id"], assignee_token=payload["assignee"])
        set_last_linear_issue_id(context, chat_id, issue["identifier"])
        return f"Assigned {issue['identifier']} to {(issue.get('assignee') or {}).get('name', 'Unknown')}.\nLink: {issue['url']}"
    raise ValueError(f"Unknown pending action: {action}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: BotConfig = context.application.bot_data["config"]
    if not ensure_authorized(update, config):
        await update.effective_message.reply_text("This bot is not authorized for this chat.")
        return

    message = update.effective_message
    if message is None or not message.text:
        return

    try:
        parsed = parse_linear_filters(
            message.text,
            last_issue_id=get_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
            ),
        ) or call_ai_for_action(config, message.text)
        action = parsed.get("action")

        if action == "needs_clarification":
            await message.reply_text(parsed.get("question", "I need a bit more detail to schedule that."))
            return

        if action == "create_calendar_event":
            selected_account = get_selected_account(context, update.effective_chat.id if update.effective_chat else None)
            attendees = resolve_attendee_tokens(parsed["attendees"])
            if not attendees:
                raise ValueError("I could not resolve any attendees from that request.")
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {
                    "action": "create_calendar_event",
                    "payload": {
                        "title": parsed["title"],
                        "start": parsed["start"],
                        "attendees": attendees,
                        "account": selected_account,
                    },
                },
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "list_todays_meetings":
            selected_account = get_selected_account(context, update.effective_chat.id if update.effective_chat else None)
            events = list_google_calendar_events_for_day(account=selected_account)
            await message.reply_text(
                format_calendar_events_readable(
                    events,
                    heading=f"Today's meetings on {ACCOUNT_LABELS.get(selected_account, selected_account)}:",
                )
            )
            return

        if action == "find_free_slots":
            selected_account = get_selected_account(context, update.effective_chat.id if update.effective_chat else None)
            slots = find_google_calendar_free_slots(
                day=parsed.get("day") or None,
                duration_minutes=int(parsed.get("duration_minutes", 60)),
                account=selected_account,
            )
            if not slots:
                await message.reply_text("No free slots found.")
            else:
                lines = [f"Free slots on {ACCOUNT_LABELS.get(selected_account, selected_account)}:"]
                for slot in slots:
                    lines.append(f"- {slot['start']} -> {slot['end']}")
                await message.reply_text("\n".join(lines))
            return

        if action == "list_linear_orgs":
            viewer = get_linear_viewer()
            teams = list_linear_teams()
            await message.reply_text(
                f"Linear viewer: {viewer['name']} <{viewer['email']}>\n" + format_linear_teams(teams)
            )
            return

        if action == "list_linear_projects":
            projects = list_linear_projects()
            if not projects:
                await message.reply_text("No Linear projects found.")
            else:
                await message.reply_text(
                    "Linear projects:\n" + "\n".join(f"- {p['name']}\n  {p['url']}" for p in projects)
                )
            return

        if action == "list_linear_labels":
            labels = list_linear_labels()
            if not labels:
                await message.reply_text("No Linear labels found.")
            else:
                await message.reply_text(
                    "Linear labels:\n"
                    + "\n".join(
                        f"- {label['name']} [{(label.get('team') or {}).get('key', 'workspace')}]"
                        for label in labels
                    )
                )
            return

        if action == "list_my_linear_assigned_issues":
            issues = list_my_linear_issues(limit=max(int(parsed.get("limit", 20)), 50))
            filtered = filter_linear_issues(
                issues,
                team_key=parsed.get("team_key"),
                state_names=parsed.get("state_filters"),
                limit=int(parsed.get("limit", 20)),
            )
            heading = "Your Linear issues:"
            if parsed.get("team_key"):
                heading = f"Your Linear issues in {parsed['team_key'].upper()}:"
            await message.reply_text(format_linear_issues_readable(filtered, heading=heading))
            if filtered:
                set_last_linear_issue_id(
                    context,
                    update.effective_chat.id if update.effective_chat else None,
                    filtered[0]["identifier"],
                )
            return

        if action == "list_linear_issues":
            team_key = parsed["team_key"]
            viewer = get_linear_viewer()
            issues = list_linear_team_issues(team_key=team_key, limit=max(int(parsed.get("limit", 20)), 50))
            filtered = filter_linear_issues(
                issues,
                only_mine=bool(parsed.get("only_mine")),
                viewer_name=viewer["name"],
                state_names=parsed.get("state_filters"),
                limit=int(parsed.get("limit", 20)),
            )
            heading = f"Linear issues in {team_key.upper()}:"
            if parsed.get("only_mine"):
                heading = f"Your Linear issues in {team_key.upper()}:"
            await message.reply_text(format_linear_issues_readable(filtered, heading=heading))
            if filtered:
                set_last_linear_issue_id(
                    context,
                    update.effective_chat.id if update.effective_chat else None,
                    filtered[0]["identifier"],
                )
            return

        if action == "create_linear_issue":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "create_linear_issue", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "update_linear_issue_state":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "update_linear_issue_state", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "update_linear_issue_labels":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "update_linear_issue_labels", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "add_linear_issue_labels":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "add_linear_issue_labels", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "remove_linear_issue_labels":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "remove_linear_issue_labels", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "update_linear_issue_project":
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "update_linear_issue_project", "payload": parsed},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        if action == "assign_linear_issue":
            payload = dict(parsed)
            contact = find_contact(payload["assignee"])
            if contact:
                payload["assignee"] = contact["email"]
            action_id = create_pending_action(
                context,
                update.effective_chat.id if update.effective_chat else None,
                {"action": "assign_linear_issue", "payload": payload},
            )
            await message.reply_text(
                build_confirmation_text(get_pending_actions(context)[action_id]),
                reply_markup=get_confirmation_markup(action_id),
            )
            return

        raise ValueError(f"Unexpected Gemini action: {action}")
    except Exception as exc:
        logger.exception("Failed to handle Telegram message")
        await message.reply_text(f"Could not schedule that yet: {exc}")


def main() -> None:
    config = load_config()
    application = Application.builder().token(config.telegram_bot_token).build()
    application.bot_data["config"] = config
    application.bot_data["selected_accounts"] = {}
    application.bot_data["last_linear_issue_ids"] = {}
    application.bot_data["pending_actions"] = {}
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("accounts", accounts_command))
    application.add_handler(CommandHandler("members", members_command))
    application.add_handler(CommandHandler("groups", groups_command))
    application.add_handler(CommandHandler("showmember", show_member_command))
    application.add_handler(CommandHandler("addmember", add_member_command))
    application.add_handler(CommandHandler("removemember", remove_member_command))
    application.add_handler(CommandHandler("addgroup", add_group_command))
    application.add_handler(CommandHandler("removegroup", remove_group_command))
    application.add_handler(CallbackQueryHandler(account_callback, pattern=r"^select_account:"))
    application.add_handler(CallbackQueryHandler(action_callback, pattern=r"^(confirm_action|cancel_action):"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
