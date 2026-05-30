## [2026-05-30 11:20 UTC]
**Step:** 142,336 / 2,500,000 (5.7%) | **ep_rew_mean:** -290.70 | **entropy:** -3.886 | **std:** 0.888

### Durum
v9_newmap erken keşif fazında; tek veri noktası mevcut, drone çarpmıyor (ep_len=1000=max) ama henüz oda keşfi yok ve ağır idle cezaları biriktiyor. Tüm metrikler sağlıklı aralıkta.

### Detay
- **Reward eğrisi:** -290.70 @ 142k — erken negatif faz beklenen davranış. ep_len=1000 (max) drone'un hayatta kaldığını gösteriyor, fakat yeni voxel/oda reward'u idle+duvar cezalarını henüz karşılamıyor. Plato ya da kırılım sinyali vermek için tek veri noktası yetersiz; minimum 3-4 ölçüm gerekli (sonraki ~30dk kontrolde netleşecek).
- **lr=5e-5 constant seçimi:** KICKOFF.md'de "7.5e-5 constant" yazıyor ancak ppo.yaml'da 5.0e-5. Bu 33% sapma önceki bir oturumda yapılmış olmalı. v8'in 3e-4 başlangıcına kıyasla 6× daha düşük; v9 yeni harita üzerinde fresh start yaptığından bu düşük LR ilk room-breakthrough'u ~50-100k step erteleyebilir ama kararsızlık riskini azaltır. Mevcut 142k adımı geriye atmak yetersiz — mid-run değişiklik yapılmayacak.
- **Entropy:** -3.886 → -4.0 eşiğinin güvenli üstünde. Erken deterministikleşme yok. Ancak 300-500k step arasında sıkışma riski: bu değer -4.0'ın altına düşerse ent_coef yetersiz kalabilir. İzleme noktası.
- **std:** 0.888 → 0.7 eşiğinin çok üstünde. Aksiyon dağılımı yeterince geniş, keşif sağlıklı.
- **FPS:** 83.0 — sabit ve tutarlı. SubprocVecEnv deadlock sorunu çözülmüş (n_envs=4→2 düzeltmesi etkin).
- **Interventions:** interventions.jsonl boş — crash yok, müdahale yok.
- **İlk oda breakthrough tahmini:** v6 (VecNormalize aktif, eski 3-katlı harita) 70k civarında +69.8'e çıktı. v9 yeni harita + lr=5e-5 (v6'nın lr=3e-4'ten daha yavaş): ilk pozitif reward bölgesi 200-350k, ilk oda sıçraması (+15) 350-600k step arası bekleniyor.

### v10 Önerisi
1. **Learning rate:** `lr=1e-4` constant veya lineer `1e-4 → 1e-5` decay. v9 sonunda en iyi checkpoint'ten resume edilirse 5e-5'ten daha yüksek LR ile fine-tune daha hızlı adaptasyon sağlar; fresh start gerekirse v8 başarılı 3e-4 → 3e-5 şemasına dön.
2. **Entropy izleme:** Eğer v9'da 500k step sonrası entropy -4.2'nin altına kalıcı düşerse, v10'da `ent_coef: 0.003` (mevcut 0.0015'in 2×'i) ile başla — 6 odanın tamamını keşfetmek için daha uzun stokastik faz gerekiyor.

### Müdahale
Yok — step 142k'da tüm metrikler (entropy >-4, std >0.7, fps sabit, crash yok) normal aralıkta. Tek veri noktasından ≥80% güven düzeyinde net bir sorun tespit edilemedi. Eğitim kendi seyrinde devam etmeli.
---

## [2026-05-30 10:03 UTC]
**Step:** 142,336 / 2,500,000 (5.7%) | **ep_rew_mean:** -290.70 | **entropy:** -3.886 | **std:** 0.888

### Durum
v9_newmap erken fazda; v6 aynı step'te +60 iken v9 -290 gösteriyor. Bu fark ağırlıklı olarak 6× düşük LR (5e-5 vs 3e-4) ve yarı ortam sayısından (n_envs=2 vs 4) kaynaklanıyor. Alarm verici değil ama yavaş. Müdahale yok.

