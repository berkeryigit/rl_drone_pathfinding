#!/usr/bin/env bash
# best_runs.json'daki top-N spawni sirayla Gazebo GUI'de oynatir.
#   ./scripts/replay_best.sh [TOP_N]   # default: tamamini oynat
# Ctrl-C ile durur.
set -eo pipefail

cd "$(dirname "$0")/.."

RESULTS="runs/ppo_v8_frontier/best_runs.json"
TOP_N="${1:-999}"

if [[ ! -f "$RESULTS" ]]; then
    echo "[replay_best] $RESULTS bulunamadi. Once scan_best.py calistirin." >&2
    exit 1
fi

MODEL="runs/ppo_v8_frontier/checkpoints/ppo_drone_final.zip"
CONFIG="configs/ppo.yaml"

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate

SIM_LOG="/tmp/rl_drone_sim.log"
SIM_PID=""

_cleanup() {
    echo ""
    echo "[replay_best] Durduruluyor..."
    [[ -n "$SIM_PID" ]] && kill "$SIM_PID" 2>/dev/null
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f parameter_bridge 2>/dev/null || true
}
trap _cleanup EXIT INT TERM

if ! pgrep -f "ros2 launch rl_drone_pathfinding sim_launch.py" >/dev/null 2>&1; then
    echo "[replay_best] Gazebo GUI baslatiliyor (ROS_DOMAIN_ID=0 GZ_PARTITION=sim0)..."
    SIM_HEADLESS=0 ROS_DOMAIN_ID=0 GZ_PARTITION=sim0 \
        nohup ros2 launch rl_drone_pathfinding sim_launch.py > "$SIM_LOG" 2>&1 &
    SIM_PID=$!
    echo -n "[replay_best] /scan bekleniyor"
    for i in $(seq 1 30); do
        if ROS_DOMAIN_ID=0 timeout 2 ros2 topic echo /scan \
               --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo " hazir."
            break
        fi
        echo -n "."
        sleep 2
    done
else
    echo "[replay_best] Sim zaten calisiyor."
fi

# JSON'dan spawn_idx listesini cek (voxel'e gore sirali, top N)
SPAWN_LIST=$(python3 -c "
import json, sys
data = json.load(open('$RESULTS'))
runs = data.get('top200', data.get('top10', []))[:$TOP_N]
for r in runs:
    print(r['spawn_idx'], r['return'], r['rooms'], r['floors'], r['voxels'])
")

if [[ -z "$SPAWN_LIST" ]]; then
    echo "[replay_best] JSON'da kayitli run yok!" >&2
    exit 1
fi

TOTAL=$(echo "$SPAWN_LIST" | wc -l)
echo "[replay_best] $TOTAL kayitli run bulundu (rooms>=3, voxel sirasina gore)"
echo "[replay_best] Her run 1 episode oynatilacak, Ctrl-C ile dur."
echo "========================================================================"

LOOP=0
while true; do
    LOOP=$((LOOP + 1))
    echo ""
    echo "--- Tur $LOOP ---"
    IDX=0
    while IFS=' ' read -r SPAWN_IDX RET ROOMS FLOORS VOX; do
        IDX=$((IDX + 1))
        echo -n "[$IDX/$TOTAL] spawn=$SPAWN_IDX  beklenen: ret≈$RET rooms=$ROOMS floors=$FLOORS vox=$VOX  →  "
        python3 -m rl_drone_pathfinding.agents.eval_ppo \
            --config  "$CONFIG" \
            --model   "$MODEL" \
            --episodes 1 \
            --spawn-idx "$SPAWN_IDX" \
            --deterministic 2>/dev/null | grep "^ep\|^mean" || true
    done <<< "$SPAWN_LIST"
done
