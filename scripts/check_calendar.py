#!/usr/bin/env python3
"""Quick check — run on Mac or Pi: python scripts/check_calendar.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_google_credentials_path, get_google_token_path
from services.calendar.auth import google_calendar_ready


def main() -> None:
    creds = get_google_credentials_path()
    token = get_google_token_path()

    print("Google Calendar status")
    print("-" * 30)
    print(f"Credentials file: {'YES' if creds.exists() else 'NO'}  ({creds})")
    print(f"Login token:      {'YES' if token.exists() else 'NO'}  ({token})")
    print(f"Ready for Jarvis: {'YES' if google_calendar_ready() else 'NO'}")

    if not google_calendar_ready():
        print("\nFix: run on your Mac:")
        print("  python scripts/google_calendar_auth.py")
        print("Then copy token to Pi:")
        print("  scp data/google_token.json rigs@192.168.0.188:~/jarvis-assistant/data/")
        return

    try:
        from services.calendar.client import list_events_for_period

        events = list_events_for_period("today")
        print(f"\nCalendar works. Events today: {len(events)}")
    except Exception as err:
        print(f"\nToken exists but API failed: {err}")


if __name__ == "__main__":
    main()
