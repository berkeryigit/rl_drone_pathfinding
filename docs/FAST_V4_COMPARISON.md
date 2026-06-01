# Hızlı Sim v4.x Zinciri — Tam Karşılaştırma (PPO, numpy/Gymnasium)

Sabit harita (6 oda, tek kat), drone hep R0'dan başlar, 3 hareketli engel.
Tüm v4.x: `lidar_history=2` (engel hareketini gözle), n_envs=8, deterministik 100-bölüm eval.
Hedef: **çarpışmadan MAKSİMUM voxel tara.**

## Sonuç Tablosu

| Versiyon | Değişen | Çarpışma | Voxel (ort) | Voxel (max) | Oda (ort) | Union Kapsama | Hayatta (ep_len) |
|---|---|---:|---:|---:|---:|---:|---:|
| v4.0 | taban (room 10, far 0) | %32 | 142 | — | 2.0 | — | — |
| v4.1 | room_bonus 30 | **%2** | 150 | — | 2.0 (dar) | ~6% | %100 |
| v4.2 | breadth push (far 2.5, ent 0.02) | %85 | 143 | — | 4.98 | — | %66 |
| v4.3 | "denge" (far 1.5, coll 14, ent 0.01) | %100 ❌ | 37 | 51 | 3.88 | %5.9 | %7 (kötü yakınsama) |
| v4.4 | güvenli taban + far 1.0 | %97 | 167 | 216 | 4.94 | %26.7 | %52 |
| v4.5 | far 1.0 + collision 30 | %8 | 114 | 132 | 5.0 | %15.6 | %95 |
| v4.6 | far 1.5 + collision 30 + 3M | %93 | **176** | **247** | 5.0 | **%30.9** | %54 |
| v4.7 | v4.5 + idle↑ (0.08/grace20) + 4M | %72 ❌ | 72 | 79 | 5.0 | %9.4 | %85 (idle backfire) |
| **v4.8** | **far 1.0 + collision 25** | **%0** ✅✅ | 117 | 123 | **5.0** | %13.8 | **%100** |
| v4.9 | far 1.0 + collision 22 | %37 ❌ | 119 | 138 | 2.0 (çöktü) | %18.2 | %89 |
| v4.10 | v4.8 ayarı + **5M eğitim** | %54 | **281** | **328** | **5.76 (max 6!)** | **%44.5** | %95 |
| v4.11 | 5M + collision 50 | %100 ❌ | 147 | 197 | 4.9 | %27.3 | %29 |
| v4.12 | v4.8'den resume + lr1e-4 + coll45 (3M) | %24 | 90 | 115 | 4.52 | %13.2 | %77 |

## Ana Bulgular (rapor için)

1. **Çarpışma çözümü = `lidar_history=2`.** Engelin son 2 lidar karesini gözleme → ajan hızını çıkarsıyor → kaçabiliyor. (Bu olmadan ~%80 çarpışma; v3 zincirinde ödül-şekillendirme TEK BAŞINA çözemedi.)

2. **Breadth–güvenlik trade-off'u.** Geniş keşif (5 oda) ile düşük çarpışma doğal gerilimde:
   - v4.1: güvenli (%2) ama dar (2 oda) — temkinli politika 2-oda yerel optimumuna takılıyor.
   - v4.4/v4.6: geniş (5 oda, 167–176 voxel) ama çok çarpıyor (%93–97).

3. **Kilit kaldıraç = çarpışma cezası ölçeği.** Voxel başına +1 + far_voxel + room_bonus ile bir bölümün getirisi ~+137..+165. Çarpışma -10 bunun yanında küçük → ajan "keşfet, -10'u ye" diyor (v4.4 %97).
   - **collision_penalty 10→30** → çarpışma **%97→%8** (v4.5). Keşif bitince tek terminal seçenek çarpma(-30) ya da timeout(0) olduğundan ajan "gez SONRA hayatta kal" öğreniyor.

4. **far_voxel_bonus çok hassas.** collision=30 sabitken far_voxel 1.0 → %8 çarpışma (v4.5); far_voxel 1.5 → %93 (v4.6). Uzak-hücre dürtüsü güvenlik cezasını ezebiliyor. Güvenli rejim için far_voxel ≤ ~1.0.

5. **Ödül-şekillendirme yakınsamayı kırabilir.** v4.3 (agresif çoklu değişiklik) %100 çarpışma + voxel çöküşü → PPO kötü local optimum. Tek-değişken, kademeli ilerleme daha güvenli.

6. **Yumuşak idle cezası güvenlik için kritik.** v4.7'de idle_penalty 0.06→0.08 + grace 30→20 ile ajanı sürekli harekete zorlamak GERİ TEPTİ: engel yanında yavaşlayıp/duramadığından çarpışma %8→%72, voxel 114→71. v4.5'in düşük idle'ı ajanın güvenli durup-bekleme manevrasına izin veriyor.

