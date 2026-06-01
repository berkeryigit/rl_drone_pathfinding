#!/bin/bash
# ============================================================================
# A3C — 8 versiyon ardışık EĞİTİM + EVAL (numpy hızlı sim, Gazebo/ROS YOK)
#   Her versiyon: 1.5M step A2C(~A3C) discrete eğitim + 100-episode eval.
#   Çıktılar: runs/a3c_v*/ , docs/EVAL_a3c_v*.md , docs/figures/ , logs/a3c_results.txt
#   MacBook'ta çalışır (CPU). Toplam ~1-2 saat (donanıma göre).
# ============================================================================
cd "$(dirname "$0")/.." || exit 1
# venv'i etkinleştir (adın farklıysa kendi venv'ini source et)
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || \
  echo "[uyari] venv bulunamadi — once: python3 -m venv .venv && pip install -r requirements_numpy.txt"

mkdir -p logs
RESULTS=logs/a3c_results.txt
echo "=== A3C 8-versiyon kosusu $(date) ===" >> "$RESULTS"

for v in a3c_v1 a3c_v2 a3c_v3 a3c_v4 a3c_v5 a3c_v6 a3c_v7 a3c_v8; do
  echo ""
  echo "################ EĞİTİM $v (1.5M) ################"
  python3 fast_sim/train_a3c.py --config "configs/$v.yaml" || { echo "[HATA] $v egitim basarisiz, sonrakine gec"; continue; }

  LH=$(grep -m1 "lidar_history:" "configs/$v.yaml" | awk '{print $2}')
  echo "################ EVAL $v (100 ep, lidar_history=$LH) ################"
  python3 fast_sim/eval_a3c.py --model "runs/$v/checkpoints/a3c_drone_final.zip" \
      --episodes 100 --version "$v" --lidar-history "$LH" | tee /tmp/_a3c_ev.txt
  grep EVAL_SUMMARY /tmp/_a3c_ev.txt | sed "s/^/$v  /" >> "$RESULTS"
done

echo ""
echo "===== TÜM VERSİYONLAR BİTTİ ====="
echo "Özet sonuçlar: $RESULTS"
echo "Detay + figürler: docs/EVAL_a3c_v*.md , docs/figures/eval_a3c_v*_*.png"
cat "$RESULTS"
