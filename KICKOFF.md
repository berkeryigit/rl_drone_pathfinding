# PPO v9 Eğitim Kickoff — 30 Mayıs 2026

Bu dosya yeni bir Claude oturumu için hazırlanmıştır.
**Okumadan hiçbir şey yapma. Her şey burada.**

---

## Proje Özeti

`~/Desktop/RLProje/rl_drone_pathfinding` — KOU RL dönem projesi.
- GitHub: `berkeryigit/rl_drone_pathfinding`, branch: **`algo/ppo`**
- Stack: Gazebo Harmonic + ROS 2 Jazzy + Stable-Baselines3 PPO + Python 3.12
- Berker → PPO continuous. Diğer arkadaşlar TD3/DQN/A3C kendi branch'lerinde.
- `main` branch'e asla push yapma — sadece `algo/ppo`.

---

## Şu Anki Durum (30 Mayıs ~11:15)

### Çalışan Eğitim — v9_newmap

```
Step        : ~64k / 2.500.000
FPS         : 83  (n_envs=2, 2x Gazebo headless)
ep_len_mean : ~945 (başta 78'di → drone duvardan kaçmayı öğreniyor)
ep_rew_mean : ~-324 (raw; VecNormalize var, erken faz negatif değeri normal)
Config      : configs/ppo.yaml
Checkpoint  : runs/ppo_v9_newmap/checkpoints/ppo_drone_60000_steps.zip
```

### Process Kontrol

```bash
pgrep -fa "train_ppo"          # eğitim process'i
tail -20 /tmp/train_ppo.log    # canlı log
```

### Yeni Harita (SAC branch'ten alındı)

- Tek katlı 16×16 m, **6 asimetrik oda** (eski 3-katlı yerine)
- Kapılar asimetrik: sol x=-2 (y∈[-4,-2]), sağ x=4 (y∈[3,5]), yatay y=0 (3 kapı)
- 3 engel SDF'de var ama animasyon devre dışı (SubprocVecEnv deadlock nedeniyle)
- Drone: 360° 2D planar lidar, lidar_up, lidar_down, IMU

### Reward Fonksiyonu (v9)

```
+1.0   yeni voxel (grid hücresi)
+15.0  yeni oda (6 oda toplam)
-0.1   idle <30 step
-0.5   idle ≥30 step
-0.5   yakın engel (<0.5m)
-10.0  çarpışma (terminate)
-0.001 her step zaman cezası
+0..+0.4  frontier bonus
+0..+0.1  en uzak sektöre dön bonusu
```

### Observation Space — 41-d

```
[0:32]  32-bin 2D lidar
[32:34] cos(yaw), sin(yaw)
[34:37] vx/v_max, vz/vz_max, wz/w_max
[37:39] keşif oranı, oda skaleri
[39:41] min_lidar/max_range, idle counter
```

### configs/ppo.yaml (güncel değerler)

```yaml
learning_rate: 3e-4  (linear decay → 3e-5)
n_steps: 512,  batch_size: 256,  n_epochs: 5
gamma: 0.99,   gae_lambda: 0.9,  clip_range: 0.1
ent_coef: 0.0015,  vf_coef: 0.5
n_envs: 2,  total_timesteps: 2_500_000
VecNormalize: enabled, clip_reward: 10.0
resume_from: null
```

---

## Geçmiş Eğitim Versiyonları (referans)

| Versiyon | Değişiklik | Peak ep_rew_mean |
|----------|-----------|-----------------|
| v1 | ilk run, 3-katlı harita | ~-19 (başaramadı) |
| v2 | reward 3x, ent_coef 0.02 | +40 @140k |
| v3 | multi-floor spawn | +95 @440k |
| v4 | ent_coef 0.001, idle decay | +85 @80k |
| v5 | clip 0.1, n_epochs 5, batch 256 | +85 @80k |
| v6 | **VecNormalize** → büyük iyileşme | +110 @150k |
| v7 | linear lr decay | +105 @210k |
| v8 | frontier shaping, n_envs=4 | **+113 @1628k (all-time)** |
| v9 | **YENİ HARİTA** (6-oda, tek kat) | ~devam ediyor |

---

## Dün Gece Yaşanan Sorun (bilgi için)

