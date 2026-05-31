#!/usr/bin/env bash
# Egitim calismiyorsa baslat (calisiyorsa dokunma). Operator/heartbeat kullanir.
#   ./scripts/ensure_training.sh [configs/ppo.yaml]
cd "$(dirname "$0")/.."
CONFIG="${1:-configs/ppo.yaml}"
if pgrep -f "train_ppo --config" >/dev/null; then
    echo "already-running"
    exit 0
fi
echo "starting training ($CONFIG)..."
setsid bash scripts/train.sh "$CONFIG" >> /tmp/train_ppo.log 2>&1 < /dev/null &
echo "started pid-group $!"
