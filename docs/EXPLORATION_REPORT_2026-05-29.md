# Keşif Durumu ve Performans Raporu — 29 Mayıs 2026

## Proje Özeti
**Görev:** 3 katlı, kat başına 4 odalı (toplam 12 oda) bir binada lidar + odometri  
tabanlı drone keşfi. PPO (continuous action space) ile eğitim.

**Ortam:** Gazebo Harmonic + ROS 2 Jazzy | **Algoritma:** PPO (SB3), MlpPolicy [128,128]  
**Action:** [vx, vz, wz] ∈ [−1,1]³ | **Obs:** 46-d (lidar + yaw + hız + keşif istatistikleri)

---

## Eğitim Versiyonları (v1–v8)

| Sürüm | Step | Peak ep_rew | Değişiklik | Sorun |
|-------|------|-------------|------------|-------|
| v1 | 140k | −12 | İlk PPO kurulumu | Drone odadan çıkamıyor |
| v2 | 290k | −12 | Ödül ×3, entropy boost | Spawn odaya takılı |
| v3 | 1.4M | +95 | Üst kat spawn'ları, kat bonusu ×2 | Peak 440k → 1.4M'de +45'e düştü |
| v4 | 310k | +85 | ent_coef 0.02→0.001, idle decay | Osilasyon devam |
| v5 | 350k | +45 | clip 0.1, epochs 5, batch 256 | Reward scaling çözülmedi |
| v6 | 235k | **+110** | **VecNormalize (en iyi peak)** | Hâlâ peak-then-regress |
| v7 | 223k | +90 | Linear lr decay 3e-4→3e-5 | Regress önlenemedi |
| **v8** | **devam** | **+60** (100k'da) | **Frontier shaping + n_envs=4** | Eğitim sürüyor |

---

## v8 Yenilikleri (Bu Oturum)

### 1. Frontier Ödül Şekillendirmesi
```
Eski (v7): voxel +3, oda +50, kat +200, çarpışma −10

Yeni (v8 ekleri):
  Frontier bonus:    +0..+0.4/adım  → lidar'ın görev burnunda açık mesafe
                                       × ileri hareket = açık alana yönelim
  Turn-toward-far:   +0..+0.1/adım  → en uzak lidar sektörüne dönmeyi ödüllendir
                                       (bin 16 = forward, sağ=8, sol=24)
  Vertical pull:     +0..+0.15/adım → alt katta, scan_up>1.5m iken yukarı çıkmayı ödüllendir
```

**Obs genişletmesi:** 45-d → 46-d (yeni: `max_lidar_bin / 32` — en açık yönün bilgisi)

### 2. Paralel Eğitim (SubprocVecEnv)

| Konfigürasyon | FPS | sim-sec/saat |
|---|---|---|
| v7: n_envs=1, STEP_DT=0.02 | 37 | 20,239 |
| v8 test: n_envs=1, STEP_DT=0.005 | 196 | 13,459 (−33%, yanıltıcı) |
| **v8 final: n_envs=4, STEP_DT=0.02** | **122** | **66,768 (3.3x)** |

**Sim RTF = 7.6x** (Gazebo izin verdiği kadar hızlı çalışıyor)

**Neden STEP_DT=0.005 başarısız oldu:**  
Her adımda 4x daha az sim-zaman → drone 4x az mesafe alıyor → voxel ödülü  
4x seyrekleşiyor → idle penalty çok erken tetikleniyor → negatif reward sarmalı.  
Net kazanç sadece +30%, maliyeti yüksek.

**n_steps=512 (n_envs=4 ile):**  
Total rollout = 512×4 = 2048 (n_envs=1, n_steps=2048 ile eşdeğer).  
Gradient-steps/update = 2048/256 × 5 = 40 (sabit). Overfit önlendi.

### 3. VecNormalize Resume
`vec_normalize.pkl` checkpoint'ten yükleniyor; n_envs=1→4 geçişinde  
running stats uyumsuzluğu test edildi — fresh start daha güvenilir bulundu.

---

## Oda Keşif Sistemi

### Bina Geometrisi
```
3 kat × 4 oda = 12 oda (global ID 0–11)

Her katta "+" iç duvar, 2m kapı aralığı:
  Oda 0 (NE): x≥0, y≥0  |  Oda 1 (NW): x<0, y≥0
  Oda 2 (SW): x<0, y<0  |  Oda 3 (SE): x≥0, y<0

Kat geçişleri:
  0→1: NE köşe delik (x: 3.5–6.5, y: 3.5–6.5)
  1→2: SW köşe delik (x: −6.5–−3.5, y: −6.5–−3.5)
```

### Voxel Grid
- Çözünürlük: 0.5m × 0.5m × kat = **3072 hücre toplamda**
- Keşif skoru = `explored_voxels / 3072`

### v7 Eval Sonuçları (223k step checkpoint, referans)
- **Return:** +250.02 (raw, 1 episode)
- **Keşfedilen oda:** 2 oda (1 kat)

---

## Güncel Eğitim Durumu (29 Mayıs 2026, ~14:00)

| Parametre | Değer |
|-----------|-------|
| Sürüm | v8 (frontier shaping) |
| Durum | **Fresh start, 2k step** |
| FPS | **122** (eski 37'den 3.3x) |
| GPU | RTX 3050 Ti — %42 (n_envs=4 ile) |
| Hedef | 2,000,000 step |
| Tahmini süre | ~4.5 saat |
| Log | `/tmp/train_v8_fresh_n4.log` |
| Checkpoint | `runs/ppo_v8_frontier/checkpoints/` |

---

## Önerilen Sonraki Adımlar

### Kısa vadeli (eğitim devam ederken)
1. **50k kontrolü**: ep_rew_mean pozitife geçti mi?
2. **150k kontrolü**: v6 peak +110'a yaklaşıyor mu?
3. **Frontier etkinliği**: turn-toward-far ve vertical pull ödülleri saptanıyor mu?

### Orta vadeli — "Soruna uygun çözüm" stratejisi
Oda yapısı değişiklik seçenekleri (kurriculum öğrenme):

| Aşama | Değişiklik | Beklenti |
|-------|-----------|---------|
| Aşama 0 | 1 kat, 4 oda, **4m kapı** (şu an 2m) | Policy hızlı öğrenir, kapı ödülü sık alınır |
| Aşama 1 | 1 kat, 4 oda, 2m kapı (mevcut) | Kapı geçişi zor ama öğrenilmiş |
| Aşama 2 | 3 kat, 4 oda/kat, 2m kapı (tam problem) | Transfer ederek başla |

Bu yaklaşım **curriculum learning** — kolaydan zora geçiş — PPO için kanıtlanmış  
en etkili strateji.

### Uzun vadeli — Otonom ajan
Eğitim sürecini izleyen, müdahale kararı veren bir ajan kurulabilir.  
Tetikleyiciler: plateau (N iterasyon ep_rew değişmedi), collapse (−%30 drop),  
peak kaçırma (son 20 iter içinde peak'ten %20 geri düşme).

---

*Rapor: 2026-05-29 | Eğitim sürüyor: `/tmp/train_v8_fresh_n4.log`*
