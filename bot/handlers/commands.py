"""
Slash commands (e.g. /start).

Future commands might live here too: /remind, /today, /tasks, etc.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start — sent when a user opens the bot or taps Start.

    This is a good place for a welcome message and a short list of what Jarvis can do
    as you add features.
    """
    welcome_message = (
        "Hi! I'm Jarvis, your personal assistant.\n\n"
        "Reminders (Telegram ping — not on calendar):\n"
        "• \"remind me to call Mike Friday at 3\"\n"
        "• /remind Friday 3pm | task\n"
        "• /reminders — your reminder list\n"
        "• /cancel 2 — cancel reminder #2\n\n"
        "Appointments (Google Calendar):\n"
        "• \"schedule estimate Friday 2pm\"\n"
        "• \"show my appointments for Monday the 18th\"\n"
        "• /today — today on calendar\n"
        "• /caladd Fri 3pm | meeting\n"
        "• cancel appointment #2  or  cancel appointment with Mike\n"
        "• /caldel 2 — cancel (confirms first)\n\n"
        "• Send notes after appointments — I'll summarize them"
    )
    await update.message.reply_text(welcome_message)


def register_command_handlers(application: Application) -> None:
    """Wire slash commands to their handler functions."""
    application.add_handler(CommandHandler("start", start_command))
