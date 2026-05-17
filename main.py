"""
Jarvis Assistant — entry point.

Run locally:
    python main.py

Project layout (grows over time):
    main.py              ← you are here (start the bot)
    config/              ← settings from .env
    bot/                 ← Telegram app and handlers
    services/            ← future: reminders, calendar, OpenAI, voice, GHL
"""

from bot.app import run_bot

if __name__ == "__main__":
    run_bot()
