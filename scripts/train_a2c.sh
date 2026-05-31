#!/usr/bin/env bash
# A2C (senkron A3C) eğitimi tek komutla:
#   ./scripts/train_a2c.sh                  # configs/a2c.yaml
#   ./scripts/train_a2c.sh configs/a2c.yaml
#
# train.sh ile aynı iskelet; tek fark: train_a2c modülü + a2c.yaml default.
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
CONFIG="${1:-configs/a2c.yaml}"

if [[ ! -f "$CONFIG" ]]; then
    echo "[train_a2c.sh] config bulunamadi: $CONFIG" >&2; exit 1
fi

# --- duplicate process guard -------------------------------------------------
LOCK_FILE="/tmp/rl_drone_train.lock"
if [[ -f "$LOCK_FILE" ]]; then
    OLD_PID=$(cat "$LOCK_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[train_a2c.sh] HATA: Egitim zaten calisiyor (pid=$OLD_PID)" >&2; exit 1
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

# --- env setup ---------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || { echo "[train_a2c.sh] once: cd ros2_ws && colcon build --symlink-install" >&2; exit 1; }
source ros2_ws/install/setup.bash
[[ -d .venv ]] || { echo "[train_a2c.sh] once: python3 -m venv .venv --system-site-packages && pip install -r requirements.txt" >&2; exit 1; }
source .venv/bin/activate

# --- gz transport loopback (KRITIK — transport freeze fix) -------------------
# Coklu ag arayuzunde gz transport "Host unreachable" verip reset()'i asiyor,
# egitim step~2048'de donuyordu. Localhost'a sabitle.
export GZ_IP=127.0.0.1
export IGN_IP=127.0.0.1
echo "[train_a2c.sh] GZ_IP=$GZ_IP"

# --- n_envs ------------------------------------------------------------------
N_ENVS=$(python3 -c "import yaml; print(int(yaml.safe_load(open('$CONFIG')).get('train',{}).get('n_envs',1)))")
echo "[train_a2c.sh] n_envs=$N_ENVS"

# --- bring up N sim instances ------------------------------------------------
declare -a SIM_PIDS=()
for i in $(seq 0 $((N_ENVS-1))); do
    ROS_DOMAIN_ID=$i GZ_PARTITION=sim$i \
        nohup ros2 launch rl_drone_pathfinding sim_launch.py > "/tmp/rl_drone_sim_${i}.log" 2>&1 &
    SIM_PIDS+=($!)
done
for i in $(seq 0 $((N_ENVS-1))); do
    ready=0
    for j in $(seq 1 30); do
        if ROS_DOMAIN_ID=$i timeout 2 ros2 topic echo /scan --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo "[train_a2c.sh] sim $i hazir"; ready=1; break
        fi; sleep 2
    done
    [[ $ready -eq 0 ]] && { echo "[train_a2c.sh] sim $i hazir olmadi" >&2; exit 1; }
done

cleanup() {
    rm -f "$LOCK_FILE"
    for pid in "${SIM_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true; done
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- train -------------------------------------------------------------------
echo "[train_a2c.sh] A2C egitimi basliyor (config=$CONFIG)..."
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.train_a2c --config "$CONFIG"
