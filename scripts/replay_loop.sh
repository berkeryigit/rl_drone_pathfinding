#!/usr/bin/env bash
# ep82 spawn konfigurasyonunu (spawn_idx=1) surekli donguyle oynatir.
# GUI acik kalir, Ctrl-C ile durdurulur.
set -eo pipefail

cd "$(dirname "$0")/.."

MODEL="runs/ppo_v8_frontier/checkpoints/ppo_drone_final.zip"
CONFIG="configs/ppo.yaml"
SPAWN_IDX="${1:-1}"    # 1. arg: spawn_idx (0-7). Default=1 (ep82 spawnu)
N_EPS="${2:-9999}"     # 2. arg: episode sayisi. Default=sonsuz

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate

SIM_LOG="/tmp/rl_drone_sim.log"
SIM_PID=""

_cleanup() {
    echo ""
    echo "[replay_loop] Durduruluyor..."
    [[ -n "$SIM_PID" ]] && kill "$SIM_PID" 2>/dev/null
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f parameter_bridge 2>/dev/null || true
}
trap _cleanup EXIT INT TERM

# Sim zaten calismiyorsa basalt (GUI modunda)
if ! pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null 2>&1; then
    echo "[replay_loop] Gazebo GUI ile sim baslatiliyor (ROS_DOMAIN_ID=0 GZ_PARTITION=sim0)..."
    SIM_HEADLESS=0 ROS_DOMAIN_ID=0 GZ_PARTITION=sim0 \
        nohup ros2 launch rl_drone_pathfinding sim_launch.py \
        > "$SIM_LOG" 2>&1 &
    SIM_PID=$!

    echo -n "[replay_loop] /scan bekleniyor"
    for i in $(seq 1 30); do
        if ROS_DOMAIN_ID=0 timeout 2 ros2 topic echo /scan \
                --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo " hazir."
            break
        fi
        echo -n "."
        sleep 2
    done
else
    echo "[replay_loop] Sim zaten calisiyor, mevcut pencere kullaniliyor."
fi

echo "[replay_loop] ep82 replay basliyor — spawn_idx=$SPAWN_IDX, $N_EPS episode, Ctrl-C ile dur."
echo "----------------------------------------------------------------------"

python3 -m rl_drone_pathfinding.agents.eval_ppo \
    --config  "$CONFIG" \
    --model   "$MODEL" \
    --episodes "$N_EPS" \
    --spawn-idx "$SPAWN_IDX" \
    --deterministic
