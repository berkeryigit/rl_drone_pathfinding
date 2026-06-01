#!/usr/bin/env bash
# Gazebo/ROS acmadan hizli 2D Gymnasium SAC egitimi.
#   ./scripts/train_sac_fast_2d.sh --timesteps 100000 --num-envs 8
set -eo pipefail

cd "$(dirname "$0")/.."

# venv varsa kullan; yoksa (Docker imaji) sistem python3'une guven
if [[ -d .venv ]]; then
    source .venv/bin/activate
else
    echo "[train_sac_fast_2d.sh] .venv yok — sistem python3 kullaniliyor (Docker)"
fi

export PYTHONPATH="$PWD/ros2_ws/src/rl_drone_pathfinding:${PYTHONPATH:-}"
python3 -m rl_drone_pathfinding.agents.train_sac_fast_2d "$@"

# --- egitim bitti: rapor grafiklerini olustur (default --out kullaniliyorsa) ---
LOG_CSV="runs/sac_fast_2d/training_log.csv"
if [[ -f "$LOG_CSV" ]]; then
    echo "[train_sac_fast_2d.sh] Grafikler olusturuluyor: runs/sac_fast_2d/plots"
    python3 scripts/plot_training.py --log "$LOG_CSV" --out runs/sac_fast_2d/plots \
        || echo "[train_sac_fast_2d.sh] grafik olusturma atlandi"
fi
