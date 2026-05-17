"""
Save reminders in a JSON file on the Pi (no database needed yet).

File location: data/reminders.json
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REMINDERS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "reminders.json"

# Telegram user_data key: IDs in the order shown in the last /reminders list.
LIST_IDS_KEY = "reminder_list_ids"


@dataclass
class Reminder:
    id: str
    chat_id: int
    text: str
    due_at: str  # ISO datetime string
    sent: bool = False
    source: str = ""  # original Telegram message, if captured


def _load_all() -> list[Reminder]:
    if not REMINDERS_FILE.exists():
        return []

    with REMINDERS_FILE.open(encoding="utf-8") as file:
        raw = json.load(file)

    return [Reminder(**item) for item in raw]


def _save_all(reminders: list[Reminder]) -> None:
    """Write reminders to disk (atomic save so nothing gets corrupted)."""
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = REMINDERS_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump([asdict(item) for item in reminders], file, indent=2)
        file.flush()
        os.fsync(file.fileno())

    temp_file.replace(REMINDERS_FILE)
    logger.info("Saved %s reminders to %s", len(reminders), REMINDERS_FILE)


def add_reminder(
    chat_id: int,
    text: str,
    due_at: datetime,
    source: str = "",
) -> Reminder:
    """Create a new reminder and save it to the file."""
    reminder = Reminder(
        id=str(uuid.uuid4())[:8],
        chat_id=chat_id,
        text=text,
        due_at=due_at.isoformat(),
        sent=False,
        source=source.strip(),
    )
    reminders = _load_all()
    reminders.append(reminder)
    _save_all(reminders)
    return reminder


def mark_sent(reminder_id: str) -> None:
    """Mark a reminder as done so we don't send it again."""
    reminders = _load_all()
    for item in reminders:
        if item.id == reminder_id:
            item.sent = True
    _save_all(reminders)


def get_by_id(reminder_id: str) -> Reminder | None:
    for item in _load_all():
        if item.id == reminder_id:
            return item
    return None


def list_upcoming(chat_id: int) -> list[Reminder]:
    """Return unsent reminders for this user, soonest first."""
    chat_id = int(chat_id)
    items = [
        item
        for item in _load_all()
        if int(item.chat_id) == chat_id and not item.sent
    ]
    items.sort(key=lambda item: item.due_at)
    return items


def save_list_context(user_data: dict, items: list[Reminder]) -> None:
    """
    Remember which reminders were shown as #1, #2, #3...

    Cancel uses these IDs so #2 means the same row you just saw.
    """
    user_data[LIST_IDS_KEY] = [item.id for item in items]


def list_due_unsent() -> list[Reminder]:
    """Return all unsent reminders (used when the bot starts up)."""
    return [item for item in _load_all() if not item.sent]


def list_all_reminders() -> list[Reminder]:
    """Return every reminder, soonest due first (for the web dashboard)."""
    items = _load_all()
    items.sort(key=lambda item: item.due_at)
    return items


def delete_reminder(reminder_id: str) -> bool:
    """
    Remove a reminder completely (used when the user cancels).

    Returns True if something was deleted.
    """
    reminders = _load_all()
    new_reminders = [item for item in reminders if item.id != reminder_id]

    if len(new_reminders) == len(reminders):
        logger.warning("Reminder %s not found in %s", reminder_id, REMINDERS_FILE)
        return False

    _save_all(new_reminders)
    return True
