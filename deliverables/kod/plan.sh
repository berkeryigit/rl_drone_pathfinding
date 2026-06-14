#!/usr/bin/env bash
# DEADLINE-FARKINDA PPO deney orkestratoru.
# Hedef: tum egitimler ~06:30'da bitsin (kullanici deadline 07:30; kalan 1 saat
# grafik/rapor/pptx/pdf derleme + paketleme icindir).
#
# Strateji (vakte sigdirma):
#  - SWEEP'ler ONCE (hocanin cekirdek istegi + rubrik Grafik 4). SEED ROUND-ROBIN:
#    her turda TUM 16 degere +1 seed eklenir => deadline gelirse kapsama dengeli
#    kalir (>=3 seed garanti, hedef 5). Sub-deadline SWEEP_DL'de durur.
#  - GRID (gamma x lr heatmap) ikinci, GRID_DL'de durur.
#  - LONG (bonus uzun-ufuk) en son, timeout ile kapakli, hedef 3M (5M degil).
#  - Her kosudan once saat kontrol; gecmisse o faz atlanir.
# STATUS surekli logs_exp/STATUS.txt'ye yazilir (ilerleme kaybolmaz).
set -u
cd "$(dirname "$0")"
PY=../../../venv/bin/python
NENV=${NENV:-7}
LOGDIR=logs_exp
mkdir -p "$LOGDIR"
STATUS="$LOGDIR/STATUS.txt"

SWEEP_DL=$(date -d "today ${SWEEP_DL_T:-06:00}" +%s)
GRID_DL=$(date -d "today ${GRID_DL_T:-06:20}" +%s)
LONG_DL=$(date -d "today ${LONG_DL_T:-06:25}" +%s)
LONG_BUDGET=${LONG_BUDGET:-900}        # bonus long max sn (15 dk)
SWEEP_TS=${SWEEP_TS:-200000}
GRID_TS=${GRID_TS:-150000}
LONG_TS=${LONG_TS:-3000000}
SEEDS=(7 13 42 123 2025)
GSEEDS=(7 42 123)
DONE=0

now() { date +%s; }
hhmm() { date +%H:%M:%S; }
log() { echo "[$(hhmm)] $*" | tee -a "$STATUS"; }

run_one() { # <out> <logname> <args...>
  local out="$1"; shift; local logn="$1"; shift
  if [ -f "$out/final_model.zip" ]; then return 0; fi
  local t0=$(now)
  "$PY" train.py --num-envs "$NENV" --no-eval --out "$out" "$@" \
    > "$LOGDIR/$logn.log" 2>&1 || log "HATA: $out"
  DONE=$((DONE+1))
  local dt=$(( $(now) - t0 ))
  log "ok($DONE) $out  [${dt}s]"
}

log "===== PLAN BASLADI ===== NENV=$NENV SWEEP_TS=$SWEEP_TS"
log "deadlines: sweep=$(date -d @$SWEEP_DL +%H:%M) grid=$(date -d @$GRID_DL +%H:%M) long=$(date -d @$LONG_DL +%H:%M)"

# --------------------------------------------------------------- FAZ A: SWEEP
log "===== FAZ A: Hiperparametre sweep'leri (round-robin seed) ====="
# (param, value) ciftleri
declare -a PV
for v in 0.1 0.2 0.3;            do PV+=("clip_range|$v|--clip-range"); done
for v in 0.0 0.005 0.01 0.05;    do PV+=("ent_coef|$v|--ent-coef"); done
for v in 0.95 0.98 0.99;         do PV+=("gamma|$v|--gamma"); done
for v in 1e-4 3e-4 1e-3;         do PV+=("learning_rate|$v|--lr"); done
for v in 0.25 0.5 1.0;           do PV+=("vf_coef|$v|--vf-coef"); done
log "sweep: ${#PV[@]} deger x ${#SEEDS[@]} seed (hedef), round-robin"

round=0
for s in "${SEEDS[@]}"; do
  if [ "$(now)" -ge "$SWEEP_DL" ]; then log "SWEEP_DL gecti, round-$round'da durduruldu"; break; fi
  round=$((round+1))
  log "--- sweep round $round (seed $s) ---"
  for pv in "${PV[@]}"; do
    if [ "$(now)" -ge "$SWEEP_DL" ]; then break; fi
    IFS='|' read -r p val flag <<< "$pv"
    run_one "runs_hp5/$p/$val/seed_$s" "hp_${p}_${val}_s${s}" \
      --seed "$s" --timesteps "$SWEEP_TS" "$flag" "$val"
  done
  log "round $round bitti (her degerde $round seed)"
done
echo "SWEEP_DONE round=$round" > "$LOGDIR/PHASE_SWEEP.marker"
log "FAZ A bitti: tamamlanan tam seed turu = $round"

# --------------------------------------------------------------- FAZ B: GRID
log "===== FAZ B: gamma x lr grid (heatmap) ====="
groundn=0
for s in "${GSEEDS[@]}"; do
  if [ "$(now)" -ge "$GRID_DL" ]; then log "GRID_DL gecti, durduruldu"; break; fi
  groundn=$((groundn+1))
  for g in 0.95 0.98 0.99; do
    for lr in 1e-4 3e-4 1e-3; do
      if [ "$(now)" -ge "$GRID_DL" ]; then break 2; fi
      run_one "runs_grid/g${g}_lr${lr}/seed_$s" "grid_g${g}_lr${lr}_s${s}" \
        --seed "$s" --timesteps "$GRID_TS" --gamma "$g" --lr "$lr"
    done
  done
  log "grid round $groundn bitti"
done
echo "GRID_DONE round=$groundn" > "$LOGDIR/PHASE_GRID.marker"

# --------------------------------------------------------------- FAZ C: LONG (bonus)
log "===== FAZ C: Bonus uzun-ufuk (seed 123 -> ${LONG_TS}, timeout ${LONG_BUDGET}s) ====="
if [ "$(now)" -lt "$LONG_DL" ] && [ ! -f runs_long/seed_123/final_model.zip ]; then
  mkdir -p runs_long
  cp -r runs/seed_123 runs_long/seed_123
  timeout "$LONG_BUDGET" "$PY" train.py --seed 123 --resume --timesteps "$LONG_TS" \
    --no-eval --num-envs 8 --out runs_long/seed_123 \
    > "$LOGDIR/long_seed_123.log" 2>&1
  log "uzun-ufuk bitti (veya timeout): $(tail -1 runs_long/seed_123/training_log.csv 2>/dev/null | cut -d, -f1-2)"
else
  log "uzun-ufuk atlandi (deadline veya mevcut)"
fi
echo "LONG_DONE" > "$LOGDIR/PHASE_LONG.marker"

log "===== PLAN BITTI ===== toplam kosu=$DONE"
echo "ALL_PPO_PLAN_DONE $(hhmm) runs=$DONE" | tee "$LOGDIR/PPO_PLAN_DONE.marker"
