"""
Handlers for normal chat messages (not slash commands).

Text from voice dictation works the same way — Telegram sends it as a text message.
"""

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config.settings import openai_configured
from services.calendar.modify import (
    handle_calendar_modify,
    handle_calendar_pending_reply,
    wants_calendar_modify,
)
from services.calendar.query import handle_calendar_add, handle_calendar_list
from services.openai.assistant import get_jarvis_reply
from services.reminders.add import handle_reminder_add
from services.reminders.cancel import cancel_reminder_by_number, parse_cancel_number
from services.reminders.list_query import build_reminder_list_reply
from services.reminders.scheduler import create_and_schedule

logger = logging.getLogger(__name__)


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Understand the message, set reminders if asked, and reply with a summary."""
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # Confirm or cancel a pending calendar delete/reschedule ("yes" / "cancel").
    try:
        pending_reply = handle_calendar_pending_reply(user_text, context.user_data)
        if pending_reply is not None:
            await update.message.reply_text(pending_reply)
            return
    except Exception:
        logger.exception("Calendar pending action failed")
        await update.message.reply_text("Could not update your calendar.")
        return

    # Cancel / delete / reschedule calendar appointments (not reminders).
    try:
        calendar_modify = handle_calendar_modify(user_text, context.user_data)
        if calendar_modify is not None:
            await update.message.reply_text(calendar_modify)
            return
    except ValueError as err:
        await update.message.reply_text(str(err))
        return
    except Exception:
        logger.exception("Calendar modify failed")
        await update.message.reply_text("Could not update your calendar.")
        return

    # "cancel reminder #2" — handle without calling OpenAI.
    cancel_number = parse_cancel_number(user_text)
    if cancel_number is not None and wants_calendar_modify(user_text):
        cancel_number = None
    if cancel_number is not None:
        try:
            cancelled = cancel_reminder_by_number(
                context.application,
                chat_id,
                cancel_number,
                context.user_data,
            )
            await update.message.reply_text(
                f"Cancelled reminder #{cancel_number}:\n{cancelled.text}\n\n"
                "Use /reminders to see the updated list."
            )
        except ValueError as err:
            await update.message.reply_text(str(err))
        return

    # Reminder list — not calendar appointments.
    list_reply = build_reminder_list_reply(chat_id, user_text, context.user_data)
    if list_reply is not None:
        await update.message.reply_text(list_reply)
        return

    # Reminder add — Telegram ping only, not Google Calendar.
    try:
        async def _schedule(when_text: str, task: str):
            return await create_and_schedule(
                context.application,
                chat_id,
                when_text,
                task,
                source=user_text,
            )

        reminder_reply = await handle_reminder_add(
            user_text, schedule_fn=_schedule
        )
        if reminder_reply is not None:
            await update.message.reply_text(reminder_reply)
            return
    except ValueError as err:
        await update.message.reply_text(str(err))
        return
    except Exception:
        logger.exception("Reminder scheduling failed")
        await update.message.reply_text("Could not set that reminder.")
        return

    # Google Calendar: list or book appointments.
    try:
        calendar_list = await handle_calendar_list(user_text, context.user_data)
        if calendar_list is not None:
            await update.message.reply_text(calendar_list)
            return

        calendar_add = await handle_calendar_add(user_text)
        if calendar_add is not None:
            await update.message.reply_text(calendar_add)
            return
    except FileNotFoundError as err:
        await update.message.reply_text(str(err))
        return
    except ValueError as err:
        if "OPENAI_API_KEY" in str(err):
            await update.message.reply_text(str(err))
            return
        await update.message.reply_text(str(err))
        return
    except Exception as err:
        logger.exception("Google Calendar failed")
        detail = str(err).strip()
        if len(detail) > 200:
            detail = detail[:200] + "…"
        await update.message.reply_text(
            f"Google Calendar error: {detail}\n\n"
            "On the Pi try: python scripts/check_calendar.py\n"
            "If auth expired: python scripts/google_calendar_auth.py"
        )
        return

    # Notes and general chat need OpenAI.
    if not openai_configured():
        await update.message.reply_text(
            "OPENAI_API_KEY is missing on the Pi.\n\n"
            "Fix: nano ~/jarvis-assistant/.env\n"
            "Add: OPENAI_API_KEY=sk-your-key\n"
            "(no # at the start)\n\n"
            "Then: sudo systemctl restart jarvis\n\n"
            "Commands still work: /reminders /today /caladd"
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        reply = await get_jarvis_reply(user_text)
        await update.message.reply_text(reply)
    except Exception:
        logger.exception("OpenAI request failed")
        await update.message.reply_text(
            "Sorry — I had trouble reaching OpenAI. "
            "Check your API key and billing at platform.openai.com, then try again."
        )


def register_message_handlers(application: Application) -> None:
    """Wire text messages to their handler functions."""
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
