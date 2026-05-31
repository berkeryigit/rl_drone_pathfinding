# rl_drone_pathfinding

Lidar + odometry tabanlı drone'un çok odalı kapalı bir ortamda **pekiştirmeli öğrenme**
ile keşif (exploration) ve çarpışmasız navigasyon yapması üzerine ekip projesi.

> Bu repo **Berker Yiğit (220202046)** tarafından maintain ediliyor ve
> **PPO (Proximal Policy Optimization, continuous action space)** algoritmasını
> içeriyor. Diğer ekip arkadaşları aynı simülasyon ortamı üzerine kendi
> algoritmalarını (TD3, DQN, A3C) ayrı paketlerde / branch'lerde geliştirecek.

## Stack

| Katman                | Seçim                                       |
|-----------------------|---------------------------------------------|
| Simülasyon            | **Gazebo Harmonic** (gz-sim)                |
| Robot middleware      | **ROS 2 Jazzy** (Ubuntu 24.04)              |
| RL kütüphanesi        | **Stable-Baselines3** (PPO)                 |
| Env interface         | **Gymnasium** (Box obs / Box action)        |
| Container             | **Docker + NVIDIA runtime + X11**           |

## Klasör yapısı

```
rl_drone_pathfinding/
├── docker/                    # Dockerfile + docker-compose + build/run helpers
├── configs/
│   └── ppo.yaml               # PPO hyperparameters + train cfg
├── docs/
│   └── PROGRESS.md            # adım adım yapılan işlerin günlüğü
├── fixes.txt                  # karşılaşılan hatalar + çözümleri
├── requirements.txt           # python (SB3, torch, gymnasium, ...)
└── ros2_ws/
    └── src/rl_drone_pathfinding/
        ├── package.xml
        ├── setup.py
        ├── launch/sim_launch.py
        ├── worlds/multi_room.sdf
        ├── models/rl_drone/{model.config, model.sdf}
        ├── config/ros_gz_bridge.yaml
        └── rl_drone_pathfinding/
            ├── envs/drone_exploration_env.py    # Gymnasium env (ROS2 node içinde)
            ├── envs/smoke_test.py
            └── agents/{train_ppo.py, eval_ppo.py}
```

## MDP özeti (öneri PDF'sinden)

* **State**: 32-bin lidar (min/sektör, 0..1) + (cosψ, sinψ) + (v, ω) + (keşif oranı, oda sayısı) + (min lidar, idle counter)
* **Action**: continuous `[v ∈ ~[-0.18, 0.6] m/s, ω ∈ [-1.5, 1.5] rad/s]`
* **Reward**:
  * yeni grid hücresi: **+1.0**
  * yeni odaya geçiş: **+15**
  * çarpışma (terminate): **-10**
  * engele yakın (<0.5 m): **-0.5**
  * aynı hücrede kalma: **-0.1**
  * her step zaman cezası: **-0.001**

## Hızlı başlangıç (host, Ubuntu 24.04 + ROS Jazzy + Gazebo Harmonic)

Sıfırdan kurulum (yeni klon, ya da venv silinmişse) — **tek seferlik**:
```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding
./scripts/setup.sh        # colcon build + .venv + pip install (3-5 dk)
```

Eğitim (her seferinde tek satır, sim'i de background'a kendisi alır):
```bash
./scripts/train.sh                       # configs/ppo.yaml ile 500k step
# veya farklı config:
./scripts/train.sh configs/ppo_quick.yaml
```

Değerlendirme (eğitilmiş modeli sim'e bağlayıp roll-out):
```bash
./scripts/eval.sh runs/ppo/checkpoints/ppo_drone_final.zip 5
```

TensorBoard:
```bash
source .venv/bin/activate
tensorboard --logdir runs/ppo/tb        # http://localhost:6006
```

Sadece simülasyonu görmek (Gazebo GUI):
```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 launch rl_drone_pathfinding sim_launch.py
```

## Docker yolu (alternatif, taşınabilir)

```bash
./docker/build.sh                # ilk seferde, 5-15 dk
./docker/run.sh                  # konteynere shell
# konteyner içinde aynı: ./scripts/setup.sh && ./scripts/train.sh
```

## En İyi Eval Turu — ep82 Replay

100 episodluk eval'de en iyi tur **ep82** oldu: `return=+505, rooms=3, floors=3` (tüm 3 kat keşfedildi).

```bash
# ep82'yi Gazebo GUI ile tekrar izlemek için (spawn idx=1 sabit):
SIM_HEADLESS=0 ./scripts/eval.sh \
    runs/ppo_v8_frontier/checkpoints/ppo_drone_final.zip 1 \
    --spawn-idx 1
```

**Spawn bilgisi:**
- `spawn_idx = 1` → `(-4.0, -4.0, 0.6, yaw=0.0)` — Kat 0, SW köşe, +X yönü
- `env seed = 42`, episode 82 için RNG bu indexi üretiyor
- VecNormalize: `runs/ppo_v8_frontier/checkpoints/vec_normalize.pkl` otomatik yüklenir

**100 tur istatistikleri (ppo_drone_final.zip):**
- Mean return: **+88.52** (std 189)
- Mean rooms: **1.6 / 12**
- Mean floors: **1.4 / 3**
- 3 kata ulaşan turlar: ep52 (+153, rooms=3), ep82 (+505, rooms=3, floors=3), ep86 (+269, rooms=3)

---

## Eğitim Sonuçları (v8 Frontier Shaping, 2026-05-29)

- **Toplam step:** 2,000,000
- **All-time peak:** **+113** (ep_rew_mean, 1628k adımda)
- **v6 rekoru (+110) kırıldı!**
- **Hız:** n_envs=4 SubprocVecEnv → 37 FPS → 122 FPS
- **Checkpoint:** `runs/ppo_v8_frontier/checkpoints/ppo_drone_final.zip`
- **Otonom müdahale:** 6× peak-regress intervention (gece boyunca otomatik)

---

## Yol haritası

* [x] ROS 2 paket iskeleti + Gazebo Harmonic dünyası + drone modeli
* [x] ros_gz_bridge köprüleri (scan/imu/odom/cmd_vel/clock)
* [x] Gymnasium env wrapper + reward shaping
* [x] PPO train/eval pipeline + YAML config + TensorBoard
* [x] Docker (NVIDIA, X11, ROS Jazzy + Gazebo Harmonic)
* [ ] İlk eğitim koşusu (~500k step) ve baseline metrikleri
* [ ] Dinamik kapı + hareketli engel + lidar gürültüsü senaryoları
* [ ] PPO vs (TD3 / DQN / A3C) karşılaştırma raporu
