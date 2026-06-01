# Parametre Değişimleri ve Davranış Gerekçeleri

Bu dosya, her kayda değer sürümde **hangi parametreyi değiştirdiğimizi**, **gözlenen sonucu** ve
**NEDEN öyle davrandığının gerekçesini** açıklar. Görseller `figurler/` klasöründe (ve orijinalleri
`rl_drone_pathfinding/docs/figures/`).

> **Okuma anahtarı.** Ödül bileşenleri: `+1/yeni voxel`, `room_bonus/yeni oda`, `−collision_penalty/çarpışma`,
> `−idle_penalty` (hareketsizlik), `far_voxel_bonus` (başlangıçtan uzak hücreye ekstra), duvar cezası.
> PPO ayarları: `ent_coef` (keşif gürültüsü), `lr` (öğrenme hızı), eğitim `step` sayısı.
> Gözlem: `lidar_history` (gözleme eklenen geçmiş lidar karesi sayısı).

---

## FAZ 2 — Gazebo, tek kat 6 oda (v2.0 → v3.0)

Burada **ödülün ceza-şekillendirmesi** denendi. Sabitler: 2D aksiyon, R0 spawn, 40-d gözlem,
`lidar_history=1` (geçmiş YOK).

### v2.0 — Sade taban  ·  *figür: `10_gazebo_v2_0_kapsama.png`*
| Parametre | Değer |
|---|---|
| Duvar cezası | **her yön** scan_min<1.0m → −0.5 |
| episode uzunluğu | 1000 adım · net_arch [128,128] · ent 0.005 |

**Sonuç:** çarpışma **%70**, kapsama %36, voxel_ort 80, ~3.6 oda.
**Gerekçe:** Sade ödülle ajan keşfe odaklanıyor ve her yönde duvardan kaçıyor. Ama **hareketli
engelin hızı gözlemde yok** → engel ajana doğru gelirken ajan bunu göremiyor, sadece "şu an yakın
mı" bilgisini görüyor → %70 çarpışma. Yine de en dengeli taban bu.

### v2.1 — Yön-duyarlı ceza  ·  *figür: `figurler/tum_surumler/gazebo_v2_1_kapsama.png`*
| Değişen | v2.0 → v2.1 |
|---|---|
| Duvar cezası | her-yön → **yalnız ileri-ark** (fwd<1.5m → −0.6) |
| + sıyırma cezası <0.5m, ileri-açık bonus 0.05→**0.10**, episode 1000→**1500** |

**Sonuç:** çarpışma **%79 (KÖTÜLEŞTİ)**, kapsama %32, voxel_ort 69.
**Gerekçe (hipotez çürüdü):** "Kapıdan geçerken yanlar yakın ama ön açık, o yüzden yalnız ileriyi
cezalandıralım" denildi. Ama yalnız ileri cezalandırınca **yan/arkaya karşı temkin kalktı** →
yandan gelen hareketli engellere daha çok çarptı. Yön-duyarlılık ters tepti.

### v2.2 — Birleşik caution  ·  *figür: `figurler/tum_surumler/gazebo_v2_2_kapsama.png`*
| Değişen | v2.2 |
|---|---|
| Duvar cezası | v2.0 **her-yön** (−0.5) + v2.1 **ileri-ark** (−0.6) = İKİSİ BİRDEN |

**Sonuç:** çarpışma **%88 (EN KÖTÜ)**, kapsama %29, voxel_ort 66.
**Gerekçe:** İki cezayı üst üste bindirmek ajanı **aşırı-tedirgin** etti → çok ceza alan ajan
donup kalıyor / kötü kaçınma manevrası yapıyor. Aşırı ceza = en kötü sonuç. (Bu ders ileride
hızlı sim'de v4.8'de tekrar doğrulanacak: ceza ölçeğinin bir **tatlı noktası** var.)

### v3.0 — En iyi tabanı güçlendir
| Değişen | v3.0 |
|---|---|
| Ödül | v2.0'a **GERİ DÖN** (sade her-yön) |
| episode 1500→**2500**, net [128]→**[256,256]**, ent 0.005→**0.008**, lr fresh |

**Sonuç:** 610k'da durduruldu, peak ödül +110, voxel_max 284.
**Gerekçe:** v2.1/v2.2 dersi: ceza-şekillendirme yolu ELENDİ. En iyi taban v2.0; onu uzun episode
(daha çok voxel için zaman) + daha büyük ağ ile güçlendir. Ama **çarpışma hâlâ darboğaz** — çünkü
kök neden (engel hızı gözlemde yok) hâlâ duruyor.

