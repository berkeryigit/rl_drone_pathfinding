# PPO Drone Kesif — Egitim Raporu

Otomatik uretildi (`scripts/report.py`). Operator agent gunceller.

## Versiyon Ozeti

| Versiyon | Son step | Son reward | Peak reward | Peak voxel (max) | Peak oda (max) |
|---|---|---|---|---|---|
| v2.0 | 792,576 | +102.8 | +121.6 | 232/1024 | 6/6 |
| v2.1 | 700,416 | +144.2 | +144.2 | 268/1024 | 6/6 |
| v2.2 | 443,712 | +91.6 | +94.2 | 202/1024 | 6/6 |

## Versiyon / Mudahale Gunlugu

| Zaman | Versiyon | Tip | Aciklama |
|---|---|---|---|
| 2026-05-31 04:30 | v2.0 | redesign | Sifirdan temiz baslangic: 2D action [v,w], sabit R0 spawn, 40-d obs, temiz odul (return~=voxel). Tek env (n_envs=1), coklu gazebo kaldirildi. VecNormalize(norm_reward). Hedef 2M step. |
| 2026-05-31 11:18 | v2.1 | version_bump | v2.0 100-ep eval: carpisma %70, ep_len 462/1000, voxels_max 201, birlesik kapsama %36. Teshis: darbogaz CARPISMA (kapi/hareketli-engel). Cozum: YON-DUYARLI lidar cezasi (ileri-ark; kapida yanlar yakin ama on acik -> ceza yok), siyirma cezasi (<0.5m), ileri-acik bonus 0.05->0.10, max_episode_steps 1000->1500. FRESH 500k. |
| 2026-05-31 12:08 | v2.1 | extend | v2.1 120k da reward +92.6 (peak, hala yukseliyor), ep_len orani 0.25->0.33 (carpisma dususte). Iyilesme pozitif -> hedef 500k->700k uzatildi (Berker onayi). 700k da: carpisma darbogazi surerse veya oda-ici tarama gibi somut gelisme varsa v2.2; yoksa devam. |
| 2026-05-31 16:40 | v2.1 | eval_result | v2.1 100-ep eval (700k): carpisma %79 (v2.0 %70 -> KOTULESTI), voxels_mean 69 (v2.0 80), birlesik kapsama 332/1024 %32 (v2.0 %36), voxels_max 195, rooms_mean 3.44. HIPOTEZ CURUDU: directional-only ceza her-yon caution kaldirdi -> yanlardan/hareketli-engelden daha cok carpisma. v2.0 reward daha iyi. (NOT: eval_v2_1 figur basligi kozmetik bug ile v2.0 yaziyor, veri v2.1.) |
| 2026-05-31 16:40 | v2.2 | version_bump | v2.1 dersine gore TEK-tema: v2.0 her-yon cezasi (scan_min<1.0m, -0.5) GERI getirildi + v2.1 ileri-ark cezasi (fwd<1.5m,-0.6) KORUNDU = birlesik caution. FRESH 500k, episode 1500, runs/ppo_v2_2. Hedef: v2.0 %70 carpisma / %36 kapsamasini gecmek. |
| 2026-05-31 18:00 | v2.2 | extend | v2.2 hedef 500k->700k (Berker onayi). 500k bitince operator final.zip ten resume. 700k eval sonrasi mantikliysa v2.3 (gozleme lidar gecmisi = hareketli engel hizi). |
| 2026-05-31 19:35 | PLAN | directive | Berker direktifi: 700k bitince v2.2 eval + v2.0/v2.1/v2.2 KIYAS kaydet -> en iyi reward+hiperparametre tabanini sec + mantikli iyilestirmeleri (env reward/policy + ppo.yaml) uygula -> en iyi surumle UZUN episode (2000-3000) + 1.5M step egit. HEDEF: maksimum voxel. Bu 1.5M karari supervisor(ben) tarafindan eval verisiyle verilecek. |

## Figurler

![reward](figures/report_reward.png)

![voxels](figures/report_voxels.png)

![rooms](figures/report_rooms.png)
