"""
Remove calendar events by list number (#1, #2, ...) or by name in the title.
"""

import re
from datetime import date

from services.calendar.client import (
    delete_event,
    list_events_for_date,
    list_events_for_period,
)
from services.calendar.format import format_event_summary, format_events
from services.reminders.cancel import WORD_TO_NUM, _parse_number_token

_NUMBER_WORDS = "|".join(WORD_TO_NUM.keys())

# Matches: "delete appointment #2", "cancel appointment number two"
CALENDAR_DELETE = re.compile(
    r"\b(?:cancel|delete|remove)\s+(?:the\s+)?"
    r"(?:(?:my\s+)?(?:calendar|cal)\s+)?(?:event|appointment)s?\s*"
    r"(?:#|number\s*)?(\d+|" + _NUMBER_WORDS + r")\b",
    re.IGNORECASE,
)

_NUMBER_IN_PHRASE = re.compile(
    r"\b(?:cancel|delete|remove)\b.{0,60}"
    r"\b(?:appointment|meeting|event)s?\s+"
    r"(?:#|number\s*)?(\d+|" + _NUMBER_WORDS + r")\b",
    re.IGNORECASE,
)

CALENDAR_LIST_IDS_KEY = "calendar_list_ids"
CALENDAR_LIST_META_KEY = "calendar_list_meta"
CALENDAR_PENDING_DELETE_KEY = "calendar_pending_delete"

_DELETE_BY_NAME = re.compile(
    r"\b(?:cancel|delete|remove)\s+"
    r"(?:(?:the\s+)?(?:appointment|meeting|event)\s+)?"
    r"(?:#?\d+\s*)?(?:with\s+)?(.+?)\s*\.?$",
    re.IGNORECASE,
)
_DELETE_NAME_BEFORE_NOUN = re.compile(
    r"\b(?:cancel|delete|remove)\s+(.+?)\s+"
    r"(?:appointment|meeting|event)s?\s*\.?$",
    re.IGNORECASE,
)

_CONFIRM = re.compile(
    r"^(?:yes|y|confirm|ok|delete\s+it|do\s+it)\s*\.?$",
    re.IGNORECASE,
)
_CANCEL = re.compile(
    r"^(?:no|n|cancel|stop|never\s*mind|nevermind)\s*\.?$",
    re.IGNORECASE,
)


def parse_calendar_delete_number(text: str) -> int | None:
    """
    Return event number to delete, or None.

    Skips reminder cancels ("cancel reminder #2").
    """
    lowered = text.lower()
    if "reminder" in lowered and "appointment" not in lowered and "calendar" not in lowered:
        return None

    match = CALENDAR_DELETE.search(text)
    if match:
        num = _parse_number_token(match.group(1))
        if num is not None:
            return num

    # "Can you delete appointment number two meeting with Jake?"
    if "calendar" in lowered or "appointment" in lowered:
        match = _NUMBER_IN_PHRASE.search(text)
        if match:
            num = _parse_number_token(match.group(1))
            if num is not None:
                return num

    return None


def parse_calendar_delete_name(text: str) -> str | None:
    """
    Return a name to match against event titles, e.g. "cancel appointment with Mike".

    Returns None if the message uses a number or is not a calendar delete.
    """
    if parse_calendar_delete_number(text) is not None:
        return None

    lowered = text.lower()
    if "reminder" in lowered and "appointment" not in lowered and "calendar" not in lowered:
        return None
    if not re.search(r"\b(?:cancel|delete|remove)\b", lowered):
        return None
    if re.search(r"\bnumber\s+(?:\d+|" + _NUMBER_WORDS + r")\b", lowered):
        return None

    match = _DELETE_NAME_BEFORE_NOUN.search(text.strip())
    if match:
        name = match.group(1).strip()
        if name and not name.isdigit():
            return name

    match = _DELETE_BY_NAME.search(text.strip())
    if not match:
        return None

    name = match.group(1).strip()
    if not name or name.isdigit() or name.lower() in ("appointment", "meeting", "event"):
        return None
    return name


def save_calendar_list_context(
    user_data: dict,
    events: list[dict],
    *,
    list_period: str = "today",
    list_date: str | None = None,
) -> None:
    """Remember event IDs for numbered lists (same order as /today)."""
    user_data[CALENDAR_LIST_IDS_KEY] = [event["id"] for event in events]
    user_data[CALENDAR_LIST_META_KEY] = {
        "period": list_period,
        "date": list_date,
    }


def _remove_from_cache(user_data: dict, event_id: str) -> None:
    ids = user_data.get(CALENDAR_LIST_IDS_KEY)
    if ids:
        user_data[CALENDAR_LIST_IDS_KEY] = [eid for eid in ids if eid != event_id]


def clear_pending_calendar_delete(user_data: dict) -> None:
    user_data.pop(CALENDAR_PENDING_DELETE_KEY, None)


def is_calendar_delete_confirm(text: str) -> bool:
    return bool(_CONFIRM.match(text.strip()))


def is_calendar_delete_cancel(text: str) -> bool:
    return bool(_CANCEL.match(text.strip()))


def _load_events_for_context(user_data: dict, period: str | None = None) -> list[dict]:
    """Load events for the last listed period, or a sensible default."""
    meta = user_data.get(CALENDAR_LIST_META_KEY) or {}
    if period is None:
        period = meta.get("period", "today")

    if period == "date" and meta.get("date"):
        return list_events_for_date(date.fromisoformat(meta["date"]))

    return list_events_for_period(period)


