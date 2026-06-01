#!/usr/bin/env bash
# v4.10 (varsayılan) politikasını GAZEBO 3B'de GUI ile izle — TAVAN KALDIRILDI (üstten görünür).
#   bash scripts/watch_v48_gazebo.sh [bölüm_sayısı] [model.zip]
#   bölüm_sayısı boş/-1 = SONSUZ (Ctrl-C / kill ile durana kadar).
# Gazebo penceresi DISPLAY :0'da açılır; drone'u canlı izlersin.
set -eo pipefail
cd "$(dirname "$0")/.."
EPISODES="${1:--1}"
MODEL="${2:-runs/fast_v4_10/checkpoints/fast_drone_final.zip}"

# eski gz/bridge kalıntısı varsa temizle
pkill -f "gz sim" 2>/dev/null || true
pkill -f "parameter_bridge" 2>/dev/null || true
sleep 1

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate
export GZ_IP=127.0.0.1 IGN_IP=127.0.0.1   # transport loopback (donma fix'i)
export SIM_HEADLESS=0                       # GUI AÇIK — izlemek için

SIM_LOG=/tmp/rl_drone_watch_sim.log
echo "[watch] Gazebo GUI başlatılıyor (log: $SIM_LOG)..."
ROS_DOMAIN_ID=0 GZ_PARTITION=sim0 \
    nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
SIM_PID=$!

cleanup() {
    echo "[watch] temizlik..."
    kill "$SIM_PID" 2>/dev/null || true
    sleep 1
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[watch] /scan bekleniyor (sim hazır olana kadar)..."
ready=0
for j in $(seq 1 45); do
    if ROS_DOMAIN_ID=0 timeout 2 ros2 topic echo /scan --once --qos-reliability best_effort >/dev/null 2>&1; then
        echo "[watch] sim hazır (${j}. deneme)"
        ready=1
        break
    fi
    sleep 2
done
[ "$ready" -eq 1 ] || { echo "[watch] sim 90s'de hazır olmadı, log: $SIM_LOG"; exit 1; }

echo "[watch] politika çalışıyor — GUI penceresinde üstten izle. (model=$MODEL, bölüm=$EPISODES)"
python3 scripts/deploy_v48_gazebo.py --model "$MODEL" --episodes "$EPISODES"
echo "[watch] bitti."
