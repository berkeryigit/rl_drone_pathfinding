#!/usr/bin/env bash
# SAC eval:
#   ./scripts/eval_sac.sh                                          # default model
#   ./scripts/eval_sac.sh runs/sac_v2_final/checkpoints/best/best_model.zip
#   ./scripts/eval_sac.sh <model> <episodes> <max-steps>
#   SIM_HEADLESS=0 ./scripts/eval_sac.sh ...                       # Gazebo GUI ac
#   DETERMINISTIC=1 ./scripts/eval_sac.sh ...                      # deterministik policy
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"

MODEL="${1:-runs/sac_fast_rooms/checkpoints/best/best_model.zip}"
EPISODES="${2:-10}"
MAX_STEPS="${3:-500}"
SIM_HEADLESS="${SIM_HEADLESS:-1}"
DETERMINISTIC="${DETERMINISTIC:-0}"
FIXED_SPAWN="${FIXED_SPAWN:-0}"

source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] && source ros2_ws/install/setup.bash
# venv varsa kullan; yoksa (Docker imaji) sistem python3'une guven
[[ -d .venv ]] && source .venv/bin/activate || echo "[eval_sac.sh] .venv yok — sistem python3"

SIM_LOG="/tmp/rl_drone_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null && {
    echo "[eval_sac.sh] sim zaten calisiyor"
    SIM_PID=""
} || {
    echo "[eval_sac.sh] sim baslatiliyor (headless=$SIM_HEADLESS)..."
    GZ_HEADLESS_RENDERING=$SIM_HEADLESS \
    nohup ros2 launch rl_drone_pathfinding sim_launch.py \
        headless:=$SIM_HEADLESS > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    for i in $(seq 1 30); do
        if ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
            echo "[eval_sac.sh] sim hazir (${i}. denemede)"
            sleep 2
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            echo "[eval_sac.sh] sim 60s'de hazir olmadi, log: $SIM_LOG" >&2
            kill "$SIM_PID" 2>/dev/null || true
            exit 1
        fi
    done
}

cleanup() {
    echo "[eval_sac.sh] cleanup..."
    [[ -n "$SIM_PID" ]] && kill "$SIM_PID" 2>/dev/null || true
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

DET_FLAG=""
[[ "$DETERMINISTIC" == "1" ]] && DET_FLAG="--deterministic"
SPAWN_FLAG=""
[[ "$FIXED_SPAWN" == "1" ]] && SPAWN_FLAG="--fixed-spawn"

echo "[eval_sac.sh] Model=$MODEL | Episodes=$EPISODES | MaxSteps=$MAX_STEPS | det=$DETERMINISTIC | fixed_spawn=$FIXED_SPAWN"
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.eval_sac \
    --model      "$MODEL"     \
    --episodes   "$EPISODES"  \
    --max-steps  "$MAX_STEPS" \
    $DET_FLAG $SPAWN_FLAG
