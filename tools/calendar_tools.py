from server import mcp
from utils.calendar_client import (
    authenticate_google_account as authenticate_google_account_impl,
    create_google_calendar_event,
    find_google_calendar_free_slots,
    list_google_calendar_events_for_day,
    list_google_accounts,
)


@mcp.tool()
def authenticate_google_account(account: str) -> str:
    """
    Authenticate and save a Google Calendar token for a named account alias.
    Args:
        account: Alias like "work" or "personal".
    Returns:
        A confirmation message for the connected account alias.
    """
    normalized_account = authenticate_google_account_impl(account)
    return f"Connected Google account alias '{normalized_account}'."


@mcp.tool()
def list_connected_google_accounts() -> str:
    """
    List the saved Google account aliases available for calendar actions.
    Returns:
        A human-readable list of connected account aliases.
    """
    accounts = list_google_accounts()
    if not accounts:
        return "No Google account aliases are connected yet."
    return "Connected Google account aliases: " + ", ".join(accounts)


@mcp.tool()
def create_calendar_event(
    title: str,
    start: str,
    attendees: list[str],
    account: str = "default",
) -> str:
    """
    Create a Google Calendar event on the authenticated user's primary calendar.
    Args:
        title: Event title.
        start: Event start time in ISO 8601 format with timezone.
        attendees: List of attendee email addresses.
        account: Named Google account alias like "work" or "personal".
    Returns:
        A confirmation message describing the created event.
    """
    created_event = create_google_calendar_event(
        title=title,
        start=start,
        attendees=attendees,
        account=account,
    )
    return (
        f"Created Google Calendar event '{created_event['title']}' for {created_event['start']} "
        f"using account '{created_event['account']}' with {created_event['attendee_count']} attendee(s). "
        f"Event ID: {created_event['id']}. "
        f"Calendar Link: {created_event['link']} "
        f"Meet Link: {created_event['meet_link']}"
    )


@mcp.tool()
def list_todays_meetings(account: str = "default") -> str:
    """
    List today's meetings for a connected Google account alias.
    """
    events = list_google_calendar_events_for_day(account=account)
    if not events:
        return f"No meetings found today on account '{account}'."
    lines = [f"Today's meetings for '{account}':"]
    for event in events:
        lines.append(f"- {event['title']}")
        lines.append(f"  {event['start']} -> {event['end']}")
        if event["meet_link"]:
            lines.append(f"  Meet: {event['meet_link']}")
    return "\n".join(lines)


@mcp.tool()
def find_free_slots(day: str = "", duration_minutes: int = 60, account: str = "default") -> str:
    """
    Find open free slots on a given day.
    """
    slots = find_google_calendar_free_slots(day=day or None, duration_minutes=duration_minutes, account=account)
    if not slots:
        return f"No free slots found for {day or 'today'} on account '{account}'."
    lines = [f"Free slots for {day or 'today'} on '{account}':"]
    for slot in slots:
        lines.append(f"- {slot['start']} -> {slot['end']}")
    return "\n".join(lines)
