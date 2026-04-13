from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = Path(__file__).resolve().parent.parent / "credentials" / "google_oauth_client.json"
TOKEN_FILE = Path(__file__).resolve().parent.parent / "credentials" / "google_token.json"


def parse_start(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("start must include a timezone offset, for example 2026-04-15T11:00:00+05:30")
    return parsed


def get_google_credentials() -> Credentials:
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "Google OAuth client file not found. Put it at credentials/google_oauth_client.json"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def create_google_calendar_event(title: str, start: str, attendees: list[str]) -> dict[str, str]:
    cleaned_title = title.strip()
    if not cleaned_title:
        raise ValueError("title must not be empty")

    start_dt = parse_start(start)
    cleaned_attendees = [attendee.strip() for attendee in attendees if attendee.strip()]

    credentials = get_google_credentials()
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
        "id": created_event.get("id", "unknown"),
        "link": created_event.get("htmlLink", "no link returned"),
        "title": cleaned_title,
        "start": start_dt.isoformat(),
        "attendee_count": str(len(cleaned_attendees)),
    }