Eğitim 10k step'te 7.5 saat deadlock'a girdi.
**Kök neden:** `_update_obstacles()` → `subprocess.Popen()` SubprocVecEnv worker'ları
içinde IPC pipe'ı bozuyor → `unix_stream_read_generic` deadlock.
**Düzeltme:** Animasyon devre dışı, n_envs=4→2, log-mtime stuck dedector eklendi.

---

## Dosya Yapısı

```
rl_drone_pathfinding/
├── configs/ppo.yaml                       ← hyperparameter + train config
├── scripts/
│   ├── train.sh                           ← sim + eğitim başlat (tek komut)
│   ├── eval.sh                            ← eval
│   └── auto_overnight.py                  ← ESKİ monitor (yetersiz, yenisiyle değiştir)
├── ros2_ws/src/rl_drone_pathfinding/
│   ├── worlds/multi_room.sdf              ← 6-oda tek katlı harita
│   ├── models/rl_drone/model.sdf          ← 2D lidar drone
│   └── rl_drone_pathfinding/
│       ├── envs/drone_exploration_env.py  ← Gymnasium env (41-d obs)
│       └── agents/train_ppo.py            ← SB3 PPO trainer
├── runs/ppo_v9_newmap/
│   ├── checkpoints/                       ← her 10k step'te .zip (gitignore'da)
│   └── tb/PPO_N/                          ← TensorBoard events (gitignore'da)
├── docs/PROGRESS.md                       ← adım adım günlük
├── fixes.txt                              ← hatalar + çözümler
└── KICKOFF.md                             ← bu dosya
```

### Başlatma Komutları (referans)

```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding

# Eğitim başlat
./scripts/train.sh configs/ppo.yaml

# Processler
pgrep -fa "train_ppo"
tail -f /tmp/train_ppo.log

# Tüm sim + train öldür
pkill -INT -f "train_ppo --config"; sleep 3
pkill -TERM -f "gz sim"; pkill -TERM -f "parameter_bridge"
pkill -TERM -f "ros2 launch rl_drone"; sleep 3

# TensorBoard
source .venv/bin/activate && tensorboard --logdir runs/ppo_v9_newmap/tb
```

---

## Görev: Yeni Monitor + Logging Altyapısı

### Temel Kural

**Monitor eğitimi DURDURMAZ.** Sadece gözlemler, loglar, raporlar.
Müdahale yalnızca ikisi durumunda:
1. Process ölmüşse (crash) → son checkpoint'ten resume et ve yeniden başlat
2. v9 tamamlandıktan sonra v10'a geç

---

### 1. `scripts/monitor_agent.py` — Yaz ve Başlat

Her **30 dakikada** bir çalışır, 31 Mayıs 04:00'a kadar.

#### 1a. Canlılık Kontrolü (crash recovery)

```python
# Process var mı + log son 15dk'da güncellendi mi?
# Eğer process ölmüşse (crash):
#   - runs/ppo_v9_newmap/checkpoints/ içinden en son .zip bul
#   - ppo.yaml resume_from'u güncelle
#   - ./scripts/train.sh'i yeniden başlat
#   - fixes.txt'e yaz, git commit+push
```

**NOT:** Eğitimi kendin asla `pkill` ile durdurma. Sadece crash sonrası recovery.

#### 1b. Metrik Okuma (TensorBoard)

```python
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
import glob

# Sadece en güncel TB dizinini oku (en büyük N'li PPO_N klasörü)
tb_dirs = sorted(glob.glob("runs/ppo_v9_newmap/tb/PPO_*"))
latest_tb = tb_dirs[-1]  # PPO_2, PPO_3 vs.

ea = EventAccumulator(latest_tb)
ea.Reload()
# Okunacak tag'lar:
#   "rollout/ep_rew_mean"
#   "rollout/ep_len_mean"
#   "time/fps"
#   "train/entropy_loss"
#   "train/std"
```

**UYARI:** Birden fazla PPO_N dizini olabilir (restart sonrası). Her zaman
sadece sonuncuyu oku. Eski dizinleri karıştırma — geçen sefer bu karıştırma
yanlış müdahaleye neden oldu.

#### 1c. Loglama — CSV + JSON

Her kontrol döngüsünde şunları **append** et:

