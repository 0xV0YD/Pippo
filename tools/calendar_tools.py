from server import mcp
from utils.calendar_client import create_google_calendar_event


@mcp.tool()
def create_calendar_event(title: str, start: str, attendees: list[str]) -> str:
    """
    Create a Google Calendar event on the authenticated user's primary calendar.
    Args:
        title: Event title.
        start: Event start time in ISO 8601 format with timezone.
        attendees: List of attendee email addresses.
    Returns:
        A confirmation message describing the created event.
    """
    created_event = create_google_calendar_event(title=title, start=start, attendees=attendees)
    return (
        f"Created Google Calendar event '{created_event['title']}' for {created_event['start']} "
        f"with {created_event['attendee_count']} attendee(s). Event ID: {created_event['id']}. "
        f"Link: {created_event['link']}"
    )
