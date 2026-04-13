from datetime import datetime, timedelta
from pathlib import Path
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKENS_DIR = Path(__file__).resolve().parent.parent / "credentials"
DEFAULT_ACCOUNT = "default"


def parse_start(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("start must include a timezone offset, for example 2026-04-15T11:00:00+05:30")
    return parsed


def normalize_account_name(account: str | None) -> str:
    raw = (account or DEFAULT_ACCOUNT).strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-")
    if not normalized:
        raise ValueError("account must contain at least one letter or number")
    return normalized


def get_token_file(account: str | None = None) -> Path:
    normalized_account = normalize_account_name(account)
    return TOKENS_DIR / f"google_token_{normalized_account}.json"


def get_client_file(account: str | None = None) -> Path:
    normalized_account = normalize_account_name(account)
    return TOKENS_DIR / f"google_oauth_client_{normalized_account}.json"


def list_google_accounts() -> list[str]:
    accounts = []
    for token_file in sorted(TOKENS_DIR.glob("google_token_*.json")):
        account = token_file.stem.removeprefix("google_token_")
        if account:
            accounts.append(account)
    return accounts


def get_google_credentials(account: str | None = None) -> Credentials:
    creds = None
    normalized_account = normalize_account_name(account)
    token_file = get_token_file(normalized_account)
    client_file = get_client_file(normalized_account)

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not client_file.exists():
        raise FileNotFoundError(
            f"Google OAuth client file not found for account '{normalized_account}'. "
            f"Put it at credentials/google_oauth_client_{normalized_account}.json"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def authenticate_google_account(account: str) -> str:
    normalized_account = normalize_account_name(account)
    get_google_credentials(normalized_account)
    return normalized_account


def create_google_calendar_event(
    title: str,
    start: str,
    attendees: list[str],
    account: str | None = None,
) -> dict[str, str]:
    cleaned_title = title.strip()
    if not cleaned_title:
        raise ValueError("title must not be empty")

    start_dt = parse_start(start)
    cleaned_attendees = [attendee.strip() for attendee in attendees if attendee.strip()]
    normalized_account = normalize_account_name(account)

    credentials = get_google_credentials(normalized_account)
    service = build("calendar", "v3", credentials=credentials)

    event_body = {
        "summary": cleaned_title,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": (start_dt + timedelta(hours=1)).isoformat()},
        "attendees": [{"email": attendee} for attendee in cleaned_attendees],
    }

    created_event = (
        service.events()
        .insert(calendarId="primary", body=event_body, sendUpdates="all")
        .execute()
    )

    return {
        "account": normalized_account,
        "id": created_event.get("id", "unknown"),
        "link": created_event.get("htmlLink", "no link returned"),
        "title": cleaned_title,
        "start": start_dt.isoformat(),
        "attendee_count": str(len(cleaned_attendees)),
    }
