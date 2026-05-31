#!/usr/bin/env bash
# Calisan egitim+sim'i temizce oldur, lock'u sil, train.sh'i detached yeniden baslat.
# Operator agent crash/freeze/mudahale sonrasi kullanir.
#   ./scripts/restart_training.sh [configs/ppo.yaml]
cd "$(dirname "$0")/.."
CONFIG="${1:-configs/ppo.yaml}"

echo "[restart] mevcut egitim durduruluyor..."
pkill -INT  -f "train_ppo --config" 2>/dev/null
sleep 5
pkill -TERM -f "gz sim"             2>/dev/null
pkill -TERM -f "parameter_bridge"   2>/dev/null
pkill -TERM -f "ros2 launch rl_drone" 2>/dev/null
sleep 3
pkill -9    -f "train_ppo --config" 2>/dev/null
pkill -9    -f "gz sim"             2>/dev/null
rm -f /tmp/rl_drone_train.lock
sleep 2

echo "[restart] yeniden baslatiliyor ($CONFIG)..."
setsid bash scripts/train.sh "$CONFIG" >> /tmp/train_ppo.log 2>&1 < /dev/null &
echo "[restart] started pid-group $!"
