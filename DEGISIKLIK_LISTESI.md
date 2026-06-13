# DEGISIKLIK LISTESI

## Gönderim: dqn_final branch — 2025

### İlk teslim

Bu, projenin ilk resmi teslim sürümüdür.

---

## Yapılan Değişiklikler

### 1. Algoritma Değişikliği

- **Önceki**: PPO (Proximal Policy Optimization) ile ROS2/Gazebo 3D simülasyon
- **Yeni**: DQN (Deep Q-Network) ile saf Python 2D simülasyon ortamı

**Gerekçe**: Stokastik, gecikmeli ödüllü, büyük durum uzaylı bir keşif problemi olduğundan RL gereklidir. DQN, off-policy özelliği sayesinde replay buffer ile veri verimliliği sağlar.

### 2. Ortam Değişikliği

- **Önceki**: `DroneExplorationEnv` — ROS2/Gazebo bağımlı, 3D ortam
- **Yeni**: `Fast2DDroneExplorationEnv` — Gazebo gerektirmez, saf Gymnasium, 100x daha hızlı

**Stokastisite kanıtı (kod satırı)**:
- Stokastik gözlem: `fast_2d_drone_env.py:233-236` — `odom_noise_std` ile ölçüm gürültüsü
- Stokastik geçiş: `fast_2d_drone_env.py:133-135` — `wind_std` ile rüzgar gürültüsü
- Stokastik başlangıç: `fast_2d_drone_env.py:208-220` — rastgele başlangıç konumu

### 3. Aksiyon Uzayı

- **Önceki**: Sürekli Box(3,) — PPO için uygun
- **Yeni**: Discrete(9) wrapper — DQN için uygun; 9 anlamlı hareket kombinasyonu

### 4. Yeni Dosyalar

- `deliverables/kod/train.py` — DQN eğitim scripti (EpisodeLogger callback ile)
- `deliverables/kod/evaluate.py` — Deterministik değerlendirme scripti
- `deliverables/kod/config.yaml` — Sabitlenmiş hiperparametreler
- `deliverables/kod/requirements.txt` — Sabitlenmiş bağımlılıklar (== ile)
- `deliverables/kod/seeds.txt` — 5 seed: 42, 7, 13, 123, 2025
- `deliverables/kod/run_all.sh` — Tüm seedleri çalıştıran script
- `deliverables/kod/env/fast_2d_drone_env.py` — Simülasyon ortamı

### 5. Kaldırılan Dosyalar

- `agents/train_ppo.py` — PPO'ya ait
- `agents/eval_ppo.py` — PPO'ya ait
- `envs/drone_exploration_env.py` — ROS2/Gazebo bağımlı 3D ortam
- `configs/ppo.yaml` — PPO config
- `scripts/train.sh`, `scripts/eval.sh` — PPO scriptleri

### 6. API Uyumluluğu

- `import gymnasium` kullanılmaktadır (yasak `import gym` yoktur) ✓
- `numpy.random.default_rng` kullanılmaktadır (yasak `np.random.seed()` yoktur) ✓
- Tüm bağımlılıklar `==` ile sabitlenmiştir ✓
