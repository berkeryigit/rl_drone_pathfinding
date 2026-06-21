# Değişiklik Listesi

Önceki gönderime göre yapılan değişiklikler madde madde aşağıdadır.
Beyan edilmeyen değişiklik yapılmamış sayılır.

**Önceki teslim:** tek seed, Gazebo üzerinde eğitim, dağınık tek grafik.
**Bu teslim:** çoklu-seed 2B eğitim, deterministik değerlendirme, baseline
karşılaştırması ve tam grafik/log pipeline'ı. Aşağıda eklenen özellikler ve
yapılan değişiklikler listelenmiştir.

---

## Eklenen özellikler

1. **Hızlı 2B eğitim ortamı** — Eğitim için saf Python + numpy + gymnasium ile
   yazılmış yeni bir 2B ortam (`env/fast_2d_drone_env.py`). Gazebo eğitim
   döngüsünden çıkarıldı; yalnızca test/gösterim için kullanılıyor.

2. **Görünürlük tabanlı keşif** — Drone sadece bastığı yeri değil, LIDAR
   ışınlarının duvara kadar gördüğü tüm hücreleri keşfeder. Işın duvara çarpınca
   durur, yani duvar arkası görülmez (gerçekçi görüş modeli).

3. **Stokastik ortam (POMDP)** — Ortama üç bağımsız gürültü kaynağı eklendi:
   rüzgâr (hareket), LIDAR (algılama) ve odometri (konum ölçümü). Gerçek konum
   bozulmaz; yalnızca gözleme giren ölçümler gürültülüdür.

4. **Çoklu-seed eğitim** — Tek seed yerine 5 farklı tohumla eğitim
   (`seeds.txt`), sonuçların varyansını/gürbüzlüğünü raporlamak için.

5. **Hiperparametre araması** — İndirim faktörü (gamma) ve öğrenme oranını
   ızgara taramasıyla deneyip en iyisini seçen otomatik arama
   (`smart_train.py`, `sweep.sh`).

6. **En iyi modeli otomatik kaydetme** — Eğitim boyunca düzenli deterministik
   değerlendirme yapılır; en yüksek skorlu model `best_model.zip` olarak ayrı
   saklanır.

7. **Erken durdurma** — Performans bir süre iyileşmezse eğitim kendiliğinden
   durur (`--stop-patience`), gereksiz hesaplama yapılmaz.

8. **Checkpoint'ten devam** — Eğitim durdurulup `--resume` ile kaldığı yerden
   sürdürülebilir; log üzerine yazmaz, ekleme yapar.

9. **Deterministik değerlendirme** — Eğitilmiş modeli greedy politikayla
   çalıştırıp episode bazında sonuç üreten ayrı betik (`evaluate.py`).

10. **Baseline karşılaştırması** — Rastgele ve sezgisel (heuristik) iki temel
    politika eklendi (`baseline.py`); ajanın öğrenmesinin gerçek kazanım
    olduğunu göstermek için.

11. **5 zorunlu grafik** — Öğrenme, eval, loss, hiperparametre duyarlılığı ve
    baseline karşılaştırması grafiklerini ayrı PNG olarak üreten betik
    (`plot_results.py`). Baseline grafiği getiri, keşfedilen oda, kapsama ve
    başarı olmak üzere dört metriği birden gösterir.

12. **Tohum bazında bireysel grafikler** — Her seed için ayrı öğrenme, eval,
    loss ve özet (dashboard) grafikleri (`plot_per_seed.py`).

13. **Hiperparametre arama görselleştirmesi** — Izgara aramasının sonuçlarını
    ısı haritası ve öğrenme eğrileriyle gösteren grafik (`plot_hp_search.py`).

14. **2B demo kaydı** — En iyi modeli 2B ortamda çalıştırıp keşfini animasyonlu
    GIF + son kare olarak kaydeden betik (`record_2d.py`).

15. **Tek komutluk pipeline** — Tüm seed eğitimi → değerlendirme → baseline →
    grafikler → özet CSV → ham log kopyalama tek komutta (`run_all.sh`).

16. **Daha hassas algılama** — LIDAR çözünürlüğü artırıldı (açısal çözünürlük
    iki katına çıktı); gözlem boyutu sabit-kodlu olmaktan çıkarılıp dinamik
    hale getirildi.

---

## Grafik standardına uyum

- Tüm grafiklerde y-ekseni **episode getirisi** (anlık/per-step ödül değil).
- Her grafikte başlık, birimli eksen etiketi, lejant, ≥5 seed ortalama ± std
  bandı ve hareketli ortalama penceresi var.
- Ham loglar `sonuclar/loglar/` altında her grafiği destekler.

## Kural uygunluğu

- `import gymnasium as gym` kullanılır; eski `import gym` **yok**.
- Tüm rastgelelik `numpy.random.default_rng` ile; `np.random.seed` /
  `np.random.choice` **yok**.
- Ödül formülü rapor ile kod (`fast_2d_drone_env.py`, `step`) birebir aynıdır.

## Teslim klasör yapısı

`rapor/  sunum/grafikler/  kod/{env, train.py, evaluate.py, config.yaml,
requirements.txt, seeds.txt, run_all.sh, README.md}  sonuclar/{loglar,
sonuclar.csv}` ve bu `DEGISIKLIK_LISTESI.md`.
