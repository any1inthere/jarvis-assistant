"""
Turn text like 'Friday 3pm' into a real date/time.
"""

import re
from datetime import datetime, timedelta

from dateutil import parser as date_parser
from dateutil.parser import ParserError

from config.settings import get_timezone, now_local

# Matches: "in 2 minutes", "in 1 hour", "in 3 days"
IN_PATTERN = re.compile(
    r"^in\s+(\d+)\s*(minute|minutes|min|hour|hours|hr|day|days)\s*$",
    re.IGNORECASE,
)

# Matches: "2 minutes from now", "1 hour from now"
FROM_NOW_PATTERN = re.compile(
    r"^(\d+)\s*(minute|minutes|min|hour|hours|hr|day|days)\s+from\s+now\s*$",
    re.IGNORECASE,
)

# Bad OpenAI output like "now + 2 minutes"
NOW_PLUS_PATTERN = re.compile(
    r"now\s*\+\s*(\d+)\s*(minute|minutes|min|hour|hours|hr)",
    re.IGNORECASE,
)

# OpenAI adds lines like: REMINDER: Friday 3pm | Send financing options
REMINDER_LINE = re.compile(
    r"^REMINDER:\s*(.+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _add_amount_from_unit(now: datetime, amount: int, unit: str) -> datetime:
    unit = unit.lower()
    if unit.startswith("min"):
        return now + timedelta(minutes=amount)
    if unit.startswith("h") or unit == "hr":
        return now + timedelta(hours=amount)
    return now + timedelta(days=amount)


def _parse_relative_time(when_text: str, now: datetime) -> datetime | None:
    """Handle 'in 2 minutes', '2 minutes from now', etc."""
    text = when_text.strip()

    match = IN_PATTERN.match(text)
    if match:
        return _add_amount_from_unit(now, int(match.group(1)), match.group(2))

    match = FROM_NOW_PATTERN.match(text)
    if match:
        return _add_amount_from_unit(now, int(match.group(1)), match.group(2))

    match = NOW_PLUS_PATTERN.search(text)
    if match:
        return _add_amount_from_unit(now, int(match.group(1)), match.group(2))

    return None


def _normalize_when_text(when_text: str) -> str:
    """Fix common phrases before parsing."""
    text = when_text.strip()

    word_to_num = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "ten": "10",
        "fifteen": "15",
        "thirty": "30",
    }
    lowered = text.lower()
    for word, num in word_to_num.items():
        if lowered.startswith(f"{word} minute"):
            return text.lower().replace(word, num, 1)

    # dateutil does not understand "noon" / "midnight" on its own.
    text = re.sub(r"\bnoon\b", "12:00 pm", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmidnight\b", "12:00 am", text, flags=re.IGNORECASE)

    # Voice/text shorthand: 12:00p, 12p, 3p → explicit minutes for the parser.
    text = re.sub(
        r"\b(\d{1,2}):(\d{2})\s*p\.?\b",
        r"\1:\2 pm",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(\d{1,2})\s*p\.?\b",
        r"\1:00 pm",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(\d{1,2}):(\d{2})\s*a\.?\b",
        r"\1:\2 am",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(\d{1,2})\s*a\.?\b",
        r"\1:00 am",
        text,
        flags=re.IGNORECASE,
    )

    return text


def parse_when(when_text: str) -> datetime:
    """
    Parse natural language times (e.g. 'Friday 3pm', 'in 2 hours').

    Uses TIMEZONE from .env (default: Eastern).
    """
    now = now_local()
    text = _normalize_when_text(when_text)

    relative = _parse_relative_time(text, now)
    if relative is not None:
        return relative

    # Missing minute/second fields must not inherit "now" (e.g. "12pm" → 12:47).
    parse_default = now.replace(minute=0, second=0, microsecond=0)

    try:
        parsed = date_parser.parse(text, fuzzy=True, default=parse_default)
    except ParserError as err:
        raise ValueError(
            f"Could not understand the time: {when_text}. "
            "Try something like Friday 3pm, noon, or 12:00 pm."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=get_timezone())
    else:
        parsed = parsed.astimezone(get_timezone())

    parsed = parsed.replace(second=0, microsecond=0)

    # Allow a few seconds of clock drift.
    if parsed <= now - timedelta(seconds=5):
        raise ValueError(
            f"That time is in the past: {when_text}. Try a future date/time."
        )

    return parsed


def split_reply_and_reminders(reply: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Pull REMINDER: lines out of OpenAI's reply.

    Returns (clean_reply, [(when_text, reminder_text), ...])
    """
    reminders: list[tuple[str, str]] = []

    for match in REMINDER_LINE.finditer(reply):
        reminders.append((match.group(1).strip(), match.group(2).strip()))

    clean = REMINDER_LINE.sub("", reply).strip()
    return clean, reminders


def parse_remind_command(args_text: str) -> tuple[str, str]:
    """
    Parse /remind Friday 3pm | Call customer

    The pipe | separates time from message. Without a pipe, we guess the split.
    """
    text = args_text.strip()
    if not text:
        raise ValueError(
            "Usage: /remind Friday 3pm | Your reminder message\n"
            "Example: /remind tomorrow 9am | Send financing options"
        )

    if "|" in text:
        when_text, message = text.split("|", 1)
        return when_text.strip(), message.strip()

    # No pipe: try splitting after the first 3 words as a guess.
    words = text.split()
    for count in range(min(5, len(words)), 0, -1):
        when_text = " ".join(words[:count])
        message = " ".join(words[count:]).strip()
        if not message:
            continue
        try:
            parse_when(when_text)
            return when_text, message
        except (ValueError, ParserError):
            continue

    raise ValueError(
        "Could not understand the time. Use:\n"
        "/remind Friday 3pm | Your reminder message"
    )
