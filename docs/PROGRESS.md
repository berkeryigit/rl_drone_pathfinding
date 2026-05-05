# PROGRESS — rl_drone_pathfinding

Adım adım yapılan işler. Her bloğun başında tarih + kim + neyi neden yaptı.

---

## 2026-05-05 — Berker — Pipeline iskeleti (Day 0)

Yarın eğitim koşulabilsin diye sadece **pipeline + Docker + GitHub repo** kuruldu;
training koşulmadı.

### Dosyalar

* `ros2_ws/src/rl_drone_pathfinding/package.xml`, `setup.py`, `setup.cfg`,
  `resource/rl_drone_pathfinding`
  → ament_python ROS 2 paket iskeleti. Entry-points: `train_ppo`, `eval_ppo`,
  `env_smoke_test`.

* `ros2_ws/src/rl_drone_pathfinding/worlds/multi_room.sdf`
  → 16x16 m kapalı bina, 4 oda (NE/NW/SW/SE), iç duvarlarda 2 m'lik kapı
  boşlukları, 3 statik engel (silindir + kutu).
  Pluginler: physics, user-commands, scene-broadcaster, sensors (ogre2),
  imu, contact.

* `ros2_ws/src/rl_drone_pathfinding/models/rl_drone/{model.config, model.sdf}`
  → Hover-drone (gravity link-level off). 0.30×0.30×0.10 chassis + nose marker.
  Sensorler: 360 ışınlı planar gpu_lidar (10 m, gauss σ=0.02), IMU.
  Pluginler: `gz-sim-velocity-control-system` (cmd_vel, body frame),
  `gz-sim-odometry-publisher-system`, `gz-sim-pose-publisher-system`.

* `ros2_ws/src/rl_drone_pathfinding/config/ros_gz_bridge.yaml`
  → `clock`, `scan`, `imu`, `odom` (GZ→ROS) ve `cmd_vel` (ROS→GZ) köprüleri.

* `ros2_ws/src/rl_drone_pathfinding/launch/sim_launch.py`
  → `gz sim`'i dünya ile başlat → `ros_gz_sim::create` ile drone'u (4, -4, 0.6)
  pozisyonunda spawn et → `parameter_bridge` ile YAML'dan köprüleri kur.
  `GZ_SIM_RESOURCE_PATH` ayarlanıyor ki SDF include'ları çözülsün.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env.py`
  → `DroneExplorationEnv(gym.Env)`. Arka planda rclpy thread'i (`_RosBridge`
  node'u) lidar/odom dinler, ana thread cmd_vel publish eder.
  Reset: `gz service /world/multi_room/set_pose` ile drone'u 4 spawn'dan
  birine teleport eder.
  Obs 40-d, action 2-d (v, ω). Reward: yeni hücre +1, yeni oda +15,
  çarpışma -10 (terminate), yakın engel -0.5, idle -0.1, step -0.001.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_ppo.py`
  → SB3 PPO, YAML'dan hyperparameter okur, `CheckpointCallback`, TensorBoard.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/eval_ppo.py`
  → trained `.zip`'i yükle, N episode roll-out, return + cells + rooms istatistiği.

* `configs/ppo.yaml`
  → lr 3e-4, n_steps 2048, batch 64, ent_coef 0.005, MlpPolicy [128,128].
  total_timesteps 500k, save_freq 25k.

* `requirements.txt`
  → gymnasium 0.29.1, stable-baselines3[extra] 2.3.2, torch 2.4.0, pyyaml,
  tensorboard, tqdm.

* `docker/Dockerfile`
  → `osrf/ros:jazzy-desktop` üstüne `ros-jazzy-ros-gz*`, `gz-harmonic`,
  Cyclone DDS, python ML stack (CUDA 12.1 wheels). Non-root `dev` user host
  UID/GID ile eşleşiyor.

* `docker/docker-compose.yml`
  → `network_mode: host`, `ipc: host`, NVIDIA runtime, X11 socket mount,
  repo `/workspace`'e bind mount. ROS_DOMAIN_ID=42.

