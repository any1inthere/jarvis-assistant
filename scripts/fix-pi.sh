#!/bin/bash
# Run this on your MAC in Terminal:
#   cd /Users/austin/Documents/jarvis-assistant
#   bash scripts/fix-pi.sh
#
# Enter your Pi password when scp/ssh asks.

set -e
PI="rigs@192.168.0.188"
DIR="/Users/austin/Documents/jarvis-assistant"

echo "=== Copying code to Pi ==="
rsync -av "$DIR/bot/" "$PI:~/jarvis-assistant/bot/"
rsync -av "$DIR/services/" "$PI:~/jarvis-assistant/services/"
rsync -av "$DIR/scripts/" "$PI:~/jarvis-assistant/scripts/"
# Always push settings.py (rsync sometimes skips it if timestamps match).
rsync -av "$DIR/config/" "$PI:~/jarvis-assistant/config/"
scp "$DIR/config/settings.py" "$PI:~/jarvis-assistant/config/settings.py"
rsync -av "$DIR/deploy/" "$PI:~/jarvis-assistant/deploy/"
rsync -av "$DIR/main.py" "$PI:~/jarvis-assistant/main.py"

echo ""
echo "=== Fixing Jarvis on Pi ==="
ssh "$PI" << 'ENDSSH'
cd ~/jarvis-assistant
source venv/bin/activate
pip install -r requirements.txt -q
echo ""
echo "=== Update systemd unit (no EnvironmentFile) ==="
sudo cp deploy/jarvis.service /etc/systemd/system/jarvis.service
sudo systemctl daemon-reload

echo ""
echo "=== Runtime check (venv Python, like the bot) ==="
./venv/bin/python scripts/check_bot_runtime.py || true
if ! ./venv/bin/python -c "from config.settings import _resolve_openai_api_key; print('settings OK')"; then
  echo "ERROR: config/settings.py did not copy correctly."
  exit 1
fi
env OPENAI_API_KEY= ./venv/bin/python scripts/check_bot_runtime.py || true

echo ""
echo "=== Stop duplicate bot processes (fixes Telegram Conflict) ==="
sudo systemctl stop jarvis || true
pkill -f "/home/rigs/jarvis-assistant/venv/bin/python main.py" 2>/dev/null || true
pkill -f "python main.py" 2>/dev/null || true
sleep 2

echo ""
echo "=== Restart Jarvis (only one instance) ==="
sudo systemctl start jarvis
sleep 2
sudo journalctl -u jarvis -n 12 --no-pager
sleep 2
sudo systemctl status jarvis --no-pager | head -15
ENDSSH

echo ""
echo "=== WARNING: do NOT copy Mac .env to Pi ==="
echo "Secrets live on the Pi only. Edit Pi .env with: ssh rigs@192.168.0.188"
echo "  nano ~/jarvis-assistant/.env"

echo ""
echo "=== Done ==="
echo "Test in Telegram: /reminders  then  /today  then a normal note"