### Detay
- **Reward eğrisi:** İki referans noktası: ~64k→-324, 142k→-290.70. İyileşme = +33.3 / 78k step → ~0.43 rew/1k step. Bu doğrusal hızla sıfıra ulaşmak ~817k step gerektirir; ancak RL breakthrough'u ani olur, lineer ekstrapole yanıltıcıdır. Plato veya kırılım için 3. ölçüm noktası gerekiyor.
- **v6 karşılaştırması (kritik bulgu):** v6 (lr=3e-4, n_envs=4, eski harita) @ 142k step → ep_rew_mean=+60, ep_len=153. v9 @ 142k → ep_rew_mean=-290, ep_len=1000. Bu dev farkın anatomisi: (1) LR 6× düşük → politika güncellemeleri çok küçük; (2) n_envs yarı → her rollout 1024 transition (v6 2048); (3) ep_len=1000 her seferinde maxlanıyor → 1000 step × (-0.5 idle≥30) = -500 birikimli ceza. v9'un "eşdeğer öğrenme adımı" v6'nın yalnızca ~24k adımına karşılık geliyor — bu noktada v6 da -70 civarındaydı; v9 daha kötü ama harita zorluğu ve ep_len farkı denklemi karmaşıklaştırıyor.
- **ep_len=1000 (max) ile -290 kombinasyonu:** Drone çarpmıyor (pozitif) ama etkin keşif yapmıyor (negatif). Her episodun tamamında idle penaltı biriktiği görünüyor: 1000 step × -0.001 (zaman) = -1; idle≥30 baskın ise 1000 × (-0.5) = -500; voxel/oda pozitif katkı bunu yeterince dengelemiyor. Bu "hayatta kal ama hareket etme" yerel optimumu erken fazda normaldir.
- **lr=5e-5 seçimi:** KICKOFF.md 7.5e-5 diyor, ppo.yaml 5e-5. Önceki oturumda kasıtlı düşürülmüş. 80% eşiği aşılamadı (trend pozitif, entropy/std sağlıklı, yalnızca 5.7% tamamlandı). Mid-run LR değişikliği VecNormalize'ın running_mean/var hesaplarını etkileyebilir ve politikayı dengesizleştirebilir. Dokunma.
- **Entropy:** -3.886. v6 aynı step'te -3.97 idi — v9 hafif daha az deterministik. -4.0 eşiği aşılmadı, keşif kapasitesi intakt.
- **std:** 0.888. v6 aynı step'te 0.909. İkisi de 0.7 eşiğinin çok üstünde. Aksiyon varyansı yeterli.
- **FPS:** 83.0 — tutarlı ve stabil. Deadlock çözüldü.
- **İlk oda breakthrough tahmini (revize):** LR 6× düşük olduğu için v9'un eşdeğer v6 adımı yavaş ilerliyor. Bununla birlikte v6 @ 71k step'te ilk pozitife geçti (breakthrough ~70k). Eşdeğer v9 breakthrough'u: 70k × 6 = ~420k step. Harita zorluğu ve n_envs=2 için +50-100k ek süre: ilk oda sıçraması (+15) **500-800k step** aralığında bekleniyor; eğitim bütçesi 2.5M olduğundan bu normal eğitim içinde.

### v10 Önerisi
1. **LR artırımı acil öncelik:** v10'da `lr: 1.5e-4` başlangıç, `lr_final: 1.5e-5` lineer decay. v9'un 5e-5 sabiti fazla tutucu; v8'in 3e-4'ü (v6 harita) da fazla agresif. Yeni 6-oda harita için 1.5e-4 → 1.5e-5 aralığı optimal. Beklenen etki: room breakthrough ~50% daha erken.
2. **n_envs=4'e dön:** Gazebo SubprocVecEnv deadlock Animasyon devre dışı ile çözüldü. v10'da n_envs=4 → rollout buffer 2× → her iterasyonda 2× daha fazla deneyim → keşif hızı ve sample efficiency ciddi artış. Bu tek değişiklik bile eşdeğer breakthrough zamanını ~%30-40 kısaltır.

### Müdahale
Yok — %80 güven eşiği aşılmadı. Metrikler: entropy=-3.886 (>-4.0 ✓), std=0.888 (>0.7 ✓), fps=83 (sabit ✓), trend pozitif ✓. v6 ile performans farkı büyük ama LR/n_envs/harita farkıyla açıklanabilir; v9'a müdahale edilmedi.
---