> **Planlanan "v2.3" buydu:** "gözleme lidar geçmişi ekle = hareketli engel hızı." Gazebo yavaş
> olduğu için bu fikir hızlı sim'e taşındı ve orada **fast_v2 = lidar_history=2** olarak çarpışmayı
> çözdü (aşağıda). Yani v2.3 fikri asla boşa gitmedi — asıl çözüm o oldu.

---

## FAZ 3 — Hızlı numpy sim (aynı 6 oda)

### Çarpışmanın çözümü: `lidar_history`

| Sürüm | Değişen | Çarpışma | Gerekçe |
|---|---|---:|---|
| fast_v1 | v2.0 ödülü, `lidar_history=1`, 1.5M | %47 | Gazebo'dan iyi ama hâlâ yüksek (engel hızı yok) |
| fast_5m | aynı, eğitim 1.5M→**5M** | %80 | **Daha çok eğitim ÇÖZMEDİ** — deterministik politika engele çarpmayı "ezberliyor"; kök neden gözlem eksikliği |
| **fast_v2** | **`lidar_history=1→2`**, 5M | **%1** | **KÖK ÇÖZÜM:** 2 ardışık lidar karesi = ajan engelin **hızını** çıkarsayıp önünden çekiliyor |

**En önemli ders:** Çarpışmayı **ödül** değil **gözlem tasarımı** çözdü. fast_v2 ile %80→%1.
Yan etki: aşırı-güvenli politika tembelleşip **yalnız 2 odaya** sıkıştı → v4.x zinciri (kapsama).

---

### v4.0 → v5.0: Kapsama ↔ Güvenlik dengesini arama

Tüm v4.x'te sabit: `lidar_history=2`, 6 oda, 2D aksiyon. Aşağıda **yalnız değişen** parametre + gerekçe.

