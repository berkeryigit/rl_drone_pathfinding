# TASK — SAC (Soft Actor-Critic)

**Branch:** `algo/td3`
**Algoritma:** SAC — off-policy actor-critic, **continuous action space**, entropi maksimizasyonu
**Sahip:** Mehmet Akif Albayrak (220202082) — GitHub: `AKeeF-Albayrak`

## Neden SAC burada uyar

- `DroneExplorationEnv` action space'i `Box([-1,-1,-1], [1,1,1])` (vx, vz, wz). PPO ile aynı env'i **sıfır değişiklik yapmadan** kullanabilirsin.
- SAC = off-policy actor-critic + **entropi regularizasyonu**. TD3'ten farkı: action noise parametresi gerekmez, entropi terimi exploration'ı otomatik dengeler (`ent_coef: auto`).
- Stable-Baselines3'te hazır: `from stable_baselines3 import SAC`.

## SAC vs TD3 temel fark

| | TD3 | SAC |
|---|---|---|
| Exploration | Manuel action noise (sigma ayarla) | `ent_coef: auto` — otomatik |
| Policy | Deterministik | Stokastik (dağılım öğrenir) |
| Kararlılık | Daha az kararlı | Genellikle daha kararlı |
| Tuning | Noise sigma kritik | Çoğunlukla `auto` yeterli |

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `ros2_ws/.../agents/train_sac.py` | SAC eğitim scripti |
| `configs/sac.yaml` | Hyperparameter config |
| `scripts/train_sac.sh` | Eğitimi başlatan script |

## Çalıştırma

```bash
# Container içinde:
./scripts/setup.sh          # ilk seferde

# Satır sonu düzeltme (Windows'ta oluşturulduysa):
sed -i 's/\r//' scripts/train_sac.sh

./scripts/train_sac.sh      # SAC eğitimi başlar
```

TensorBoard:
```bash
tensorboard --logdir /workspace/runs/sac/tb --host 0.0.0.0
# Windows tarayıcıda: http://localhost:6006
```

## Önerilen Hyperparameters (`configs/sac.yaml`)

```yaml
sac:
  policy: MlpPolicy
  learning_rate: 3.0e-4
  buffer_size: 200000
  learning_starts: 10000   # ilk 10k step rastgele, sonra train başlar
  batch_size: 256
  tau: 0.005
  gamma: 0.99
  train_freq: [1, step]
  gradient_steps: 1
  ent_coef: auto           # entropi katsayısı otomatik ayarlanır
  target_entropy: auto     # -dim(action) = -3
  use_sde: false
  policy_kwargs:
    net_arch: [256, 256]
```

## ⚠ ZORUNLU: 250k step'te ara test

**PPO branch'inde yaşanan tuzak:** 290k step eğitim sonrası drone spawn odasından çıkamıyordu, local optimum'a sıkışmıştı. Bu hatayı tekrar yapma.

### Adım 1: 250k'da Ctrl+C

```bash
# Eğitim çalışırken:
Ctrl+C    # model otomatik kaydedilir → sac_drone_interrupted.zip
```

### Adım 2: Ne görüyorsun?

| Gözlem | Anlamı | Çözüm |
|---|---|---|
| Spawn odasından çıkmıyor | Local optimum | `learning_starts` artır (10k→20k), `learning_rate` düşür |
| Sürekli duvara dalıyor | Exploration fazla | `ent_coef` sabitini düşür (örn. `0.05`) |
| 1-2 oda dolaşıyor, kapı bulamıyor | Discovery sinyali zayıf | `gamma: 0.99→0.95` |
| Kata atlıyor (z>2.5) | **Bravo** — devam et | `total_timesteps: 500000` yap |

### Adım 3: Resume veya sıfırdan başlat

**Devam (küçük tweak):**
```yaml
train:
  resume_from: ./runs/sac/checkpoints/sac_drone_250000_steps.zip
  total_timesteps: 500000
```

**Sıfırdan (büyük değişiklik):**
```yaml
train:
  resume_from: null
  log_dir: ./runs/sac_v2
  ckpt_dir: ./runs/sac_v2/checkpoints
  tb_log: ./runs/sac_v2/tb
```

## Notlar / Tuzaklar

- SAC off-policy; `learning_starts=10k` dolana kadar GPU/CPU yükü düşük olur, sonra artar.
- `ent_coef: auto` çoğu ortamda iyi çalışır. Drone çok agresif davranıyorsa sabit bir değer ver (`ent_coef: 0.05`).
- 200k buffer × 45-d obs × 4 byte ≈ ~36 MB RAM. Sıkıntı yok.
- Sim crash olursa `pkill -f "gz sim"` ve baştan başlat.

## Definition of Done

- 200-300k step eğitilmiş `sac_drone_*.zip` model
- TensorBoard: `rollout/ep_rew_mean`, `train/critic_loss`, `train/actor_loss`, `train/ent_coef`
- Eval: 3-5 episode, keşfedilen voxel sayısı, ulaşılan kat sayısı
- Hyperparameter tablosu + neden SAC seçildi notları
- PPO/DQN/A3C ile karşılaştırma satırı (rapor için ortak tablo)

---

## Hızlı referans: PPO branch'inde ne yapıldı

- Run 1: 0→140k, baseline.
- Run 2: 140k→290k resume. Eval'de drone spawn odasında takıldı.
- Run 3 (v2): reward 3x büyütüldü, ent_coef artırıldı, SDF delikleri büyütüldü, sıfırdan başlandı.
- **"Ara checkpoint'te eval et"** prensibi SAC için de geçerli.
