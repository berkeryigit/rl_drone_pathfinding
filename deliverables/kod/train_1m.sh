#!/usr/bin/env bash
# ======================================================================
# Her seed icin 1M step SAC egitimi (500k checkpoint'tan resume).
# En iyi model EvalCallback tarafindan kaydedilir.
# Ogrenme yavaslayinca --stop-patience ile otomatik durur.
#
# Kullanim:
#     bash train_1m.sh                         # tum seedler, 1M step
#     SEEDS="2025 123" bash train_1m.sh        # sadece belirli seedler
#     TIMESTEPS=1500000 bash train_1m.sh       # farkli hedef
#     PATIENCE=50 bash train_1m.sh             # daha sabırli durdurma
#     NUM_ENVS=4 bash train_1m.sh              # daha az paralel env
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")"

SEEDS_STR="${SEEDS:-7 13 42 123 2025}"
TIMESTEPS="${TIMESTEPS:-1000000}"
PATIENCE="${PATIENCE:-40}"
NUM_ENVS="${NUM_ENVS:-}"

EXTRA=()
[ -n "$NUM_ENVS" ] && EXTRA+=(--num-envs "$NUM_ENVS")

echo "======================================================"
echo " 1M EGITIM (resume mod)"
echo " Seeds    : $SEEDS_STR"
echo " Hedef    : ${TIMESTEPS} toplam step"
echo " Patience : ${PATIENCE} ardisik eval'da iyilesme yoksa dur"
echo "======================================================"
echo ""

FAILED=()
for s in $SEEDS_STR; do
    echo "--- seed $s basliyor ---"
    if python3 train.py --seed "$s" --timesteps "$TIMESTEPS" \
        --resume --stop-patience "$PATIENCE" "${EXTRA[@]}"; then
        echo "--- seed $s tamamlandi ---"
    else
        echo "--- seed $s HATA (devam ediliyor) ---"
        FAILED+=("$s")
    fi
    echo ""
done

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "UYARI: Su seedlerde hata olustu: ${FAILED[*]}"
fi

echo "======================================================"
echo " Tum egitimler bitti."
echo " Sonraki adimlar:"
echo ""
echo "  1) Eval guncelle:"
echo "     python3 evaluate.py --runs-root runs --seeds-file seeds.txt \\"
echo "         --out ../sonuclar/eval_per_episode.csv"
echo ""
echo "  2) Bireysel seed grafikleri:"
echo "     python3 plot_per_seed.py"
echo ""
echo "  3) Birlesik rubrik grafikleri:"
echo "     python3 plot_results.py --runs-root runs --seeds-file seeds.txt \\"
echo "         --eval-csv ../sonuclar/eval_per_episode.csv \\"
echo "         --baseline-csv ../sonuclar/baseline_per_episode.csv \\"
echo "         --hp-root runs_hp --out ../sunum/grafikler \\"
echo "         --summary-out ../sonuclar/sonuclar.csv"
echo "======================================================"
