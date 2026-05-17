"""
Business logic and external integrations.

Stage 1 does not use this package yet. As you build Jarvis, add modules such as:

    services/reminders/     — send and schedule reminders
    services/calendar/      — Google Calendar read/write
    services/openai/        — chat and task parsing with OpenAI
    services/voice/         — transcribe voice notes
    services/ghl/           — GoHighLevel CRM integration

Handlers in bot/handlers/ should stay thin: receive a Telegram update,
call a function in services/, then reply to the user.
"""
