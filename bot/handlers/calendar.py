"""
Calendar commands: /today, /calendar, /caladd
"""

import logging

from googleapiclient.errors import HttpError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from services.calendar.auth import google_calendar_ready
from services.calendar.query import _setup_message
from services.calendar.client import create_event, list_events_for_period
from services.calendar.delete import (
    request_calendar_delete_confirmation,
    save_calendar_list_context,
)
from services.calendar.modify import (
    handle_calendar_pending_reply,
    request_calendar_reschedule_confirmation,
)
from services.calendar.format import format_events
from services.reminders.parser import parse_when

logger = logging.getLogger(__name__)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/today — what's on your calendar today."""
    try:
        if not google_calendar_ready():
            await update.message.reply_text(_setup_message())
            return

        events = list_events_for_period("today")
        save_calendar_list_context(context.user_data, events, list_period="today")
        await update.message.reply_text(format_events(events, "today"))
    except HttpError as err:
        logger.exception("/today failed")
        await update.message.reply_text(f"Google Calendar error: {err}")
    except Exception:
        logger.exception("/today failed")
        await update.message.reply_text(
            "Calendar error. On the Pi run: python scripts/check_calendar.py"
        )


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/calendar — next 7 days on your calendar."""
    try:
        if not google_calendar_ready():
            await update.message.reply_text(_setup_message())
            return

        events = list_events_for_period("week")
        save_calendar_list_context(context.user_data, events, list_period="week")
        await update.message.reply_text(format_events(events, "next 7 days"))
    except HttpError as err:
        logger.exception("/calendar failed")
        await update.message.reply_text(f"Google Calendar error: {err}")
    except Exception:
        logger.exception("/calendar failed")
        await update.message.reply_text(
            "Calendar error. On the Pi run: python scripts/check_calendar.py"
        )


async def caladd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /caladd Friday 3pm | Call customer

    Add an event to Google Calendar.
    """
    if not google_calendar_ready():
        await update.message.reply_text(_setup_message())
        return

    text = " ".join(context.args) if context.args else ""
    if not text or "|" not in text:
        await update.message.reply_text(
            "Usage: /caladd Friday 3pm | Event title\n"
            "Example: /caladd tomorrow 10am | Estimate at Smith residence"
        )
        return

    when_text, title = text.split("|", 1)
    when_text = when_text.strip()
    title = title.strip()

    try:
        start = parse_when(when_text)
        event = create_event(title, start)
        await update.message.reply_text(
            f"Added to Google Calendar:\n{title}\n"
            f"{start.strftime('%a %b %d, %I:%M %p')}"
        )
    except ValueError as err:
        await update.message.reply_text(str(err))
    except HttpError as err:
        logger.exception("/caladd failed")
        await update.message.reply_text(f"Google Calendar error: {err}")
    except Exception:
        logger.exception("/caladd failed")
        await update.message.reply_text(
            "Could not add the event. Check Google Calendar setup on the Pi."
        )


async def caldel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /caldel 2 — ask to confirm deleting event #2
    /caldel yes — confirm a pending delete
    /caldel cancel — cancel a pending delete
    /caldel — show today's numbered list
    """
    if not google_calendar_ready():
        await update.message.reply_text(_setup_message())
        return

    if not context.args:
        try:
            events = list_events_for_period("today")
            save_calendar_list_context(context.user_data, events)
            await update.message.reply_text(format_events(events, "today"))
        except HttpError as err:
            await update.message.reply_text(f"Google Calendar error: {err}")
        except Exception:
            await update.message.reply_text("Could not load today's calendar.")
        return

    arg = context.args[0].lower()

    if arg in ("yes", "confirm", "y"):
        try:
            reply = handle_calendar_pending_reply("yes", context.user_data)
            if reply:
                await update.message.reply_text(
                    f"{reply}\n\nUse /today to see the updated list."
                )
            else:
                await update.message.reply_text("Nothing waiting to confirm.")
        except ValueError as err:
            await update.message.reply_text(str(err))
        except HttpError as err:
            await update.message.reply_text(f"Google Calendar error: {err}")
        except Exception:
            await update.message.reply_text("Could not update that event.")
        return

    if arg in ("cancel", "no", "n"):
        reply = handle_calendar_pending_reply("cancel", context.user_data)
        await update.message.reply_text(reply or "Nothing waiting to confirm.")
        return

    try:
        number = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Usage: /caldel 2\n"
            "Then reply yes or use /caldel yes to confirm.\n\n"
            "/caldel alone shows today's list."
        )
        return

    try:
        reply = request_calendar_delete_confirmation(context.user_data, number)
        await update.message.reply_text(reply)
    except ValueError as err:
        await update.message.reply_text(str(err))
    except HttpError as err:
        await update.message.reply_text(f"Google Calendar error: {err}")
    except Exception:
        await update.message.reply_text("Could not find that event.")


async def calmove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /calmove 2 Friday 3pm — reschedule event #2 (asks for confirmation)

    /calmove yes — confirm pending reschedule
    """
    if not google_calendar_ready():
        await update.message.reply_text(_setup_message())
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /calmove 2 Friday 3pm\n"
            "Example: /calmove 1 tomorrow at noon\n\n"
            "Then reply yes or use /calmove yes to confirm."
        )
        return

    arg = context.args[0].lower()

    if arg in ("yes", "confirm", "y"):
        try:
            reply = handle_calendar_pending_reply("yes", context.user_data)
            if reply:
                await update.message.reply_text(
                    f"{reply}\n\nUse /today to see the updated list."
                )
            else:
                await update.message.reply_text("Nothing waiting to confirm.")
        except ValueError as err:
            await update.message.reply_text(str(err))
        except HttpError as err:
            await update.message.reply_text(f"Google Calendar error: {err}")
        except Exception:
            await update.message.reply_text("Could not reschedule that event.")
        return

    if arg in ("cancel", "no", "n"):
        reply = handle_calendar_pending_reply("cancel", context.user_data)
        await update.message.reply_text(reply or "Nothing waiting to confirm.")
        return

    try:
        number = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /calmove 2 Friday 3pm")
        return

    when_text = " ".join(context.args[1:]).strip()
    if not when_text:
        await update.message.reply_text("Usage: /calmove 2 Friday 3pm")
        return

    try:
        reply = request_calendar_reschedule_confirmation(
            context.user_data, number, when_text
        )
        await update.message.reply_text(reply)
    except ValueError as err:
        await update.message.reply_text(str(err))
    except HttpError as err:
        await update.message.reply_text(f"Google Calendar error: {err}")
    except Exception:
        await update.message.reply_text("Could not reschedule that event.")


def register_calendar_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("calendar", calendar_command))
    application.add_handler(CommandHandler("caladd", caladd_command))
    application.add_handler(CommandHandler("caldel", caldel_command))
    application.add_handler(CommandHandler("calmove", calmove_command))
