# PPO ile GPS'siz Drone Keşfi — Dönem Projesi Raporu

**Öğrenci:** Berker Yiğit (220202046) · **Algoritma:** PPO (continuous → 2D) · **Branch:** `algo/ppo`
**Ders:** KOÜ Pekiştirmeli Öğrenme · **Tarih:** Haziran 2026

---

## 1. Problem Tanımı

Bir drone'un, **GPS olmadan**, yalnızca **lidar + odometri** ile kapalı bir ortamı keşfetmesi.
Hedef: **çarpışmadan, mümkün olduğunca çok hücreyi (voxel) taramak.** Ortam hareketli engeller içerir.

**Nihai sabit ortam (Faz 2'den itibaren):**
- Tek katlı, **6 odalı** sabit harita (`multi_room.sdf`)
- Drone **her zaman R0'dan (-5,-5)** başlar (sabit spawn)
- **3 hareketli engel** (dairesel, sabit hızlarla gider-gelir)
- **2D aksiyon** `[v, ω]` (doğrusal hız + açısal hız; irtifa sabit hover)
- **Ödül felsefesi:** `dönüş ≈ taranan voxel sayısı` (+1/yeni voxel, +bonus/yeni oda, −ceza/çarpışma)
- Keşif ızgarası: **1024 hücre** (kapsama = taranan benzersiz hücre / 1024)

---

## 2. Yolculuğun Üç Fazı

| Faz | Ortam | Sim | Ana kazanım |
|---|---|---|---|
| **1. Erken keşif** | 3 kat / 12 oda, 3D aksiyon | Gazebo | Kurulum + "peak-then-regress" problemi teşhisi |
| **2. Temiz tasarım** | 1 kat / 6 oda, 2D aksiyon | Gazebo | Sade ödül en iyi; çarpışma = ana darboğaz |
| **3. Hızlı sim** | aynı 6 oda | numpy/Gymnasium | Çarpışma ÇÖZÜLDÜ + kapsama↔güvenlik trade-off'u haritalandı |

> **Neden sim değişti?** Gazebo/ROS başta tercih edilmişti ama hoca şartı değildi. Aynı ortamın
> **numpy/Gymnasium 2D ray-cast klonu** ~100× hızlı (≈4000 fps vs Gazebo ≈40 fps). Böylece 14 deney
> bir gecede tamamlandı. **Gazebo sonuçları silinmedi** — iki-ayaklı kanıt olarak rapora katkı sağlar.

---

## 3. FAZ 1 — Erken Gazebo Keşfi (3 kat, 12 oda)

İlk kurulum: PPO continuous, aksiyon `[vx, vz, wz]`, 46-d gözlem, MlpPolicy [128,128].

| Sürüm | Step | Peak ödül | Değişiklik | Sorun |
|---|---|---|---|---|
| v1 | 140k | −12 | İlk PPO kurulumu | Drone odadan çıkamıyor |
| v2 | 290k | −12 | Ödül ×3, entropy artışı | Spawn odasına takılı |
| v3 | 1.4M | +95 | Kat bonusu, üst-kat spawn | Peak 440k → 1.4M'de +45'e geriledi |
| v4 | 310k | +85 | ent_coef ↓, idle decay | Osilasyon |
| v5 | 350k | +45 | clip 0.1, batch 256 | Ödül ölçeği çözülmedi |
| **v6** | 235k | **+110** | **VecNormalize** | En iyi peak ama hâlâ regress |
| v7 | 223k | +90 | Linear lr decay | Regress önlenemedi |
| v8 | — | +60 | Frontier shaping + n_envs=4 | — |

**Faz 1 dersi:** Karmaşık 12-oda/3-kat ortam + 3D aksiyon ile politika kararsız ("peak-then-regress":
ödül tepe yapıp geriliyor). Bu, problemi **basitleştirme** kararına yol açtı.

---

## 4. FAZ 2 — Temiz Yeniden Tasarım (Gazebo, 1 kat / 6 oda)

Sıfırdan ("clean slate"): tek env (n_envs=1), **2D aksiyon `[v,ω]`**, sabit R0 spawn, 40-d gözlem,
sade ödül (`return ≈ voxel`), VecNormalize. Üç ödül varyantı 100-bölüm deterministik eval ile kıyaslandı:

| Sürüm | Step | Çarpışma | Voxel (ort) | Voxel (max) | Kapsama | Oda | Not |
|---|---|---:|---:|---:|---:|---:|---|
| **v2.0** | 793k | **%70** | **80** | 201 | **%36** | 3.6 | Sade ceza (her-yön <1m) — **EN İYİ TABAN** |
| v2.1 | 700k | %79 | 69 | 195 | %32 | 3.44 | Yön-duyarlı (yalnız ileri-ark) ceza → **kötüleşti** |
| v2.2 | 701k | %88 | 66 | 168 | %29 | 3.77 | Birleşik caution → **en kötü** |
| v3.0 | 610k | — | — | 284 | — | 6/6 | v2.0 ödülü + uzun episode (2500) + [256,256] |

**Faz 2 dersi (KRİTİK):** Ödül-şekillendirme ile çarpışmayı azaltma denemeleri (v2.1 yön-duyarlı,
v2.2 birleşik) **çarpışmayı DÜŞÜRMEDİ, kötüleştirdi.** En sade ödül (v2.0) en iyiydi. Asıl darboğaz
**hareketli engellere çarpma** — ve bunun kaynağı: **gözlem engel hızını içermiyordu.**

---

## 5. FAZ 3 — Hızlı Sim: Çarpışmanın Çözümü + Trade-off Çalışması

### 5.1 Çarpışmanın çözümü — `lidar_history`

Hızlı sim'e geçişte ilk denemeler çarpışmayı çözmedi (daha çok eğitim bile: fast_5m %80):

| Sürüm | Eğitim | Çarpışma | Voxel | Oda | Not |
|---|---|---:|---:|---:|---|
| fast_v1 | 1.5M | %47 | 120 | 4.74 | Gazebo v2.0'dan (%70) zaten iyi |
| fast_5m | 5M | %80 | 132 | 5.0 | Daha çok eğitim ÇÖZMEDİ |
| **fast_v2** | 5M | **%1** ✅ | **157** | 2.0 | **`lidar_history=2` → ÇARPIŞMA ÇÖZÜLDÜ** |

> **Anahtar fikir:** Gözleme **son 2 lidar karesini** eklemek (frame-stacking). Ajan iki kareden
> engelin **hızını** çıkarsayıp önündeki hareketli engelden kaçabiliyor. Çarpışma **%80 → %1**.
> Ödül-şekillendirme aylarca çözemediğini, doğru **gözlem tasarımı** çözdü.

Ama yeni sorun: güvenli politika tembelleşip **yalnız 2 odaya** sıkıştı (rooms 2.0). Bu, planlı
**v4.0 → v4.6 ilerleme zincirini** (kapsama genişletme) başlattı — ardından v5.0'a kadar uzadı.

### 5.2 v4.0 → v5.0 — 14 deney, dört kaldıraç

| Sürüm | Ne değişti | Çarpışma | Voxel | Oda | Kapsama | Hayatta | Sonuç |
|---|---|---:|---:|---:|---:|---:|---|
| v4.0 | taban (room 10) | %32 | 142 | 2.0 | — | — | 2-oda yerel optimum |
| v4.1 | room_bonus 30 | %2 | 150 | 2.0 | %6 | %100 | güvenli ama dar |
| v4.2 | breadth push (far+idle+ent) | %85 | 143 | 4.98 | — | %66 | 5 oda açıldı ama çarpışma↑ |
| v4.3 | "denge" (çok değişken) | %100 | 37 | 3.88 | %5.9 | %7 | başarısız (kötü yakınsama) |
| v4.4 | güvenli taban + far 1.0 | %97 | 167 | 4.94 | %26.7 | %52 | en iyi ham keşif ama çarpıyor |
| **v4.5** | **collision 10→30** | %8 | 114 | 5.0 | %15.6 | %95 | hipotez doğrulandı |
| v4.6 | far 1.5 + 3M | %93 | 176 | 5.0 | %30.9 | %54 | far çok hassas, güvenliği ezdi |
| v4.7 | idle↑ + 4M | %72 | 72 | 5.0 | %9.4 | %85 | idle nudge geri tepti |
| **v4.8** ⭐ | **collision 25** | **%0** | 117 | 5.0 | %13.8 | **%100** | **GÜVENLİ ŞAMPİYON** |
| v4.9 | collision 22 | %37 | 119 | 2.0 | %18.2 | %89 | tatlı nokta dar, çöktü |
| **v4.10** ⭐ | **5M eğitim** | %54 | **281** | **5.76** | **%44.5** | %95 | **KAPSAM UCU (6 oda)** |
| v4.11 | 5M + collision 50 | %100 | 147 | 4.9 | %27.3 | %29 | yüksek ceza kurtarmadı |
| v4.12 | curriculum (resume) | %24 | 90 | 4.52 | %13.2 | %77 | nazik fine-tune geriletti |
| v4.13 | 8M eğitim | %26 | 134 | 4.99 | %15.6 | %95 | kapsam 5M'de tepe, sonra geriledi |
| v5.0 | lidar_history=3 | %35 | 106 | 4.81 | %15.4 | %88 | obs zenginliği kırmadı |

---

## 6. Ana Bulgular (rapor için en kayda değer sonuçlar)

1. **Çarpışma çözümü = gözlem tasarımı, ödül değil.** `lidar_history=2` (engel hareketini gözleme)
   çarpışmayı **%80 → %1-2** indirdi. Ödül-şekillendirme (Faz 2'de aylarca) bunu çözemedi.

2. **Sade ödül > karmaşık ceza-şekillendirme.** v2.0 (sade) tüm yön-duyarlı/birleşik ceza
   varyantlarını yendi. Aşırı şekillendirme yakınsamayı bozabiliyor (v4.3 %100 çarpışma).

3. **Kapsama ↔ güvenlik TEMEL bir ödünleşim.** Bu ortam+ödül+2D-aksiyon kurulumunda "çok kapsa"
   ile "hiç çarpma" aynı anda elde edilemiyor. Dört bağımsız kaldıraç — **ödül-şekillendirme,
   eğitim süresi, curriculum/resume, gözlem zenginliği** — hepsi aynı Pareto cephesini doğruladı.

4. **Çarpışma cezası = baş kaldıraç, ama tatlı noktası DAR.** collision_penalty ∈ {22:çöktü,
   **25:OPTIMAL (%0)**, 30:%8, 50@5M:%100}. Sezgiye aykırı: cezayı 30→25 düşürmek çarpışmayı %8→%0
   yaptı (çok yüksek ceza ajanı aşırı-tedirgin edip hatalı manevraya itiyor).

5. **Eğitim süresi de bir trade-off kaldıracı (monoton değil).** Aynı ödül, 2M→5M: voxel 117→281
   (2.4×), kapsama %13.8→%44.5, ama çarpışma %0→%54. 8M'de ise kapsama geriledi → **5M geçici tepe.**

---

## 7. SONUÇ — İki Teslim Politikası

Optimizasyon **kesin yakınsadı** (bkz. `figurler/pareto_cephesi.png`). İki Pareto-optimal uç:

| Politika | Model dosyası | Çarpışma | Voxel | Oda | Kapsama | Kullanım |
|---|---|---:|---:|---:|---:|---|
| **v4.8 — GÜVENLİ** ⭐ | `runs/fast_v4_8/checkpoints/fast_drone_final.zip` | **%0** | 117 | 5.0 | %13.8 | "çarpışmadan keşif" = **ödev hedefinin cevabı** |
| **v4.10 — KAPSAM** | `runs/fast_v4_10/checkpoints/fast_drone_final.zip` | %54 | **281** | **6** | **%44.5** | "max voxel" = kapasite tavanı |

**Önerilen ana sonuç: v4.8.** Proje hedefi "çarpışmadan maksimum voxel" olduğundan, görevi
güvenle tamamlayan (100/100 bölümde hiç çarpmadan, 6 odanın 5'ini her bölümde gezerek) tek
politika v4.8'dir. v4.10 ise modelin kapasite tavanını (6 odanın hepsi, 281 voxel) gösteren
tamamlayıcı kanıttır.

### Gazebo ↔ numpy iki-ayaklı kanıt
- **Gazebo (yavaş, gerçekçi fizik):** en iyi v2.0 → çarpışma %70, kapsama %36, ~2 oda.
- **numpy/Gymnasium (~100× hızlı):** v4.8 → çarpışma **%0**, 5 oda; v4.10 → kapsama **%44.5**, 6 oda.

---

## 8. Gelecek İş (cepheyi sağa kaydırmak için)

Tüm "kısıt-içi" kaldıraçlar tükendi. Trade-off'u kırmak (hem yüksek kapsam hem ~%0 çarpışma) için
sabit kıstasların dışına çıkmak gerekir:
- **RecurrentPPO/LSTM:** sabit kare-yığını yerine bellek → engel dinamiğini uzun ufukta entegre.
- **Engel-hız müfredatı (curriculum):** yavaş engellerle başlayıp hızlandırmak.
- **SAC** (off-policy, örnek-verimli) ile aynı ortamda kıyas.
- Aksiyon/gözlem değişikliği (ivme-kontrolü, engel-merkezli kanallar).

---

## Dosya Rehberi

- `RAPOR.md` — bu dosya (tam anlatı)
- `SONUCLAR.csv` — tüm 25 sürümün makine-okunur metrik tablosu
- `figurler/` — anahtar görseller (Pareto cephesi, eğitim eğrileri, kapsama haritaları, yörüngeler)
- `ham_veri/versiyon_gunlugu.jsonl` — zaman damgalı tüm karar/eval kayıtları
- Model dosyaları repoda: `rl_drone_pathfinding/runs/fast_v4_8/` ve `.../fast_v4_10/`