**`logs/training_metrics.csv`** — tablo çıkarmak için:
```csv
timestamp,step,ep_rew_mean,ep_len_mean,fps,entropy_loss,std,ckpt_file
2026-05-30 11:30:00,64512,-324.1,945.3,83,−4.24,0.996,ppo_drone_60000_steps.zip
```

**`logs/room_voxel_log.jsonl`** — oda/voxel verisi için (eval çalıştırarak değil,
TB'den `ep_rew_mean` trend'inden tahmin et; gerçek oda/voxel verisi ancak
`eval.sh` ile ölçülebilir, onu 500k'da bir çalıştır):
```jsonl
{"ts":"2026-05-30 11:30","step":64512,"ep_rew_mean":-324,"ep_len":945,"fps":83}
```

**`logs/interventions.jsonl`** — her müdahale kaydı:
```jsonl
{"ts":"...","type":"crash_recovery","step":X,"resume_from":"ppo_drone_60000_steps.zip","reason":"..."}
{"ts":"...","type":"v10_transition","step":2500000,"changes":{"ent_coef":0.005,...}}
```

`logs/` dizini `.gitignore`'da DEĞİL — commit et, raporlama için önemli.

#### 1d. v10 Geçişi (training bittikten sonra)

v9 2.5M step tamamladığında veya training durduğunda:

```python
# v10 için önerilen değişiklikler (v9 sonuçlarına göre ayarla):
# - ent_coef: düşükse artır (daha fazla keşif)
# - learning_rate: 3e-4 → 1e-4 (fine-tune)
# - total_timesteps: 2_500_000 (aynı)
# - log_dir: ./runs/ppo_v10
# - resume_from: null (fresh start) ya da v9 en iyi checkpoint
# - Kararını fixes.txt'e yaz, neden v10'a geçiyorsun açıkla
```

---

### 2. `logs/report_template.md` — Rapor Altyapısı

Aşağıdaki yapıda bir dosya oluştur (veri placeholder'larla):

```markdown
# PPO Eğitim Raporu — v9/v10

## Özet Tablo
| Versiyon | Steps | Peak Reward | Ort. Oda | Ort. Voxel | FPS |
|----------|-------|-------------|----------|------------|-----|
| v9 | ... | ... | ... | ... | 83 |

## Öğrenme Eğrisi
- İlk pozitif reward: step X
- En iyi ep_rew_mean: +Y @ step Z
- Toplam müdahale sayısı: N

## Oda/Voxel Keşif İstatistikleri
...

## Hyperparameter Tablosu
...
```

---

### 3. `scripts/generate_report.py` — CSV'den Tablo Üretici

```python
# Çalıştır: python3 scripts/generate_report.py
# Çıktı: docs/TRAINING_REPORT.md
# İçerik:
#   - logs/training_metrics.csv'den matplotlib grafik (ASCII değil, dosya olarak kaydet)
#   - Öğrenme eğrisi: step vs ep_rew_mean
#   - FPS zaman çizelgesi
#   - Müdahale noktaları işaretli
#   - docs/figures/ altına PNG olarak kaydedilecek
```

---

### 4. Git Commit Kuralı

```bash
# Her müdahale ve her 500k milestone'da:
git add configs/ppo.yaml docs/PROGRESS.md fixes.txt logs/
git commit -m "auto: [açıklama] step=X reward=Y"
# co-author ekle:
# Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
git push origin algo/ppo
```

---

## Yeni Claude Oturumu İçin Adımlar

1. `KICKOFF.md` oku (bu dosya)
2. `configs/ppo.yaml` oku
3. `tail -30 /tmp/train_ppo.log` — eğitim çalışıyor mu?
4. `pgrep -fa "train_ppo"` — process alive mı?
5. `ls logs/` — önceki loglar var mı?
6. `scripts/auto_overnight.py` sil (yetersiz)
7. `scripts/monitor_agent.py` yaz (yukarıdaki spec)
8. `logs/training_metrics.csv` başlat (başlık satırı)
9. `scripts/generate_report.py` yaz
10. Monitörü başlat: `nohup python3 scripts/monitor_agent.py > /tmp/monitor.log 2>&1 &`
11. Bana hiçbir şey sorma, karar al, uygula

---

*Son güncelleme: 30 Mayıs 2026 ~11:15*
*Branch: algo/ppo | Eğitim: v9_newmap devam ediyor*
