"""
Create reminders from plain English (not Google Calendar).
"""

from datetime import datetime

from config.settings import get_timezone, openai_configured
from services.intent import wants_appointment_action, wants_reminder_action
from services.reminders.extract import extract_reminder_from_message
from services.reminders.simple import parse_simple_reminder


async def handle_reminder_add(
    user_text: str,
    *,
    schedule_fn,
) -> str | None:
    """
    If the user asked for a reminder, schedule it and return confirmation.

    schedule_fn(when_text, task) must create the reminder and return the Reminder object.
    """
    if not wants_reminder_action(user_text):
        return None
    if wants_appointment_action(user_text):
        return None

    when_text: str | None = None
    task: str | None = None

    simple = parse_simple_reminder(user_text)
    if simple:
        when_text, task = simple
    elif openai_configured():
        wants, when_text, task = await extract_reminder_from_message(user_text)
        if not wants:
            return None
    else:
        return (
            "Reminder (Telegram ping — not on your calendar):\n\n"
            "/remind Friday 3pm | Your task\n"
            "Or: remind me to call Mike Friday at 3pm"
        )

    if not when_text or not task:
        return None

    reminder = await schedule_fn(when_text, task)
    due = datetime.fromisoformat(reminder.due_at).astimezone(get_timezone())
    return (
        f"Reminder set (you'll get a Telegram message — not on Google Calendar):\n"
        f"{due.strftime('%a %b %d, %I:%M %p')}\n{task}"
    )
