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

### Henüz **yapılmamış** olanlar (yarın)

1. `./docker/build.sh` → ilk image build (5-15 dk).
2. Konteyner içinde `colcon build --symlink-install` → paket binary'leri.
3. `ros2 launch rl_drone_pathfinding sim_launch.py` → Gazebo + bridge sanity.
4. `ros2 topic echo /scan` / `/odom` → veri akıyor mu?
5. `python3 -m rl_drone_pathfinding.envs.smoke_test` → env reset/step gerçekten
   ROS2 ile konuşuyor mu?
6. Asıl eğitim: `python3 -m rl_drone_pathfinding.agents.train_ppo`.
   500k step için RTX-class GPU'da ~kaç saat olacağını ölç → not düş.
7. TensorBoard'da reward eğrisi + episode_length + custom metrik (cells, rooms).
