# TASK — A3C (Asynchronous Advantage Actor-Critic)

**Branch:** `algo/a3c`
**Algoritma:** A3C → **A2C (synchronous variant)** önerilir, aşağıyı oku
**Sahip:** Kürşat Emircan Balta (220202065) — GitHub: `heroicbattle`

## Önemli — A3C vs A2C

A3C orijinal makaledeki "asynchronous" varyant: **N tane bağımsız worker** kendi env kopyalarında paralel rollout toplar, ortak global ağa async gradient gönderir.

**Bizim sorun:** Her worker = ayrı bir Gazebo instance. Tek makinede 4-8 sim açmak (a) RAM yetmez, (b) GPU çakışır, (c) port collision riski. Pratik değil.

**Pratik çözüm:** **A2C** (Synchronous A3C) kullan. Aynı paper family, aynı update kuralı, sadece worker'ların gradient'ı senkron toplanıyor. Stable-Baselines3'te hazır: `from stable_baselines3 import A2C`. **Raporda bu seçimi açıkla:** "tek-makine kısıtı nedeniyle async A3C yerine senkron A2C kullanıldı; algoritma ailesi aynı".

Eğer ille de async A3C istiyorsan — ileride tartışırız (4 SubprocVecEnv worker + lightweight env mock olabilir, ama drone projesinde anlamı sınırlı).

## Ne Yapacaksın

### 1. Trainer

`ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_a2c.py` — `train_ppo.py`'yi şablon al:

```python
from stable_baselines3 import A2C

model = A2C(
    policy="MlpPolicy",
    env=vec_env,
    learning_rate=float(a2c_cfg["learning_rate"]),
    n_steps=int(a2c_cfg["n_steps"]),
    gamma=float(a2c_cfg["gamma"]),
    gae_lambda=float(a2c_cfg["gae_lambda"]),
    ent_coef=float(a2c_cfg["ent_coef"]),
    vf_coef=float(a2c_cfg["vf_coef"]),
    max_grad_norm=float(a2c_cfg["max_grad_norm"]),
    use_rms_prop=bool(a2c_cfg["use_rms_prop"]),
    policy_kwargs={"net_arch": a2c_cfg["policy_kwargs"]["net_arch"]},
    tensorboard_log=str(tb_log),
    verbose=1,
    seed=env_cfg.get("seed"),
)
```

`CheckpointCallback` `name_prefix="a2c_drone"`. PPO'daki `try/except KeyboardInterrupt` save bloğunu koru.

A2C continuous action space ile direkt çalışır (mevcut env'i kullanabilirsin, **discrete'e çevirmen gerekmez**).

### 2. Config

`configs/a2c.yaml`:

```yaml
env:
  world_name: multi_room
  drone_name: rl_drone
  max_episode_steps: 1000
  seed: 42

a2c:
  policy: MlpPolicy
  learning_rate: 7.0e-4
  n_steps: 5                # A2C tipik kısa rollout (PPO'daki 2048'in tersine)
  gamma: 0.99
  gae_lambda: 1.0           # 1.0 = full Monte Carlo advantage (orijinal A3C'deki gibi)
  ent_coef: 0.01
  vf_coef: 0.5
  max_grad_norm: 0.5
  use_rms_prop: true        # orijinal A3C RMSProp kullanır
  policy_kwargs:
    net_arch:
      pi: [128, 128]
      vf: [128, 128]

train:
  total_timesteps: 300000
  save_freq: 10000
  log_dir: ./runs/a2c
  ckpt_dir: ./runs/a2c/checkpoints
  tb_log: ./runs/a2c/tb
  resume_from: null
```

### 3. Script

`scripts/train.sh`'i kopyalayıp `scripts/train_a2c.sh` yap; `train_ppo` modül adını `train_a2c` ile değiştir.

## Çalıştırma

```bash
cd ros2_ws && colcon build --symlink-install && cd ..
source ros2_ws/install/setup.bash
source .venv/bin/activate

./scripts/train_a2c.sh configs/a2c.yaml          # eğitim
SIM_HEADLESS=0 ./scripts/eval.sh \
    runs/a2c/checkpoints/a2c_drone_300000_steps.zip 5    # eval
tensorboard --logdir runs/a2c/tb
```

`eval.sh` PPO için yazılmış — A2C için içine `from stable_baselines3 import A2C; model = A2C.load(...)` switch'i eklemen gerekebilir.

## Notlar / Tuzaklar
- **n_steps=5 doğru, yazım hatası değil** — A2C kısa, sık update yapar; PPO'nun `n_steps=2048`'i çok farklı bir paradigma.
- A2C **on-policy** (PPO gibi) — replay buffer yok, her update'ten sonra rollout buffer atılır. Sample efficiency PPO'dan biraz düşük olabilir, walltime benzer.
- `use_rms_prop=true` orijinal A3C'ye sadık kalır; Adam ile de denenebilir (`use_rms_prop=false`).
- `gae_lambda=1.0` full MC tahmin = yüksek varyans ama bias yok. 0.95'e çekersen PPO'ya daha yakın davranış olur.
- **Önemli — single-env A2C:** SB3'te A2C `n_envs=1` ile çalışır ama `n_envs=4` (SubprocVecEnv) ile gradient'ler ortalama alınır. Bizde tek sim olduğundan `DummyVecEnv` ile `n_envs=1` kalsın.

## A3C Açıklama (rapor için cümle örneği)

> A3C orijinalinde N adet bağımsız aktör paralel ortamlarda rollout toplar ve global ağa asenkron gradient gönderir. Tek-makine + Gazebo simülasyonunun yüksek bellek/GPU maliyeti nedeniyle bu projede A3C yerine onun senkron varyantı olan **A2C** uygulanmıştır. İki algoritma aynı policy gradient + value baseline güncellemesini kullanır; tek fark gradient toplama biçimidir.

## Definition of Done
- 200-300k step eğitilmiş `a2c_drone_*.zip` model
- TensorBoard ekranları: `rollout/ep_rew_mean`, `train/value_loss`, `train/policy_loss`, `train/entropy_loss`
- Eval video / GIF (3-5 episode), keşfedilen voxel sayısı, ulaşılan kat sayısı
- Hyperparameter tablosu + tasarım notları (neden A2C, A3C ile fark açıklaması)
- PPO/TD3/DQN ile karşılaştırma satırı (rapor için ortak tablo)