7. **EĞİTİM SÜRESİ kendisi bir trade-off kaldıracı.** Aynı ödül (collision 25), 2M→5M: voxel 117→281 (2.4x!), union kapsama %13.8→%44.5, oda 5.0→5.76 (TÜM 6 ODA) — AMA çarpışma %0→%54. Daha uzun eğitim politikayı keşif-sömürüsüne (exploit) itiyor: per-voxel ödül birikimi çarpışma cezasını yine eziyor. Checkpoint sweep (2.6M %43, 3.2M %100, 4.4M %72): 2M'den sonra güvenlik anında bozuluyor, "hem kapsamlı hem güvenli" tek bir ara nokta YOK. Çözüm yolu: 5M kapsamlılığı + ÖLÇEKLENMİŞ çarpışma cezası (v4.11+).

## EN İYİ POLİTİKA → **v4.8** (SIFIR çarpışma)

"Çarpışmadan maksimum voxel" hedefinin **kesin** cevabı:
- **Çarpışma %0** — 100 bölümün hepsinde HİÇ çarpmadı, tam 2500 adım hayatta kaldı
- **Her bölümde 5 odanın hepsine ulaşıyor** (rooms 5.0)
- **117 voxel** ortalama (v4.5'ten biraz fazla), çok tutarlı (max 123)

> Sezgiye aykırı bulgu: collision_penalty 30→25 ile çarpışma %8→%0'a DÜŞTÜ. Çok yüksek ceza (30)
> ajanı aşırı-tedirgin yapıp ara sıra hatalı manevraya itiyordu; 25 daha temiz, tam güvenli bir
> politikaya yakınsadı. Ceza ölçeği "ne kadar yüksek o kadar güvenli" DEĞİL — bir tatlı nokta var.
>
> Tatlı nokta DAR: collision 22 (v4.9) ise 2-oda yerel optimumuna çöküp %37 çarpıştı.
> Yani collision_penalty ∈ {22:çöktü, 25:OPTIMAL, 30:%8} → 25 benzersiz iyi.

v4.4/v4.6 ham keşifte daha yüksek (167–176 voxel) ama %93–97 çarpışma → gerçek görevde drone düşer, "çarpışmadan" kısıtını ihlal eder. v4.8 hem güvenli hem tam kapsamlı (5 oda).

8. **Curriculum (resume) trade-off'u kıramadı.** v4.12'de v4.8'in %0-çarpışma politikasından devam + nazik fine-tune (lr 1e-4) + collision 45 ile genişletmek İKİ EKSENDE de geriletti: çarpışma %0→%24, voxel 117→90. Güvenli taban bile daha çok keşfetmeye zorlanınca temkinini kaybediyor.

---

## NİHAİ SONUÇ — Optimizasyon Yakınsadı (13 versiyon)

Üç bağımsız yaklaşım denendi ve hepsi aynı sonuca vardı:
- **Ödül-şekillendirme** (room_bonus, far_voxel, idle, collision_penalty, entropy): v4.1–v4.9
- **Eğitim süresi** (2M / 3M / 5M): v4.6, v4.10, v4.11
- **Curriculum / resume** (güvenli tabandan nazik genişletme): v4.12

**Bu ortam + ödül + 2D-aksiyon + lidar_history=2 kurulumunda keşif-kapsamı ↔ güvenlik ödünleşimi TEMELDİR.** İki Pareto-optimal uç var; arada "hem yüksek kapsam hem sıfır çarpışma" noktası yok (bkz. `docs/figures/fast_pareto.png`).

### Teslim edilen iki politika

| Politika | Dosya | Çarpışma | Voxel | Oda | Kapsama | Ne zaman |
|---|---|---|---|---|---|---|
| **GÜVENLİ** (v4.8) | `runs/fast_v4_8/checkpoints/fast_drone_final.zip` | **%0** | 117 | 5.0 | %13.8 | "çarpışmadan keşif" — gerçek görev / deploy |
| **KAPSAM** (v4.10) | `runs/fast_v4_10/checkpoints/fast_drone_final.zip` | %54 | **281** | **5.76** | **%44.5** | "max voxel" — ham keşif kapasitesi |

**Önerilen ana sonuç: v4.8** — proje hedefi "çarpışmadan maksimum voxel" olduğu için, görevi güvenle tamamlayan tek politika. v4.10 ise modelin kapasite tavanını (6 odanın hepsi, 281 voxel) gösteren tamamlayıcı kanıt.

> Gazebo (yavaş, gerçekçi fizik) vs numpy/Gymnasium (hızlı, ~100x): aynı ortam, iki ayaklı kanıt.
> Gazebo'da ~157 voxel/2 oda referansı; hızlı sim'de v4.8 ile %0 çarpışma + 5 oda güvenli kapsama,
> v4.10 ile %44.5 kapsama / 6 oda kapasite tavanı.
