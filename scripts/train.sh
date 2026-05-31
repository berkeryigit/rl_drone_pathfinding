#!/usr/bin/env bash
# Tek komutla eğitime başla:
#   ./scripts/train.sh                            # default config (configs/ppo.yaml)
#   ./scripts/train.sh configs/ppo_quick.yaml     # alt config
#
# n_envs > 1 ise N Gazebo instance açılır. Her biri farklı ROS_DOMAIN_ID ve
# GZ_PARTITION ile izole edilir (domain i → sim isimlendirmesi: sim<i>).
# `set -u` would fire on unbound vars inside ROS's setup.bash; drop it.
set -eo pipefail

cd "$(dirname "$0")/.."
PROJ_ROOT="$(pwd)"
CONFIG="${1:-configs/ppo.yaml}"

if [[ ! -f "$CONFIG" ]]; then
    echo "[train.sh] config bulunamadi: $CONFIG" >&2
    exit 1
fi

# --- duplicate process guard -------------------------------------------------
LOCK_FILE="/tmp/rl_drone_train.lock"
if [[ -f "$LOCK_FILE" ]]; then
    OLD_PID=$(cat "$LOCK_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[train.sh] HATA: Egitim zaten calisiyor (pid=$OLD_PID, lock=$LOCK_FILE)" >&2
        echo "[train.sh] Onceki sureci durdurmak icin: kill $OLD_PID" >&2
        exit 1
    fi
    echo "[train.sh] Eski lock temizleniyor (pid=$OLD_PID artik yok)"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
echo "[train.sh] Lock olusturuldu: $LOCK_FILE (pid=$$)"

# --- env setup ---------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
[[ -f ros2_ws/install/setup.bash ]] || {
    echo "[train.sh] ros2_ws/install yok; once: cd ros2_ws && colcon build --symlink-install" >&2
    exit 1
}
source ros2_ws/install/setup.bash
[[ -d .venv ]] || {
    echo "[train.sh] .venv yok; once: python3 -m venv .venv --system-site-packages && pip install -r requirements.txt" >&2
    exit 1
}
source .venv/bin/activate

# --- gz transport loopback (KRITIK) ------------------------------------------
# Bu makinede wlp4s0 (hotspot) UP, docker0/eno1 DOWN. gz transport service
# yanitlarini erisilemez arayuze gondermeye calisip "Host unreachable" seli
# uretiyor; reset()'teki set_pose asiliyor ve egitim step 2048'de donuyordu.
# Her sey localhost'ta -> transport'u loopback'e sabitle.
export GZ_IP=127.0.0.1
export IGN_IP=127.0.0.1
echo "[train.sh] GZ_IP=$GZ_IP (transport loopback'e sabitlendi)"

# --- read n_envs from config -------------------------------------------------
N_ENVS=$(python3 -c "
import yaml, sys
c = yaml.safe_load(open('$CONFIG'))
print(int(c.get('train', {}).get('n_envs', 1)))
")
echo "[train.sh] n_envs=$N_ENVS"

# --- bring up N sim instances ------------------------------------------------
declare -a SIM_PIDS=()

for i in $(seq 0 $((N_ENVS-1))); do
    SIM_LOG="/tmp/rl_drone_sim_${i}.log"
    echo "[train.sh] sim $i baslatiliyor (ROS_DOMAIN_ID=$i GZ_PARTITION=sim$i)..."
    ROS_DOMAIN_ID=$i GZ_PARTITION=sim$i \
        nohup ros2 launch rl_drone_pathfinding sim_launch.py \
        > "$SIM_LOG" 2>&1 &
    SIM_PIDS+=($!)
done

# --- wait for all sims to be ready -------------------------------------------
for i in $(seq 0 $((N_ENVS-1))); do
    echo "[train.sh] sim $i icin /scan bekleniyor..."
    ready=0
    for j in $(seq 1 30); do
        if ROS_DOMAIN_ID=$i timeout 2 ros2 topic echo /scan \
               --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo "[train.sh] sim $i hazir (${j}. denemede)"
            ready=1
            break
        fi
        sleep 2
    done
    if [[ $ready -eq 0 ]]; then
        echo "[train.sh] sim $i 60s'de hazir olmadi, log: /tmp/rl_drone_sim_${i}.log" >&2
        exit 1
    fi
done

cleanup() {
    echo
    echo "[train.sh] cleanup..."
    rm -f "$LOCK_FILE"
    for pid in "${SIM_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
    done
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "parameter_bridge" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- train -------------------------------------------------------------------
echo "[train.sh] PPO egitimi basliyor (config=$CONFIG)..."
cd "$PROJ_ROOT"
python3 -m rl_drone_pathfinding.agents.train_ppo --config "$CONFIG"
