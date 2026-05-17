"""
Cancel or reschedule Google Calendar appointments from plain English.
"""

import re

from services.calendar.auth import google_calendar_ready
from services.calendar.client import list_events_for_period, update_event_start
from services.calendar.delete import (
    CALENDAR_PENDING_DELETE_KEY,
    clear_pending_calendar_delete,
    execute_pending_calendar_delete,
    format_delete_confirm_prompt,
    parse_calendar_delete_name,
    parse_calendar_delete_number,
    request_calendar_delete_by_name,
    request_calendar_delete_confirmation,
    resolve_calendar_event_by_number,
    save_calendar_list_context,
)
from services.calendar.format import format_event_summary, format_events
from services.reminders.cancel import _parse_number_token
from services.reminders.parser import parse_when

CALENDAR_PENDING_RESCHEDULE_KEY = "calendar_pending_reschedule"

_MODIFY_VERBS = re.compile(
    r"\b(?:cancel|delete|remove|reschedule|move|change|push\s+back)\b",
    re.IGNORECASE,
)
_CALENDAR_NOUNS = re.compile(
    r"\b(?:appointment|appointments|meeting|meetings|event|events|calendar)\b",
    re.IGNORECASE,
)

_RESCHEDULE_WITH_NUM = re.compile(
    r"\b(?:reschedule|move|change|push\s+back)\b"
    r".{0,50}?"
    r"(?:appointment|meeting|event|calendar)?s?\s*#?\s*"
    r"(\d+|[a-z]+)\b"
    r".{0,15}?\b(?:to|for|at)\b\s+(.+)$",
    re.IGNORECASE,
)

_RESCHEDULE_NUM_TO = re.compile(
    r"\b(?:appointment|meeting|event)\s*#?\s*(\d+|[a-z]+)\b"
    r".{0,15}?\b(?:to|for|at)\b\s+(.+)$",
    re.IGNORECASE,
)

_CONFIRM = re.compile(
    r"^(?:yes|y|confirm|ok|do\s+it)\s*\.?$",
    re.IGNORECASE,
)
_ABORT = re.compile(
    r"^(?:no|n|cancel|stop|never\s*mind|nevermind)\s*\.?$",
    re.IGNORECASE,
)


def _setup_message() -> str:
    return (
        "Google Calendar is not connected yet.\n\n"
        "1. Put credentials/google_credentials.json on the Pi\n"
        "2. Run: python scripts/google_calendar_auth.py\n"
        "3. Restart Jarvis"
    )


def wants_calendar_modify(text: str) -> bool:
    """
    True if the user wants to cancel or reschedule a calendar event.

    Does not match reminder-only requests.
    """
    lowered = text.lower()
    if not _MODIFY_VERBS.search(text):
        return False
    if "reminder" in lowered and not _CALENDAR_NOUNS.search(text):
        return False
    if _CALENDAR_NOUNS.search(text) or "calendar" in lowered:
        return True
    if re.search(r"\b(?:reschedule|move)\b", lowered):
        return True
    return False


def parse_calendar_reschedule(text: str) -> tuple[int, str] | None:
    """
    Return (event_number, new_when_text) for reschedule requests.

    Examples:
    - reschedule appointment #2 to Friday 3pm
    - move meeting 1 to tomorrow at noon
    """
    lowered = text.lower()
    if "reminder" in lowered and not _CALENDAR_NOUNS.search(text):
        return None
    if not re.search(r"\b(?:reschedule|move|change|push\s+back)\b", lowered):
        return None

    for pattern in (_RESCHEDULE_WITH_NUM, _RESCHEDULE_NUM_TO):
        match = pattern.search(text.strip())
        if match:
            number = _parse_number_token(match.group(1))
            when_text = match.group(2).strip()
            if number and when_text:
                return number, when_text

    return None


def _calendar_list_with_hints(user_data: dict, intro: str) -> str:
    events = list_events_for_period("today")
    save_calendar_list_context(user_data, events)
    return (
        f"{intro}\n\n"
        f"{format_events(events, 'today')}\n\n"
        "Examples:\n"
        "• cancel appointment #2\n"
        "• reschedule appointment #2 to Friday 3pm\n"
        "• /caldel 2  or  /calmove 2 Friday 3pm"
    )


