"""
Load configuration from environment variables.

Required: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY
Optional: OPENAI_MODEL (defaults to gpt-4o-mini)
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Always load .env from the project folder (not wherever systemd happens to run from).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _clean_env_value(value: str) -> str:
    """Remove quotes, spaces, and stray CR from a value read out of .env."""
    return value.strip().strip('"').strip("'").strip().rstrip("\r")


def _read_openai_key_from_file(env_path: Path) -> str | None:
    """
    Read OPENAI_API_KEY directly from .env (last active line wins).

    Handles long keys, quotes, and a value accidentally split onto the next line.
    """
    if not env_path.exists():
        return None

    text = env_path.read_text(encoding="utf-8-sig")
    best: str | None = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        i += 1
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("OPENAI_API_KEY="):
            continue

        value = _clean_env_value(stripped.split("=", 1)[1].split("#", 1)[0])
        if not value and i < len(lines):
            # Wrapped in nano: key continued on next line without "KEY="
            next_line = lines[i].strip()
            if next_line and "=" not in next_line and not next_line.startswith("#"):
                value = _clean_env_value(next_line)
                i += 1
        # Prefer the longest valid key (avoids a blank duplicate line at the bottom).
        if value and (not best or len(value) > len(best)):
            best = value
    return best


def describe_openai_env_status() -> list[str]:
    """Human-readable hints about OPENAI_API_KEY in .env (no secret values)."""
    if not ENV_FILE.exists():
        return [".env file not found at " + str(ENV_FILE)]

    lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    hints: list[str] = []
    saw_commented = False
    saw_active = False

    for line in lines:
        stripped = line.strip()
        if "OPENAI_API_KEY" not in stripped:
            continue
        if stripped.startswith("#"):
            saw_commented = True
            hints.append("Found commented line (starts with #): remove the #")
        elif stripped.startswith("OPENAI_API_KEY="):
            saw_active = True

    key = _read_openai_key_from_file(ENV_FILE) or ""
    if saw_active and not key:
        hints.append("Found OPENAI_API_KEY= but value is empty")
    elif saw_active and key.startswith("sk-your"):
        hints.append("Found placeholder key — paste your real sk-... key")
    elif saw_active and key:
        hints.append(f"Active key in file (length {len(key)})")

    if saw_commented and not saw_active:
        hints.append("OpenAI line is commented out — Jarvis will not see the key")
    if not saw_commented and not saw_active:
        hints.append("No OPENAI_API_KEY= line in .env — add one")

    return hints


def _load_env_file() -> None:
    """Load .env into os.environ."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)

    # Fallback: parse file ourselves (long keys, quotes, wrapped lines).
    key = _read_openai_key_from_file(ENV_FILE)
    if key:
        os.environ["OPENAI_API_KEY"] = key


_load_env_file()


def _missing_key_message(key_name: str, help_line: str) -> str:
    return (
        f"Error: {key_name} is missing or still set to the placeholder.\n"
        f"{help_line}\n"
        "Then restart Jarvis: sudo systemctl restart jarvis"
    )


def get_telegram_token() -> str:
    """Return the Telegram bot token or exit with a helpful message."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token or token == "your_telegram_bot_token_here":
        print(
            _missing_key_message(
                "TELEGRAM_BOT_TOKEN",
                "Add your token from @BotFather to .env",
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    return token


def _resolve_openai_api_key() -> str:
    """
    Return the OpenAI key, preferring .env on disk over os.environ.

    systemd's EnvironmentFile can inject an empty or truncated OPENAI_API_KEY;
    reading the file avoids that.
    """
    key = _read_openai_key_from_file(ENV_FILE) or ""
    if not key:
        key = _clean_env_value(os.getenv("OPENAI_API_KEY", ""))
    return key


def openai_configured() -> bool:
    """True if OPENAI_API_KEY is set in .env (not a placeholder)."""
    key = _resolve_openai_api_key()
    return bool(key) and not key.startswith("sk-your")


def get_openai_api_key() -> str:
    """
    Return the OpenAI API key.

    Raises ValueError if missing (so the bot can tell you in Telegram instead of crashing).
    """
    key = _resolve_openai_api_key()
    if not key or key.startswith("sk-your"):
        raise ValueError(
            "OPENAI_API_KEY is missing on the Pi.\n\n"
            "Fix: nano ~/jarvis-assistant/.env\n"
            "Add: OPENAI_API_KEY=sk-your-key\n"
            "(no # at the start of the line)\n\n"
            "Then: sudo systemctl restart jarvis"
        )

    # Keep os.environ in sync for libraries that read it directly.
    os.environ["OPENAI_API_KEY"] = key
    return key


def get_timezone() -> ZoneInfo:
    """
    Your local timezone for reminders and displayed times.

    Default: America/New_York (Eastern). Change in .env if needed.
    """
    tz_name = os.getenv("TIMEZONE", "America/New_York")
    return ZoneInfo(tz_name)


def now_local() -> datetime:
    """Current date/time in your timezone."""
    return datetime.now(get_timezone())


def get_google_credentials_path() -> Path:
    """OAuth client JSON from Google Cloud Console."""
    name = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json")
    return PROJECT_ROOT / name


def get_google_token_path() -> Path:
    """Saved login token (created by scripts/google_calendar_auth.py)."""
    name = os.getenv("GOOGLE_TOKEN_PATH", "data/google_token.json")
    return PROJECT_ROOT / name
