# PPO v9 Eğitim Kickoff — 30 Mayıs 2026

Bu dosya yeni bir Claude oturumu için hazırlanmıştır.
**Okumadan hiçbir şey yapma. Her şey burada.**

---

## Proje Özeti

`~/Desktop/RLProje/rl_drone_pathfinding` — KOU RL dönem projesi.
- GitHub: `berkeryigit/rl_drone_pathfinding`, branch: **`algo/ppo`**
- Stack: Gazebo Harmonic + ROS 2 Jazzy + Stable-Baselines3 PPO + Python 3.12
- Berker → PPO continuous. Diğer arkadaşlar TD3/DQN/A3C kendi branch'lerinde.

---

## Şu Anki Durum (30 Mayıs ~11:00)

### Çalışan Eğitim

```
Versiyon    : v9_newmap (fresh start)
Step        : ~64k / 2.500.000
FPS         : 83 (n_envs=2, 2x Gazebo headless)
ep_len_mean : ~945 (başlangıçta 78'di, artıyor = drone duvardan kaçmayı öğreniyor)
ep_rew_mean : ~-324 (raw; VecNormalize var, bu beklenen negatif erken-faz değeri)
Config      : configs/ppo.yaml
Log dir     : runs/ppo_v9_newmap/
Checkpoint  : runs/ppo_v9_newmap/checkpoints/ppo_drone_60000_steps.zip (son)
```

### Çalışan Processler

```bash
pgrep -fa "train_ppo|gz sim"   # bunlar görünmeli
/tmp/train_ppo.log             # canlı eğitim logu
/tmp/auto_overnight.log        # monitoring logu (monitor da çalışıyor)
```

### Yeni Harita (SAC branch'ten alındı)

- **Tek katlı 16×16 m, 6 asimetrik oda** (eski 3-katlı yerine)
- Kapılar: sol duvar x=-2 (y∈[-4,-2]), sağ duvar x=4 (y∈[3,5]), yatay y=0 (3 kapı)
- 3 hareketli engel SDF'de tanımlı ama **animasyon şu an devre dışı** (aşağıda neden açıklanıyor)
- Drone: 360° 2D planar lidar (3D yok, değişiklik gerekmedi)

### Reward Fonksiyonu (v9)

```
+1.0   yeni voxel
+15.0  yeni oda (6 oda toplam)
-0.1   aynı hücrede (<30 step)
-0.5   aynı hücrede (≥30 step — oda bitmis, cik)
-0.5   yakın engel (<0.5m clearance)
-10.0  çarpışma (episode biter)
-0.001 her step zaman cezası
+0..+0.4  frontier bonus (forward lidar açık + ileri gidiyorsa)
+0..+0.1  en uzak sektöre dönüş bonusu
```

### Observation (41-d)

```
[0:32]  32-bin yatay lidar
[32:34] cos(yaw), sin(yaw)
[34:37] vx/v_max, vz/vz_max, wz/w_max
[37:39] keşif oranı, oda skaleri
[39:41] min_lidar/max_range, idle counter
```

### PPO Config (configs/ppo.yaml güncel)

```yaml
learning_rate: 3e-4 (linear decay → 3e-5)
n_steps: 512, batch_size: 256, n_epochs: 5
gamma: 0.99, gae_lambda: 0.9, clip_range: 0.1
ent_coef: 0.0015, vf_coef: 0.5
n_envs: 2, total_timesteps: 2_500_000
VecNormalize: enabled, clip_reward: 10.0
```

---

## Gece Boyunca Yaşanan Sorun ve Düzeltmeler

### Sorun: SubprocVecEnv Deadlock

Dün gece eğitim 10k step'te tamamen dondu (7.5 saat sıfır ilerleme).

**Kök neden:** Yeni env'deki `_update_obstacles()` her 5 adımda
`subprocess.Popen()` ile gz service çağırıyordu. SubprocVecEnv worker
process'leri içinde Popen çağrısı, worker↔main IPC pipe'ını bozuyor →
tüm processler `unix_stream_read_generic`'te deadlock'a girdi.

**Teşhis komutu:** `cat /proc/<train_ppo_pid>/wchan` → `unix_stream_read_generic`

### Uygulanan Düzeltmeler

1. `envs/drone_exploration_env.py` — `_update_obstacles()` step döngüsünden çıkarıldı
2. `configs/ppo.yaml` — `n_envs: 4 → 2`
3. `scripts/auto_overnight.py` — `is_training_stuck()` eklendi: log dosyası 15 dk güncellenmezse kill + restart

### Monitörün Zayıflığı (DÜZELTİLMESİ GEREKEN)

Mevcut `auto_overnight.py` sadece `pgrep -f train_ppo` ile "canlı mı?" diye
bakıyor. Process alive görünürse hiçbir şey yapmıyor — dün gece tam da bu
yüzden deadlock'ı kaçırdı. **Yeni agent bunu düzeltmeli.**

---

## Görev: Yeni Otonom Agent Kur

### Ne Yapacak?

31 Mayıs gece 04:00'a kadar her **30 dakikada** bir:

1. **Canlılık kontrolü** — sadece process varlığına bakma; log dosyasının son
   değiştirilme zamanını kontrol et. 15 dk güncellenmemişse TAKILI KALMIŞ.

2. **Gerçek ilerleme ölç** — TB event dosyasından son metrikleri oku:
   - `ep_rew_mean` (son 10 kayıt ortalaması)
   - `ep_len_mean`
   - Ayrıca `info` dict'teki `visited_rooms`, `explored_voxels` değerlerine bak

