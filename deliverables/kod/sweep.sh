#!/usr/bin/env bash
# ======================================================================
# Hiperparametre duyarliligi (Grafik 4 + Grafik 10) icin sweep.
# Hocanin "metrikleri degistir, yeniden egit, kiyasla" istegi dogrultusunda
# BES hiperparametre, her biri >=3 deger x 5 seed ile yeniden egitilir:
#
#   clip_range    : 0.1, 0.2, 0.3            (PPO politika klipsi)
#   ent_coef      : 0.0, 0.005, 0.01, 0.05   (entropi/kesif bonusu)
#   gamma         : 0.95, 0.98, 0.99         (indirim faktoru / ufuk)
#   learning_rate : 1e-4, 3e-4, 1e-3         (adim buyuklugu)
#   vf_coef       : 0.25, 0.5, 1.0           (deger-kaybi katsayisi)
#
# Ayrica gamma x learning_rate 3x3 izgara (Grafik 10 isi haritasi).
# Cikti: runs_hp5/<param>/<value>/seed_<s>/  ve  runs_grid/g<g>_lr<lr>/seed_<s>/
# viz.py bu yapilardan Grafik 4 ve Grafik 10'u uretir.
#
# Kisa butce (HP etkisini izole etmek icin); maliyet ayarlanabilir:
#     HP_TIMESTEPS=120000 HP_SEEDS="7 13 42 123 2025" bash sweep.sh
# Not: deadline-farkinda paralel orkestrasyon icin plan.sh kullanilir; bu script
# basit, deterministik, sirali yeniden-uretim icindir.
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")"

HP_TIMESTEPS="${HP_TIMESTEPS:-120000}"
HP_SEEDS="${HP_SEEDS:-7 13 42 123 2025}"
GRID_TIMESTEPS="${GRID_TIMESTEPS:-120000}"
GRID_SEEDS="${GRID_SEEDS:-7 42 123}"

sweep() {  # <param-dir> <flag> <values...>
    local p="$1" flag="$2"; shift 2
    echo "=== sweep: $p ==="
    for v in "$@"; do
        for s in $HP_SEEDS; do
            python3 train.py --seed "$s" --timesteps "$HP_TIMESTEPS" --no-eval \
                "$flag" "$v" --out "runs_hp5/$p/$v/seed_$s"
        done
    done
}

sweep clip_range    --clip-range 0.1 0.2 0.3
sweep ent_coef      --ent-coef   0.0 0.005 0.01 0.05
sweep gamma         --gamma      0.95 0.98 0.99
sweep learning_rate --lr         1e-4 3e-4 1e-3
sweep vf_coef       --vf-coef    0.25 0.5 1.0

echo "=== gamma x lr izgarasi (Grafik 10 isi haritasi) ==="
for g in 0.95 0.98 0.99; do
    for lr in 1e-4 3e-4 1e-3; do
        for s in $GRID_SEEDS; do
            python3 train.py --seed "$s" --timesteps "$GRID_TIMESTEPS" --no-eval \
                --gamma "$g" --lr "$lr" --out "runs_grid/g${g}_lr${lr}/seed_$s"
        done
    done
done

echo "=== sweep bitti. viz.py --section main ile Grafik 4 + 10 uretilir. ==="
