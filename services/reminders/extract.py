"""
Use OpenAI to understand when someone asks for a reminder in plain English.
"""

import os
import re

from openai import AsyncOpenAI

from config.settings import get_openai_api_key

EXTRACT_PROMPT = """You read messages sent to a personal assistant named Jarvis.

Decide if the user wants a REMINDER (a Telegram ping at a time — NOT a Google Calendar appointment).

Reminder examples:
- "remind me to call them Friday at 3"
- "set a reminder to send the quote tomorrow"
- "ping me in 2 hours to follow up"

NOT reminders (say WANTS_REMINDER: no):
- "schedule an appointment", "book a meeting", "add to my calendar"
- "show my appointments", "cancel appointment #2"

Respond with ONLY these three lines (no other text):
WANTS_REMINDER: yes or no
WHEN: the date/time phrase to use (e.g. Friday at 3pm, tomorrow 9am, May 20 at 2pm) or none
TASK: the short reminder message or none

Rules:
- Reminders are for tasks Jarvis will message about — not calendar events.
- WHEN must be a parseable English date/time, not vague words like "soon" or "later".
- For relative times use exactly: "in 2 minutes", "in 1 hour" (never "now + 2 minutes").
- For a specific clock time use: "May 16 at 5:53 PM" or "Friday at 3pm".
- TASK should be the action (call, text, send quote, follow up, etc.)."""

_WANTS = re.compile(r"^WANTS_REMINDER:\s*(yes|no)\s*$", re.I | re.M)
_WHEN = re.compile(r"^WHEN:\s*(.+?)\s*$", re.I | re.M)
_TASK = re.compile(r"^TASK:\s*(.+?)\s*$", re.I | re.M)


def _get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _parse_extraction(text: str) -> tuple[bool, str | None, str | None]:
    wants_match = _WANTS.search(text)
    when_match = _WHEN.search(text)
    task_match = _TASK.search(text)

    wants = wants_match and wants_match.group(1).lower() == "yes"
    when = when_match.group(1).strip() if when_match else None
    task = task_match.group(1).strip() if task_match else None

    if when and when.lower() in ("none", "n/a", ""):
        when = None
    if task and task.lower() in ("none", "n/a", ""):
        task = None

    return wants, when, task


async def extract_reminder_from_message(
    user_message: str,
) -> tuple[bool, str | None, str | None]:
    """
    Returns (wants_reminder, when_text, task_text).

    If wants_reminder is False, when and task will be None.
    """
    client = AsyncOpenAI(api_key=get_openai_api_key())

    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=120,
        temperature=0,
    )

    raw = (response.choices[0].message.content or "").strip()
    return _parse_extraction(raw)
