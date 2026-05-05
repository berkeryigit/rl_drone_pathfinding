#!/usr/bin/env bash
# Snapshots training health every N seconds into a single log file.
# Spawned alongside training; loops until the train_ppo process is gone.
#
# Output file: /tmp/training_progress.log  (overwritten each run)
set -eo pipefail
INTERVAL="${1:-300}"   # default 5 minutes
OUT=/tmp/training_progress.log
PROJ="$(cd "$(dirname "$0")/.." && pwd)"

source /opt/ros/jazzy/setup.bash 2>/dev/null || true

: > "$OUT"
echo "[watchdog] started PID=$$  interval=${INTERVAL}s  output=$OUT" >> "$OUT"

# Wait up to 5 minutes for the python train_ppo process to appear before
# starting the snapshot loop (train.sh first brings the sim up, which can
# take ~20 s).
for _ in $(seq 1 60); do
    pgrep -f "train_ppo --config" >/dev/null && break
    sleep 5
done
echo "[watchdog] train_ppo seen, entering snapshot loop" >> "$OUT"

while pgrep -f "train_ppo --config" >/dev/null; do
    {
        echo "================ $(date '+%Y-%m-%d %H:%M:%S') ================"
        echo "-- alive PIDs --"
        pgrep -fa "train_ppo|gz sim|ros2 launch rl_drone|parameter_bridge|timeout.*train" \
            2>/dev/null | grep -v "snapshot-bash" | head -8
        echo "-- gz /stats (RTF, sim_time) --"
        timeout 2 gz topic -e -n 1 -t /stats 2>/dev/null \
            | grep -E "real_time_factor|sim_time|iterations" \
            | head -4 || echo "  (no /stats)"
        echo "-- checkpoints --"
        ls -lt "$PROJ/runs/ppo/checkpoints/" 2>/dev/null | head -8
        echo "-- last 12 lines of train log --"
        tail -12 /tmp/train_ppo.log 2>/dev/null
        echo
    } >> "$OUT"
    sleep "$INTERVAL"
done

echo "================ $(date '+%Y-%m-%d %H:%M:%S') TRAIN GONE ================" >> "$OUT"
echo "-- final checkpoints --" >> "$OUT"
ls -lt "$PROJ/runs/ppo/checkpoints/" 2>/dev/null | head -10 >> "$OUT"
echo "-- last 30 lines of train log --" >> "$OUT"
tail -30 /tmp/train_ppo.log 2>/dev/null >> "$OUT"
