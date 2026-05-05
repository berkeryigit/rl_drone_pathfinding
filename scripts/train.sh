#!/usr/bin/env bash
# Tek komutla eğitime başla:
#   ./scripts/train.sh                            # default config (configs/ppo.yaml)
#   ./scripts/train.sh configs/ppo_quick.yaml     # alt config
#
# Ne yapar:
#   1) ROS + colcon install + venv'i source eder
#   2) sim_launch.py'yi background'a alır, /scan ve /odom mesajını bekler
#   3) train_ppo'yu ön planda koşturur (loglar terminale)
#   4) Eğitim biter / Ctrl-C basılınca sim'i temiz şekilde indirir
set -euo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
CONFIG="${1:-configs/ppo.yaml}"

if [[ ! -f "$CONFIG" ]]; then
    echo "[train.sh] config bulunamadi: $CONFIG" >&2
    exit 1
fi

# --- env setup ---------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || {
    echo "[train.sh] ros2_ws/install yok; once: cd ros2_ws && colcon build --symlink-install" >&2
    exit 1
}
source ros2_ws/install/setup.bash
[[ -d .venv ]] || {
    echo "[train.sh] .venv yok; once: python3 -m venv .venv --system-site-packages && pip install -r requirements.txt" >&2
    exit 1
}
source .venv/bin/activate

# --- bring up sim ------------------------------------------------------------
SIM_LOG="/tmp/rl_drone_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null && {
    echo "[train.sh] sim zaten calisiyor; mevcut sim'e bagliyorum"
    SIM_PID=""
} || {
    echo "[train.sh] sim_launch.py baslatiliyor..."
    nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    # /scan'i bekle (60s timeout)
    echo "[train.sh] /scan'in publish edilmesi bekleniyor..."
    for i in $(seq 1 30); do
        if timeout 2 ros2 topic echo /scan --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo "[train.sh] sim hazir (${i}. denemede)"
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            echo "[train.sh] sim 60s'de hazir olmadi, log: $SIM_LOG" >&2
            kill "$SIM_PID" 2>/dev/null || true
            exit 1
        fi
    done
}

cleanup() {
    echo
    echo "[train.sh] cleanup..."
    if [[ -n "$SIM_PID" ]] && kill -0 "$SIM_PID" 2>/dev/null; then
        kill "$SIM_PID" 2>/dev/null || true
        sleep 2
        kill -9 "$SIM_PID" 2>/dev/null || true
    fi
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- train -------------------------------------------------------------------
echo "[train.sh] PPO egitimi basliyor (config=$CONFIG)..."
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.train_ppo --config "$CONFIG"
