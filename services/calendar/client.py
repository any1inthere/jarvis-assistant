"""
Talk to Google Calendar API.
"""

from datetime import date, datetime, timedelta

from googleapiclient.discovery import build

from config.settings import get_timezone, now_local
from services.calendar.auth import get_google_credentials


def _service():
    return build("calendar", "v3", credentials=get_google_credentials())


def _to_rfc3339(when: datetime) -> str:
    """RFC3339 time for the Calendar API list endpoint."""
    return when.astimezone(get_timezone()).isoformat()


def _google_event_time(when: datetime) -> dict:
    """Start/end time for creating events (timezone + local time, no offset)."""
    local = when.astimezone(get_timezone())
    return {
        "dateTime": local.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": str(get_timezone()),
    }


def list_events_between(start: datetime, end: datetime, max_results: int = 15) -> list[dict]:
    """Return calendar events between two times."""
    service = _service()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=_to_rfc3339(start),
            timeMax=_to_rfc3339(end),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def list_events_for_period(period: str) -> list[dict]:
    """
    period: 'today', 'tomorrow', or 'week'
    """
    now = now_local()
    today = now.date()

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:  # week
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

    return list_events_between(start, end)


def list_events_for_date(target: date, max_results: int = 25) -> list[dict]:
    """Return all events on a specific calendar day."""
    tz = get_timezone()
    start = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=tz)
    end = start + timedelta(days=1)
    return list_events_between(start, end, max_results=max_results)


def create_event(title: str, start: datetime, duration_minutes: int = 30) -> dict:
    """Add an event to your primary Google Calendar."""
    end = start + timedelta(minutes=duration_minutes)

    body = {
        "summary": title,
        "start": _google_event_time(start),
        "end": _google_event_time(end),
    }

    service = _service()
    return service.events().insert(calendarId="primary", body=body).execute()


def _event_duration(event: dict) -> timedelta:
    """How long the event lasts (default 30 minutes)."""
    start = event.get("start", {})
    end = event.get("end", {})
    if "dateTime" in start and "dateTime" in end:
        start_dt = datetime.fromisoformat(start["dateTime"])
        end_dt = datetime.fromisoformat(end["dateTime"])
        duration = end_dt - start_dt
        if duration.total_seconds() > 0:
            return duration
    return timedelta(minutes=30)


def update_event_start(event_id: str, start: datetime) -> dict:
    """Move an event to a new start time (keeps the same duration)."""
    service = _service()
    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    if "date" in event.get("start", {}) and "dateTime" not in event.get("start", {}):
        raise ValueError("All-day events cannot be rescheduled from Telegram yet.")

    duration = _event_duration(event)
    end = start + duration
    event["start"] = _google_event_time(start)
    event["end"] = _google_event_time(end)

    return (
        service.events()
        .patch(calendarId="primary", eventId=event_id, body=event)
        .execute()
    )


def delete_event(event_id: str) -> None:
    """Remove an event from your primary Google Calendar."""
    service = _service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