3. **Plateau tespiti** — Son 200k step'te `ep_rew_mean` < 5 puan iyileşmediyse:
   - Önce `ent_coef`'i artır (0.001 → 0.003 gibi, keşfi arttır)
   - Sonraki 200k'da hâlâ plateau → `learning_rate`'i yarıya indir
   - En son çare → yeni checkpoint'ten resume + fresh VecNormalize

4. **Peak-regress tespiti** — Peak değerden %40 düşüş olursa peak
   yakınındaki checkpoint'ten resume et

5. **Her mudahalede:**
   - `configs/ppo.yaml`'ı güncelle
   - Mevcut eğitimi KILL et (train_ppo + gz sim + parameter_bridge)
   - Yeniden başlat (`./scripts/train.sh configs/ppo.yaml`)
   - `fixes.txt`'e ne yaptığını ve neden yaptığını yaz
   - `docs/PROGRESS.md`'ye müdahale bloğu ekle
   - `git add -u && git commit -m "auto: ..."` + `git push origin algo/ppo`

6. **Her 30 dk'da sadece durum logu** (mudahale yoksa) — şunu içermeli:
   ```
   [HH:MM] step=X, ep_rew=Y, ep_len=Z, rooms=W, voxels=V, fps=F
   ```

7. **Gece 04:00'da dur** — son commit + push yap, özet yaz.

### Kritik Kurallar

- **`main` branch'e asla push yapma** — sadece `algo/ppo`
- **Commit'te her zaman** `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` ekle
- `runs/` altındaki dosyalar `.gitignore`'da — checkpoint'leri commit etme
- Training başlatmak için her zaman `./scripts/train.sh configs/ppo.yaml` kullan
- `resume_from` belirtmek için `configs/ppo.yaml`'daki `train.resume_from` alanını güncelle

### Ölçülecek Metrikler (TB + info)

```python
# TB event okuma:
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
# tag: "rollout/ep_rew_mean"
# Sadece en son TB alt dizinini oku (PPO_N numarası en büyük olan)

# info dict metrikleri (eval için):
# info["visited_rooms"]   → kaç oda ziyaret edildi (max 6)
# info["explored_voxels"] → kaç grid hücresi keşfedildi (max 1024)
```

### Hangi Parametreler Ne Zaman Değişir?

| Durum | Aksiyon |
|-------|---------|
| Plateau >200k step, ent_coef<0.005 | ent_coef *= 2 |
| Plateau >200k step, ent_coef≥0.005 | learning_rate *= 0.5 |
| Peak-regress >40% | en yakın peak checkpoint'ten resume |
| Entropy explosion (std>10) | ent_coef = 0.001 |
| Takılı kalma (log >15dk) | kill + resume interrupted.zip |
| Crash (process yok) | resume interrupted.zip veya son checkpoint |

---

## Dosya Yapısı (önemli olanlar)

```
rl_drone_pathfinding/
├── configs/ppo.yaml                    ← hyperparameter + train config
├── scripts/
│   ├── train.sh                        ← tek komutla sim+eğitim başlat
│   ├── eval.sh                         ← eval scripti
│   └── auto_overnight.py               ← mevcut (zayıf) monitor
├── ros2_ws/src/rl_drone_pathfinding/
│   ├── worlds/multi_room.sdf           ← yeni tek-katlı 6-oda harita
│   ├── models/rl_drone/model.sdf       ← 2D planar lidar drone
│   └── rl_drone_pathfinding/
│       ├── envs/drone_exploration_env.py  ← Gymnasium env (41-d obs)
│       └── agents/train_ppo.py           ← SB3 PPO trainer
├── runs/ppo_v9_newmap/
│   ├── checkpoints/                    ← her 10k step'te .zip
│   ├── tb/PPO_N/                       ← TensorBoard events
│   └── (gitignore'da, push edilmez)
├── docs/PROGRESS.md                    ← adım adım yapılan işler günlüğü
├── fixes.txt                           ← hatalar ve çözümleri
└── KICKOFF.md                          ← bu dosya
```

---

## Başlatma Komutları (referans)

```bash
# Eğitim durumunu kontrol et
grep "total_timesteps\|ep_rew_mean\|ep_len" /tmp/train_ppo.log | tail -10
pgrep -fa "train_ppo|gz sim"

# Eğitim başlat (sıfırdan veya resume_from dolu ise devam)
cd ~/Desktop/RLProje/rl_drone_pathfinding
./scripts/train.sh configs/ppo.yaml

# Tüm sim + train processlerini öldür
pkill -INT -f "train_ppo --config"; sleep 3
pkill -TERM -f "gz sim"; pkill -TERM -f "parameter_bridge"
pkill -TERM -f "ros2 launch rl_drone"; sleep 3

# TensorBoard
source .venv/bin/activate
tensorboard --logdir runs/ppo_v9_newmap/tb
```

---

## Yeni Agent İçin Adımlar

1. Bu KICKOFF.md dosyasını oku
2. `configs/ppo.yaml` ve `docs/PROGRESS.md` içeriğini oku
3. `/tmp/train_ppo.log` son 30 satırını oku — eğitim çalışıyor mu kontrol et
4. `scripts/auto_overnight.py`'yi SİL ya da tamamen yeniden yaz
5. Yeni, sağlam bir `scripts/monitor_agent.py` yaz (yukarıdaki spec'e göre)
6. Monitörü başlat: `nohup python3 scripts/monitor_agent.py > /tmp/monitor.log 2>&1 &`
7. Her 30 dk'da bir kontrol et, gerekirse müdahale et, commit at
8. Gece 04:00'da son özet commit yap

---

*Son güncelleme: 30 Mayıs 2026, ~11:15*
*Bir önceki session'da yapılanlar: v9 harita geçişi, deadlock teşhisi ve düzeltmesi, eğitim yeniden başlatma*
