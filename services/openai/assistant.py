"""
Send user messages to OpenAI and return Jarvis's reply.

Tuned for outside fence sales notes (appointments, follow-ups, etc.).
"""

import os

from openai import AsyncOpenAI

from config.settings import get_openai_api_key

# Instructions for the AI — you can edit this file to change how Jarvis behaves.
SYSTEM_PROMPT = """You are Jarvis, a personal assistant for an outside fence sales rep.

The user sends quick notes after appointments (often dictated as text). Your job:
1. Summarize the note clearly and briefly.
2. Pull out actionable details when present:
   - What the customer wants (material, color, style, etc.)
   - Follow-up date/time
   - Decision makers
   - Urgent tasks (e.g. "send financing tonight")
   - Objections or concerns
3. End with a short "Suggested next steps" bullet list (2–4 items max).

IMPORTANT — reminders:
- This bot CAN set reminders and WILL schedule them automatically.
- NEVER say you cannot set reminders, cannot use timers, or tell them to use their phone.
- If they ask for a reminder, reply briefly: "Got it — I'm setting that reminder now." (or similar).
- Do not explain how reminders work; the system sends a separate confirmation.
- Do NOT handle canceling reminders or calendar appointments yourself.
- Reminders: say "Use /reminders to see the list, then cancel reminder #2."
- Calendar: say "Use /today to see appointments, then cancel appointment #2 or reschedule appointment #2 to Friday 3pm."

Keep replies compact and easy to read on a phone. Use plain text, not markdown headers.
If the message is casual chat, still be helpful and brief."""


def _get_model() -> str:
    """Which OpenAI model to use (gpt-4o-mini is fast and inexpensive)."""
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _get_client() -> AsyncOpenAI:
    """Create an OpenAI client using the API key from .env."""
    return AsyncOpenAI(api_key=get_openai_api_key())


async def get_jarvis_reply(user_message: str) -> str:
    """
    Send the user's text to OpenAI and return Jarvis's response.

    Raises openai.APIError and other exceptions if the API call fails.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=600,
        temperature=0.4,
    )

    reply = response.choices[0].message.content or ""
    reply = reply.strip()

    if not reply:
        return "I couldn't generate a reply. Please try again."

    # Telegram messages max out around 4096 characters.
    if len(reply) > 4000:
        reply = reply[:3997] + "..."

    return reply
