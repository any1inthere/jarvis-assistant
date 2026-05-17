#!/usr/bin/env python3
"""Find why Jarvis won't start. Run: python scripts/diagnose.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("Jarvis diagnose")
print("-" * 40)

root = Path(__file__).resolve().parent.parent
checks = [
    root / ".env",
    root / "credentials" / "google_credentials.json",
    root / "data" / "google_token.json",
    root / "services" / "calendar" / "delete.py",
    root / "bot" / "handlers" / "calendar.py",
]

for path in checks:
    print(f"{'OK' if path.exists() else 'MISSING':8} {path.name}")

print("-" * 40)
print("Checking .env keys (not showing values)...")
from dotenv import load_dotenv
import os

load_dotenv(root / ".env")
tg = os.getenv("TELEGRAM_BOT_TOKEN", "")
ai = os.getenv("OPENAI_API_KEY", "")
print(f"{'OK' if tg and 'your_telegram' not in tg else 'MISSING':8} TELEGRAM_BOT_TOKEN")
print(f"{'OK' if ai and not ai.startswith('sk-your') else 'MISSING':8} OPENAI_API_KEY")
if ai and ai.startswith("#"):
    print("  (line might be commented with # — remove the #)")

print("-" * 40)
print("Testing imports...")

try:
    from bot.app import create_application

    create_application()
    print("OK — bot can start. Run: sudo systemctl restart jarvis")
except SystemExit as err:
    print(f"FAILED — config problem (exit {err.code})")
    print("Check .env has TELEGRAM_BOT_TOKEN")
except Exception as err:
    print(f"FAILED — {type(err).__name__}: {err}")
    import traceback

    traceback.print_exc()
