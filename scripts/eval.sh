#!/usr/bin/env bash
# Egitilmis modeli sim'e baglayip kac episode roll-out yapar.
#   ./scripts/eval.sh runs/ppo/checkpoints/ppo_drone_final.zip [N_EPS]
# `set -u` trips on ROS setup.bash unbound vars; keep -e + pipefail.
set -eo pipefail

cd "$(dirname "$0")/.."

MODEL="${1:?usage: eval.sh <model.zip> [n_eps]}"
N_EPS="${2:-5}"

if [[ "$MODEL" == *"dqn"* ]]; then
    AGENT_MODULE="eval_dqn"
    CONFIG="configs/dqn.yaml"
else
    AGENT_MODULE="eval_ppo"
    CONFIG="configs/ppo.yaml"
fi

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate

SIM_LOG="/tmp/rl_drone_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null || {
    echo "[eval.sh] sim baslatiliyor..."
    nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    for i in $(seq 1 30); do
        if timeout 2 ros2 topic echo /scan --once --qos-reliability best_effort >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done
    trap "kill $SIM_PID 2>/dev/null; pkill -f 'gz sim' 2>/dev/null; pkill -f parameter_bridge 2>/dev/null" EXIT INT TERM
}

python3 -m rl_drone_pathfinding.agents.$AGENT_MODULE \
    --config "$CONFIG" \
    --model "$MODEL" \
    --episodes "$N_EPS" \
    --deterministic
