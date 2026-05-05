# TASK — TD3 (Twin Delayed DDPG)

**Branch:** `algo/td3`
**Algoritma:** TD3 — off-policy actor-critic, **continuous action space**
**Sahip:** Mehmet Akif Albayrak (220202082) — GitHub: `AKeeF-Albayrak`

## Neden TD3 burada uyar
- `DroneExplorationEnv` action space'i `Box([-1,-1,-1], [1,1,1])` (vx, vz, wz). PPO ile aynı env'i, **sıfır değişiklik yapmadan** kullanabilirsin.
- TD3 = DDPG + (twin Q-network, target policy smoothing, delayed policy updates). Stable-Baselines3'te hazır: `from stable_baselines3 import TD3`.

## Ne Yapacaksın
1. `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_td3.py` oluştur. `train_ppo.py`'yi şablon al; `PPO`'yu `TD3` ile değiştir, replay buffer + action noise ekle.
2. `configs/td3.yaml` oluştur (örnek aşağıda).
3. `scripts/train.sh`'i kopyalayıp `scripts/train_td3.sh` yap; içindeki `train_ppo` modül adını `train_td3` ile değiştir.
4. `runs/td3/checkpoints/` ve `runs/td3/tb/` dizinleri otomatik oluşur (zaten gitignore'da `runs/`).

## Şablon (train_td3.py'de değişen yerler)

```python
import numpy as np
from stable_baselines3 import TD3
from stable_baselines3.common.noise import NormalActionNoise

n_actions = vec_env.action_space.shape[-1]   # 3
action_noise = NormalActionNoise(
    mean=np.zeros(n_actions),
    sigma=0.1 * np.ones(n_actions),
)

model = TD3(
    policy=ppo_cfg["policy"],          # "MlpPolicy"
    env=vec_env,
    learning_rate=float(td3_cfg["learning_rate"]),
    buffer_size=int(td3_cfg["buffer_size"]),
    learning_starts=int(td3_cfg["learning_starts"]),
    batch_size=int(td3_cfg["batch_size"]),
    tau=float(td3_cfg["tau"]),
    gamma=float(td3_cfg["gamma"]),
    train_freq=tuple(td3_cfg["train_freq"]),  # (1, "step")
    gradient_steps=int(td3_cfg["gradient_steps"]),
    action_noise=action_noise,
    policy_delay=int(td3_cfg["policy_delay"]),
    target_policy_noise=float(td3_cfg["target_policy_noise"]),
    target_noise_clip=float(td3_cfg["target_noise_clip"]),
    policy_kwargs={"net_arch": td3_cfg["policy_kwargs"]["net_arch"]},
    tensorboard_log=str(tb_log),
    verbose=1,
    seed=env_cfg.get("seed"),
)
```

`CheckpointCallback`, `model.learn(...)`, try/except `KeyboardInterrupt` save bloğunu PPO'daki gibi koru. `name_prefix="td3_drone"` yap.

## Önerilen Hyperparameters (`configs/td3.yaml`)

```yaml
env:
  world_name: multi_room
  drone_name: rl_drone
  max_episode_steps: 1000
  seed: 42

td3:
  policy: MlpPolicy
  learning_rate: 1.0e-3
  buffer_size: 200000
  learning_starts: 10000
  batch_size: 256
  tau: 0.005
  gamma: 0.99
  train_freq: [1, step]
  gradient_steps: 1
  policy_delay: 2
  target_policy_noise: 0.2
  target_noise_clip: 0.5
  policy_kwargs:
    net_arch:
      pi: [256, 256]
      qf: [256, 256]

train:
  total_timesteps: 300000
  save_freq: 10000
  log_dir: ./runs/td3
  ckpt_dir: ./runs/td3/checkpoints
  tb_log: ./runs/td3/tb
  resume_from: null
```

## Çalıştırma

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source .venv/bin/activate

./scripts/train_td3.sh configs/td3.yaml          # eğitim
SIM_HEADLESS=0 ./scripts/eval.sh \
    runs/td3/checkpoints/td3_drone_300000_steps.zip 5    # eval
tensorboard --logdir runs/td3/tb                  # metrics
```

`scripts/eval.sh` içinde model loader generic — direkt çalışır. Bakmak istersen `scripts/eval.sh` PPO için yazılmış ama `BaseAlgorithm.load` üzerinden TD3'ü de tanır; problem olursa `from stable_baselines3 import TD3` import edip `TD3.load(...)` deyip switch ekle.

## Notlar / Tuzaklar
- TD3 off-policy; replay buffer dolarken (`learning_starts=10k`) GPU/CPU yükü düşük olur, sonra train freq'e göre artar. Checkpoint'ler boş policy'lerle başlayabilir, **9-10k'dan önce eval anlamlı değil.**
- Action noise sigma'yı çok yüksek tutarsan drone duvara dalar (collision -10 spam'i). 0.1 makul başlangıç.
- 200k buffer × 45-d obs × 4 byte ≈ ~36 MB RAM. Sıkıntı yok.
- Sim crash olursa `pkill -f "gz sim"` ve baştan başlat; replay buffer eğitim sırasında diske kaydedilmez (default), o yüzden interrupt olursa partial kayıp normal.

## Definition of Done
- 200-300k step eğitilmiş `td3_drone_*.zip` model
- TensorBoard ekranları: `rollout/ep_rew_mean`, `train/critic_loss`, `train/actor_loss`
- Eval video / GIF (3-5 episode), keşfedilen voxel sayısı, ulaşılan kat sayısı
- Hyperparameter tablosu + tasarım notları (neden TD3, action noise stratejisi)
- PPO/DQN/A2C(A3C) ile karşılaştırma satırı (rapor için ortak tablo)
