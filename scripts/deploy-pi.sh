#!/bin/bash
# Option B: push code from Mac, pull on Pi, restart Jarvis.
# Run on Mac from project folder:
#   bash scripts/deploy-pi.sh

set -e
PI="rigs@192.168.0.188"
REPO="https://github.com/any1inthere/jarvis-assistant.git"

cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  echo "No git repo here. One-time setup:"
  echo "  git init && git remote add origin $REPO"
  echo "  git add -A && git commit -m 'Jarvis assistant'"
  echo "  git push -u origin main"
  exit 1
fi

echo "=== Push from Mac ==="
git push

echo ""
echo "=== Pull on Pi and restart ==="
ssh "$PI" << 'ENDSSH'
cd ~/jarvis-assistant
git pull
source venv/bin/activate
pip install -r requirements.txt -q
python scripts/check_env.py
sudo cp deploy/jarvis.service /etc/systemd/system/jarvis.service
sudo systemctl daemon-reload
sudo systemctl restart jarvis
ENDSSH

echo ""
echo "Done. Test in Telegram with a normal note (not a command)."
