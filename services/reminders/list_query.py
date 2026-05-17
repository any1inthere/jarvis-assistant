"""
Understand "show my reminders for this week" and filter the list.
"""

import re
from datetime import datetime, timedelta

from config.settings import get_timezone, now_local
from services.reminders.format import format_reminder_list
from services.reminders.store import (
    LIST_IDS_KEY,
    Reminder,
    list_upcoming,
    save_list_context,
)

# User wants to see reminders, not set one.
LIST_REQUEST = re.compile(
    r"\b("
    r"(?:show|list|see|view|check).{0,40}reminders?"
    r"|what\s+reminders?"
    r"|reminders?\s+(?:for|today|this\s+week|this\s+month)"
    r")\b",
    re.IGNORECASE,
)


def wants_reminder_list(text: str) -> bool:
    """True if the user is asking to see reminders (not calendar appointments)."""
    lowered = text.lower()
    if "remind me" in lowered or "set a reminder" in lowered:
        return False
    if re.search(r"\b(?:appointments?|meetings?|calendar|schedule)\b", lowered):
        if "reminder" not in lowered:
            return False
    return bool(LIST_REQUEST.search(text))


def detect_period(text: str) -> str:
    """
    Which time range to show: today, week, month, or all.

    Returns one of: 'today', 'week', 'month', 'all'
    """
    lowered = text.lower()

    if re.search(r"\btoday\b", lowered):
        return "today"
    if re.search(r"\bthis month\b|\bfor (?:the )?month\b", lowered):
        return "month"
    if re.search(r"\bthis week\b|\bfor (?:the )?week\b", lowered):
        return "week"

    return "all"


def _due_date(item: Reminder) -> datetime:
    return datetime.fromisoformat(item.due_at).astimezone(get_timezone())


def filter_by_period(items: list[Reminder], period: str) -> list[Reminder]:
    """Keep only reminders in today / this week / this month."""
    now = now_local()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    filtered: list[Reminder] = []
    for item in items:
        due_date = _due_date(item).date()

        if period == "today" and due_date == today:
            filtered.append(item)
        elif period == "week" and week_start <= due_date <= week_end:
            filtered.append(item)
        elif period == "month" and due_date.year == today.year and due_date.month == today.month:
            filtered.append(item)
        elif period == "all":
            filtered.append(item)

    return filtered


_PERIOD_TITLES = {
    "today": "today",
    "week": "this week",
    "month": "this month",
    "all": "all upcoming",
}


def build_reminder_list_reply(
    chat_id: int,
    user_text: str,
    user_data: dict,
) -> str | None:
    """
    If the user asked to see reminders, return the formatted list.

    Returns None if this is not a list request.
    """
    if not wants_reminder_list(user_text):
        return None

    period = detect_period(user_text)
    items = list_upcoming(chat_id)
    filtered = filter_by_period(items, period)
    title = _PERIOD_TITLES[period]

    if not filtered:
        user_data.pop(LIST_IDS_KEY, None)
        return f"No reminders for {title}."

    save_list_context(user_data, filtered)
    header = f"Reminders for {title} (soonest first)"
    return format_reminder_list(filtered, title=header)
