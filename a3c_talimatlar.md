# A3C (Discrete) Eğitim Talimatları — Drone Oda Keşfi

> ## ⚠️ ÖNCE BUNU OKU — BRANCH
> Bu görev **`algo/a3c`** branch'inde yapılır. Başka branch'e (özellikle `algo/ppo`
> veya `main`) **dokunma**, oraya **push etme**.
> ```bash
> cd ~/Desktop/RLProje/rl_drone_pathfinding   # (kendi klonunda yol farklı olabilir)
> git fetch origin
> git checkout algo/a3c
> git pull origin algo/a3c
> ```
> Bütün commit/push'lar **sadece `origin algo/a3c`**'ye. `main`'e push KAPALI.

Bu dosya, Berker'in (PPO) ekibinden A3C ile çalışacak arkadaş içindir. Berker'in
PPO tarafında **acı çekerek öğrendiği dersler** burada hazır; aynı tuzaklara düşme.

---

## 0. Bu nedir, hedef ne?
Kapalı, **tek katlı 6 odalı sabit** bir binada lidar+odometri ile keşif yapan bir drone.
Amaç: **çarpışmadan maksimum zemin alanını (voxel) gezmek.** Ekip aynı ortamda farklı
RL algoritmaları koşup karşılaştırıyor:
- Berker → **PPO (continuous)**  ← referans, `algo/ppo`
- Sen → **A3C (discrete)**  ← bu branch
- Diğerleri → TD3 (continuous), DQN (discrete)

**Ortam birebir aynı** (harita, drone, lidar, ödül, gözlem, başlangıç). Tek fark **aksiyon uzayı**:
A3C **discrete** kullanır. Bu sayede "continuous vs discrete" karşılaştırması adil olur.

---

## 1. Ortam (tek seferlik kurulum)
Gereken: **Ubuntu + ROS 2 Jazzy + Gazebo Harmonic + NVIDIA GPU (opsiyonel ama tavsiye)**.

```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding   # algo/a3c checkout'lu

# 1) ROS 2 paketini derle
source /opt/ros/jazzy/setup.bash
cd ros2_ws && colcon build --symlink-install && cd ..

# 2) Python sanal ortam (ROS python'unu görmek için --system-site-packages ŞART)
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt    # stable-baselines3, torch(CUDA), gymnasium, tensorboard...

# 3) (varsa) sürdür: her terminalde önce şunları source et
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate
```

**Smoke testi** (sim açıkken env çalışıyor mu — discrete):
```bash
# Terminal A: sim
export GZ_IP=127.0.0.1 ROS_DOMAIN_ID=0 GZ_PARTITION=sim0
ros2 launch rl_drone_pathfinding sim_launch.py
# Terminal B: env'i discrete modda dürt
python3 -c "
from rl_drone_pathfinding.envs import DroneExplorationEnv
import numpy as np
e=DroneExplorationEnv(max_episode_steps=200, discrete=True)
print('action_space:', e.action_space)   # Discrete(4) beklenir
o,_=e.reset()
for i in range(40):
    o,r,term,trunc,info=e.step(np.random.randint(4))
    if i%10==0: print(i, 'r=%.2f vox=%d rooms=%d'%(r,info['explored_voxels'],info['visited_rooms']))
    if term or trunc: break
e.close()
"
```

---

## 2. ⚠️ BİZİM ZOR ÖĞRENDİĞİMİZ DERSLER (bunlara uy, zaman kazan)