| Sürüm | Değişen parametre(ler) | Sonuç (çarpışma / voxel / oda) | NEDEN böyle davrandı |
|---|---|---|---|
| **v4.0** | taban: room 10, far 0, coll 10, 2M | %32 / 142 / **2 oda** | Az eğitim + zayıf oda dürtüsü → **2-oda yerel optimumu** (yakın 2 odayı tara, yeter) |
| **v4.1** | room_bonus 10→**30** | %2 / 150 / 2 oda | Oda bonusu **güvenliği** çok iyileştirdi ama keşfi açmadı: ajan uzak odayı **hiç denemediği** için orayı keşfetmenin değerini öğrenemiyor (keşif çıkmazı) |
| **v4.2** | far_voxel 0→**2.5**, idle 0.05→**0.15**(grace 40→20), ent 0.008→**0.02** | %85 / 143 / **4.98 oda** | far_voxel "uzağa git" + idle "yerelde oyalanma" + yüksek entropi "dene" → **breadth açıldı (5 oda!)** AMA yüksek gürültü + riskli geçişler → çarpışma patladı |
| **v4.3** | "denge": ent 0.02→0.01, coll 10→14, far 2.5→1.5, idle→0.10 | %100 / 37 / 3.88 | **Çok değişkeni AYNI ANDA** oynamak PPO'yu kötü local optimuma soktu → hemen çarpıp çöktü. Ders: tek-değişken ilerle |
| **v4.4** | güvenli taban (v4.1) + far_voxel **1.0** (ılımlı) | %97 / **167** / 4.94 | **En iyi ham keşif** (5 oda, 167 voxel) AMA çarpışma cezası (−10), bir bölümün keşif kazancına (+137) kıyasla **küçük** → ajan "keşfet, sondaki −10'u ye" diyor |
| **v4.5** ⭐ | **collision_penalty 10→30** | **%8** / 114 / 5.0 | **Hipotez doğrulandı:** keşif bitince ödül kalmaz; tek terminal seçenek çarpma(−30) ya da timeout(0) → ajan "gez SONRA hayatta kal" öğreniyor. Temkinli olduğu için voxel 114'e düştü |
| **v4.6** | far_voxel 1.0→**1.5** + eğitim 3M | %93 / **176** / 5.0 | far_voxel'i artırmak collision-30'un **güvenliğini ezdi** → tekrar agresif keşfet-çarp. **far_voxel çok hassas:** 1.0=güvenli, 1.5=tehlikeli |
| **v4.7** | idle 0.06→**0.08** (grace 30→20) + 4M | %72 / 72 / 5.0 | idle cezasını artırıp ajanı **sürekli harekete zorlamak GERİ TEPTİ:** engel yanında **yavaşlayıp duramadı** → hem çarptı hem az taradı. Yumuşak idle güvenlik için kritikmiş |
| **v4.8** ⭐⭐ | **collision_penalty 30→25** | **%0** / 117 / 5.0 | **SEZGİYE AYKIRI:** cezayı DÜŞÜRMEK çarpışmayı %8→%0 yaptı. Çünkü 30 ajanı **aşırı-tedirgin** edip ara sıra hatalı manevraya itiyordu; 25 daha temiz, **tam güvenli** politikaya yakınsadı (100/100 bölüm, hiç çarpmadan) |
| **v4.9** | collision_penalty 25→**22** | %37 / 119 / **2 oda** | Tatlı nokta **DAR:** 22 yetersiz kaldı → ajan kolaya kaçıp **2-oda yerel optimumuna çöktü** + güvenlik de bozuldu. {22:çöktü, **25:OPTIMAL**, 30:%8} |
| **v4.10** ⭐ | v4.8 ayarı SABİT, eğitim 2M→**5M** | **%54** / **281** / **5.76 (6 oda)** | **Eğitim süresi de bir kaldıraç:** daha uzun eğitimde **per-voxel ödül birikimi** (281 voxel ≈ +281) collision-25'i tekrar **ezdi** → cesur "tüm 6 odayı tara, sondaki −25'i ye". Kapsama %44.5 (rekor) ama çarpışma %54 |
| **v4.11** | 5M + collision_penalty 25→**50** | %100 / 147 | Cezayı 2×'lemek 5M'de güvenliği **kurtarmadı**, kötüleştirdi (kaotik etkileşim — v2.2'deki aşırı-ceza dersi gibi) |
| **v4.12** | v4.8'den **resume** + lr 3e-4→**1e-4** + coll 45, +3M | %24 / 90 | **Curriculum:** güvenli tabandan nazik genişletme bile **iki eksende geriletti** — güvenli politika genişlemeye zorlanınca temkinini kaybediyor |
| **v4.13** | v4.10 ayarı + eğitim 5M→**8M** | %26 / 134 | Kapsama 5M'de **tepe** yapıp 8M'de güvenliğe **regularize** oldu (monoton değil) → "daha uzun eğit, daha çok voxel" YOK; v4.10'un zirvesi geçici |
| **v5.0** | `lidar_history` 2→**3** (engel ivmesi) | %35 / 106 | Daha zengin gözlem ajanı **daha temkinli** ama **daha az kapsamlı** yaptı → v4.8 tarafından domine edilen bir nokta (%0/117 > %35/106). Gözlem darboğaz değilmiş |

---

## "İki yıldız" durumun gerekçesi (Berker'in sorduğu çekirdek)

### Neden v4.8 = HİÇ çarpışma yok (%0)?
- `collision_penalty=25` **tatlı noktada**: ajanı çarpışmadan caydıracak kadar büyük, ama
  aşırı-tedirgin edip dondurmayacak kadar küçük (30 fazla, 22 az).
- Eğitim 2M = **temkinli rejim**: ajan henüz "her voxeli kovalama" agresifliğine girmemiş;
  6 odanın 5'ine güvenle gidip kalanını riske atmadan timeout'a kadar hayatta kalıyor.
- Sonuç: keşif kazancını **güvenle** topladıktan sonra hayatta kalmak optimal → %0 çarpışma,
  %100 hayatta, 117 voxel (tutarlı, düşük varyans).

### Neden v4.10 = hem kapsayıcı (281 voxel) hem çarpışmalı (%54)?
- Tek fark v4.8'e göre **eğitim süresi 2M→5M**. Ceza aynı (25).
- Uzun eğitimde ajan **çok daha fazla voxel toplamayı** öğreniyor (281 ≈ +281 ödül). Bu birikim,
  bölüm sonundaki **tek bir −25 çarpışma cezasını ezer** → "tüm 6 odayı agresif tara, sonda çarpsam
  da kârdayım" stratejisi optimal hale gelir.
- Yani **aynı ceza, farklı eğitim süresi** → tamamen farklı denge. Bu, kapsama↔güvenlik
  ödünleşiminin **eğitim süresiyle de** kontrol edilebildiğinin kanıtı.

**Özet:** v4.8 ve v4.10 aynı ödülün iki ucu — biri "güvenli ama temkinli", diğeri "kapsamlı ama
riskli". İkisi arasında "hem yüksek kapsam hem %0 çarpışma" noktası **yok** (Pareto cephesi,
`figurler/01_pareto_cephesi.png`). 14 deney bunu dört bağımsız kaldıraçla doğruladı.
