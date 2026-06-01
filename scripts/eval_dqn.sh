#!/usr/bin/env bash
# Tek komutla degerlendirme (evaluation) yap:
#   ./scripts/eval_dqn.sh configs/dqn_obstacles.yaml runs/dqn_obstacles/checkpoints/dqn_drone_final.zip
#
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
CONFIG="${1:-configs/dqn.yaml}"
MODEL="$2"

if [[ -z "$MODEL" ]]; then
    echo "[eval_dqn.sh] HATA: Model yolu belirtilmedi!"
    echo "Kullanim: ./scripts/eval_dqn.sh <config_yolu> <model_yolu.zip>"
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "[eval_dqn.sh] config bulunamadi: $CONFIG" >&2
    exit 1
fi

WORLD_NAME=$(grep "world_name:" "$CONFIG" | awk '{print $2}' | tr -d '"' | tr -d "'")
if [[ -z "$WORLD_NAME" ]]; then
    WORLD_NAME="multi_room"
fi

# --- env setup ---------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || {
    echo "[eval_dqn.sh] ros2_ws/install yok; once build et." >&2
    exit 1
}
source ros2_ws/install/setup.bash
source .venv/bin/activate

# --- bring up sim ------------------------------------------------------------
SIM_LOG="${PROJ_ROOT}/runs/rl_drone_eval_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null && {
    echo "[eval_dqn.sh] sim zaten calisiyor; mevcut sim'e bagliyorum"
    SIM_PID=""
} || {
    # Test asamasinda headless flag'i kapatip (gui=True) Gazebo arayuzunu acmak istersen
    # sim_launch.py icindeki headless=false yapman gerekebilir, ama biz SIM_HEADLESS=0 gonderecegiz
    echo "[eval_dqn.sh] Gazebo baslatiliyor (world: $WORLD_NAME)..."
    export SIM_HEADLESS=0
    nohup ros2 launch rl_drone_pathfinding sim_launch.py world_file_name:="${WORLD_NAME}.sdf" > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    
    echo "[eval_dqn.sh] /scan bekleniyor..."
    for i in $(seq 1 30); do
        if timeout 2 ros2 topic echo /scan --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo "[eval_dqn.sh] sim hazir!"
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            echo "[eval_dqn.sh] sim 60s'de hazir olmadi." >&2
            kill "$SIM_PID" 2>/dev/null || true
            exit 1
        fi
    done
}

cleanup() {
    echo
    echo "[eval_dqn.sh] cleanup..."
    if [[ -n "$SIM_PID" ]] && kill -0 "$SIM_PID" 2>/dev/null; then
        kill "$SIM_PID" 2>/dev/null || true
        sleep 2
        kill -9 "$SIM_PID" 2>/dev/null || true
    fi
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- evaluate -------------------------------------------------------------------
echo "[eval_dqn.sh] DQN Test basliyor..."
cd "$PROJ_ROOT"
export PYTHONPATH="$PROJ_ROOT/ros2_ws/src/rl_drone_pathfinding:$PYTHONPATH"
python3 -m rl_drone_pathfinding.agents.eval_dqn --config "$CONFIG" --model "$MODEL" --episodes 5 --deterministic
