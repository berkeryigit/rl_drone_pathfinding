#!/usr/bin/env bash
# SAC egitimini tek komutla baslatir:
#   ./scripts/train_sac.sh                      # default config (configs/sac.yaml)
#   ./scripts/train_sac.sh configs/sac.yaml     # explicit config
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
CONFIG="${1:-configs/sac.yaml}"

if [[ ! -f "$CONFIG" ]]; then
    echo "[train_sac.sh] config bulunamadi: $CONFIG" >&2
    exit 1
fi

# --- env setup ---------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || {
    echo "[train_sac.sh] ros2_ws/install yok; once: ./scripts/setup.sh" >&2
    exit 1
}
source ros2_ws/install/setup.bash
[[ -d .venv ]] || {
    echo "[train_sac.sh] .venv yok; once: ./scripts/setup.sh" >&2
    exit 1
}
source .venv/bin/activate

# --- bring up sim ------------------------------------------------------------
SIM_LOG="/tmp/rl_drone_sim.log"
pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null && {
    echo "[train_sac.sh] sim zaten calisiyor; mevcut sim'e bagliyorum"
    SIM_PID=""
} || {
    echo "[train_sac.sh] sim_launch.py baslatiliyor..."
    nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    echo "[train_sac.sh] /scan'in publish edilmesi bekleniyor..."
    for i in $(seq 1 30); do
        if ros2 topic list 2>/dev/null | grep -q "^/scan$"; then
            echo "[train_sac.sh] sim hazir (${i}. denemede)"
            sleep 2
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            echo "[train_sac.sh] sim 60s'de hazir olmadi, log: $SIM_LOG" >&2
            kill "$SIM_PID" 2>/dev/null || true
            exit 1
        fi
    done
}

cleanup() {
    echo
    echo "[train_sac.sh] cleanup..."
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
echo "[train_sac.sh] SAC egitimi basliyor (config=$CONFIG)..."
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.train_sac --config "$CONFIG"

# --- egitim bitti: grafikleri olustur ------------------------------------
LOG_DIR=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG')); print(c['train']['log_dir'])" 2>/dev/null || echo "runs/sac")
echo "[train_sac.sh] Grafikler olusturuluyor: $LOG_DIR/plots"
python3 "$PROJ_ROOT/scripts/plot_training.py" \
    --log "$LOG_DIR/training_log.csv" \
    --out "$LOG_DIR/plots" || echo "[train_sac.sh] Grafik olusturma basarisiz (devam)"
