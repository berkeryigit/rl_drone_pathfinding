# kod/ — 2D RL Drone Pathfinding · PPO (egitim + eval + grafik)

Egitim **SADECE 2D Gymnasium ortaminda** (`env/fast_2d_drone_env.py`) yapilir.
Gazebo egitim icin **kullanilmaz**; yalnizca egitilmis politikanin
test/gosterimi icindir.

Bu paket, `algo/td3` (SAC) branch'inin 11 Haziran teslimi ile **birebir ayni
ortam, ayni seed'ler (7,13,42,123,2025), ayni eval/baseline protokolu ve ayni 5
grafik standardini** kullanir. Tek fark algoritmadir: **PPO** (on-policy,
actor-critic, clipped surrogate). `env/fast_2d_drone_env.py` SAC teslimindeki
dosya ile bayt-bayt aynidir (ayni MDP).

## Kurulum
```bash
pip install -r requirements.txt
```

## Tek komutla her sey
```bash
bash run_all.sh                    # config.yaml'daki total_timesteps (1M)
TIMESTEPS=1500000 bash run_all.sh  # daha uzun egitim
```
Sirasiyla: her seed icin egitim -> deterministik eval -> baseline -> 5 grafik
+ `sonuclar.csv`, ve ham loglari `../sonuclar/loglar/` altina kopyalar.

## Tek tek
```bash
python train.py --seed 7 --timesteps 1000000     # tek seed egitim
python evaluate.py --out ../sonuclar/eval_per_episode.csv
python baseline.py --out ../sonuclar/baseline_per_episode.csv
python plot_results.py --out ../sunum/grafikler --summary-out ../sonuclar/sonuclar.csv
bash sweep.sh                                     # Grafik 4 icin HP sweep
```

## Dosyalar
| Dosya | Islev |
|---|---|
| `env/fast_2d_drone_env.py` | 2D Gymnasium ortami (lidar, hareketli engel, ruzgar — stokastik) |
| `train.py` | Tek-seed **PPO** egitimi (config.yaml + CLI override) |
| `evaluate.py` | Deterministik (greedy) eval -> per-episode CSV |
| `baseline.py` | Random + heuristik baseline (Grafik 5) |
| `plot_results.py` | 5 zorunlu grafik + sonuclar.csv |
| `config.yaml` | Tek kaynak konfigurasyon (PPO hiperparametreleri) |
| `seeds.txt` | >=5 seed |
| `run_all.sh` / `sweep.sh` | Pipeline / HP sweep |

## Odul formulu (rapor ile birebir ayni)
`env/fast_2d_drone_env.py::step()` icinde, adim basina:

```
r = -0.01
    + 3.0  * 1[yeni voxel kesfedildi]
    + 20.0 * 1[yeni odaya girildi]
    - 0.10 * 1[50 adimdir yeni voxel yok]
    - 0.3  * max(0, (0.7 - min_lidar)/0.7)        # duvara yakinlik cezasi
    + (-40.0) * 1[carpisma]                        # collision_penalty
    + 60.0 * 1[6 odanin tamami gezildi]            # all_rooms_bonus
    - 0.10 * 1[hucre son 60 adimda tekrar ziyaret]
```
Kod karsiligi: `env/fast_2d_drone_env.py` `step()` metodu (`reward = -0.01` satiri
ile baslayan blok).

## PPO hiperparametreleri (config.yaml `ppo:`)
| Parametre | Deger | Islevi (3 kelime) |
|---|---|---|
| learning_rate | 3e-4 | adim buyuklugu |
| n_steps | 1024 | rollout uzunlugu |
| batch_size | 512 | minibatch boyutu |
| n_epochs | 10 | rollout tekrar sayisi |
| gamma | 0.98 | indirim faktoru |
| gae_lambda | 0.95 | avantaj yumusatma |
| clip_range | 0.2 | politika klipsi |
| ent_coef | 0.005 | entropi/kesif bonusu |
| vf_coef | 0.5 | critic kayip agirligi |
| max_grad_norm | 0.5 | gradyan kirpma |
| net_arch | [256,256] | ag genisligi |

## Kurallara uygunluk
- `import gymnasium as gym` (yeni API) — `import gym` **yok**.
- Tum rastgelelik `numpy.random.default_rng` ile — `np.random.seed` / `np.random.choice` **yok**.
- y-ekseni her grafikte **episode getirisi** (anlik/per-step odul degil).
- >=5 seed, ortalama +/- std bandi, hareketli ortalama penceresi her grafikte.
