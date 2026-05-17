"""
Build and run the Telegram bot application.

This file is the "wiring" layer: it creates the bot, registers handlers, and starts polling.
"""

import logging

from telegram.ext import Application

from bot.handlers import register_handlers
from config.settings import ENV_FILE, get_telegram_token, openai_configured
from services.reminders.scheduler import restore_reminders

# Basic logging so you can see when the bot starts and if errors occur.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Reduce noise from the httpx library used under the hood.
logging.getLogger("httpx").setLevel(logging.WARNING)


async def _on_startup(application: Application) -> None:
    """Re-load reminders after a restart (so they still fire)."""
    logging.info(
        "Startup: OPENAI configured=%s (.env at %s)",
        openai_configured(),
        ENV_FILE,
    )
    if application.job_queue is None:
        raise RuntimeError(
            'Job queue missing. On the Pi run:\n'
            '  pip install "python-telegram-bot[job-queue]==21.10"'
        )
    restore_reminders(application)


def create_application() -> Application:
    """
    Create the python-telegram-bot Application with your token and handlers.
    """
    token = get_telegram_token()
    application = (
        Application.builder()
        .token(token)
        .post_init(_on_startup)
        .build()
    )
    register_handlers(application)
    return application


def run_bot() -> None:
    """
    Start the bot and listen for updates from Telegram.

    run_polling() keeps a long-running connection: whenever someone messages your bot,
    Telegram delivers the update and your handlers run.
    """
    application = create_application()
    print("Jarvis is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message"])
