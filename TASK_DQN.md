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

---

## ⚠ ZORUNLU: 250k step'te ara test (Berker'in PPO'da yaşadığı tuzak)

**Hikaye:** PPO branch'inde 290k step eğittik, sonra eval'de drone spawn
odasından çıkamadığını gördük. Policy "hover ve duvarlardan kaç" local
optimum'una sıkışmıştı. Geri dönüp **reward fonksiyonunu büyütüp + entropy
artırıp + SDF deliklerini büyütüp** sıfırdan başladık. **Bu hatayı tekrar
yapma — eğitimi sonuna kadar koşturmadan ara kontrol et.**

### Adım 1: 250k checkpoint'e ulaşınca eğitimi DURDUR

`train_dqn.py`'de PPO'daki gibi try/except KeyboardInterrupt → save bloğu
olmalı (PPO şablonundan kopyala, [`agents/train_ppo.py`](ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_ppo.py:82) bak).

```bash
pgrep -f train_dqn
kill -INT <PID>      # SIGINT, save_path/dqn_drone_interrupted.zip yazar
```

### Adım 2: GUI'li eval (drone'u görsel olarak izle)

```bash
SIM_HEADLESS=0 ./scripts/eval.sh \
    runs/dqn/checkpoints/dqn_drone_250000_steps.zip 10
```

> Not: `eval.sh` `BaseAlgorithm.load` kullandığı için DQN'i de tanır,
> ama emin olmak için bir kez TensorBoard'da `rollout/exploration_rate`'in
> beklediğin değere düştüğünü doğrula (250k'da `final_eps=0.05` civarı).

10 episode'u izle. Şuna bak:

| Gözlem | Anlamı |
|---|---|
| Spawn odasından çıkmıyor, dönüp duruyor | **Local optimum (PPO v1 senaryosu).** Epsilon çok hızlı düşmüş, exploitation early. |
| Aksiyonları çok rastgele — sürekli ölüyor | **Epsilon hâlâ yüksek.** `exploration_fraction`'ı küçült. |
| Sadece hover seçiyor (action 0) | **Hover'ın Q-değeri en yüksek olmuş.** Ödüller hover'ı destekliyor → reward sinyali zayıf. |
| 1 oda dolaşıyor ama kapıdan geçmiyor | **7 aksiyon bu task için çok kaba** olabilir. ACTION_TABLE'ı genişlet (27 aksiyon). |
| Kata atlıyor (z>2.5) | **Bravo.** Devam ettir. |

### Adım 3: Beğenmediysen — DQN'e özgü ayar setleri

**A) Spawn'da takıldıysa — exploration erken bitti:**
```yaml
# configs/dqn.yaml
dqn:
  ...
  exploration_fraction: 0.3 → 0.5     # epsilon decay'ini yavaşlat
  exploration_final_eps: 0.05 → 0.10  # min epsilon yüksek tut
  learning_starts: 10000 → 20000      # daha çok rastgele eylemle başla
```

**B) Sürekli ölüyorsa — exploration fazla:**
```yaml
dqn:
  exploration_fraction: 0.3 → 0.15
  learning_rate: 1.0e-4 → 5.0e-5      # daha temkinli güncelleme
```

**C) Sadece hover seçiyorsa — Q-fn miyop:**
```yaml
dqn:
  gamma: 0.99 → 0.995                # daha uzak hedefler kıymetlensin
  # veya target_update_interval'ı uzat (target net daha sık güncellense bias artar)
```

**D) 7 aksiyon yetmiyorsa — action space büyüt:**

`drone_exploration_env.py`'deki wrapper'ında ACTION_TABLE'ı 7 → 27 yap:
```python
# Wrapper kodunda:
ACTION_TABLE = []
for vx in [-V_MAX*0.5, 0.0, V_MAX]:
    for vz in [-VZ_MAX, 0.0, VZ_MAX]:
        for wz in [-W_MAX, 0.0, W_MAX]:
            ACTION_TABLE.append((vx, vz, wz))
# 27 aksiyon. Q-network çıkış katmanı 7 → 27 olur, otomatik.
```

> ⚠ **Env reward'larına dokunma** — PPO ile karşılaştırma bozulur.
> Sadece kendi wrapper'ın (action discretization) ve `dqn.yaml`'ı oynat.

### Adım 4: Resume veya baştan başlat

**Resume (küçük tweak):**
```yaml
train:
  resume_from: ./runs/dqn/checkpoints/dqn_drone_250000_steps.zip
  total_timesteps: 500000
```
> DQN'de `resume_from` `DQN.load(path, env=...)` ile yapılır. Replay buffer
> default'ta zip içinde DEĞİL (boyut sebebiyle); `model.load_replay_buffer()`
> ayrıca lazım. Detay için: SB3 docs `DQN.save_replay_buffer`.

**Baştan (büyük tweak — exploration veya action_table değiştirdiysen):**
```yaml
train:
  resume_from: null
  log_dir: ./runs/dqn_v2
  ckpt_dir: ./runs/dqn_v2/checkpoints
  tb_log: ./runs/dqn_v2/tb
```

### Adım 5: Kayıt tut

`fixes.txt` + `docs/PROGRESS.md` — Berker PPO'da bu disiplini kurdu, sen de
kendi DQN bölümünü aç. Hocaya rapor verirken "v1 denedik, böyle takıldı,
v2'de şu tweak ile çözdük" narratifi puan açısından kıymetli.

---

## Hızlı referans: PPO branch'inde ne yapıldı

Detaylı: `git checkout algo/ppo && cat docs/PROGRESS.md` (en alttaki
2026-05-06 bölümü).

Özetle:
- Run 1: sıfırdan 0→140k baseline.
- Run 2: 140k→290k resume → eval'de drone spawn odasında takıldı.
- Run 3 (v2): reward 3x büyütüldü, ent_coef 0.005→0.02, SDF delikleri
  2x2→3x3, baştan başlatıldı.
- Algoritma seçimine özgü tuzaklar farklı (PPO entropy oynar, DQN epsilon
  oynar) ama **"ara checkpoint'te eval et"** prensibi ortak.
