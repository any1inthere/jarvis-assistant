"""
Cancel reminders by list number (#1, #2, ...).
"""

import logging
import re

from telegram.ext import Application

from services.reminders.store import (
    LIST_IDS_KEY,
    Reminder,
    delete_reminder,
    get_by_id,
    list_upcoming,
)

logger = logging.getLogger(__name__)

# Words people use instead of digits: "cancel reminder number two"
WORD_TO_NUM: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
}


def _parse_number_token(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return WORD_TO_NUM.get(token)


def parse_cancel_number(text: str) -> int | None:
    """
    Return the reminder number to cancel, or None if not a cancel request.

    Handles:
    - cancel reminder #2
    - cancel reminder 2
    - cancel reminder number two
    - can you cancel reminder number two?
    """
    lowered = text.lower()
    if not re.search(r"\b(?:cancel|delete|remove)\b", lowered):
        return None
    if "reminder" not in lowered:
        return None

    # #2
    match = re.search(r"#\s*(\d+)", text)
    if match:
        return int(match.group(1))

    # "number two" or "number 2"
    match = re.search(r"number\s+(\d+|[a-z]+)", text, re.IGNORECASE)
    if match:
        number = _parse_number_token(match.group(1))
        if number:
            return number

    # "cancel reminder 2"
    match = re.search(
        r"(?:cancel|delete|remove)\s+(?:the\s+)?reminder\s*#?\s*(\d+)\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1))

    # "cancel the second reminder"
    match = re.search(
        r"(?:cancel|delete|remove)\s+(?:the\s+)?(\d+|[a-z]+)\s+reminder\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_number_token(match.group(1))

    return None


def _remove_scheduled_job(application: Application, reminder_id: str) -> None:
    """Stop a pending Telegram job for this reminder."""
    if application.job_queue is None:
        return

    for job in application.job_queue.jobs():
        if job.name == f"reminder-{reminder_id}":
            job.schedule_removal()


def _remove_from_list_cache(user_data: dict, reminder_id: str) -> None:
    """Keep the numbered list in sync after a cancel."""
    ids = user_data.get(LIST_IDS_KEY)
    if ids:
        user_data[LIST_IDS_KEY] = [item_id for item_id in ids if item_id != reminder_id]


def cancel_reminder_by_number(
    application: Application,
    chat_id: int,
    number: int,
    user_data: dict | None = None,
) -> Reminder:
    """
    Cancel reminder #1, #2, etc.

    Uses the same numbered list you last saw (/reminders or "show for this week").
    """
    user_data = user_data if user_data is not None else {}

    # Prefer the list the user actually saw (fixes cancel after filtered views).
    cached_ids: list[str] | None = user_data.get(LIST_IDS_KEY)
    if cached_ids and 1 <= number <= len(cached_ids):
        reminder_id = cached_ids[number - 1]
        target = get_by_id(reminder_id)
        if target and int(target.chat_id) == int(chat_id):
            if not delete_reminder(reminder_id):
                raise ValueError("Could not remove that reminder. Try /reminders and cancel again.")
            _remove_scheduled_job(application, reminder_id)
            _remove_from_list_cache(user_data, reminder_id)
            logger.info("Cancelled reminder %s (#%s) for chat %s", reminder_id, number, chat_id)
            return target

    # Fallback: full upcoming list (same order as plain /reminders).
    items = list_upcoming(chat_id)

    if number < 1 or number > len(items):
        raise ValueError(
            f"No reminder #{number}. You have {len(items)} reminder(s). "
            "Use /reminders to see the list."
        )

    target = items[number - 1]
    if not delete_reminder(target.id):
        raise ValueError("Could not remove that reminder. Try /reminders and cancel again.")

    _remove_scheduled_job(application, target.id)
    _remove_from_list_cache(user_data, target.id)
    logger.info("Cancelled reminder %s (#%s) for chat %s", target.id, number, chat_id)
    return target