def format_reschedule_confirm_prompt(
    event: dict, number: int, when_text: str, new_start
) -> str:
    summary = format_event_summary(event)
    new_time = new_start.strftime("%a %b %d, %I:%M %p")
    return (
        f"Reschedule calendar event #{number}?\n\n"
        f"Currently:\n{summary}\n\n"
        f"New time: {new_time}\n"
        f"(parsed from: {when_text})\n\n"
        "Reply yes to confirm, or cancel to keep the current time."
    )


def request_calendar_reschedule_confirmation(
    user_data: dict,
    number: int,
    when_text: str,
    period: str = "today",
) -> str:
    """Stage a reschedule — nothing changes until confirmed."""
    clear_pending_calendar_delete(user_data)

    event = resolve_calendar_event_by_number(user_data, number, period)
    new_start = parse_when(when_text)

    user_data[CALENDAR_PENDING_RESCHEDULE_KEY] = {
        "number": number,
        "event_id": event["id"],
        "summary": event.get("summary", "Calendar event"),
        "when_text": when_text,
        "new_start_iso": new_start.isoformat(),
        "period": period,
    }
    return format_reschedule_confirm_prompt(event, number, when_text, new_start)


def execute_pending_calendar_reschedule(user_data: dict) -> str:
    pending = user_data.get(CALENDAR_PENDING_RESCHEDULE_KEY)
    if not pending:
        raise ValueError("No reschedule waiting for confirmation.")

    number = pending["number"]
    event_id = pending["event_id"]
    name = pending.get("summary", "Event")
    new_start = parse_when(pending["when_text"])

    update_event_start(event_id, new_start)
    user_data.pop(CALENDAR_PENDING_RESCHEDULE_KEY, None)

    return (
        f"Rescheduled calendar #{number}:\n{name}\n"
        f"New time: {new_start.strftime('%a %b %d, %I:%M %p')}"
    )


def clear_pending_calendar_reschedule(user_data: dict) -> None:
    user_data.pop(CALENDAR_PENDING_RESCHEDULE_KEY, None)


def handle_calendar_pending_reply(text: str, user_data: dict) -> str | None:
    """Handle yes/cancel for pending delete or reschedule."""
    pending_delete = user_data.get(CALENDAR_PENDING_DELETE_KEY)
    pending_reschedule = user_data.get(CALENDAR_PENDING_RESCHEDULE_KEY)

    if not pending_delete and not pending_reschedule:
        return None

    if _CONFIRM.match(text.strip()):
        if pending_reschedule:
            try:
                return execute_pending_calendar_reschedule(user_data)
            except Exception:
                clear_pending_calendar_reschedule(user_data)
                raise
        try:
            return execute_pending_calendar_delete(user_data)
        except Exception:
            clear_pending_calendar_delete(user_data)
            raise

    if _ABORT.match(text.strip()):
        if pending_reschedule:
            number = pending_reschedule["number"]
            name = pending_reschedule.get("summary", "Event")
            clear_pending_calendar_reschedule(user_data)
            return f"Kept original time for #{number}:\n{name}"
        number = pending_delete["number"]
        name = pending_delete.get("summary", "Event")
        clear_pending_calendar_delete(user_data)
        return f"Kept on calendar #{number}:\n{name}"

    return None


def handle_calendar_modify(user_text: str, user_data: dict) -> str | None:
    """
    Cancel, delete, or reschedule calendar events.

    Returns a reply string, or None if this is not a calendar modify request.
    """
    reschedule = parse_calendar_reschedule(user_text)
    delete_num = parse_calendar_delete_number(user_text)
    delete_name = parse_calendar_delete_name(user_text)
    is_modify = wants_calendar_modify(user_text)

    if not reschedule and delete_num is None and delete_name is None and not is_modify:
        return None

    if not google_calendar_ready():
        return _setup_message()

    if reschedule:
        number, when_text = reschedule
        return request_calendar_reschedule_confirmation(
            user_data, number, when_text
        )

    if delete_num is not None:
        clear_pending_calendar_reschedule(user_data)
        return request_calendar_delete_confirmation(user_data, delete_num)

    if delete_name is not None:
        clear_pending_calendar_reschedule(user_data)
        return request_calendar_delete_by_name(user_data, delete_name)

    if is_modify:
        if re.search(r"\b(?:reschedule|move|change)\b", user_text, re.I):
            intro = "Which appointment should I reschedule? Include the new time."
        else:
            intro = "Which appointment should I cancel or delete?"
        return _calendar_list_with_hints(user_data, intro)

    return None
