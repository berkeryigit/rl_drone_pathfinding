#!/usr/bin/env bash
# Training gibi N_ENVS paralel Gazebo + N_ENVS paralel scan süreci başlatır.
# Her süreç kendi domain'inde (ROS_DOMAIN_ID=i, GZ_PARTITION=simi) koşar.
# Bittikten sonra tüm sonuçları birleştirir → best_runs.json
#
# Kullanım:
#   ./scripts/scan_parallel.sh [TOPLAM_EP] [N_ENVS]
#   ./scripts/scan_parallel.sh 20000 4      # default
set -eo pipefail

cd "$(dirname "$0")/.."

TOTAL_EPS="${1:-20000}"
N_ENVS="${2:-4}"
EP_PER_ENV=$(( (TOTAL_EPS + N_ENVS - 1) / N_ENVS ))   # ceil division

source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate

echo "============================================================"
echo "[scan_parallel] $TOTAL_EPS ep toplam, $N_ENVS paralel env"
echo "[scan_parallel] Her env: $EP_PER_ENV ep"
echo "============================================================"

# --- Gazebo instance'larını başlat -------------------------------------------
declare -a SIM_PIDS=()
for i in $(seq 0 $((N_ENVS-1))); do
    LOG="/tmp/rl_drone_sim_${i}.log"
    echo "[scan_parallel] Sim $i baslatiliyor (domain=$i, partition=sim$i)..."
    ROS_DOMAIN_ID=$i GZ_PARTITION=sim$i SIM_HEADLESS=1 \
        nohup ros2 launch rl_drone_pathfinding sim_launch.py \
        > "$LOG" 2>&1 &
    SIM_PIDS+=($!)
done

# --- Simler hazır olana kadar bekle ------------------------------------------
for i in $(seq 0 $((N_ENVS-1))); do
    echo -n "[scan_parallel] Sim $i /scan bekleniyor"
    for j in $(seq 1 30); do
        if ROS_DOMAIN_ID=$i timeout 2 ros2 topic echo /scan \
               --once --qos-reliability best_effort >/dev/null 2>&1; then
            echo " hazir ($j. deneme)"
            break
        fi
        echo -n "."; sleep 2
    done
done

cleanup() {
    echo "[scan_parallel] Cleanup..."
    for pid in "${SIM_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f parameter_bridge 2>/dev/null || true
    # scan prosesleri zaten bitti
}
trap cleanup EXIT INT TERM

# --- Paralel scan süreçlerini başlat -----------------------------------------
declare -a SCAN_PIDS=()
declare -a OUT_FILES=()
for i in $(seq 0 $((N_ENVS-1))); do
    OUT="/tmp/scan_env${i}.json"
    LOG="/tmp/scan_env${i}.log"
    OUT_FILES+=("$OUT")
    echo "[scan_parallel] Scan $i baslatiliyor ($EP_PER_ENV ep) → $LOG"
    ENV_ID=$i PYTHONUNBUFFERED=1 \
        python3 scripts/scan_best.py "$EP_PER_ENV" --out "$OUT" \
        > "$LOG" 2>&1 &
    SCAN_PIDS+=($!)
done

echo ""
echo "[scan_parallel] Tum scanler calisiyor. Log'lar:"
for i in $(seq 0 $((N_ENVS-1))); do
    echo "  tail -f /tmp/scan_env${i}.log"
done
echo ""
echo "[scan_parallel] Hepsini birden izlemek icin:"
echo "  tail -f /tmp/scan_env*.log"
echo ""

# --- Hepsinin bitmesini bekle ------------------------------------------------
for i in "${!SCAN_PIDS[@]}"; do
    wait "${SCAN_PIDS[$i]}" 2>/dev/null || true
    echo "[scan_parallel] Scan env$i tamamlandi."
done

echo ""
echo "[scan_parallel] Sonuclar birlestiriliyor..."

# --- Merge: tum JSON'lari birleştir, global top-200 kaydet -------------------
python3 - "${OUT_FILES[@]}" << 'PYEOF'
import json, sys
from pathlib import Path

TOP_N = 200
MIN_ROOMS = 3

merged: list[dict] = []
total_eps = 0
total_found3 = 0

for path in sys.argv[1:]:
    try:
        data = json.loads(Path(path).read_text())
    except Exception as e:
        print(f"  [merge] {path} okunamadi: {e}")
        continue
    total_eps    += data.get("done_eps", 0)
    total_found3 += data.get("rooms3_found", 0)
    merged.extend(data.get("top200", []))

# Global sort: reward DESC, voxels DESC
merged.sort(key=lambda x: (-x["return"], -x["voxels"]))
top = merged[:TOP_N]

out = Path("runs/ppo_v8_frontier/best_runs.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    "total_eps":    total_eps,
    "rooms3_found": total_found3,
    "top200":       top,
}, indent=2))

print(f"  [merge] {total_eps} ep toplam, rooms>=3: {total_found3}")
print(f"  [merge] Top {len(top)} kaydedildi → {out}")

if top:
    print(f"\n  {'EP':>6} {'ENV':>4} {'SPAWN':>18} {'RETURN':>8} "
          f"{'ROOMS':>5} {'FLOORS':>6} {'VOX':>6} {'STEPS':>5}")
    for r in top[:20]:
        sx = r["spawn_idx"]
        sp = r["spawn_pos"]
        print(f"  {r['ep']:6d} {r['env_id']:4d} "
              f"s{sx}({sp[0]:+.0f},{sp[1]:+.0f},z={sp[2]:.1f})  "
              f"{r['return']:+8.1f} {r['rooms']:5d} {r['floors']:6d} "
              f"{r['voxels']:6d} {r['steps']:5d}")
    print(f"\n  Replay: ./scripts/replay_best.sh")
else:
    print("  rooms>=3 bulunamadi!")
PYEOF

echo ""
echo "[scan_parallel] Tamamlandi. best_runs.json hazir."
echo "Replay: ./scripts/replay_best.sh"
