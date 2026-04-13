from datetime import datetime, timedelta
from pathlib import Path
import re
from uuid import uuid4

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
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid4()),
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet",
                },
            }
        },
    }

    created_event = (
        service.events()
        .insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all",
            conferenceDataVersion=1,
        )
        .execute()
    )

    meet_link = created_event.get("hangoutLink", "")
    if not meet_link:
        entry_points = ((created_event.get("conferenceData") or {}).get("entryPoints") or [])
        for entry in entry_points:
            if entry.get("entryPointType") == "video" and entry.get("uri"):
                meet_link = entry["uri"]
                break

    return {
        "account": normalized_account,
        "id": created_event.get("id", "unknown"),
        "link": created_event.get("htmlLink", "no link returned"),
        "meet_link": meet_link or "no Google Meet link returned",
        "title": cleaned_title,
        "start": start_dt.isoformat(),
        "attendee_count": str(len(cleaned_attendees)),
    }


def list_google_calendar_events_for_day(
    day: str | None = None,
    account: str | None = None,
) -> list[dict]:
    normalized_account = normalize_account_name(account)
    credentials = get_google_credentials(normalized_account)
    service = build("calendar", "v3", credentials=credentials)

    if day:
        target_day = datetime.fromisoformat(day).date()
    else:
        target_day = datetime.now().astimezone().date()

    start_of_day = datetime.combine(target_day, datetime.min.time()).astimezone()
    end_of_day = start_of_day + timedelta(days=1)

    events = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    normalized_events = []
    for event in events:
        start_raw = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
        end_raw = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
        normalized_events.append(
            {
                "id": event.get("id", ""),
                "title": event.get("summary", "Untitled"),
                "start": start_raw or "",
                "end": end_raw or "",
                "link": event.get("htmlLink", ""),
                "meet_link": event.get("hangoutLink", ""),
                "attendees": [entry.get("email", "") for entry in event.get("attendees", []) if entry.get("email")],
                "account": normalized_account,
            }
        )
    return normalized_events


def find_google_calendar_free_slots(
    day: str | None = None,
    duration_minutes: int = 60,
    account: str | None = None,
    workday_start_hour: int = 9,
    workday_end_hour: int = 18,
) -> list[dict]:
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")

    if day:
        target_day = datetime.fromisoformat(day).date()
    else:
        target_day = datetime.now().astimezone().date()

    now = datetime.now().astimezone()
    day_start = datetime.combine(target_day, datetime.min.time()).astimezone().replace(
        hour=workday_start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    day_end = day_start.replace(hour=workday_end_hour)
    events = list_google_calendar_events_for_day(day=target_day.isoformat(), account=account)

    busy_ranges = []
    for event in events:
        if "T" not in event["start"] or "T" not in event["end"]:
            continue
        start_dt = parse_start(event["start"])
        end_dt = parse_start(event["end"])
        if end_dt <= day_start or start_dt >= day_end:
            continue
        busy_ranges.append((max(start_dt, day_start), min(end_dt, day_end)))

    busy_ranges.sort(key=lambda item: item[0])
    merged = []
    for start_dt, end_dt in busy_ranges:
        if not merged or start_dt > merged[-1][1]:
            merged.append([start_dt, end_dt])
        else:
            merged[-1][1] = max(merged[-1][1], end_dt)

    slots = []
    cursor = max(day_start, now) if target_day == now.date() else day_start
    for start_dt, end_dt in merged:
        if start_dt - cursor >= timedelta(minutes=duration_minutes):
            slots.append({"start": cursor.isoformat(), "end": start_dt.isoformat()})
        cursor = max(cursor, end_dt)

    if day_end - cursor >= timedelta(minutes=duration_minutes):
        slots.append({"start": cursor.isoformat(), "end": day_end.isoformat()})

    return slots
