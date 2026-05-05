# TASK — DQN (Deep Q-Network)

**Branch:** `algo/dqn`
**Algoritma:** DQN — value-based, **discrete action space**
**Sahip:** Berk Karaoğlu (220202079) — GitHub: `brkrgl`

## Önemli — DQN sürekli aksiyonu kabul etmez
Mevcut `DroneExplorationEnv` continuous (Box) action veriyor. DQN için **discrete wrapper env** yazman gerek. Aşağıda 7-aksiyonluk basit şema önerilmiş; istersen 27-aksiyonluk full grid de yapabilirsin.

## Ne Yapacaksın

### 1. Discrete env wrapper

`ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env_discrete.py` oluştur:

```python
import gymnasium as gym
import numpy as np
from .drone_exploration_env import DroneExplorationEnv, V_MAX, VZ_MAX, W_MAX

# 7 aksiyon: hover / forward / back / yaw_left / yaw_right / up / down
ACTION_TABLE = np.array([
    [   0.0,    0.0,    0.0],   # 0: hover
    [ V_MAX,    0.0,    0.0],   # 1: forward
    [-V_MAX,    0.0,    0.0],   # 2: back
    [   0.0,    0.0,  W_MAX],   # 3: yaw left
    [   0.0,    0.0, -W_MAX],   # 4: yaw right
    [   0.0,  VZ_MAX,    0.0],  # 5: up
    [   0.0, -VZ_MAX,    0.0],  # 6: down
], dtype=np.float32)


class DroneExplorationEnvDiscrete(DroneExplorationEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_space = gym.spaces.Discrete(len(ACTION_TABLE))

    def step(self, action: int):
        return super().step(ACTION_TABLE[int(action)])
```

`envs/__init__.py`'a `from .drone_exploration_env_discrete import DroneExplorationEnvDiscrete` ekle.

### 2. Trainer

`ros2_ws/src/.../agents/train_dqn.py` — `train_ppo.py`'yi şablon al:

```python
from stable_baselines3 import DQN
from rl_drone_pathfinding.envs import DroneExplorationEnvDiscrete

def _factory():
    env = DroneExplorationEnvDiscrete(
        world_name=env_cfg["world_name"],
        drone_name=env_cfg["drone_name"],
        max_episode_steps=env_cfg["max_episode_steps"],
        seed=env_cfg.get("seed"),
    )
    return Monitor(env)

model = DQN(
    policy="MlpPolicy",
    env=vec_env,
    learning_rate=float(dqn_cfg["learning_rate"]),
    buffer_size=int(dqn_cfg["buffer_size"]),
    learning_starts=int(dqn_cfg["learning_starts"]),
    batch_size=int(dqn_cfg["batch_size"]),
    tau=float(dqn_cfg["tau"]),
    gamma=float(dqn_cfg["gamma"]),
    train_freq=int(dqn_cfg["train_freq"]),
    gradient_steps=int(dqn_cfg["gradient_steps"]),
    target_update_interval=int(dqn_cfg["target_update_interval"]),
    exploration_fraction=float(dqn_cfg["exploration_fraction"]),
    exploration_initial_eps=float(dqn_cfg["exploration_initial_eps"]),
    exploration_final_eps=float(dqn_cfg["exploration_final_eps"]),
    policy_kwargs={"net_arch": dqn_cfg["policy_kwargs"]["net_arch"]},
    tensorboard_log=str(tb_log),
    verbose=1,
    seed=env_cfg.get("seed"),
)
```

`CheckpointCallback` `name_prefix="dqn_drone"` yap. Try/except `KeyboardInterrupt` save bloğunu PPO'daki gibi koru.

### 3. Config

`configs/dqn.yaml`:

```yaml
env:
  world_name: multi_room
  drone_name: rl_drone
  max_episode_steps: 1000
  seed: 42

dqn:
  policy: MlpPolicy
  learning_rate: 1.0e-4
  buffer_size: 100000
  learning_starts: 10000
  batch_size: 64
  tau: 1.0                    # hard update
  gamma: 0.99
  train_freq: 4
  gradient_steps: 1
  target_update_interval: 1000
  exploration_fraction: 0.3
  exploration_initial_eps: 1.0
  exploration_final_eps: 0.05
  policy_kwargs:
    net_arch: [128, 128]

train:
  total_timesteps: 300000
  save_freq: 10000
  log_dir: ./runs/dqn
  ckpt_dir: ./runs/dqn/checkpoints
  tb_log: ./runs/dqn/tb
  resume_from: null
```

### 4. Script

`scripts/train.sh`'i kopyalayıp `scripts/train_dqn.sh` yap; `train_ppo` modül adını `train_dqn` ile değiştir.

## Çalıştırma

```bash
cd ros2_ws && colcon build --symlink-install && cd ..
source ros2_ws/install/setup.bash
source .venv/bin/activate

./scripts/train_dqn.sh configs/dqn.yaml          # eğitim
SIM_HEADLESS=0 ./scripts/eval.sh \
    runs/dqn/checkpoints/dqn_drone_300000_steps.zip 5    # eval
tensorboard --logdir runs/dqn/tb
```

`eval.sh` PPO için yazılmış — DQN için içine `from stable_baselines3 import DQN; model = DQN.load(...)` switch'i eklemen gerekebilir.

## Notlar / Tuzaklar
- 7 discrete aksiyon kaba bir abstraction — ajan sürekli kontrol kadar çevik olamaz, dolayısıyla `ep_rew_mean` PPO/TD3'ten daha düşük kalabilir. Bu **beklenen** ve raporda tartışılması gereken bir nokta.
- Eğer 7 aksiyon az gelirse: `ACTION_TABLE`'ı 27'ye genişlet (3×3×3 ızgara: vx∈{-V,0,V} × vz∈{-V,0,V} × wz∈{-W,0,W}). Discrete action sayısı arttıkça Q-network çıkış katmanı büyür ama eğitim hâlâ feasible.
- `learning_starts=10000` öncesi eylemler tamamen rastgele — ilk 10k step çok kötü davranır, normal.
- Replay buffer 100k × 45-d obs × 4 byte ≈ ~18 MB. Sıkıntı yok.

## Definition of Done
- 200-300k step eğitilmiş `dqn_drone_*.zip` model
- TensorBoard ekranları: `rollout/ep_rew_mean`, `train/loss`, `rollout/exploration_rate`
- Eval video / GIF (3-5 episode), keşfedilen voxel sayısı, ulaşılan kat sayısı
- Hyperparameter tablosu + tasarım notları (neden 7 aksiyon, exploration schedule)
- PPO/TD3/A2C(A3C) ile karşılaştırma satırı (rapor için ortak tablo)
