#!/usr/bin/env python3
"""
One-time Google Calendar login for Jarvis.

RUN THIS ON YOUR MAC (not the Pi):
    cd /Users/austin/Documents/jarvis-assistant
    source venv/bin/activate
    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
    python scripts/google_calendar_auth.py

Your browser will open. Sign in and click Allow.

Then copy the token to the Pi:
    scp data/google_token.json rigs@192.168.0.188:~/jarvis-assistant/data/google_token.json

Restart Jarvis on the Pi:
    sudo systemctl restart jarvis
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.calendar.auth import credentials_configured, get_google_credentials_path, run_auth_flow


def main() -> None:
    if not credentials_configured():
        path = get_google_credentials_path()
        print(f"Missing: {path}")
        print("Copy your Google JSON to credentials/google_credentials.json first.")
        sys.exit(1)

    run_auth_flow()
    print("\nNext: copy token to Pi with scp (see top of this script).")


if __name__ == "__main__":
    main()
