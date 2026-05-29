#!/usr/bin/env bash
# SAC modelini degerlendirip GIF + CSV + PNG olusturur:
#   ./scripts/eval_sac.sh runs/sac/checkpoints/best/best_model.zip
#   ./scripts/eval_sac.sh runs/sac/checkpoints/best/best_model.zip 5
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
MODEL="${1:?Model yolu gerekli: ./scripts/eval_sac.sh <model.zip> [episode_sayisi]}"
EPISODES="${2:-5}"

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=42

SIM_LOG="/tmp/rl_drone_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null && {
    echo "[eval_sac.sh] sim zaten calisiyor"
    SIM_PID=""
} || {
    echo "[eval_sac.sh] sim baslatiliyor..."
    nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    for i in $(seq 1 30); do
        if ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
            echo "[eval_sac.sh] sim hazir"
            sleep 2; break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            echo "[eval_sac.sh] sim 60s'de hazir olmadi" >&2
            kill "$SIM_PID" 2>/dev/null || true; exit 1
        fi
    done
}

cleanup() {
    if [[ -n "${SIM_PID:-}" ]] && kill -0 "$SIM_PID" 2>/dev/null; then
        kill "$SIM_PID" 2>/dev/null || true
    fi
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[eval_sac.sh] Eval basliyor: $MODEL ($EPISODES episode)"
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.eval_sac \
    --model "$MODEL" \
    --episodes "$EPISODES" \
    --out-dir runs/sac/eval_results
