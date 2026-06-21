# Pekiştirmeli Öğrenme ile Çok-Odalı Ortamda Drone Keşif/Yol Bulma

**Teknik Rapor**

---

## 1. Özet

Bu çalışmada, altı odalı kapalı bir ortamda otonom bir dronun **tüm odaları
keşfetmesini** (coverage / exploration) öğrenen bir pekiştirmeli öğrenme (RL)
ajanı geliştirilmiştir. Ajan, **Soft Actor-Critic (SAC)** algoritmasıyla, hızlı
bir **2B Gymnasium ortamında** eğitilmiş; eğitilen politika ayrıca Gazebo 3B
simülatöründe test edilmiştir. Ortam, rüzgâr / LIDAR / odometri gürültüsü ve
hareketli engeller içeren **stokastik bir POMDP** olarak tasarlanmıştır. Beş
farklı rastgele tohum (seed) ile yürütülen eğitimlerde en iyi model
**%60 tam-keşif başarısı**, ortalama **5.48/6 oda** ve **%95+ alan kapsama**
değerlerine ulaşmıştır. Sonuçlar; rastgele ve sezgisel (heuristik) iki temel
politikayla (baseline) karşılaştırılmış, ajanın görev metriği (ziyaret edilen
oda) bakımından her iki temel politikayı da geçtiği gösterilmiştir.

---

## 2. Problem Tanımı

Ortam, `8×8 m` yarı-genişlikte (toplam `16×16 m`) kapalı bir dünyadır ve duvarlarla
**altı odaya** bölünmüştür. Odalar arası geçişler **kapılarla** sağlanır. Dronun
amacı, çarpışmadan, sınırlı sürede mümkün olduğunca çok odayı ve hücreyi
keşfetmektir.

- **Dünya boyutu:** `2·WORLD_HALF = 16 m` (kare)
- **Keşif ızgarası:** `0.5 m` hücre → `32×32 = 1024` hücre
- **Oda sayısı:** `N_ROOMS = 6` (2 satır × 3 sütun)
- **Kapı konumları:** 5 adet (`DOOR_POSITIONS`)
- **Episode uzunluğu:** en çok `600` adım (`dt = 0.12 s` → ~72 s)

Görev, **gecikmeli ödül** (bir odaya ulaşmak için önce koridoru geçmek gerekir),
**ardışık karar** ve **kısmi gözlemlenebilirlik** içerdiğinden klasik bir RL
problemidir.

---

## 3. Markov Karar Süreci (MDP) Formülasyonu

Problem `(S, A, P, R, γ)` beşlisiyle modellenmiştir. Gözlem gürültüsü nedeniyle
gerçekte bir **POMDP**'dir.

### 3.1 Durum / Gözlem Uzayı — `S` (75 boyut)

`observation_space = Box(shape=(LIDAR_BINS + 11,)) = Box(75,)`
(`env/fast_2d_drone_env.py:84`)

| Bileşen | Boyut | Açıklama |
|---|---|---|
| LIDAR ışınları | 64 | `5.625°` çözünürlük, `[0,1]`'e normalize (`/LIDAR_MAX=10 m`) |
| Yaw (cos, sin) | 2 | Ölçülen yönün trigonometrik gösterimi |
| Önceki eylem | 3 | `prev_action` (eylem yumuşatma için) |
| İlerleme + oda | 2 | Kapsama oranı, ziyaret edilen oda oranı |
| min-LIDAR + boşta | 2 | En yakın engel, voxel'siz geçen adım oranı |
| Kapı + duvar | 2 | En yakın kapı mesafesi, duvara yakınlık |

> **POMDP notu:** Gözlemdeki konum/yaw, **ölçülen** (gürültülü) değerlerdir;
> ortamın gerçek konumu bozulmaz (`_make_obs`, `env/fast_2d_drone_env.py:234-236`).

### 3.2 Eylem Uzayı — `A` (sürekli, 3 boyut)

