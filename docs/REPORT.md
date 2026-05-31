# PPO Drone Kesif — Egitim Raporu

Otomatik uretildi (`scripts/report.py`). Operator agent gunceller.

## Versiyon Ozeti

| Versiyon | Son step | Son reward | Peak reward | Peak voxel (max) | Peak oda (max) |
|---|---|---|---|---|---|
| v2.0 | 792,576 | +102.8 | +121.6 | 232/1024 | 6/6 |
| v2.1 | 507,904 | +131.6 | +133.4 | 268/1024 | 6/6 |

## Versiyon / Mudahale Gunlugu

| Zaman | Versiyon | Tip | Aciklama |
|---|---|---|---|
| 2026-05-31 04:30 | v2.0 | redesign | Sifirdan temiz baslangic: 2D action [v,w], sabit R0 spawn, 40-d obs, temiz odul (return~=voxel). Tek env (n_envs=1), coklu gazebo kaldirildi. VecNormalize(norm_reward). Hedef 2M step. |
| 2026-05-31 11:18 | v2.1 | version_bump | v2.0 100-ep eval: carpisma %70, ep_len 462/1000, voxels_max 201, birlesik kapsama %36. Teshis: darbogaz CARPISMA (kapi/hareketli-engel). Cozum: YON-DUYARLI lidar cezasi (ileri-ark; kapida yanlar yakin ama on acik -> ceza yok), siyirma cezasi (<0.5m), ileri-acik bonus 0.05->0.10, max_episode_steps 1000->1500. FRESH 500k. |
| 2026-05-31 12:08 | v2.1 | extend | v2.1 120k da reward +92.6 (peak, hala yukseliyor), ep_len orani 0.25->0.33 (carpisma dususte). Iyilesme pozitif -> hedef 500k->700k uzatildi (Berker onayi). 700k da: carpisma darbogazi surerse veya oda-ici tarama gibi somut gelisme varsa v2.2; yoksa devam. |

## Figurler

![reward](figures/report_reward.png)

![voxels](figures/report_voxels.png)

![rooms](figures/report_rooms.png)
