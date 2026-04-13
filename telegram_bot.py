import json
import logging
import os
import re
from dataclasses import dataclass

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

from utils.calendar_client import create_google_calendar_event
from utils.linear_client import (
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
- For "add ANT-147 to project Monitoring" use action "update_linear_issue_project".
- If limit is not specified for Linear list actions, use 20.
- If any required field is missing or ambiguous, return:
{"action":"needs_clarification","question":"..."}
"""


@dataclass
class BotConfig:
    telegram_bot_token: str
    telegram_allowed_chat_id: int | None
    gemini_api_key: str
    gemini_model: str


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


def call_gemini_for_action(config: BotConfig, user_message: str) -> dict:
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


def parse_linear_filters(user_message: str, last_issue_id: str | None = None) -> dict | None:
    text = user_message.strip()
    lowered = text.lower()
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
                return {
                    "action": "update_linear_issue_labels",
                    "issue_id": issue_id,
                    "label_names": label_names,
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


def format_linear_teams(teams: list[dict]) -> str:
    if not teams:
        return "No Linear teams found."
    return "Linear teams:\n" + "\n".join(
        f"- {team['key']}: {team['name']} (id: {team['id']})" for team in teams
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
        parsed = parse_linear_filters(
            message.text,
            last_issue_id=get_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
            ),
        ) or call_gemini_for_action(config, message.text)
        action = parsed.get("action")

        if action == "needs_clarification":
            await message.reply_text(parsed.get("question", "I need a bit more detail to schedule that."))
            return

        if action == "create_calendar_event":
            selected_account = get_selected_account(context, update.effective_chat.id if update.effective_chat else None)
            event = create_google_calendar_event(
                title=parsed["title"],
                start=parsed["start"],
                attendees=parsed["attendees"],
                account=selected_account,
            )
            await message.reply_text(
                "Scheduled it.\n"
                f"Account: {ACCOUNT_LABELS.get(event['account'], event['account'])}\n"
                f"Title: {event['title']}\n"
                f"Start: {event['start']}\n"
                f"Attendees: {event['attendee_count']}\n"
                f"Link: {event['link']}"
            )
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
            team = get_linear_team_by_key(parsed["team_key"])
            viewer = get_linear_viewer()
            issue = create_linear_issue(
                team_id=team["id"],
                title=parsed["title"],
                description=parsed.get("description", ""),
                assignee_id=viewer["id"] if parsed.get("assign_to_me") else None,
            )
            await message.reply_text(
                f"Created Linear issue {issue['identifier']} in {team['key']}.\n"
                f"Title: {issue['title']}\n"
                f"Link: {issue['url']}"
            )
            set_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
                issue["identifier"],
            )
            return

        if action == "update_linear_issue_state":
            issue = update_linear_issue_state(
                issue_id=parsed["issue_id"],
                state_name=parsed["state_name"],
            )
            await message.reply_text(
                f"Updated {issue['identifier']} to {issue['state']['name']}.\n"
                f"Title: {issue['title']}\n"
                f"Link: {issue['url']}"
            )
            set_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
                issue["identifier"],
            )
            return

        if action == "update_linear_issue_labels":
            issue = update_linear_issue_labels(
                issue_id=parsed["issue_id"],
                label_names=parsed["label_names"],
            )
            label_text = ", ".join(label["name"] for label in issue["labels"]["nodes"]) or "no labels"
            await message.reply_text(
                f"Updated labels for {issue['identifier']}.\n"
                f"Labels: {label_text}\n"
                f"Link: {issue['url']}"
            )
            set_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
                issue["identifier"],
            )
            return

        if action == "update_linear_issue_project":
            issue = update_linear_issue_project(
                issue_id=parsed["issue_id"],
                project_name=parsed["project_name"],
            )
            project_name = issue["project"]["name"] if issue.get("project") else "No project"
            await message.reply_text(
                f"Updated project for {issue['identifier']}.\n"
                f"Project: {project_name}\n"
                f"Link: {issue['url']}"
            )
            set_last_linear_issue_id(
                context,
                update.effective_chat.id if update.effective_chat else None,
                issue["identifier"],
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
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("accounts", accounts_command))
    application.add_handler(CallbackQueryHandler(account_callback, pattern=r"^select_account:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
