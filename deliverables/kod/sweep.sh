#!/usr/bin/env bash
# ======================================================================
# Hiperparametre duyarliligi (Grafik 4) icin sweep: 2 parametre x 3 deger.
#   - learning_rate: 1e-4, 3e-4, 1e-3   (algo/td3 sweep'i ile AYNI degerler)
#   - ent_coef     : 0.0, 0.01, 0.05    (PPO entropi bonusu => kesif-somuru)
# Cikti: runs_hp/<param>/<value>/seed_<s>/training_log.csv
# plot_results.py bu yapidan Grafik 4'u uretir.
#
# Maliyeti dusurmek icin daha az step + az seed kullanilabilir:
#     HP_TIMESTEPS=150000 HP_SEEDS="7 13 42" bash sweep.sh
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")"

HP_TIMESTEPS="${HP_TIMESTEPS:-200000}"
HP_SEEDS="${HP_SEEDS:-7 13 42}"

echo "=== sweep: learning_rate ==="
for v in 1e-4 3e-4 1e-3; do
    for s in $HP_SEEDS; do
        python3 train.py --seed "$s" --timesteps "$HP_TIMESTEPS" --no-eval \
            --lr "$v" --out "runs_hp/learning_rate/$v/seed_$s"
    done
done

echo "=== sweep: ent_coef ==="
for v in 0.0 0.01 0.05; do
    for s in $HP_SEEDS; do
        python3 train.py --seed "$s" --timesteps "$HP_TIMESTEPS" --no-eval \
            --ent-coef "$v" --out "runs_hp/ent_coef/$v/seed_$s"
    done
done

echo "=== sweep bitti. plot_results.py --hp-root runs_hp ile Grafik 4 uretilir. ==="
