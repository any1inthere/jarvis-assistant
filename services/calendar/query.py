"""
Detect plain-English calendar questions and commands.
"""

import re

from config.settings import openai_configured
from services.calendar.auth import google_calendar_ready
from services.calendar.client import (
    create_event,
    list_events_for_date,
    list_events_for_period,
)
from services.calendar.dates import format_date_label, parse_appointment_list_date
from services.calendar.delete import save_calendar_list_context
from services.calendar.extract import extract_calendar_event
from services.calendar.format import format_events
from services.intent import wants_appointment_action, wants_appointment_list
from services.reminders.parser import parse_when

CALENDAR_LIST = re.compile(
    r"\b("
    r"(?:what.?s|show|see|check|list|view).{0,30}(?:calendar|schedule|appointments)"
    r"|(?:calendar|schedule|appointments).{0,20}(?:today|tomorrow|this\s+week|week)"
    r")\b",
    re.IGNORECASE,
)

CALENDAR_ADD = re.compile(
    r"\b("
    r"(?:add|create|put)\s+.{0,40}(?:to\s+)?(?:my\s+)?calendar"
    r"|\bschedule\b.{0,30}(?:to\s+)?(?:my\s+)?calendar"
    r"|\b(?:schedule|set|book)\b.{0,30}(?:an?\s+)?(?:appointment|meeting)"
    r"|(?:add|create).{0,20}(?:an?\s+)?(?:appointment|meeting).{0,20}calendar"
    r")\b",
    re.IGNORECASE,
)

_CALENDAR_MODIFY_VERBS = re.compile(
    r"\b(?:cancel|delete|remove|reschedule|move|change|push\s+back)\b",
    re.IGNORECASE,
)

# "schedule estimate Friday 2pm" — verb + title + day/time (no "calendar" required)
CALENDAR_ADD_LOOSE = re.compile(
    r"^(?:please\s+)?(?:schedule|book|set)\s+.+"
    r"\b(?:"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mon|tue|wed|thu|fri|sat|sun|tomorrow|today|next\s+week"
    r")\b",
    re.IGNORECASE,
)

_WHEN_ANCHOR = re.compile(
    r"\b("
    r"(?:next\s+)?(?:"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mon|tue|wed|thu|fri|sat|sun|tomorrow|today"
    r")"
    r"(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?"
    r")\b",
    re.IGNORECASE,
)

_SCHEDULE_VERB = re.compile(
    r"^(?:please\s+)?(schedule|book|set|add)\s+",
    re.IGNORECASE,
)

_GENERIC_EVENT_TITLES = frozenset(
    {"appointment", "meeting", "event", "appt", "call"}
)


def _setup_message() -> str:
    return (
        "Google Calendar is not connected yet.\n\n"
        "1. Put credentials/google_credentials.json on the Pi\n"
        "2. Run: python scripts/google_calendar_auth.py\n"
        "3. Restart Jarvis"
    )


def detect_list_period(text: str) -> str | None:
    """Return today, tomorrow, week — None if not a relative list request."""
    if not CALENDAR_LIST.search(text) and not wants_appointment_list(text):
        return None

    lowered = text.lower()
    if parse_appointment_list_date(text):
        return None
    if "tomorrow" in lowered:
        return "tomorrow"
    if "today" in lowered:
        return "today"
    if "week" in lowered:
        return "week"
    if wants_appointment_list(text):
        return "today"
    return "today"


def parse_simple_calendar_add(text: str) -> tuple[str, str] | None:
    """
    Rule-based parse for: schedule estimate Friday 2pm

    Returns (title, when_text) or None.
    """
    if not _SCHEDULE_VERB.match(text.strip()):
        return None

    rest = _SCHEDULE_VERB.sub("", text.strip(), count=1).strip()
    match = _WHEN_ANCHOR.search(rest)
    if not match:
        return None

    when_text = match.group(1).strip()
    title = rest[: match.start()].strip()
    title = re.sub(
        r"^(?:an?\s+)?(?:appointment|meeting|event)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    if not title or not when_text:
        return None
    return title, when_text


def wants_calendar_add(text: str) -> bool:
    from services.intent import wants_reminder_action

    if wants_appointment_list(text) or detect_list_period(text):
        return False
    if wants_reminder_action(text):
        return False
    if not wants_appointment_action(text) and not CALENDAR_ADD.search(text):
        if not CALENDAR_ADD_LOOSE.search(text.strip()) and not parse_simple_calendar_add(text):
            return False
    lowered = text.lower()
    if "remind me" in lowered or re.search(r"\bset\s+(?:a\s+)?reminder\b", lowered):
        return False
    if _CALENDAR_MODIFY_VERBS.search(text):
        return False
    if parse_calendar_delete_wants(text):
        return False
    if CALENDAR_ADD.search(text):
        return True
    if CALENDAR_ADD_LOOSE.search(text.strip()):
        return True
    if parse_simple_calendar_add(text):
        return True
    return wants_appointment_action(text)


def parse_calendar_delete_wants(text: str) -> bool:
    """True if user wants to remove a calendar event (not a reminder)."""
    from services.calendar.delete import (
        parse_calendar_delete_name,
        parse_calendar_delete_number,
    )

    if parse_calendar_delete_number(text) is not None:
        return True
    if parse_calendar_delete_name(text) is not None:
        return True
    return False


async def handle_calendar_list(user_text: str, user_data: dict) -> str | None:
    """If user asked to see calendar, return formatted numbered events."""
    specific = parse_appointment_list_date(user_text)
    period = detect_list_period(user_text)

    if specific is None and period is None:
        return None

    if not google_calendar_ready():
        return _setup_message()

    if specific is not None:
        events = list_events_for_date(specific)
        label = format_date_label(specific)
        save_calendar_list_context(
            user_data,
            events,
            list_period="date",
            list_date=specific.isoformat(),
        )
        return format_events(events, label)

    titles = {"today": "today", "tomorrow": "tomorrow", "week": "next 7 days"}
    events = list_events_for_period(period)
    save_calendar_list_context(user_data, events, list_period=period)
    return format_events(events, titles.get(period, period))


async def handle_calendar_add(user_text: str) -> str | None:
    """If user asked to add a calendar event, create it."""
    if not wants_calendar_add(user_text):
        return None

    if not google_calendar_ready():
        return _setup_message()

    when_text: str | None = None
    title: str | None = None

    simple = parse_simple_calendar_add(user_text)
    if simple:
        simple_title, simple_when = simple
        if simple_title.lower() not in _GENERIC_EVENT_TITLES:
            title, when_text = simple_title, simple_when

    if not when_text or not title:
        if not openai_configured():
            return (
                "I couldn't parse that phrase without OpenAI.\n\n"
                "Book on Google Calendar without OpenAI:\n"
                "/caladd Friday 3pm | Call customer\n\n"
                "Or fix the key on the Pi:\n"
                "nano ~/jarvis-assistant/.env\n"
                "sudo systemctl restart jarvis"
            )
        wants, when_text, title = await extract_calendar_event(user_text)
        if not wants or not when_text or not title:
            return (
                "I couldn't understand the appointment.\n"
                "Try: schedule estimate Friday 2pm\n"
                "Or: /caladd Friday 3pm | Call customer"
            )

    start = parse_when(when_text)
    event = create_event(title, start)
    link = event.get("htmlLink", "")
    reply = (
        f"Added to Google Calendar:\n{title}\n"
        f"{start.strftime('%a %b %d, %I:%M %p')}"
    )
    if link:
        reply += f"\n{link}"
    return reply
