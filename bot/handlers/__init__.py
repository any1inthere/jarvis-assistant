"""
Register all Telegram handlers on the Application.

Add new handler modules here as Jarvis grows (reminders, calendar, etc.).
"""

from telegram.ext import Application

from bot.handlers.calendar import register_calendar_handlers
from bot.handlers.commands import register_command_handlers
from bot.handlers.messages import register_message_handlers
from bot.handlers.reminders import register_reminder_handlers


def register_handlers(application: Application) -> None:
    """Attach every handler to the bot application."""
    register_command_handlers(application)
    register_calendar_handlers(application)
    register_reminder_handlers(application)
    register_message_handlers(application)
