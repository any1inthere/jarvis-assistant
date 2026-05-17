"""
Schedule reminders and send a Telegram message when they're due.
"""

import logging
from datetime import datetime

from telegram.ext import Application, ContextTypes

from config.settings import now_local
from services.reminders.store import Reminder, get_by_id, list_due_unsent, mark_sent

logger = logging.getLogger(__name__)


def _seconds_until(due_at_iso: str) -> float:
    due = datetime.fromisoformat(due_at_iso)
    now = now_local()
    return (due - now).total_seconds()


async def _send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called by the job queue when a reminder is due."""
    reminder_id = context.job.data
    reminder = get_by_id(reminder_id)

    if not reminder or reminder.sent:
        return

    await context.bot.send_message(
        chat_id=reminder.chat_id,
        text=f"Reminder\n\n{reminder.text}",
    )
    mark_sent(reminder.id)
    logger.info("Sent reminder %s", reminder.id)


def schedule_reminder(application: Application, reminder: Reminder) -> None:
    """Tell the bot to send this reminder at the right time."""
    seconds = _seconds_until(reminder.due_at)

    if seconds <= 0:
        logger.warning("Skipping past reminder %s", reminder.id)
        return

    application.job_queue.run_once(
        _send_reminder,
        when=seconds,
        data=reminder.id,
        name=f"reminder-{reminder.id}",
    )
    logger.info("Scheduled reminder %s in %.0f seconds", reminder.id, seconds)


def restore_reminders(application: Application) -> None:
    """Re-schedule reminders after the Pi reboots or Jarvis restarts."""
    for reminder in list_due_unsent():
        try:
            schedule_reminder(application, reminder)
        except Exception:
            logger.exception("Could not restore reminder %s", reminder.id)


async def create_and_schedule(
    application: Application,
    chat_id: int,
    when_text: str,
    message: str,
    source: str = "",
) -> Reminder:
    """Parse the time, save the reminder, and schedule it."""
    from services.reminders.parser import parse_when
    from services.reminders.store import add_reminder

    due_at = parse_when(when_text)
    reminder = add_reminder(chat_id, message, due_at, source=source)
    schedule_reminder(application, reminder)
    return reminder
