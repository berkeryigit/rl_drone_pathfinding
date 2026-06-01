#!/usr/bin/env bash
# Gazebo zaten calisirken Gymnasium API uzerinden SAC egitimini baslatir.
#   ./scripts/train_sac_gymnasium.sh --timesteps 100000 --out runs/sac_gym
set -eo pipefail

cd "$(dirname "$0")/.."

source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || {
    echo "[train_sac_gymnasium.sh] ros2_ws/install yok; once: ./scripts/setup.sh" >&2
    exit 1
}
source ros2_ws/install/setup.bash
[[ -d .venv ]] || {
    echo "[train_sac_gymnasium.sh] .venv yok; once: ./scripts/setup.sh" >&2
    exit 1
}
source .venv/bin/activate

if ! ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
    echo "[train_sac_gymnasium.sh] /scan yok; once Gazebo'yu baslat: ros2 launch rl_drone_pathfinding sim_launch.py" >&2
    exit 1
fi

python3 -m rl_drone_pathfinding.agents.train_sac_gymnasium "$@"
