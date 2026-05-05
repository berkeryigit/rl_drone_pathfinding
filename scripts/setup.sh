#!/usr/bin/env bash
# Bir kerelik kurulum: colcon build + venv + pip install.
# Yarin sifirdan baslarken (yeni clone vb.) tek komut:
#   ./scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[setup.sh] colcon build..."
source /opt/ros/jazzy/setup.bash
( cd ros2_ws && colcon build --symlink-install --packages-select rl_drone_pathfinding )

echo "[setup.sh] venv olusturuluyor..."
[[ -d .venv ]] || python3 -m venv .venv --system-site-packages

echo "[setup.sh] python deps..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[setup.sh] DONE. Sirada: ./scripts/train.sh"
