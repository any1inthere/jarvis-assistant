#!/usr/bin/env python3
"""Check if .env is loaded correctly. Run on Pi: python scripts/check_env.py"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    ENV_FILE,
    _read_openai_key_from_file,
    _resolve_openai_api_key,
    describe_openai_env_status,
    openai_configured,
)

print("Jarvis .env check")
print("-" * 40)
print(f".env file exists: {ENV_FILE.exists()}")
print(f".env path: {ENV_FILE}")
print()

for hint in describe_openai_env_status():
    print(f"  • {hint}")

print()
file_key = _read_openai_key_from_file(ENV_FILE) or ""
env_key = os.getenv("OPENAI_API_KEY", "")
resolved = _resolve_openai_api_key()
print(f"Key in .env file:  {len(file_key)} chars")
print(f"Key in os.environ: {len(env_key)} chars")
print(f"OPENAI loaded by Jarvis: {openai_configured()}")

key = resolved
if key:
    print(f"Key starts with: {key[:8]}...  (length {len(key)})")
    print()
    print("OK — restart if you just edited .env: sudo systemctl restart jarvis")
else:
    print("Key is EMPTY in memory — Jarvis cannot use OpenAI yet")
    print()
    print("Fix on THIS machine (Pi or Mac):")
    print('  nano ~/jarvis-assistant/.env')
    print('  Add ONE line (quotes help for long keys):')
    print('  OPENAI_API_KEY="sk-proj-your-key-here"')
    print("  (no # at the start of the line)")
    print()
    print("Then: sudo systemctl restart jarvis")