1. **TEK sim, TEK env (`n_envs=1`).** Çoklu Gazebo / paralel env süreci **sürekli bozdu**
   (gz transport çakışması, IPC pipe bozulması, step ~2048'de donma). `configs/a2c.yaml`'de
   `n_envs: 1` kalsın. **(A3C'ye özel uyarı için §4'e bak.)**

2. **`GZ_IP=127.0.0.1` ŞART.** Çoklu ağ arayüzü olan makinede (wifi + docker0 vs) gz transport
   service yanıtlarını erişilemez adrese gönderip **"Host unreachable"** seli üretiyor;
   `reset()`'teki `gz service set_pose` çağrısı asılıyor ve **eğitim step ~2048'de donuyordu.**
   `scripts/train_a2c.sh` bunu zaten export ediyor. Elle koşarsan sen de export et.

3. **gz service çağrılarına Python timeout var** (env içinde, reset + engel hareketi).
   Bu yüzden transport hıçkırığı eğitimi artık dondurmaz — silme/değiştirme.

4. **"core dumped / python3.12 çöktü" bildirimi ZARARSIZ.** Eğitim process'i ÇIKARKEN
   (tamamlanma veya kill anında) rclpy+Gazebo C++ teardown'u segfault verir. Model bundan
   ÖNCE kaydedilir → kayıp yok. Panik yapma; sadece latest checkpoint'ten resume et.

5. **Checkpoint + resume.** Her `save_freq` (20k) step'te checkpoint yazılır. Crash/freeze
   olursa `configs/a2c.yaml`'de `resume_from: <latest ckpt>` yapıp yeniden başlat.

6. **Harita / başlangıç SABİT.** `multi_room.sdf`, drone modeli, **R0 (-5,-5) sabit spawn**
   değişmez. Hareketli 3 engel kalır. (Berker'in kuralları — değiştirme.)

---

## 3. Discrete aksiyon (PPO'dan TEK fark)
Env `discrete=True` ile **`Discrete(4)`** verir:
| Aksiyon | Anlam | (v, ω) |
|---|---|---|
| 0 | İleri | (V_MAX, 0) |
| 1 | Sola dön | (0.5·V_MAX, +W_MAX) |
| 2 | Sağa dön | (0.5·V_MAX, −W_MAX) |
| 3 | Dur/hover | (0, 0) |

Gözlem **40-d** (32 lidar bin + yaw + hız + keşif oranı + min_lidar/idle) — PPO ile aynı.
Ödül **v2.1** (PPO ile birebir, adil karşılaştırma için):
`+1 yeni voxel`, `+10 yeni oda`, `-0.6·(1−ön/1.5)` yön-duyarlı engel cezası,
`-0.3·(1−d/0.5)` sıyırma, `+0.10·ön-açık·ileri` bonus, `-10` çarpışma (terminal), `-0.01` zaman.
Episodik getiri ≈ keşfedilen voxel sayısı.

---

## 4. A3C mi A2C mi? (DÜRÜST NOT — rapora yaz)
- **SB3'te "A3C" sınıfı YOK.** A2C, A3C'nin **senkron** halidir (aynı advantage actor-critic,
  worker'lar asenkron değil). Akademik olarak A2C = "senkron A3C" kabul edilir.
- Bizim **tek-sim dersimiz** ile gerçek async A3C (çoklu paralel worker) **çelişir** —
  çoklu Gazebo bizde kararsız. O yüzden **önerimiz: A2C'yi `n_envs=1` ile koş**
  (= tek-worker advantage actor-critic). Bu, sağlam ve sorunsuz çalışır.
- **Raporda şöyle yaz:** "A3C'nin senkron eşdeğeri A2C (SB3) kullanıldı; çoklu-worker
  asenkron kurulum, simülatör kararlılığı nedeniyle tek-sim ile değiştirildi."
- Gerçekten async A3C istiyorsan (hoca şart koşarsa): her worker'a **ayrı Gazebo + ayrı
  `GZ_PARTITION`/`ROS_DOMAIN_ID`** gerekir; bunu denemeden önce tek-sim A2C baseline'ını
  bitir, sonra 2 worker ile **dikkatli** dene (CPU/GPU sınırı + transport çakışması riski).

`train_a2c.py` zaten hazır: `A2C` (SB3), discrete env, paylaşılan loglama/engel-updater.

---

## 5. Eğitimi çalıştır
```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding   # algo/a3c
# Tek komut (sim'i kendi açar, GZ_IP export eder, A2C başlatır):
./scripts/train_a2c.sh configs/a2c.yaml

# Ayrı terminalde canlı grafikler:
source .venv/bin/activate
tensorboard --logdir runs/a2c_v1/tb
```
Loglar: `/tmp/train_ppo.log` yerine bu scriptte stdout terminalde; istersen
`./scripts/train_a2c.sh >> /tmp/train_a2c.log 2>&1 &` ile arka plana al.
Checkpoint: `runs/a2c_v1/checkpoints/`. İlerleme CSV: `runs/a2c_v1/progress.csv`.

**Hedef:** `total_timesteps` (config'te 700k). Berker'in tecrübesi: **doğru ödülle ~500-700k
yeterli** (2M şart değil). ~40 fps'de 700k ≈ 5 saat.

---

## 6. İzleme + sorun giderme (Berker'in araçları, hepsi hazır)
```bash
source .venv/bin/activate
python3 scripts/tb_metrics.py --config configs/a2c.yaml   # JSON: step/reward/voxels/rooms/ep_len/fps
python3 scripts/report.py                                  # docs/figures + docs/REPORT.md
# Eğitim sonu / kıyas için 100-ep değerlendirme + kapsama haritası:
#   (sim açıkken; pattern için /tmp/rl_eval.sh benzeri bir akış kur)
python3 scripts/eval_coverage.py --model runs/a2c_v1/checkpoints/a2c_drone_final.zip \
        --episodes 100 --version a2c_v1
```
| Belirti | Tanı | Çözüm |
|---|---|---|
| step ilerlemiyor, log bayat | freeze (transport) | `GZ_IP=127.0.0.1` mi? kill + latest ckpt'ten resume |
| "core dumped" bildirimi | iyi-huylu teardown | yok say; kayıp yok |
| reward hep negatif, ep kısa | çok çarpışma | normal erken evre; ent_coef↑ veya yön-ceza ayarı |
| reward platosu | öğrenme durdu | lr×0.5; veya ödül shaping (yeni versiyon) |
| `n_envs>1` denedin, bozuldu | çoklu Gazebo | `n_envs=1`'e dön |

**Çarpışma proxy:** `ep_len_mean / max_episode_steps`. Düşükse (örn <0.4) çok çarpışıyor demektir
(Berker'in PPO'sunda ana darboğaz buydu; yön-duyarlı lidar cezasıyla iyileştirdik).

---

## 7. (Opsiyonel) Otonom operatör
Berker'in kurduğu otonom Claude operatörü `.claude/agents/rl-train-operator.md`'de.
Aynı mantığı A2C için kullanabilirsin: periyodik sağlık kontrolü, freeze/crash kurtarma,
plato'da reward shaping, versiyon atlama, log + commit. İstersen bir Claude terminaline
"bu playbook'u oku ve a2c.yaml'ı izle" dedirt (config yolunu `configs/a2c.yaml` ver).

---

## 8. Rapor için (hoca sunumu)
Her şey loglanıyor — sunumda kullan:
- `runs/a2c_v1/progress.csv` → step/reward/voxels/rooms eğrileri
- `docs/figures/report_*.png` → versiyon eğrileri | `docs/REPORT.md` → özet tablo
- `scripts/eval_coverage.py` → 100-ep kapsama ısı haritası + yörünge + **çarpışma %**
- PPO ile karşılaştırma: Berker'in `algo/ppo`'daki `runs/ppo_v2_*/progress.csv` + `docs/EVAL_v2_0.md`
  ile aynı metrikleri yan yana koy (continuous PPO vs discrete A2C).

---

## 9. İLK KOŞU CHECKLIST (sırayla)
1. [ ] `git checkout algo/a3c` (DOĞRU branch).
2. [ ] `colcon build --symlink-install` + venv + `pip install -r requirements.txt`.
3. [ ] Smoke testi (§1) → `Discrete(4)`, voxel artıyor, çarpışma yok.
4. [ ] `./scripts/train_a2c.sh configs/a2c.yaml` → sim açılıyor, step ilerliyor, **2048'i geçiyor**.
5. [ ] tensorboard'da reward yükseliyor mu, ep_len artıyor mu izle.
6. [ ] ~700k'da `eval_coverage.py` ile 100-ep değerlendir + figürler.
7. [ ] `git add -A && git commit && git push origin algo/a3c` (SADECE bu branch).

---

## 10. Git kuralları
- Sadece **`algo/a3c`**'ye commit/push. `main`'e ASLA.
- `runs/`, `build/`, `install/`, `log/`, `.venv/` zaten `.gitignore`'da (checkpoint'leri push etme).
- Anlamlı commit mesajı + ilerlemeyi `docs/PROGRESS.md`'ye, hata+çözümleri `fixes.txt`'ye yaz.

Kolay gelsin — takılırsan Berker'in `algo/ppo`'daki `docs/PROGRESS.md` ve `fixes.txt`'sinde
tüm hata/çözüm geçmişi var, oraya bak. 🚁
