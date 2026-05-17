"""
Parse specific dates from phrases like "Monday the 18th" or "May 18".
"""

import re
from datetime import date, timedelta

from dateutil import parser as date_parser
from dateutil.parser import ParserError

from config.settings import now_local

# "for Monday the 18th", "on May 18", "the 18th"
_FOR_DATE = re.compile(
    r"\b(?:for|on)\s+(.+?)(?:\s*$|\s+(?:and|then)\b)",
    re.IGNORECASE,
)

_APPOINTMENTS_THEN_DATE = re.compile(
    r"\bappointments?\s+(?:for|on)\s+(.+)$",
    re.IGNORECASE,
)


def _parse_date_fragment(fragment: str) -> date | None:
    text = fragment.strip().rstrip(".")
    if not text:
        return None

    now = now_local()
    default = now.replace(hour=12, minute=0, second=0, microsecond=0)

    try:
        parsed = date_parser.parse(text, fuzzy=True, default=default)
    except (ParserError, ValueError):
        return None

    return parsed.date()


def parse_appointment_list_date(text: str) -> date | None:
    """
    Extract a calendar day from list requests.

    Examples:
    - show all my appointments for Monday the 18th
    - appointments on May 18
  """
    for pattern in (_FOR_DATE, _APPOINTMENTS_THEN_DATE):
        match = pattern.search(text)
        if match:
            found = _parse_date_fragment(match.group(1))
            if found:
                return found

    # "Monday the 18th" anywhere in the message
    match = re.search(
        r"\b("
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"\s+(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?"
        r"|\d{1,2}(?:st|nd|rd|th)?\s+of\s+\w+"
        r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}"
        r")\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return _parse_date_fragment(match.group(1))

    return None


def format_date_label(target: date) -> str:
    """Human label for a list header."""
    today = now_local().date()
    if target == today:
        return "today"
    if target == today + timedelta(days=1):
        return "tomorrow"
    return target.strftime("%A, %b %d")
