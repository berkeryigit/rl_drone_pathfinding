# TASK — PPO (Continuous) — Berker Yiğit

**Branch:** `algo/ppo`
**Algoritma:** PPO (Proximal Policy Optimization), continuous action space
**Sahip:** Berker Yiğit

## Durum
- Pipeline + sim hazır, ilk eğitim 140k step'e kadar yapıldı (`runs/ppo/checkpoints/ppo_drone_140000_steps.zip`).
- Şu an 140k → 500k arası devam eden ikinci run var (`reset_num_timesteps=False` ile sayaç korunuyor).

## Dosyalar
- `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_ppo.py` — PPO trainer
- `configs/ppo.yaml` — PPO hyperparameters + train target
- `scripts/train.sh` — sim'i ayağa kaldır + train_ppo'yu çalıştır
- `scripts/eval.sh <checkpoint.zip> <n_episodes>` — eğitilen policy'yi GUI'de izle
- `runs/ppo/tb/PPO_*` — TensorBoard logları (gitignore'da)
- `runs/ppo/checkpoints/` — her 10k step'te `.zip` (gitignore'da)

## Hızlı Komutlar
```bash
# 0. Tek seferlik kurulum
cd ros2_ws && colcon build --symlink-install && cd ..
python3 -m venv .venv --system-site-packages
source .venv/bin/activate && pip install -r requirements.txt

# 1. Sıfırdan eğitim (resume_from: null)
./scripts/train.sh configs/ppo.yaml

# 2. Checkpoint'ten devam (configs/ppo.yaml içinde resume_from: <path>)
./scripts/train.sh configs/ppo.yaml

# 3. Eval (GUI'li)
SIM_HEADLESS=0 ./scripts/eval.sh runs/ppo/checkpoints/ppo_drone_500000_steps.zip 5

# 4. TensorBoard
tensorboard --logdir runs/ppo/tb
```

## Definition of Done (rapor için)
- 500k step'lik eğitilmiş model (`ppo_drone_500000_steps.zip` veya `ppo_drone_final.zip`)
- TensorBoard ekran görüntüleri: `ep_rew_mean`, `ep_len_mean`, `explained_variance`, `entropy_loss`
- Eval video / GIF (3-5 episode), keşfedilen voxel sayısı, ulaşılan kat sayısı
- Hyperparameter tablosu + tasarım notları (neden PPO continuous, neden bu ödüller)
- Diğer 3 algoritma ile karşılaştırma tablosu (final ep_rew_mean, %success rate, walltime)
