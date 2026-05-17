"""
Rule-based reminder parsing (no OpenAI required).
"""

import re

from services.reminders.parser import parse_when

# remind me to call Mike Friday at 3pm
_REMIND_ME_TO = re.compile(
    r"\bremind\s+me\s+to\s+(.+?)\s+"
    r"((?:on|at|by|this|next|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|may).+)$",
    re.IGNORECASE,
)

_SET_REMINDER_TO = re.compile(
    r"\bset\s+(?:a\s+)?reminder\s+(?:for\s+me\s+)?to\s+(.+)$",
    re.IGNORECASE,
)

_WHEN_FROM_END = re.compile(
    r"\b("
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"(?:\s+the)?\s+\d{1,2}(?:st|nd|rd|th)?"
    r"(?:\s+at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}"
    r"(?:\s+at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
    r"|tomorrow|today"
    r"(?:\s+at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
    r")\s*$",
    re.IGNORECASE,
)


def _split_task_and_when(rest: str) -> tuple[str, str] | None:
    """Split 'call Sam Monday the 18th at 12 PM' into task + when."""
    when_match = _WHEN_FROM_END.search(rest.strip())
    if not when_match:
        return None

    when_text = when_match.group(1).strip()
    task = rest[: when_match.start()].strip()
    if not task or not when_text:
        return None

    try:
        parse_when(when_text)
    except ValueError:
        return None

    return task, when_text


def parse_simple_reminder(text: str) -> tuple[str, str] | None:
    """
    Parse: remind me to <task> <when>

    Returns (when_text, task) or None.
    """
    stripped = text.strip()

    match = _REMIND_ME_TO.search(stripped)
    if match:
        task = match.group(1).strip()
        when_text = match.group(2).strip()
        if task and when_text:
            try:
                parse_when(when_text)
                return when_text, task
            except ValueError:
                pass

    match = _SET_REMINDER_TO.search(stripped)
    if match:
        split = _split_task_and_when(match.group(1).strip())
        if split:
            task, when_text = split
            return when_text, task

    lowered = text.lower()
    if "remind me" not in lowered and "set a reminder" not in lowered:
        return None

    # "remind me to call Sam — Monday the 18th at 12 PM"
    if "—" in text or " - " in text:
        sep = "—" if "—" in text else " - "
        left, right = text.split(sep, 1)
        when_text = right.strip()
        task = re.sub(
            r"^(?:can you\s+)?(?:set\s+(?:a\s+)?reminder\s+(?:for\s+me\s+)?(?:to\s+)?|remind\s+me\s+to\s+)",
            "",
            left.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if when_text and task:
            try:
                parse_when(when_text)
                return when_text, task
            except ValueError:
                return None

    return None
