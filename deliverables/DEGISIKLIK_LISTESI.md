# DEGISIKLIK LISTESI

Bu belge, onceki gondedrime gore yapilan **her** degisikligi madde madde listeler.
(Beyan edilmeyen degisiklik yapilmamis sayilir.)

> Not: Ilk teslim iseniz bu dosyayi tek satirla "ilk teslim" olarak degistirin.
> Asagidaki liste, mevcut repodaki onceki SAC/Gazebo calismasina gore yapilan
> degisiklikleri belgeler.

## 1. Egitim mimarisi: SADECE 2D (Gazebo egitimden cikarildi)
- Egitim artik **yalnizca** `kod/env/fast_2d_drone_env.py` (saf Python + numpy +
  gymnasium) uzerinde yapilir. Gazebo egitim dongusunden cikarildi.
- Gazebo **yalnizca** egitilmis politikanin testi/gosterimi icin kullanilir
  (ana repo: `ros2_ws/.../agents/eval_sac.py`).
- Gerekce: 2D ortam ile egitim ~onlarca kat hizli; ayni MDP (lidar, ardisik
  eylem, gecikmeli odul, stokastik dinamik) korunuyor.

## 2. Hiz / replay buffer ayarlari (egitimi hizlandirma)
`kod/config.yaml` ve `kod/train.py` (ayrica ana repo `train_sac_fast_2d.py`):
- `buffer_size`: 250.000 -> **600.000** (100k+ step icin yeterli replay kapasitesi)
- `batch_size`: 256 -> **512** (GPU verimliligi)
- `learning_starts`: 5.000 -> **10.000**
- `train_freq`: (1, step) -> **(32, step)** + `gradient_steps`: 1 -> **32**
  (burst toplama; Python dongu yuku azalir, ~1:8 update:data orani korunur)
- `optimize_memory_usage` opsiyonu eklendi (cok buyuk buffer'da RAM ~yariya iner)
- `total_timesteps` varsayilani 100.000 -> **300.000** (ve `--timesteps` ile
  istenildigi kadar artirilabilir)

## 2b. Lidar cozunurlugu 32 -> 64 (gozlem boyutu 43 -> 75)
- `LIDAR_BINS`: 32 -> **64** (acisal cozunurluk 11.25° -> 5.625°).
- `observation_space` artik **dinamik**: `shape=(LIDAR_BINS + 11,)` = 75
  (onceden hardcoded `shape=(43,)` idi -> gizli kuplaj giderildi).
- Hem 2D egitim ortami (`fast_2d_drone_env.py`) hem Gazebo test ortami
  (`drone_exploration_env.py`) **birlikte** guncellendi; Gazebo `_bin_lidar`
  ham 360 nokta /scan'i 64 bin'e indirir => 2D'de egitilen model Gazebo testinde
  ayni 75-d gozlemle calisir.
- NOT: Eski 43-d egitilmis modeller bu degisiklikten sonra yuklenemez; sifirdan
  egitim gerekir (zaten yeniden egitiliyor).

## 2c. Stokastisite: odom_noise artik uygulaniyor (olu parametre giderildi)
- `odom_noise_std` onceden dataclass'ta tanimliydi ama **hicbir yerde kullanilmiyordu**
  (kod/iddia tutarsizligi). Artik `_make_obs` icinde uygulaniyor:
  GERCEK poz/yaw (dinamik + carpisma) bozulmadan, **olculen** poz/yaw gozleme
  gurultulu girer => stokastik gozlem (POMDP tadi).
- Ortamin stokastik oldugunun kod-satiri kaniti (savunma icin):
  - Gecis gurultusu (ruzgar): `fast_2d_drone_env.py` step(), `self._rng.normal(...)`
    vx/vy/wz uzerine => ayni (s,a) -> farkli s'  (P(s'|s,a) dejenere degil).
  - Gozlem gurultusu (lidar): `_compute_lidar`, `self._rng.normal(...)`.
  - Gozlem gurultusu (odom): `_make_obs`, olculen poz/yaw.
- NOT: Rastgele baslangic (reset) tek basina stokastik SAYILMAZ; yalnizca baslangic
  dagilimi mu(s0)'i etkiler. Hareketli engeller deterministik (sin(adim)).

## 3. Yeni teslim pipeline'i (kod/)
Onceki gonderimde tek-seed, dagil grafik vardi. Eklenenler:
- `train.py` — config.yaml tabanli **tek-seed** egitim (CLI override'lar: timesteps,
  num_envs, lr, ent_coef, device, out).
- `evaluate.py` — **deterministik (greedy)** eval, per-episode CSV (eval egrisi/B2).
- `baseline.py` — **random + heuristik** baseline (B5 baseline grafigi).
- `plot_results.py` — **5 zorunlu grafik** (ayri PNG) + `sonuclar.csv`.
- `run_all.sh` — tum seed egitim -> eval -> baseline -> grafik tek komut.
- `sweep.sh` — hiperparametre duyarliligi sweep (2 param x 3 deger, B4).
- `seeds.txt` (5 seed), `requirements.txt` (**== sabit surum**), `config.yaml`.

## 4. Grafik standardina uyum
- Tum grafiklerde y-ekseni **episode getirisi** (anlik/per-step odul DEGIL).
  Log kolonu `ep_reward` -> **`ep_return`** olarak yeniden adlandirildi (netlik).
- Her grafikte: baslik, birimli eksen etiketi, lejant, **>=5 seed mean +/- std bandi**,
  hareketli ortalama penceresi (lejant basliginda belirtildi).

## 5. Kural ihlali kontrolu (sert kurallar)
- `import gym` (eski API): repoda **yok** — her yerde `import gymnasium as gym`.
- `np.random.seed()` / `np.random.choice()`: repoda **yok** — tum rastgelelik
  `numpy.random.default_rng` ile (ortam RNG'si, baseline RNG'si, eval seed'leri).
- Bu maddeler dogrulandi; ihlal bulunmadi.

## 6. Teslim klasor yapisi
Rehber §A'ya birebir uyacak iskelet olusturuldu:
`rapor/  sunum/grafikler/  kod/{env, train.py, evaluate.py, config.yaml,
requirements.txt, seeds.txt, run_all.sh, README.md}  sonuclar/{loglar, sonuclar.csv}`
ve bu `DEGISIKLIK_LISTESI.md`.

---
### Henuz uretilmesi gerekenler (egitim kullanici tarafindan calistirilacak)
- `bash kod/run_all.sh` -> `sonuclar/loglar/` ham loglari + `sunum/grafikler/` 5 PNG
  + `sonuclar/sonuclar.csv` doldurulacak.
- `bash kod/sweep.sh` -> Grafik 4 (hiperparametre duyarliligi) verisi.
- Her grafik altina 4 cumlelik yorum (Gozlem->Karsilastirma->Aciklama->Sonuc) rapora.