* `docker/{build.sh, run.sh}`
  → host UID/GID ile build + `xhost +local:docker` + container'a shell.

* `.gitignore`, `README.md`, `fixes.txt`

### Aynı gün — pip + venv + smoke test (eğitim öncesi son hazırlık)

Yarın eğitim koşulurken sürpriz çıkmasın diye Python tarafı da bugün doğrulandı.

* `python3 -m venv .venv --system-site-packages` (rclpy gibi ROS Python paketlerini
  görmesi için `--system-site-packages` şart) + `pip install -r requirements.txt`.
* `requirements.txt`: `stable-baselines3[extra]==2.3.2` Python 3.12 ile uyumsuz
  (ale-py 0.8 build edemiyor) → düz `stable-baselines3==2.3.2` + ayrı
  `tensorboard` / `rich` ile değiştirildi.
* Torch 2.4.0 + NVIDIA CUDA 12.1 wheel'leriyle kuruldu (~2GB).
* `python3 -m rl_drone_pathfinding.envs.smoke_test` — sim canlı iken: env
  reset OK, 50 step OK, lidar normalize doğru (0.10..0.40), reward fonksiyonu
  çalışıyor, exception yok. **Pipeline yarın eğitime hazır.**
* `scripts/setup.sh` (colcon + venv + pip), `scripts/train.sh` (sim auto-launch
  + train_ppo), `scripts/eval.sh` eklendi → README güncellendi.

### Aynı gün — host'ta sim doğrulama koşusu

Docker'a girmeye gerek kalmadan host'ta (Ubuntu 24.04 + ROS Jazzy + gz Harmonic
+ ros-jazzy-ros-gz*) doğrulama yapıldı, **eğitim koşulmadı**.

İlk denemede **2 bug** çıktı, ikisi de düzeltildi (detay `fixes.txt`'de):

1. `setup.py` data_files: `glob('models/*')` → setuptools dir kopyalayamayıp
   colcon build fail ediyor. Her model dir için ayrı entry yazıldı:
   `(share/.../models/rl_drone, glob('models/rl_drone/*'))`.
2. `launch/sim_launch.py`: `IncludeLaunchDescription` için `gz_args`'a `-r`
   eklenmemişti → gz paused başlıyor, sensör/clock publish etmiyordu.
   `'gz_args': f'-r -v 3 {world_file}'` olarak düzeltildi.

Doğrulama sonucu (host, `ros2 launch rl_drone_pathfinding sim_launch.py` +
elle `ros2 topic pub /cmd_vel`):

* /clock + /scan + /odom + /imu hepsi yayında, sim time akıyor.
* `cmd_vel.linear.x = 0.3` 3s → drone y: -4.0 → -3.04 (~0.95m, beklenen 0.9m).
  Yaw=π/2 spawn olduğundan body-x → world +y, doğru.
* `cmd_vel.angular.z = 0.5` 2s → yaw 1.57 → 2.65 rad (Δ≈1.08, beklenen 1.0).
* Z sabit 0.6 → link-level gravity-off doğru çalışıyor.

### Yarın (2026-05-06) eğitim — tek satır

```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding
./scripts/train.sh                              # configs/ppo.yaml, 500k step
# ayrı terminal: source .venv/bin/activate && tensorboard --logdir runs/ppo/tb
```

500k step için RTX-class GPU'da ~süreyi ölç ve buraya not düş. Eğer 8 saat+ olursa
configs/ppo_quick.yaml diye `total_timesteps: 100000` olan bir varyant aç,
önce onunla baseline al.

### İleride (eğitimden sonra)

1. (opsiyonel, sadece ekip teslimatı için) `./docker/build.sh` → image build.
2. Reward eğrisi + ep_len + custom metrik (cells, rooms) TensorBoard'da grafik.
3. Dinamik kapı + hareketli engel + lidar gürültüsü senaryoları (PDF §2 + §3).
4. PPO vs (TD3 / DQN / A3C) karşılaştırma — ekip arkadaşlarının kendi paketleri
   (ya ayrı klasör ya ayrı branch) hazır olunca aynı env üstünde koşturup
   reward/cells/rooms karşılaştır.