def find_events_matching_name(
    user_data: dict,
    name: str,
    *,
    search_week_if_needed: bool = True,
) -> list[tuple[int, dict]]:
    """Return [(list_number, event), ...] where title contains name (case-insensitive)."""
    name_lower = name.lower().strip()
    if len(name_lower) < 2:
        return []

    events = _load_events_for_context(user_data)
    matches: list[tuple[int, dict]] = []
    for index, event in enumerate(events, start=1):
        summary = event.get("summary", "")
        if name_lower in summary.lower():
            matches.append((index, event))

    if matches or not search_week_if_needed:
        return matches

    week_events = list_events_for_period("week")
    save_calendar_list_context(user_data, week_events, list_period="week")
    for index, event in enumerate(week_events, start=1):
        summary = event.get("summary", "")
        if name_lower in summary.lower():
            matches.append((index, event))
    return matches


def resolve_calendar_event_by_number(
    user_data: dict,
    number: int,
    period: str | None = None,
) -> dict:
    """
    Look up event #1, #2, etc.

    Uses the last list you viewed (/today or "appointments for Monday the 18th").
    """
    events = _load_events_for_context(user_data, period)
    meta = user_data.get(CALENDAR_LIST_META_KEY) or {}
    save_calendar_list_context(
        user_data,
        events,
        list_period=meta.get("period", period or "today"),
        list_date=meta.get("date"),
    )

    cached_ids: list[str] | None = user_data.get(CALENDAR_LIST_IDS_KEY)

    if cached_ids and 1 <= number <= len(cached_ids):
        event_id = cached_ids[number - 1]
        event = next((e for e in events if e["id"] == event_id), None)
        if event is None:
            event = {"id": event_id, "summary": "Calendar event"}
        return event

    if number < 1 or number > len(events):
        hint = format_events(events, "today")
        raise ValueError(
            f"No calendar event #{number}.\n\n{hint}"
        )

    return events[number - 1]


def resolve_calendar_event_by_name(user_data: dict, name: str) -> tuple[dict, int]:
    """Find one event by name in the title. Raises ValueError if ambiguous or missing."""
    matches = find_events_matching_name(user_data, name)
    if not matches:
        raise ValueError(
            f'No appointment found matching "{name}".\n\n'
            "List appointments first, then cancel by # or name:\n"
            '• "show my appointments for Monday the 18th"\n'
            "• cancel appointment #2"
        )
    if len(matches) > 1:
        lines = [f'Multiple appointments match "{name}":\n']
        for number, event in matches:
            summary = event.get("summary", "(no title)")
            lines.append(f"  #{number} — {summary}")
        lines.append("\nSay: cancel appointment #2")
        raise ValueError("\n".join(lines))

    number, event = matches[0]
    return event, number


def format_delete_confirm_prompt(event: dict, number: int) -> str:
    summary = format_event_summary(event)
    return (
        f"Delete calendar event #{number}?\n\n"
        f"{summary}\n\n"
        "Reply yes to confirm, or cancel to keep it.\n"
        "You can also use /caldel yes or /caldel cancel."
    )


def request_calendar_delete_confirmation(
    user_data: dict,
    number: int,
    period: str | None = None,
) -> str:
    """Stage a delete — nothing is removed until confirmed."""
    user_data.pop("calendar_pending_reschedule", None)

    event = resolve_calendar_event_by_number(user_data, number, period)
    user_data[CALENDAR_PENDING_DELETE_KEY] = {
        "number": number,
        "event_id": event["id"],
        "summary": event.get("summary", "Calendar event"),
        "period": user_data.get(CALENDAR_LIST_META_KEY, {}).get("period", period or "today"),
    }
    return format_delete_confirm_prompt(event, number)


def request_calendar_delete_by_name(user_data: dict, name: str) -> str:
    """Stage a delete by matching event title — confirm with yes."""
    user_data.pop("calendar_pending_reschedule", None)
    event, number = resolve_calendar_event_by_name(user_data, name)
    user_data[CALENDAR_PENDING_DELETE_KEY] = {
        "number": number,
        "event_id": event["id"],
        "summary": event.get("summary", "Calendar event"),
        "period": user_data.get(CALENDAR_LIST_META_KEY, {}).get("period", "today"),
    }
    return format_delete_confirm_prompt(event, number)


def execute_pending_calendar_delete(user_data: dict) -> str:
    """Delete the staged event. Raises ValueError if nothing is pending."""
    pending = user_data.get(CALENDAR_PENDING_DELETE_KEY)
    if not pending:
        raise ValueError("No delete waiting for confirmation.")

    number = pending["number"]
    event_id = pending["event_id"]
    name = pending.get("summary", "Event")

    delete_event(event_id)
    _remove_from_cache(user_data, event_id)
    clear_pending_calendar_delete(user_data)

    return f"Removed from calendar #{number}:\n{name}"


def handle_calendar_delete_reply(text: str, user_data: dict) -> str | None:
    """
    If a delete is pending, handle yes/cancel replies.

    Returns a reply string, or None to keep processing the message.
    """
    pending = user_data.get(CALENDAR_PENDING_DELETE_KEY)
    if not pending:
        return None

    if is_calendar_delete_confirm(text):
        try:
            return execute_pending_calendar_delete(user_data)
        except Exception as err:
            clear_pending_calendar_delete(user_data)
            raise err

    if is_calendar_delete_cancel(text):
        number = pending["number"]
        name = pending.get("summary", "Event")
        clear_pending_calendar_delete(user_data)
        return f"Kept on calendar #{number}:\n{name}"

    return None


def delete_calendar_event_by_number(
    user_data: dict,
    number: int,
    period: str = "today",
) -> dict:
    """
    Delete immediately (used after confirmation).

    Prefer request_calendar_delete_confirmation for user-facing flows.
    """
    event = resolve_calendar_event_by_number(user_data, number, period)
    delete_event(event["id"])
    _remove_from_cache(user_data, event["id"])
    clear_pending_calendar_delete(user_data)
    return event
