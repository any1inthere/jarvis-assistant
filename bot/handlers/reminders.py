"""
Reminder commands: /remind, /reminders, /cancel
"""

from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import get_timezone
from services.reminders.cancel import cancel_reminder_by_number
from services.reminders.format import format_reminder_list
from services.reminders.parser import parse_remind_command
from services.reminders.scheduler import create_and_schedule
from services.reminders.store import list_upcoming, save_list_context


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /remind Friday 3pm | Follow up with customer

    Set a manual reminder. The | separates time from message.
    """
    try:
        when_text, message = parse_remind_command(
            " ".join(context.args) if context.args else ""
        )
        raw = " ".join(context.args) if context.args else ""
        reminder = await create_and_schedule(
            context.application,
            update.effective_chat.id,
            when_text,
            message,
            source=f"/remind {raw}".strip(),
        )
        due = datetime.fromisoformat(reminder.due_at).astimezone(get_timezone())
        await update.message.reply_text(
            f"Reminder set for {due.strftime('%a %b %d, %I:%M %p')}:\n{message}"
        )
    except ValueError as err:
        await update.message.reply_text(str(err))


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reminders — list your upcoming reminders (numbered, soonest first)."""
    items = list_upcoming(update.effective_chat.id)
    save_list_context(context.user_data, items)
    await update.message.reply_text(format_reminder_list(items))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel 2 — cancel reminder #2 from the list."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /cancel 2\n\nUse /reminders to see the numbers."
        )
        return

    try:
        number = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Usage: /cancel 2\n\nThe number must match /reminders (e.g. /cancel 1)."
        )
        return

    try:
        cancelled = cancel_reminder_by_number(
            context.application,
            update.effective_chat.id,
            number,
            context.user_data,
        )
        await update.message.reply_text(
            f"Cancelled reminder #{number}:\n{cancelled.text}\n\n"
            "Use /reminders to see the updated list."
        )
    except ValueError as err:
        await update.message.reply_text(str(err))


def register_reminder_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
