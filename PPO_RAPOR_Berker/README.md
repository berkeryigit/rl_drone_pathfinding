# PPO Drone Keşfi — Rapor Klasörü (Berker Yiğit)

Bu klasör, projenin **en baştaki kurulumdan (v1) son sürüme (v5.0) kadar** tüm kayda değer
sonuçlarını, parametre değişimlerini ve gerekçelerini içerir.

## Nereden başlamalı?

| Dosya | İçerik |
|---|---|
| **`RAPOR.md`** | ⭐ Ana rapor — problem, 3 faz, ana bulgular, sonuç. **Önce bunu oku.** |
| **`PARAMETRELER_VE_GEREKCELER.md`** | ⭐ Her sürümde **ne değişti + NEDEN öyle davrandı** (v4.8 neden %0, v4.10 neden hem kapsayıcı hem %54 vb.) |
| `SONUCLAR.csv` | Tüm 25 sürümün makine-okunur metrik tablosu (Excel/pandas'a aç) |
| `figurler/` | Anahtar görseller (01–12 numaralı, hikaye sırasında) |
| `figurler/tum_surumler/` | Her sürümün kapsama + yörünge haritası (tartışmak için) |
| `ham_veri/` | Zaman damgalı karar günlüğü + detaylı kıyas dokümanları |

## En önemli iki sonuç

- **`figurler/03_v4_8_GUVENLI_kapsama.png`** — v4.8: **%0 çarpışma**, 5 oda, 117 voxel (ödev hedefinin cevabı)
- **`figurler/05_v4_10_KAPSAM_kapsama.png`** — v4.10: **281 voxel, 6 oda**, %44.5 kapsama ama %54 çarpışma (kapasite tavanı)
- **`figurler/01_pareto_cephesi.png`** — kapsama↔güvenlik ödünleşiminin Pareto cephesi (rapor için ideal figür)

## Tek cümlelik özet

Çarpışmayı **gözlem tasarımı** (lidar geçmişi) çözdü (%80→%1); ardından "çok kapsa" ile "hiç
çarpma" arasında **temel bir ödünleşim** olduğu, 14 deney + 4 bağımsız kaldıraçla kanıtlandı —
iki teslim politikası: **v4.8 (güvenli)** ve **v4.10 (kapsamlı)**.

## Model dosyaları nerede?

Eğitilmiş ağırlıklar repo içinde:
- `rl_drone_pathfinding/runs/fast_v4_8/checkpoints/fast_drone_final.zip` (güvenli)
- `rl_drone_pathfinding/runs/fast_v4_10/checkpoints/fast_drone_final.zip` (kapsamlı)
