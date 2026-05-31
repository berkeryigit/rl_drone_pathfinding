#!/usr/bin/env bash
# Hizli numpy sim PPO egitimi baslat (Gazebo/ROS YOK, sadece venv).
#   ./scripts/run_fast.sh [configs/fast.yaml]
cd "$(dirname "$0")/.."
source .venv/bin/activate
CONFIG="${1:-configs/fast.yaml}"
if pgrep -f "train_fast.py --config" >/dev/null; then
    echo "already-running"; exit 0
fi
setsid python3 -u fast_sim/train_fast.py --config "$CONFIG" >> /tmp/train_fast.log 2>&1 < /dev/null &
echo "fast training started (pid-group $!)"
