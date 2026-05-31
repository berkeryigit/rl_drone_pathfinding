#!/usr/bin/env bash
# Hizli sim egitimini durdur + yeniden baslat (crash/resume kurtarma).
#   ./scripts/restart_fast.sh [configs/fast.yaml]
cd "$(dirname "$0")/.."
source .venv/bin/activate
CONFIG="${1:-configs/fast.yaml}"
pkill -INT -f "train_fast.py --config" 2>/dev/null
sleep 4
pkill -9 -f "train_fast.py --config" 2>/dev/null
sleep 1
setsid python3 -u fast_sim/train_fast.py --config "$CONFIG" >> /tmp/train_fast.log 2>&1 < /dev/null &
echo "fast restarted (pid-group $!)"
