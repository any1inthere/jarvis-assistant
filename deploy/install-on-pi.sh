#!/bin/bash
# Run this ON THE RASPBERRY PI (after SSH in):
#   bash install-on-pi.sh
#
# Or paste the whole script into your Pi terminal.

set -e

echo "Installing Jarvis systemd service..."

sudo tee /etc/systemd/system/jarvis.service > /dev/null << 'EOF'
[Unit]
Description=Jarvis Telegram Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rigs
WorkingDirectory=/home/rigs/jarvis-assistant
Environment=PATH=/home/rigs/jarvis-assistant/venv/bin
ExecStart=/home/rigs/jarvis-assistant/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable jarvis
sudo systemctl restart jarvis

echo ""
echo "Done. Status:"
sudo systemctl status jarvis --no-pager
