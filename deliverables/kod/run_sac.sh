#!/usr/bin/env bash
# SAC 5 seed paralel egitim (PPO ile adil kiyas verisi). Her seed tek torch
# thread'i kullanir (5 proc ~= 5 cekirdek); PPO orkestratoru ayni anda kalan
# cekirdekleri kullanir. Cikti: runs_sac/seed_<N>/
set -u
cd "$(dirname "$0")"
PY=../../../venv/bin/python
SEEDS=(7 13 42 123 2025)
TIMESTEPS=${1:-500000}
LOGDIR=logs_exp
mkdir -p "$LOGDIR"

echo "[run_sac] baslangic: ${#SEEDS[@]} seed x ${TIMESTEPS} adim (paralel)"
pids=()
for s in "${SEEDS[@]}"; do
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    "$PY" train_sac.py --seed "$s" --timesteps "$TIMESTEPS" \
    > "$LOGDIR/sac_seed_${s}.log" 2>&1 &
  pids+=($!)
  echo "[run_sac] seed=$s pid=$! basladi"
  sleep 2
done

fail=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "[run_sac] seed=${SEEDS[$i]} BITTI (ok)"
  else
    echo "[run_sac] seed=${SEEDS[$i]} HATA (exit!=0)"; fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "ALL_SAC_DONE" | tee "$LOGDIR/SAC_DONE.marker"
else
  echo "SAC_DONE_WITH_ERRORS" | tee "$LOGDIR/SAC_DONE.marker"
fi
