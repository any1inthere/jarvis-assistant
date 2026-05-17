"""
Format reminder lists for Telegram messages.
"""

from datetime import datetime

from config.settings import get_timezone
from services.reminders.store import Reminder


def format_reminder_list(items: list[Reminder], title: str | None = None) -> str:
    """Numbered list, soonest first (#1 is next up)."""
    if not items:
        return "No upcoming reminders."

    heading = title or "Upcoming reminders (soonest first)"
    lines = [f"{heading}:\n"]
    for index, item in enumerate(items, start=1):
        due = datetime.fromisoformat(item.due_at).astimezone(get_timezone())
        lines.append(
            f"#{index} — {due.strftime('%a %b %d, %I:%M %p')}\n   {item.text}"
        )

    lines.append('\nTo cancel: /cancel 2  or say "cancel reminder #2"')
    return "\n".join(lines)
