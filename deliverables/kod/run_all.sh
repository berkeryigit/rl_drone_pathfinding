#!/usr/bin/env bash
# run_all.sh — Tüm seed'leri sırayla eğitir
# ==========================================
# Kullanım:
#   chmod +x run_all.sh
#   ./run_all.sh                       # 300k adım, config.yaml
#   ./run_all.sh --timesteps 500000    # farklı adım sayısı
#   ./run_all.sh --config my.yaml      # farklı config
#
# Çıktı:
#   ../sonuclar/loglar/seed_<N>/checkpoints/dqn_drone_final.zip
#   ../sonuclar/loglar/seed_<N>/logs/progress.csv
#   ../sonuclar/loglar/seed_<N>/training_log.csv
#   ../sonuclar/loglar/seed_<N>/run_meta.json

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SEEDS_FILE="${SEEDS_FILE:-seeds.txt}"
CONFIG="${CONFIG:-config.yaml}"
EXTRA_ARGS="$*"

if [[ ! -f "$SEEDS_FILE" ]]; then
    echo "[run_all] Hata: $SEEDS_FILE bulunamadı" >&2
    exit 1
fi

SEEDS=()
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    SEEDS+=("$line")
done < "$SEEDS_FILE"

echo "[run_all] ${#SEEDS[@]} seed eğitilecek: ${SEEDS[*]}"
echo "[run_all] Config: $CONFIG"
echo "----------------------------------------"

START_TOTAL=$(date +%s)

for SEED in "${SEEDS[@]}"; do
    echo ""
    echo "========================================="
    echo "[run_all] Seed $SEED eğitimi başlıyor..."
    echo "========================================="
    START=$(date +%s)

    python train.py --config "$CONFIG" --seed "$SEED" $EXTRA_ARGS

    END=$(date +%s)
    ELAPSED=$((END - START))
    echo "[run_all] Seed $SEED tamamlandı — ${ELAPSED}s"
done

END_TOTAL=$(date +%s)
TOTAL=$((END_TOTAL - START_TOTAL))

echo ""
echo "========================================="
echo "[run_all] Tüm seedler tamamlandı — toplam ${TOTAL}s"
echo "========================================="
echo ""
echo "Sonuçlar ve grafikler oluşturuluyor..."
python plot_results.py
echo "İşlem tamam! Loglar ../sonuclar/loglar altında, grafikler ../sunum/grafikler altında."
