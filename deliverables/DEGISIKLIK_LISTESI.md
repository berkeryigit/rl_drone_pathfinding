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

---

# EK — 2. Surum Gelistirmeleri (rapor/sunum zenginlestirme + RL-ozgu yeniden egitimler)

Bu bolum, ilk standart teslimden sonra yapilan **ek** gelistirmeleri madde madde
listeler (hocanin "metrikleri degistirip yeniden egit, kiyasla" istegi dogrultusunda).

## E1. Hiperparametre taramasi genisletildi (2 param -> 5 param, 3 seed -> 5 seed)
- Eskiden: `learning_rate` ve `ent_coef`, 3 deger x 3 seed (200k).
- Simdi: **bes** hiperparametre, her biri >=3 deger x **5 seed** (120k, kisa butce
  hiperparametre etkisini izole etmek icin):
  `clip_range {0.1,0.2,0.3}`, `ent_coef {0,0.005,0.01,0.05}`, `gamma {0.95,0.98,0.99}`,
  `learning_rate {1e-4,3e-4,1e-3}`, `vf_coef {0.25,0.5,1.0}`.
- `train.py`'ye `--clip-range`, `--gamma`, `--vf-coef` CLI override'lari eklendi.
- Ek olarak `gamma x learning_rate` icin 3x3 izgara koSuldu (isi haritasi, Grafik 10).
- Tum koSular `numpy.random.default_rng` ile; ham loglar teslimde.

## E2. PPO vs SAC kiyasi: YAN-YANA (ekip SAC grafikleriyle)
- Ortam ekip SAC teslimiyle (M. A. Albayrak, 220202082) **bayt-bayt ayni** oldugundan,
  iki algoritma dogrudan kiyaslanabilir.
- Yaklasim: **ekip arkadasimizin yayinlanmis SAC grafikleri** (220202082 sunumundan
  cikarilan PNG'ler) bizim ayni tip PPO grafigimizin **YANINA** konularak gorsel
  kiyas yapildi (`make_comparison_figs.py` -> `KIYAS_1..6.png`; sol PPO, sag SAC).
- Ust-uste bindirme yerine yan-yana panel tercih edildi (her algoritma kendi
  grafiginde net okunur).
- Kiyas tablosu (`karsilastirma_tablo.tex`) her iki teslimin yayinlanmis sayilarini
  verir; SAC degerleri 220202082 raporundandir.
- Kaynak: `kiyas/PPO_vs_SAC_Karsilastirma.pdf` + rapor Bolum 8 + sunum kiyas slaytlari.

## E3. Grafikler: 5 zorunlu -> 13+ (ekipteki TUM grafiklerin PPO karsiligi)
- Eklendi: Grafik 1b (episode-bazli ogrenme egrisi), 6 (PPO ic dinamikleri:
  clip_fraction/approx_kl/entropy -- DQN epsilon'unun karsiligi), 7 (oda kesif
  sureci), 8 (carpisma orani), 9 (seed karsilastirmasi), 10 (gamma x lr isi
  haritasi), 13 (explained_variance), 5b (baseline 4-metrik), per-seed 2x2 paneller
  (her seed icin getiri/eval/kapsama/oda) ve PPO-vs-SAC yan-yana kiyas figurleri (KIYAS_1-6).
- Tum grafikler tek motor `viz.py`'den; `progress.csv`'deki PPO-ozel metrikler okunur.

## E4. Rapor ve sunum zenginlestirildi
- Rapor: yeni grafikler + 4-cumlelik yorumlar + 5-param HP duyarlilik + yan-yana SAC
  kiyas bolumu + uzun-ufuk + savunma analizi. Tablolar `make_tables.py` ile **ham
  CSV'lerden** uretilir (`sonuclar_tablo.tex`, `karsilastirma_tablo.tex`).
- Sunum (`make_pptx.py`): ~26+ slayt; tum grafikler, per-seed paneller, PPO-vs-SAC
  (yan-yana kiyas figurleri), savunma ozeti.

## E5. Bonus: uzun-ufuk kararlilik
- En iyi tohum (123) ayri `runs_long/` altinda daha uzun ufka uzatildi; ana 5-seed
  teslim 1.5M'de (validated, surekli loglar) korundu. Grafik 12: 1.5M sonrasi plato
  bozulmuyor -> butce yeterliligi dogrulanir.

## E6. Kural ihlali kontrolu (tekrar dogrulandi)
- `import gym` yok; `np.random.seed`/`np.random.choice` yok; `default_rng` var.
- Yeni eklenen `viz.py`, `make_comparison_figs.py`, `make_episode_figs.py`,
  `make_tables.py` de ayni kurallara uyar.

## E7. Savunma analizi DETAYLANDIRILDI (rapor + sunum)
- Eskiden: 4 kavram alani kisa paragraflarla yanitlaniyordu.
- Simdi: her isterler.md sorusu **gerekceli** yanitlandi ("Evet/Hayir" yetmez; sebep +
  kod satiri + ornek). Hem **rapor** (Bolum 9, dort alt-bolum) hem **sunum** (tek slayt
  -> 4 detayli slayt):
  - **Alan 1 (Stokastik):** stokastikligi saglayan DEGERLER + kod satirlari acikca yazildi
    --- ruzgar $\sigma=0.015$ [step, 133-135, GECIS], lidar $\sigma=0.015$ [319-320],
    odometri $\sigma=0.004$ [233-236], 3 hareketli engel [203-206]; somut $p(s'|s,a)$
    ornegi (drone (5,5) + ileri -> $s'$ bir dagilim); tohum/baslangic-rastgeleligi ayrimi.
  - **Alan 2 (On-policy):** davranis=hedef politika, replay buffer yok, neden ornek-verimsiz,
    SARSA vs Q-Learning tek-satir fark.
  - **Alan 3 (Markov):** yaklasik Markov; onceki eylem ile hiz tasinir (top ornegi),
    engel fazi eksik; Atari 4-kare analojisi; iki cozum.
  - **Alan 4 (POMDP):** gercek durum vs gozlem ayri ayri; eksik bilgi; belief state.
- Sunum Ortam/MDP slaytina stokastiklik deger kutusu eklendi.

## E8. Episode-eksenli grafikler eklendi (`make_episode_figs.py`)
- Rehber "episode sayisina gore ogrenme egrisi" istiyor ve "x: episode VEYA adim --
  ikisi de gecerli" diyor. Ana egrilerin x-ekseni kumulatif adim idi; ek olarak
  **x = episode** versiyonlari uretildi:
  `EP1_ogrenme_episode.png` (ogrenme), `EP2_oda_episode.png` (oda kesfi),
  `EP3_carpisma_episode.png` (carpisma), `EP4_seed_episode.png` (seed karsilastirma).
  Ayrica mevcut `1b_ogrenme_egrisi_episode.png` (episode-bazli ogrenme) korunur.
- Bu PNG'ler `sunum/grafikler/` altinda; ana 5-seed `training_log.csv`'lerin `episode`
  kolonundan uretilir (sentetik degil).
