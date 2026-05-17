"""
Log in to Google Calendar (one-time setup, then token is reused).
"""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config.settings import get_google_credentials_path, get_google_token_path

# Lets Jarvis read your calendar and add events.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def credentials_configured() -> bool:
    """True if the Google credentials file exists on disk."""
    return get_google_credentials_path().exists()


def token_exists() -> bool:
    """True if we already completed the one-time Google login."""
    return get_google_token_path().exists()


def google_calendar_ready() -> bool:
    """True if credentials and token are both present."""
    return credentials_configured() and token_exists()


def _redirect_uri_from_file(creds_path: Path) -> str:
    """Read the redirect URI from Google's JSON file (usually http://localhost)."""
    data = json.loads(creds_path.read_text(encoding="utf-8"))
    if "installed" in data:
        uris = data["installed"].get("redirect_uris", ["http://localhost"])
        return uris[0]
    if "web" in data:
        uris = data["web"].get("redirect_uris", [])
        if uris:
            return uris[0]
    return "http://localhost"


def get_google_credentials() -> Credentials:
    """
    Load saved Google credentials, refreshing if expired.

    Raises FileNotFoundError if setup was not completed.
    """
    creds_path = get_google_credentials_path()
    token_path = get_google_token_path()

    if not creds_path.exists():
        raise FileNotFoundError(
            "Google credentials file not found.\n"
            f"Expected: {creds_path}\n"
            "See setup steps from your Jarvis install guide."
        )

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    raise FileNotFoundError(
        "Google Calendar is not authorized yet.\n"
        "Run on your Mac:\n"
        "  python scripts/google_calendar_auth.py\n"
        "Then copy data/google_token.json to the Pi."
    )


def run_auth_flow() -> Credentials:
    """
    First-time login — run scripts/google_calendar_auth.py on your Mac.

    Opens a browser window automatically (easiest). Works with Desktop OAuth app.
    """
    creds_path = get_google_credentials_path()
    token_path = get_google_token_path()

    if not creds_path.exists():
        raise FileNotFoundError(f"Missing credentials file: {creds_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    flow.redirect_uri = _redirect_uri_from_file(creds_path)

    print("Opening your browser to sign in to Google...")
    print(f"Using redirect: {flow.redirect_uri}")
    print("(Run this on your Mac, not over SSH on the Pi.)\n")

    # Opens browser; Google redirects to localhost with the token.
    creds = flow.run_local_server(port=8080, prompt="consent", open_browser=True)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nSaved token to {token_path}")
    return creds