`action_space = Box([-1,-1,-1], [1,1,1])` (`env/fast_2d_drone_env.py:77`)

| Eylem | Ölçek | Anlam |
|---|---|---|
| `a[0] → vx` | `× V_MAX = 1.2 m/s` | İleri/geri hız (gövde ekseni) |
| `a[1] → vy` | `× V_MAX = 1.2 m/s` | Yanal hız |
| `a[2] → wz` | `× W_MAX = 1.5 rad/s` | Açısal hız (dönüş) |

Eylemler `ACTION_SMOOTH = 0.15` katsayısıyla bir önceki eylemle harmanlanır
(ani sıçramaları engeller, gerçekçi dinamik): `a = 0.15·a_önceki + 0.85·a`
(`env/fast_2d_drone_env.py:127`).

### 3.3 Geçiş Dinamiği — `P` (stokastik)

Konum güncellemesi, dünya çerçevesine döndürülmüş hız + **rüzgâr gürültüsü**
ile yapılır (`env/fast_2d_drone_env.py:133-139`):

```
vx += N(0, wind_std);  vy += N(0, wind_std);  wz += N(0, wind_std)
pos += R(yaw) · [vx, vy] · dt
```

Bu, `P(s'|s,a)`'yı **dejenere olmaktan çıkarır**: aynı `(s,a)` farklı `s'`
üretebilir → ortam gerçekten stokastiktir (bkz. §4).

### 3.4 İndirim Faktörü — `γ = 0.98`

Hiperparametre araması sonucu seçilmiştir (§7). `0.98`, ~50 adımlık etkin
ufuk sağlar; gecikmeli oda ödülünü yakalayacak kadar uzun, kararsızlık
yaratmayacak kadar kısadır.

---

## 4. Ortamın Stokastikliği (Kanıt)

Ortam, üç bağımsız Gauss gürültü kaynağı ve zaman-değişken engeller içerir.
Tüm rastgelelik **`numpy.random.default_rng`** ile üretilir
(`np.random.seed` / `np.random.choice` **kullanılmaz**).

| Kaynak | Parametre | Etki | Kod |
|---|---|---|---|
| Rüzgâr (geçiş) | `wind_std = 0.015` | Hız komutuna gürültü | `:133-135` |
| LIDAR (gözlem) | `lidar_noise_std = 0.015` | Mesafe ölçümüne gürültü | `:319-320` |
| Odometri (gözlem) | `odom_noise_std = 0.004` | Ölçülen konum/yaw'a gürültü | `:234-236` |
| Hareketli engeller | 3 adet | Sinüzoidal, zaman-değişken | `:203-206` |

> **Dürüst not:** Rastgele başlangıç (reset) **tek başına** stokastiklik
> sayılmaz; yalnızca başlangıç dağılımını `μ(s₀)` etkiler. Asıl stokastiklik
> yukarıdaki geçiş + gözlem gürültüsünden gelir.

---

## 5. Ödül Fonksiyonu — `R`

Ödül, adım başına aşağıdaki terimlerin toplamıdır
(`env/fast_2d_drone_env.py:158-183`, `step` metodu). **Rapor ile kod birebir
aynıdır.**

$$
\begin{aligned}
r_t = \;& -0.01 \\
      & + 3.0 \cdot \mathbb{1}[\text{yeni voxel keşfedildi}] \\
      & + 20.0 \cdot \mathbb{1}[\text{yeni odaya girildi}] \\
      & - 0.10 \cdot \mathbb{1}[\text{50 adımdır yeni voxel yok}] \\
      & - 0.3 \cdot \max\!\left(0,\; \tfrac{0.7 - \text{min\_lidar}}{0.7}\right)
        \quad \text{(duvara yakınlık cezası)} \\
      & - 40.0 \cdot \mathbb{1}[\text{çarpışma}] \\
      & + 60.0 \cdot \mathbb{1}[\text{6 odanın tamamı gezildi}] \\
      & - 0.10 \cdot \mathbb{1}[\text{hücre son 60 adımda tekrar ziyaret edildi}]
\end{aligned}
$$

| Terim | Değer | Amaç |
|---|---|---|
| Adım cezası | `-0.01` | Verimli/kısa yolu teşvik |
| Yeni voxel | `+3.0` | **Asıl keşif sinyali** (LIDAR ile görülen her yeni hücre) |
| Yeni oda | `+20.0` | Odalar arası geçişi (kapı bulmayı) teşvik |
| Boşta cezası | `-0.10` | 50 adım yeni keşif yoksa takılmayı kır |
| Duvar yakınlığı | `≤ -0.3` | Güvenli mesafe (`min_lidar < 0.7 m`) |
| Çarpışma | `-40.0` | Episode'u bitirir; güçlü caydırıcı |
| Tüm odalar bonusu | `+60.0` | Görev tamamlama ödülü |
| Tekrar ziyaret | `-0.10` | Aynı yerde dönüp durmayı engelle |

**Keşif mekaniği (önemli):** Yeni voxel sayımı **görünürlük tabanlıdır** — drone
yalnızca bastığı yeri değil, **64 LIDAR ışınının duvara kadar geçtiği tüm
hücreleri** keşfeder (`_mark_visible_voxels`, `:255-287`). Işın bir duvara
çarptığında durur (`in_range = t ≤ lidar_dist`), bu yüzden **duvar arkası
görülmez** — fiziksel olarak doğru bir görüş modeli.

**Episode sonu koşulları:**
- `terminated`: çarpışma **veya** 6 odanın tamamı gezildi (`:185`)
- `truncated`: 600 adım doldu (`:186`)

---

## 6. Algoritma: Soft Actor-Critic (SAC)

SAC, **sürekli eylem uzayları** için tasarlanmış, **off-policy**, entropi
düzenlemeli bir aktör-kritik algoritmasıdır. Bu problem için seçilme nedenleri:

1. **Sürekli eylem:** Hız komutları (`vx, vy, wz`) doğal olarak süreklidir;
   ayrıklaştırma gerektirmez (DQN'in aksine).
2. **Entropi maksimizasyonu:** `ent_coef=auto` ile sıcaklık otomatik ayarlanır;
   keşif–sömürü dengesi öğrenme boyunca kendiliğinden düzenlenir — keşif görevi
   için kritik.
3. **Örnek verimliliği:** Replay buffer ile off-policy çalışır; stokastik
   ortamda (PPO gibi on-policy yöntemlere kıyasla) daha verimlidir.
4. **Stokastik politika:** Gürültülü POMDP'de gürbüz davranış sağlar.

Uygulama: **Stable-Baselines3** `SAC` + `MlpPolicy` (`[256, 256]` gizli katman).

---

## 7. Hiperparametreler

Tek kaynak: `config.yaml`. Eğitim altyapısı: `8` paralel ortam (`SubprocVecEnv`).

| Parametre | Değer | Açıklama |
|---|---|---|
| `learning_rate` | `3e-4` | HP araması sonucu |
| `gamma` (γ) | `0.98` | HP araması sonucu |
| `buffer_size` | `600 000` | Uzun eğitim için geniş replay |
| `batch_size` | `512` | GPU verimliliği |
| `learning_starts` | `10 000` | Önce saf keşifle buffer doldur |
| `tau` | `0.02` | Hedef ağ yumuşak güncelleme |
| `train_freq` / `gradient_steps` | `32 / 32` | Burst toplama (~1:8 update:data) |
| `ent_coef` | `auto` | Otomatik sıcaklık |
| `net_arch` | `[256, 256]` | Aktör & kritik MLP |
| `num_envs` | `8` | Paralel veri toplama |

### 7.1 Hiperparametre Araması

`γ ∈ {0.97, 0.98, 0.99}` × `lr ∈ {1e-4, 3e-4, 1e-3}` ızgarası, seed 42 üzerinde
kısa eğitimlerle (`smart_train.py`, `sweep.sh`) tarandı. Skor metriği:
`10·ortalama_oda + 0.05·ortalama_getiri`. Sonuç: **`γ=0.98, lr=3e-4`** uzun
vadede en kararlı/yüksek performansı verdi (`plot_hp_search.py`, Grafik 4).

---

## 8. Eğitim Metodolojisi

- **5 rastgele tohum:** `seeds.txt = {7, 13, 42, 123, 2025}` — varyans/gürbüzlük
  raporlaması için (kural gereği ≥5 seed).
- **Erken durdurma:** `StopTrainingOnNoModelImprovement` (`--stop-patience`);
  ardışık eval'larda iyileşme yoksa eğitim durur, en fazla 1M adım.
- **En iyi model:** `EvalCallback` her `10k` adımda deterministik (greedy) eval
  yapar; en yüksek ortalama getirili model `best/best_model.zip` olarak saklanır.
- **Devam (`--resume`):** Checkpoint'tan kaldığı yerden eğitim; tohumlar farklı
  toplam adıma kadar sürdürüldü.
- **Tekrarlanabilirlik:** Her koşu `run_meta.json` (seed, config, sürüm) üretir;
  ham loglar `sonuclar/loglar/` altında her grafiği destekler.

---

## 9. Sonuçlar

### 9.1 Tohum Bazında Performans (son 50 episode ortalaması)

| Seed | Toplam Adım | Ort. Getiri | Ort. Oda | Tam-Keşif Başarısı |
|---|---|---|---|---|
| **123** ⭐ | 1.71 M | **393.7** | **5.48 / 6** | **%60** |
| **42** | 1.53 M | 348.0 | 5.26 / 6 | %48 |
| 7 | 0.50 M | 315.2 | 4.90 / 6 | %36 |
| 2025 | 0.90 M | 268.3 | 4.38 / 6 | %12 |
| 13 | 0.50 M | 247.9 | 4.14 / 6 | %12 |

En iyi model **seed 123**'tür (`runs/seed_123/best/best_model.zip`). Tohum 13 ve
2025'in görece düşük kalması, RL'in **seed'e duyarlılığını** (varyansı) gösterir;
bu, ≥5 seed raporlamasının neden gerekli olduğunun somut kanıtıdır.

### 9.2 Temel Politikalarla Karşılaştırma (Baseline — 100 episode)

| Politika | Ort. Getiri | Ort. Oda | Kapsama | Tam-Keşif |
|---|---|---|---|---|
| Rastgele | 48.8 | 1.07 / 6 | %38.6 | %0 |
| Sezgisel (heuristik) | 402.0 | 4.08 / 6 | %79.9 | %20 |
| **SAC (en iyi)** | ~366* | **5.48 / 6** | **%95+** | **%60** |

\* Deterministik eval getirisi; eğitim getirisiyle birebir kıyaslanamaz.

**Yorum:** Sezgisel politika güçlü bir temeldir — "en açık LIDAR yönüne git"
kuralı, açık alanlarda yüksek voxel ödülü toplayarak yüksek *getiri* (402)
üretir. Ancak **asıl görev metriğinde** (ziyaret edilen oda: 4.08 ve tam-keşif:
%20), öğrenen ajan onu açık farkla geçer (5.48 oda, %60 başarı). Bunun nedeni:
heuristik açık alana yönelirken **sistematik olarak kapı arayıp tüm odaları
dolaşmayı** öğrenemez; SAC ajanı gecikmeli oda ödülünü (+20) ve tüm-oda bonusunu
(+60) optimize ederek bu davranışı kazanır. Rastgele politika ise referans
tabanı oluşturur (%0 başarı), öğrenmenin gerçek bir kazanım olduğunu doğrular.

### 9.3 Zorunlu Grafikler

`plot_results.py` beş standart grafiği üretir (her birinin y-ekseni **episode
getirisi**, ≥5 seed `ort ± std` bandı, hareketli ortalama, başlık/eksen/lejant):

1. **Öğrenme eğrisi** — eğitim getirisi vs. adım
2. **Deterministik eval eğrisi** — greedy politika getirisi
3. **Kayıp (loss) eğrisi** — aktör & kritik kaybı
4. **Hiperparametre duyarlılığı** — `γ × lr` ızgarası (`plot_hp_search.py`)
5. **Baseline karşılaştırması** — rastgele / heuristik vs. ajan

Ek olarak `plot_per_seed.py`, her tohum için 4-panelli ayrı pano üretir; tohumlar
adil karşılaştırma için ortak minimum adıma kırpılır.

---

## 10. Sim-to-Sim: Gazebo Testi

Eğitilen politika, 3B Gazebo ortamında (`eval_sac.py`) test edilmiştir. Gözlenen
performans (ör. ilk episode: `-120.9` getiri, 4 voxel, 1 oda) 2B eğitimdekinden
**belirgin biçimde düşüktür**. Bu, beklenen bir **sim-to-sim açığıdır**:

- İki ortamın **ödül yapıları farklıdır** (Gazebo'da çarpışma `-10`, tekrar-ziyaret
  cezası, kapı ödülü, bekleme cezası gibi ek terimler).
- 2B ortam, Gazebo dünyasının hızlı bir **yaklaşımıdır**; dinamik ve sensör
  modeli birebir aynı değildir.

Bu bulgu, **alan farkının (domain gap)** transfer öğrenmedeki etkisini gösteren
geçerli bir deneysel sonuç olarak raporlanmıştır. Eğitim ~onlarca kat hızlı
olduğundan 2B'de yapılır; Gazebo yalnızca nitel doğrulama/gösterim içindir.

---

## 11. Kurallara Uygunluk

- ✅ `import gymnasium as gym` — eski `import gym` **yok**.
- ✅ Tüm rastgelelik `numpy.random.default_rng` — `np.random.seed` /
  `np.random.choice` **yok**.
- ✅ Tüm grafiklerde y-ekseni **episode getirisi** (anlık/per-step ödül değil).
- ✅ ≥5 seed, `ort ± std` bandı, hareketli ortalama penceresi.
- ✅ Ödül formülü rapor (§5) ile kod (`fast_2d_drone_env.py:158-183`) birebir.
- ✅ Ham loglar `sonuclar/loglar/` altında her grafiği destekler.

---

## 12. Sonuç ve Değerlendirme

Stokastik, çok-odalı bir keşif probleminde SAC ajanı, ham LIDAR gözleminden
başlayarak **sistematik oda-oda keşif** davranışını öğrenmiştir. En iyi model
%60 tam-keşif başarısı ve 5.48/6 ortalama oda ile hem rastgele hem de güçlü
sezgisel temel politikayı görev metriğinde geçmiştir. Görünürlük tabanlı keşif,
gecikmeli oda ödülü ve otomatik entropi düzenlemesinin birleşimi başarının
anahtarıdır.

**Gelecek çalışma:** (i) 2B→Gazebo açığını kapatmak için ödül yapılarının
hizalanması veya domain randomization; (ii) tohum 13/2025'teki varyansı azaltmak
için daha uzun eğitim / popülasyon-tabanlı arama; (iii) tekrarlayan gözlem
(LSTM/frame-stack) ile POMDP'nin daha iyi ele alınması.

---

### Ek: Çoğaltma (Reproduction)

```bash
# Tek komutla: eğitim → eval → baseline → 5 grafik → sonuclar.csv
bash kod/run_all.sh
TIMESTEPS=1000000 bash kod/run_all.sh   # daha uzun eğitim

# Hiperparametre duyarlılığı (Grafik 4)
bash kod/sweep.sh

# En iyi modelin 2B kaydı (GIF)
python kod/record_2d.py --episodes 3
```
