#!/bin/bash
# Run the reminder dashboard on the Pi (or Mac for testing).
#   cd ~/jarvis-assistant && bash scripts/run_dashboard.sh

set -e
cd "$(dirname "$0")/.."
source venv/bin/activate
pip install -q flask
exec python dashboard/app.py
