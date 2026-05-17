"""
Format Google Calendar events for Telegram.
"""

from datetime import datetime

from config.settings import get_timezone


def _parse_event_time(event: dict) -> tuple[datetime | None, bool]:
    """Return (datetime, is_all_day)."""
    start = event.get("start", {})
    if "dateTime" in start:
        return datetime.fromisoformat(start["dateTime"]), False
    if "date" in start:
        return datetime.fromisoformat(start["date"]), True
    return None, False


def format_event_summary(event: dict) -> str:
    """One-line summary for confirm prompts."""
    when, all_day = _parse_event_time(event)
    name = event.get("summary", "(no title)")

    if when is None:
        return name

    if not all_day:
        when = when.astimezone(get_timezone())
        time_str = when.strftime("%a %b %d, %I:%M %p")
    else:
        time_str = when.strftime("%a %b %d (all day)")

    return f"{time_str}\n   {name}"


def format_events(events: list[dict], title: str) -> str:
    """Numbered list for calendar — #1 matches /caldel 1 and "delete appointment #1"."""
    if not events:
        return f"No events {title}."

    heading = f"Calendar — {title} (soonest first)"
    lines = [f"{heading}:\n"]
    tz = get_timezone()

    for index, event in enumerate(events, start=1):
        when, all_day = _parse_event_time(event)
        name = event.get("summary", "(no title)")

        if when is None:
            lines.append(f"#{index} — {name}")
            continue

        if not all_day:
            when = when.astimezone(tz)
            time_str = when.strftime("%a %b %d, %I:%M %p")
        else:
            time_str = when.strftime("%a %b %d (all day)")

        lines.append(f"#{index} — {time_str}\n   {name}")

    lines.append("\n(Appointments are on Google Calendar — not the reminder list.)")
    lines.append("To cancel: cancel appointment #2  or  cancel appointment with Mike")
    lines.append("To reschedule: reschedule appointment #2 to Friday 3pm")
    lines.append(
        'To book: /caladd Friday 3pm | meeting  or  "schedule estimate Friday 2pm"'
    )
    lines.append('For a reminder (Telegram ping only): "remind me to … Friday at 3"')
    return "\n".join(lines)
