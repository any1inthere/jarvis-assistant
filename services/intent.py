"""
Route messages to reminders (Telegram pings) vs appointments (Google Calendar).
"""

import re

# Reminders = Jarvis reminder list, not on Google Calendar.
REMINDER_ACTION = re.compile(
    r"\b("
    r"remind(?:\s+me)?(?:\s+to)?"
    r"|reminder"
    r"|ping\s+me"
    r"|nudge\s+me"
    r"|set\s+(?:a\s+)?reminder"
    r")\b",
    re.IGNORECASE,
)

# Appointments = Google Calendar events.
APPOINTMENT_ACTION = re.compile(
    r"\b("
    r"appointments?"
    r"|meetings?"
    r"|my\s+calendar"
    r"|on\s+(?:my\s+)?calendar"
    r"|to\s+(?:my\s+)?calendar"
    r"|book\s+(?:an?\s+)?(?:appointment|estimate|meeting)"
    r"|schedule\s+(?:an?\s+)?(?:appointment|estimate|meeting)"
    r")\b",
    re.IGNORECASE,
)

APPOINTMENT_LIST = re.compile(
    r"\b("
    r"(?:show|list|see|view|check|what(?:'s|s|\s+is)?).{0,45}"
    r"(?:all\s+)?(?:my\s+)?(?:appointments?|meetings?|calendar|schedule)"
    r"|(?:appointments?|meetings?|calendar).{0,25}(?:for|on)\s+\w"
    r")\b",
    re.IGNORECASE,
)


def wants_reminder_action(text: str) -> bool:
    """User wants a Telegram reminder (not a calendar event)."""
    lowered = text.lower()
    if not REMINDER_ACTION.search(text):
        return False
    # "remind me about my appointment" → list/calendar, not a new reminder.
    if "remind me about" in lowered or "remind me of my" in lowered:
        return False
    if APPOINTMENT_ACTION.search(text) and not re.search(
        r"\bremind\s+me\s+to\b", lowered
    ):
        return False
    return True


def wants_appointment_action(text: str) -> bool:
    """User wants something on Google Calendar."""
    if wants_appointment_list(text):
        return False
    if APPOINTMENT_ACTION.search(text):
        return True
    # "schedule estimate Friday 2pm" — no word "appointment" but clearly booking.
    if re.match(
        r"^(?:please\s+)?(?:schedule|book|set)\s+",
        text.strip(),
        re.IGNORECASE,
    ):
        if REMINDER_ACTION.search(text) and "remind me to" in text.lower():
            return False
        return True
    return False


def wants_appointment_list(text: str) -> bool:
    """User wants to see calendar appointments (not the reminder list)."""
    from services.reminders.list_query import wants_reminder_list

    if wants_reminder_list(text):
        return False
    return bool(APPOINTMENT_LIST.search(text))
