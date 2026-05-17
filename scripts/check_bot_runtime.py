#!/usr/bin/env python3
"""
Simulate how the systemd bot loads config (same venv Python as jarvis.service).

Run on Pi:
  cd ~/jarvis-assistant
  ./venv/bin/python scripts/check_bot_runtime.py

Also test with a blank env var (systemd sometimes does this):
  env OPENAI_API_KEY= ./venv/bin/python scripts/check_bot_runtime.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings as settings_module
from config.settings import (
    ENV_FILE,
    _read_openai_key_from_file,
    _resolve_openai_api_key,
    openai_configured,
)

has_file_read_fix = hasattr(settings_module, "_resolve_openai_api_key")

file_key = _read_openai_key_from_file(ENV_FILE) or ""
env_key = os.getenv("OPENAI_API_KEY", "")

print("Jarvis runtime check (same Python as systemd)")
print("-" * 50)
print(f"OpenAI fix in settings.py: {has_file_read_fix}")
if not has_file_read_fix:
    print("  -> OLD code on Pi. On Mac run: bash scripts/fix-pi.sh")
print(f"Python:     {sys.executable}")
print(f".env path:  {ENV_FILE}")
print(f"Key in file:       {len(file_key)} chars")
print(f"Key in os.environ: {len(env_key)} chars")
print(f"Resolved key:      {len(_resolve_openai_api_key())} chars")
print(f"openai_configured: {openai_configured()}")
print()

if file_key and not openai_configured():
    print("PROBLEM: .env has a key but Jarvis logic says it is missing.")
    print("Deploy latest code, then:")
    print("  sudo cp deploy/jarvis.service /etc/systemd/system/jarvis.service")
    print("  sudo systemctl daemon-reload && sudo systemctl restart jarvis")
elif not file_key:
    print("PROBLEM: No key found in .env file.")
elif env_key and len(env_key) != len(file_key):
    print("NOTE: os.environ key length differs from file — systemd may have mangled it.")
    print("After updating jarvis.service (no EnvironmentFile), restart jarvis.")
else:
    print("OK — bot should see OpenAI. Restart if you just updated code:")
    print("  sudo systemctl restart jarvis")
    print("  sudo journalctl -u jarvis -n 15 --no-pager")
