#!/usr/bin/env bash
# PPO deney orkestratoru (hocanin "metrikleri degistir, yeniden egit, kiyasla"
# istegi). SAC ayri ~5 cekirdek kullandigi icin PPO burada num_envs=7 ile kosar.
#
# Faz 1  Bonus uzun-ufuk: seed 123'u 5M adima uzat (kullanicinin uzun-egitim
#        istegi). Ana 5-seed teslim 1.5M'de tutulur; bu AYRI runs_long/'da.
# Faz 2  Hiperparametre sweep'leri (5 param x >=3 deger x 5 seed x 200k):
#        clip_range, ent_coef, gamma, learning_rate, vf_coef  -> runs_hp5/
# Faz 3  gamma x lr grid (3x3 x 3 seed x 150k)  -> runs_grid/  (heatmap icin)
set -u
cd "$(dirname "$0")"
PY=../../../venv/bin/python
NENV=7
SEEDS=(7 13 42 123 2025)
GSEEDS=(7 42 123)
SWEEP_TS=200000
GRID_TS=150000
LONG_TS=5000000
LOGDIR=logs_exp
mkdir -p "$LOGDIR"
ts() { date +%H:%M:%S; }

run_one() { # <out> <logname> <extra-args...>
  local out="$1"; shift
  local logn="$1"; shift
  if [ -f "$out/final_model.zip" ]; then
    echo "[$(ts)] ATLA (mevcut): $out"; return 0
  fi
  echo "[$(ts)] KOS: $out  ($*)"
  "$PY" train.py --num-envs "$NENV" --no-eval --out "$out" "$@" \
    > "$LOGDIR/$logn.log" 2>&1 || echo "[$(ts)] HATA: $out (devam)"
}

# ---------------------------------------------------------------- Faz 1
echo "===== FAZ 1: Bonus uzun-ufuk (seed 123 -> ${LONG_TS}) $(ts) ====="
if [ ! -f runs_long/seed_123/final_model.zip ]; then
  mkdir -p runs_long
  cp -r runs/seed_123 runs_long/seed_123
  echo "[$(ts)] seed_123 kopyalandi -> runs_long/ (resume ile uzatiliyor)"
  "$PY" train.py --seed 123 --resume --timesteps "$LONG_TS" --no-eval \
    --num-envs 8 --out runs_long/seed_123 \
    > "$LOGDIR/long_seed_123.log" 2>&1 || echo "[$(ts)] HATA: long seed_123"
fi
echo "FAZ1_DONE" > "$LOGDIR/PHASE1.marker"

# ---------------------------------------------------------------- Faz 2
echo "===== FAZ 2: Hiperparametre sweep'leri $(ts) ====="
declare -A FLAG=( [clip_range]="--clip-range" [ent_coef]="--ent-coef" \
                  [gamma]="--gamma" [learning_rate]="--lr" [vf_coef]="--vf-coef" )
sweep() { # <param> <values...>
  local p="$1"; shift
  for v in "$@"; do
    for s in "${SEEDS[@]}"; do
      run_one "runs_hp5/$p/$v/seed_$s" "hp_${p}_${v}_s${s}" \
        --seed "$s" --timesteps "$SWEEP_TS" "${FLAG[$p]}" "$v"
    done
  done
}
sweep clip_range    0.1 0.2 0.3
sweep ent_coef      0.0 0.005 0.01 0.05
sweep gamma         0.95 0.98 0.99
sweep learning_rate 1e-4 3e-4 1e-3
sweep vf_coef       0.25 0.5 1.0
echo "FAZ2_DONE" > "$LOGDIR/PHASE2.marker"

# ---------------------------------------------------------------- Faz 3
echo "===== FAZ 3: gamma x lr grid (heatmap) $(ts) ====="
for g in 0.95 0.98 0.99; do
  for lr in 1e-4 3e-4 1e-3; do
    for s in "${GSEEDS[@]}"; do
      run_one "runs_grid/g${g}_lr${lr}/seed_$s" "grid_g${g}_lr${lr}_s${s}" \
        --seed "$s" --timesteps "$GRID_TS" --gamma "$g" --lr "$lr"
    done
  done
done
echo "FAZ3_DONE" > "$LOGDIR/PHASE3.marker"

echo "ALL_PPO_EXP_DONE $(ts)" | tee "$LOGDIR/PPO_EXP_DONE.marker"
