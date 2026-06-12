# DEGISIKLIK LISTESI — PPO teslimi

Bu belge, onceki gonderime gore yapilan **her** degisikligi madde madde listeler.
(Beyan edilmeyen degisiklik yapilmamis sayilir.)

> Bu, PPO izinin rubrik (§A) formatindaki **ilk** standart teslimidir. Asagidaki
> liste hem "ilk teslim" beyani hem de onceki ad-hoc PPO denemelerine ve referans
> aldigimiz `algo/td3` (SAC) teslimine gore farklari belgeler.

## 0. Ozet
- Onceki PPO calismasi: eski/ayri bir 2D ortamda (v4.x deneme zinciri), tek-seed,
  dagil grafikli, rubrik formatinda OLMAYAN ad-hoc denemelerdi.
- Bu teslim: `algo/td3` (SAC) branch'inin 11 Haziran teslimiyle **birebir ayni
  ortam / seed / eval / baseline / grafik standardi** altinda, **PPO** ile
  yeniden kuruldu. Amac: ayni kosullarda algoritma karsilastirmasi.

## 1. Ortam: SAC teslimi ile BIREBIR AYNI (bayt-bayt)
- `kod/env/fast_2d_drone_env.py`, `algo/td3` teslimindeki dosya ile **md5 ayni**
  (61ec1d6a8ca09fd601f4fbde5522c7c0). Ayni MDP: ayni 6 oda, ayni hareketli
  engeller, ayni odul formulu, ayni 75-d gozlem, ayni 3-D surekli eylem.
- Ayni env kosullari: `max_episode_steps=600`, `random_start=true`,
  `lidar_noise_std=0.015`, `odom_noise_std=0.004`, `wind_std=0.015`.
- Ayni seed listesi: 7, 13, 42, 123, 2025 (`seeds.txt` aynen).
- Ayni eval protokolu (deterministik, 20 episode, +20000 seed sapmasi) ve ayni
  baseline (random + heuristic, 20 episode). `evaluate.py`/`baseline.py` yalnizca
  model sinifinda (SAC->PPO) farkli; protokol birebir ayni.

## 2. Algoritma: SAC -> PPO (on-policy)
- `train.py` artik `stable_baselines3.PPO` kullanir (SAC degil).
- **Replay buffer kaldirildi** (PPO on-policy; veri her guncellemeden sonra atilir).
  Bu nedenle SAC'a ozgu `buffer_size`, `learning_starts`, `tau`, `train_freq`,
  `gradient_steps`, `target_update_interval`, `target_entropy` parametreleri
  config'ten cikarildi.
- **PPO hiperparametreleri eklendi** (`config.yaml` `ppo:`):
  `n_steps=1024`, `batch_size=512`, `n_epochs=10`, `gae_lambda=0.95`,
  `clip_range=0.2`, `vf_coef=0.5`, `max_grad_norm=0.5`, `ent_coef=0.005`.
- **Adil karsilastirma icin SAC ile ayni tutulanlar**: `learning_rate=3e-4`,
  `gamma=0.98`, `net_arch=[256,256]`, `num_envs=8`.
- `total_timesteps`: SAC 500k'da yakinsiyordu; PPO on-policy ve daha az ornek-verimli
  oldugundan varsayilan **1.000.000** adim (CLI `--timesteps` ile artirilabilir).
- `device`: PPO + MlpPolicy kucuk ag oldugundan **CPU** (GPU transfer yuku olmadan
  daha hizli; SB3 onerisi).

## 3. Loglama: ayni CSV semasi, PPO kayiplari
- `training_log.csv` semasi SAC teslimiyle **ayni** (plot_results degismeden calisir):
  `episode,timestep,ep_return,steps,explored_voxels,coverage_pct,visited_rooms,
  success,crashed,min_lidar,ent_coef,actor_loss,critic_loss`.
- PPO eslemesi: `actor_loss = train/policy_gradient_loss`,
  `critic_loss = train/value_loss`, `ent_coef = config sabit ent_coef`.
- Logger temizleme zamanlamasina karsi **carry-forward** eklendi: episode bitiminde
  son bilinen loss yazilir (Grafik 3 sifirlarla dolmaz).

## 4. Grafik 4 (HP sweep): PPO'ya uygun degerler
- `learning_rate`: 1e-4, 3e-4, 1e-3 (SAC sweep'i ile **ayni** degerler).
- `ent_coef`: 0.0, 0.01, 0.05 (PPO entropi bonusu olcegi; SAC'in 0.05/0.1/0.2
  otomatik-sicaklik araligindan farkli cunku PPO'da ent_coef dogrudan kayba katsayidir).
- Yapi degismedi: 2 parametre x 3 deger x 3 seed.

## 5. Grafik standardina uyum (degismeden korunan)
- Tum grafiklerde y-ekseni **episode getirisi** (anlik/per-step odul DEGIL).
- Her grafikte: baslik, birimli eksen etiketi, lejant, **>=5 seed mean +/- std bandi**,
  hareketli ortalama penceresi (lejant basliginda).

## 6. Kural ihlali kontrolu (sert kurallar)
- `import gym` (eski API): **yok** — her yerde `import gymnasium as gym`.
- `np.random.seed()` / `np.random.choice()`: **yok** — tum rastgelelik
  `numpy.random.default_rng` ile (ortam RNG'si, baseline RNG'si, eval seed'leri).
- `requirements.txt` sabit (`==`) surumler, SAC teslimiyle ayni.
- Dogrulandi; ihlal bulunmadi.

## 7. Teslim klasor yapisi (Rehber §A'ya birebir)
`rapor/  sunum/{sunum, grafikler}  kod/{env, train.py, evaluate.py, baseline.py,
plot_results.py, config.yaml, requirements.txt, seeds.txt, run_all.sh, sweep.sh,
README.md}  sonuclar/{loglar, sonuclar.csv}` ve bu `DEGISIKLIK_LISTESI.md`.
