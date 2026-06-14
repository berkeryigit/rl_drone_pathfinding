#!/usr/bin/env bash
# ======================================================================
# Tum pipeline: her seed icin 2D PPO egitimi -> deterministik eval ->
# baseline -> 5 zorunlu grafik + sonuclar.csv.
#
# Egitim SADECE 2D Gymnasium ortaminda yapilir (Gazebo'da DEGIL).
# Ortam/eval/baseline kosullari algo/td3 (SAC) teslimi ile birebir aynidir.
#
# Kullanim:
#     bash run_all.sh                    # config.yaml'daki total_timesteps (1M)
#     TIMESTEPS=1500000 bash run_all.sh  # daha uzun egitim
#     NUM_ENVS=12 bash run_all.sh
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")"

SEEDS_FILE="seeds.txt"
RUNS_ROOT="runs"
TIMESTEPS="${TIMESTEPS:-}"
NUM_ENVS="${NUM_ENVS:-}"

EXTRA=()
[ -n "$TIMESTEPS" ] && EXTRA+=(--timesteps "$TIMESTEPS")
[ -n "$NUM_ENVS" ] && EXTRA+=(--num-envs "$NUM_ENVS")

SEEDS=$(grep -vE '^\s*#|^\s*$' "$SEEDS_FILE")

echo "=== 1) EGITIM (her seed, PPO) ==="
for s in $SEEDS; do
    echo "--- seed $s ---"
    python3 train.py --config config.yaml --seed "$s" --out "$RUNS_ROOT/seed_$s" "${EXTRA[@]}"
done

echo "=== 2) DETERMINISTIK EVAL ==="
python3 evaluate.py --runs-root "$RUNS_ROOT" --seeds-file "$SEEDS_FILE" \
    --out ../sonuclar/eval_per_episode.csv

echo "=== 3) BASELINE (random + heuristic) ==="
python3 baseline.py --seeds-file "$SEEDS_FILE" --out ../sonuclar/baseline_per_episode.csv

echo "=== 4) GRAFIKLER + sonuclar.csv ==="
# 5 zorunlu grafik + ozet (minimal, rubrik):
python3 plot_results.py --runs-root "$RUNS_ROOT" --seeds-file "$SEEDS_FILE" \
    --eval-csv ../sonuclar/eval_per_episode.csv \
    --baseline-csv ../sonuclar/baseline_per_episode.csv \
    --hp-root runs_hp5 \
    --out ../sunum/grafikler --summary-out ../sonuclar/sonuclar.csv
# Genis grafik seti (oda/carpisma/seed/ic-dinamik/heatmap/per-seed/PPO-vs-SAC):
python3 viz.py --section all --out ../sunum/grafikler || true
# Rapor LaTeX tablolari (ham CSV'lerden):
python3 make_tables.py || true

echo "=== ham loglari sonuclar/loglar/ altina kopyala ==="
mkdir -p ../sonuclar/loglar
for s in $SEEDS; do
    if [ -f "$RUNS_ROOT/seed_$s/training_log.csv" ]; then
        cp "$RUNS_ROOT/seed_$s/training_log.csv" "../sonuclar/loglar/training_log_seed_$s.csv"
    fi
    if [ -d "$RUNS_ROOT/seed_$s/tb" ]; then
        mkdir -p "../sonuclar/loglar/tb_seed_$s"
        cp -r "$RUNS_ROOT/seed_$s/tb/." "../sonuclar/loglar/tb_seed_$s/" 2>/dev/null || true
    fi
done

echo "=== BITTI (ana PPO pipeline). Grafikler: ../sunum/grafikler/  Loglar: ../sonuclar/loglar/ ==="
echo ""
echo "EK ADIMLAR (hocanin RL-ozgu istekleri + algoritma kiyasi):"
echo "  1) Hiperparametre taramasi (5 param x >=3 deger x 5 seed):"
echo "       bash sweep.sh                       # -> runs_hp5/ , runs_grid/"
echo "  2) Tum grafikleri + ozet tablosunu yeniden uret:"
echo "       python3 viz.py --section all --out ../sunum/grafikler && python3 make_tables.py"
echo "  3) PPO vs SAC yan-yana kiyas figurleri (Akif'in yayinlanmis grafikleriyle):"
echo "       python3 make_comparison_figs.py"
echo "  4) Deadline-farkinda paralel orkestrasyon: bash plan.sh"
