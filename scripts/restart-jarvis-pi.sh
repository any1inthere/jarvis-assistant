#!/bin/bash
# Run ON THE PI to restart Jarvis and kill duplicate bot processes.
#   bash scripts/restart-jarvis-pi.sh

set -e
cd ~/jarvis-assistant

echo "Stopping Jarvis and any duplicate python main.py processes..."
sudo systemctl stop jarvis || true
pkill -f "jarvis-assistant/venv/bin/python main.py" 2>/dev/null || true
pkill -f "python main.py" 2>/dev/null || true
sleep 2

echo "Starting Jarvis..."
sudo systemctl start jarvis
sleep 2
sudo systemctl status jarvis --no-pager | head -12
echo ""
sudo journalctl -u jarvis -n 8 --no-pager
