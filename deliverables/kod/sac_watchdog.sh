#!/usr/bin/env bash
# SAC kesme bekcisi (deadline yonetimi). SAC bu ortamda hizli yakinsadigindan
# (61k adimda ~346 getiri / 4.7 oda), 250k adim fazlasiyla oturmus politikadir.
# SAC seed_7 >= CAP adima ULASINCA veya en gec HARD_T'de SAC'i durdurur; boylece
# cekirdekler bosalir ve PPO sweep'leri 5 seed'i deadline'dan once bitirir.
# training_log.csv (egriler) + best_model.zip + checkpoints korunur.
set -u
cd "$(dirname "$0")"
CAP=${CAP:-250000}
HARD=$(date -d "today ${HARD_T:-05:00}" +%s)
LOGDIR=logs_exp
log() { echo "[$(date +%H:%M:%S)] watchdog: $*" | tee -a "$LOGDIR/STATUS.txt"; }
log "basladi (CAP=$CAP adim, hard_kill=$(date -d @$HARD +%H:%M))"

while true; do
  if ! pgrep -f train_sac.py >/dev/null; then
    log "SAC zaten bitti/durdu"; break
  fi
  ts=$(tail -1 runs_sac/seed_7/training_log.csv 2>/dev/null | cut -d, -f2)
  ts=${ts:-0}
  now=$(date +%s)
  if [ "$ts" -ge "$CAP" ] 2>/dev/null || [ "$now" -ge "$HARD" ]; then
    reason=$([ "$ts" -ge "$CAP" ] 2>/dev/null && echo "CAP ($ts adim)" || echo "hard deadline")
    log "SAC durduruluyor -> $reason"
    pkill -f train_sac.py
    sleep 4
    pkill -9 -f train_sac.py 2>/dev/null
    log "SAC durduruldu. seed adimlari: $(for s in 7 13 42 123 2025; do tail -1 runs_sac/seed_$s/training_log.csv 2>/dev/null|cut -d, -f2;done|tr '\n' ' ')"
    break
  fi
  sleep 30
done
echo "SAC_CAPPED" > "$LOGDIR/SAC_CAPPED.marker"
