"""
Use OpenAI to pull event title and time from plain English.
"""

import os
import re

from openai import AsyncOpenAI

from config.settings import get_openai_api_key

EXTRACT_PROMPT = """The user wants to add an APPOINTMENT to Google Calendar (not a Telegram reminder).

Respond with ONLY these three lines:
WANTS_EVENT: yes or no
WHEN: date/time phrase (e.g. Friday at 3pm, tomorrow 9am) or none
TITLE: short event title or none

Rules:
- "Schedule an appointment Friday at 3 to call Mike" → yes, Friday at 3pm, Call Mike
- "Schedule estimate Friday 2pm" → yes, Friday 2pm, Estimate
- "Remind me to..." without calendar/appointment wording → WANTS_EVENT: no
- "At noon" or "12pm" → WHEN must be noon or 12:00 pm (never copy the current clock time).
- For relative times use: "in 2 hours", "in 30 minutes" (not "now + 2 minutes").
- TITLE is who/what (customer name, meeting purpose), not "appointment" or "calendar"."""

_WANTS = re.compile(r"^WANTS_EVENT:\s*(yes|no)\s*$", re.I | re.M)
_WHEN = re.compile(r"^WHEN:\s*(.+?)\s*$", re.I | re.M)
_TITLE = re.compile(r"^TITLE:\s*(.+?)\s*$", re.I | re.M)


def _get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _parse(text: str) -> tuple[bool, str | None, str | None]:
    wants_match = _WANTS.search(text)
    when_match = _WHEN.search(text)
    title_match = _TITLE.search(text)

    wants = wants_match and wants_match.group(1).lower() == "yes"
    when = when_match.group(1).strip() if when_match else None
    title = title_match.group(1).strip() if title_match else None

    if when and when.lower() in ("none", "n/a"):
        when = None
    if title and title.lower() in ("none", "n/a"):
        title = None

    return wants, when, title


async def extract_calendar_event(user_message: str) -> tuple[bool, str | None, str | None]:
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
    return _parse(raw)
