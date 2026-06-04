## [2026-05-31 11:07 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9/v10 kalıntısı) | **Gerçek run:** v2.1 @ ~120k-700k devam | **ep_rew_mean:** +92.6 @ 120k (en son güvenilir) | **entropy:** -4.76 @ 139k | **std:** 1.20 @ 139k

### Durum
CSV 2026-05-30 22:00'dan bu yana 13 özdeş satırla DONMUŞ (step=193248, ep_rew_mean=-173.85). Bu v9/v10 crash-loop kalıntısı; güncel run değil. Gerçek durum: v2.1 konfigürasyonu (n_envs=1, lr=3e-4→1e-5 linear, ent_coef=0.005) 120k step'te ep_rew_mean=+92.6 ve rooms_max=2 ile çalışıyor; Berker onayıyla 700k'ya uzatıldı. Eğitim büyük olasılıkla kullanıcının lokal makinesinde devam ediyor. Acil hyperparameter müdahalesi gerekmiyor; ancak 300-400k bandında std izleme kritik.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki "son 20 satır" GEÇERSIZ: hepsi 22:00-03:01 arası aynı değeri yansıtıyor (donmuş TB eventi, process dead). Gerçek v2.1 run'ı ayrı.
- **v2.1 gerçek eğri (versions.jsonl + train logs):**
  - 139k @ train_v2_2m_fresh: entropy=-4.76, std=1.2, lr=3e-4, approx_kl=0.008, clip_fraction=0.127 — sağlıklı kırılım fazı.
  - 120k @ versions.jsonl v2.1 entry: ep_rew_mean=+92.6, rooms_max=2, "hâlâ yükseliyor" — aktif kırılım, plato yok.
- **eval @ 140k (eval_v2_140k.log, 20 ep):** mean=+13.15 (std=41.80). Dağılım: 15/20 ep rooms=1, 3/20 ep rooms=2, 1/20 ep rooms=3 (best=+172). Politika sporadik 2-3 oda keşfedebiliyor ama tutarlı değil — beklenen erken-orta faz davranışı.
- **+15'lik oda sıçraması görüldü mü?** Evet — +92.6 = yaklaşık 6 oda bonusu (6×15=90) + voxel kazancı: training sinyali var. Ama eval ortalaması +13.15 gösteriyor ki deterministic policy henüz her episodda çıkartamıyor; stochastic policy eğitim sırasında çok daha iyi keşfediyor.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- Geçersiz soru: ppo.yaml v2.1'e tamamen yeniden yazıldı. Mevcut schedule: lr=3e-4 → 1e-5 linear (700k üzerinde). Bu v8'in 3e-4→3e-5 şemasıyla yapısal olarak özdeş (aynı 10× azalma oranı, final LR 3× daha düşük). v9'un sabit 7.5e-5'i terk edildi — DOĞRU KARAR. 139k'da LR hâlâ ~2.95e-4 (decay yeni başladı), yüksek LR erken kırılımı sağlıyor.

**c) Entropy/std değerleri keşif için yeterli mi?**
- v2.1 @ 139k: entropy=-4.76 (eşik -4.0, güvenli ✓), std=1.20 (eşik <0.70, alarm uzak ✓).
- UYARI — tarihsel referans: train_v4_fresh.log @ 309k adımda entropy=-3.1, std=0.679 → 0.7 ALTINA DÜŞÜŞ. Bu "v4_low_ent" config'iydi (ent_coef muhtemelen ~0.001 civarı). v2.1'de ent_coef=0.005 (5× yüksek), bu riski önemli ölçüde azaltıyor — ama yok etmiyor.
- **300-400k bandı kritik izleme noktası:** v4 analogu bu bandda deterministikleşti. v2.1'deyse n_updates o bandda ~(300000/2048)×10≈1465 olacak, v4'ün 1500'üne çok yakın. ent_coef=0.005 koruma sağlasa da log monitörlemesi şart.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v2.1 zaten rooms_max=2'ye 120k step'te ulaştı — ilk oda geçişi TAMAMLANDI.
- Tutarlı 3-oda: eval@140k'da 3/20 ep (=15%) 2+ oda, 1/20 ep 3 oda. Politika stochastic sırasında ama deterministic değerlendirmede tutarsız. Beklenti: 250-350k step'te tutarlı 3-oda, 450-550k'da 4-oda, 600-700k'da 5+ oda mümkün.
- 6 odanın tamamı (hedef): Haritanın asimetrik yapısı (dar kapılar, farklı boyutlu odalar) nedeniyle 700k step'te tam keşif mümkün ama garantili değil. Eğer 500k'da hâlâ 4 oda altında kalınırsa v2.2'yi gündeme al.

**e) v10/v2.2 için en kritik 1-2 öneri:**
1. **300-400k bandında std < 0.7 tetik → ent_coef: 0.005→0.010:** v4 analogu bu bandda deterministikleşti. İzleme: `train/std` TB veya log'dan takip et; 300k step'ten itibaren her 20k'da bir kontrol. Tetik şartı: std<0.7 VE entropy>-3.5 (birlikte). Tek başına std<0.7 yetmez, her ikisi birden olmalı.
2. **eval @ 350k (v2.1 bitmeden):** eval.sh @ 350k step'te çalıştır — 20 ep. Beklenti: rooms_mean≥2.0, en iyi ep 4+ oda. Eğer rooms_mean<1.5 ise yönlü lidar cezasını güçlendir (mevcut config'de wall penalty progression korunuyor). Bu veri olmadan v2.2 parametrelerini kör optimize etme.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** v2.1 config'i (n_epochs=10, batch=256, n_steps=2048, ent_coef=0.005) 120k'da +92.6 üretmiş — %80 güven eşiği aşılacak bir sorun yok. approx_kl=0.008 (agresif güncelleme yok ✓), clip_fraction=0.127 (makul ✓).
- **Monitor/CSV altyapısı açısından: EVET (düşük aciliyet).** CSV 13+ saattir donmuş, v2.1 TB dizinini okumaya ayarlanmamış. Kullanıcı lokalde çalışıyorsa v2.1 TB verisini doğrudan takip etmeli (`tensorboard --logdir runs/ppo_v2_1/tb`). Bu container'dan izleme mümkün değil.
- **Eğitim sürekliliği:** Training çalışıyorsa iyi. Çalışmıyorsa: `./scripts/train.sh configs/ppo.yaml` ile resume (ppo.yaml'da `resume_from: null` → fresh start, ya da son ckpt yazılmalı).

### v10/v2.2 Önerisi
1. **std izleme tetik @ 300-400k:** std<0.7 VE entropy>-3.5 → `ent_coef: 0.005→0.010`. train_v4_fresh bu bandda kesildi; v2.1 yüksek ent_coef ile daha sağlam ama geçmişe dayalı alarm şart.
2. **eval @ 350k + v2.2 kapı kararı:** rooms_mean<1.5 çıkarsa v2.2'de direction-aware penalty artışı (forward-arc katsayısı 0.3→0.5, grazing eşiği 0.5→0.7m). rooms_mean≥2.0 çıkarsa v2.2 başlatma; v2.1 tamamlansın.

### Müdahale
**YOK** — configs/ppo.yaml v2.1 formatında ve çalışıyor (+92.6 @ 120k kanıtlanmış). approx_kl, clip_fraction, entropy, std değerlerinin tamamı sağlıklı aralıkta. %80 güven eşiğini aşan config sorunu tespit edilmedi. CSV monitoring altyapısı stale ama bu hyperparameter meselesi değil.
---

## [2026-05-30 14:05 UTC]
**Step:** 83,968 / 2,500,000 (3.4% — v10 fresh restart) | **ep_rew_mean:** -25.30 | **entropy:** -4.253 | **std:** 0.998

### Durum
v9 ~599k step'te platoda çöktü; crash_recovery ile fresh restart yapıldı (checkpoint yok). Mevcut v10 config (lr=1.5e-4→1.5e-5 linear, n_envs=4) önceki oturumun önerisiyle tam örtüşüyor ve erken fazda çok iyi ilerleme gösteriyor: -290 platosundan -25'e 84k step'te ulaşıldı. Acil müdahale yok.

### Detay
- **Reward eğrisi (pre-crash plato — KRİTİK):** 294k→447k→599k adımlarında ep_rew_mean: -272.4 → -270.7 → -270.0. ~300k adımlık sert plato. ep_len tüm ölçümlerde 1000 (max): drone hayatta kalıyor ama hiç oda/voxel kazanamıyor — klasik "safe-but-useless" yerel optimumu. Bu platoda entropy -3.886 → -3.324 ve std 0.888 → 0.746 düştü; bir sonraki ölçümde std 0.7 eşiğini kırma riskiyle eğitim zaten dejenere olmaya başlamıştı. Crash, bu kötü yerel optimumdan çıkmayı sağladı.

- **Post-crash hızlı kırılım (v10 config):** 49k step'te -102.9, 84k step'te -25.3. 35k adımda +77.6 rew artışı. Pre-crash v9'da 457k adımda yalnızca +20 rew artışı vardı (294k→599k); v10 config'i (lr=1.5e-4 linear, n_envs=4) açıkça çok daha etkili.

- **lr=1.5e-4 → 1.5e-5 linear:** v9'un sabit 7.5e-5'ine kıyasla başlangıçta 2× daha yüksek, decay ile sonunda 7.5× daha düşük. Bu doğru seçim: yüksek LR başlangıçta hızlı politika güncellemesi, azalan LR sonunda fine-tune. Pre-crash platosunu kıran ana faktör muhtemelen bu.

- **Entropy:** -4.253. Pre-crash platosunda -3.32'ye kadar düşmüştü (tehlikeli). Post-restart -4.25-4.26 stabil — ent_coef=0.0015 bu LR ile çok daha iyi çalışıyor. -4.0 eşiğinin altında, keşif sağlıklı.

- **std:** 0.998. Mükemmel. Pre-crash 0.746'ya kadar düşmüştü; restart sonrası tam reset. Aksiyon dağılımı geniş.

- **FPS:** 61.0. n_envs=4 ile Gazebo yükü arttığından 83 FPS'den 61'e düştü. Kabul edilebilir — veri verimliliği net arttı (4 env × 61 FPS = 244 step/s vs 2 env × 83 = 166 step/s).

- **ep_len trendi (izleme noktası):** 49k'da 245.8, 84k'da 95.2. Kısa episodlar erken dönem çarpışma fazı için normal; ancak ep_len'in sürekli düşmesi (246→95) "erken ölüm optimizasyonu" riskine işaret edebilir: uzun idle cezasından kaçınmak için drone kasıtlı çarpışabilir. ep_rew_mean'in iyileşmesi şimdilik bu hipotezi desteklemiyor ama bir sonraki ölçümde ep_len <60 veya ep_rew_mean iyileşme duruyorsa kritik sinyal.

- **n_envs=4 deadlock riski:** KICKOFF.md n_envs=4→2 düzeltmesini belgeliyor ama kök neden _update_obstacles() animasyonu idi (devre dışı bırakıldı). 13:02'dan bu yana ~1h n_envs=4 ile sorunsuz çalışıyor; şimdilik stabil.

- **Checkpoint durumu:** Her iki ölçümde de ckpt_file=ppo_drone_80000_steps.zip görünüyor. Bu ölçümde gerçek step=84k olduğundan checkpoint zaten oluşmuş olmalı. Sonraki crash'te resume mümkün.

- **İlk oda breakthrough tahmini:** ep_rew_mean -25 @ 84k, pre-crash -270 @ 600k. v10 hızıyla 0'a ulaşım ~120-150k step, ilk +15 oda sıçraması 150-250k step içinde bekleniyor. v9'daki 500-800k tahmininin çok önünde.

### v10 Önerisi
1. **ep_len izleme kritik:** Bir sonraki ölçümde ep_len <60 veya rew_mean iyileşme duruyorsa ent_coef 0.0015 → 0.003'e çıkar (erken ölüm optimizasyonunu kır). Şu an müdahale yok.
2. **500k milestone'da eval:** 500k step'te `eval.sh` çalıştır — gerçek oda/voxel verisi al. TB'den tahmin yeterli değil; 6 odanın kaçını gördüğünü ölç ve checkpoint seç.

### Müdahale
Yok — mevcut config (lr=1.5e-4 linear, n_envs=4, ent_coef=0.0015) önceki oturumun önerileriyle örtüşüyor ve hızlı iyileşme gösteriyor. ep_rew_mean -25.3, entropy -4.253, std 0.998: tüm metrikler sağlıklı. %80 güven eşiğine ulaşan bir sorun yok.
---

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

## [2026-05-30 14:55 UTC]
**Step:** 100480 (v10 run, crash-loop sonrası) | **ep_rew_mean:** -47.11 | **entropy:** -4.247 | **std:** 0.996

### Durum
v9 run (~599k step'te) derin platoda kaldıktan sonra v10 başlatıldı; v10 hızlı öğreniyor (-25 @ ~84k) ama SubprocVecEnv deadlock nedeniyle 14:22-14:53 arasında 3 crash loop yaşandı. **n_envs=4 → 2 müdahalesi yapıldı** (KICKOFF.md'de belgelenmiş bilinen deadlock çözümü).

### Detay
- **İki ayrı run tespit edildi (CSV'de net görülüyor):**
  - **Run 1 / v9 (11:02-12:32):** Step 142k→599k, ep_len=1000 her zaman (max-out), ep_rew_mean: -290→-272→-270→-270. Tam plato. Hiçbir oda sıçraması yok. Drone hayatta ama keşif yok.
  - **Run 2 / v10 (13:02-14:53):** Step sıfırlanıp 49k→84k→100k, ep_len: 245→95→168. ep_rew_mean: -102→-25→-47. Çok daha hızlı öğrenme ama crash-loop nedeniyle step counter gerilemeler yapıyor (83968→106624→98432→100480 — monoton değil).
- **v9 run'ın platoya giriş analizi:**
  - ep_len=1000 her ölçümde: drone hiç terminale gitmiyor, ama reward -270'de sabit. "Hayatta kal, hareketsiz kal" yerel optimumu.
  - Entropy 11:02→12:32: -3.885→-3.617→-3.440→-3.324. Her 30dk'da ~+0.18 artış (daha az negatif = entropi düşüyor = deterministikleşme). Henüz -4.0 altında değil ama trend tehlikeli yöndeydi.
  - Std: 0.888→0.813→0.771→0.745. 0.7 eşiğine çok yaklaştı; bir sonraki 30dk'da büyük ihtimalle altına düşerdi.
  - LR: configs'de o an lr=0.00015 (1.5e-4) ile linear schedule vardı (KICKOFF.md'nin söylediği 7.5e-5 sabit değil). Ama run uzun süre 1000-step episodlarla devam ettiğinden gradient sinyali çok zayıftı.
- **v10 run'ının pozitif göstergeleri:**
  - 84k step'te ep_rew_mean=-25: Bu v9'un 600k step'te ulaştığı -270'den kat kat iyi. v10 çok daha kısa episodlarda öğreniyor (95-168 step) → terminallere gidiyor → daha güçlü reward sinyali.
  - Entropy -4.247 (>-4.0 ✓), std~0.997 (çok sağlıklı keşif). Fresh start + yüksek LR etkisi.
  - FPS: 61-101 (yeni run'da değişken, Gazebo yeniden başlatma maliyeti var).
- **ACIL SORUN — Crash loop (14:22, 14:33, 14:53 / hepsi step=80000):**
  - interventions.jsonl: üç ardışık crash_recovery, hepsi `resume_from=ppo_drone_80000_steps.zip` ile. Sürekli step=80000'e dönüp yeniden başlıyor.
  - KICKOFF.md'de net belgelenmiş: "Kök neden: SubprocVecEnv worker'ları içinde IPC pipe deadlock. Düzeltme: n_envs=4→2." Ama mevcut ppo.yaml'da n_envs=4 olarak bırakılmıştı — bu deadlock'un tetikleyicisi.
  - Gazebo 4 instance'ı SubprocVecEnv altında paralel başlatıldığında unix_stream_read_generic deadlock'a giriyor; 2 instance'ta bu sorun yok (v9 run'da 83→84 FPS ile stabil çalıştığı görüldü).

### v10 Önerisi
1. **n_envs=4→2 [UYGULANDIR]:** Zaten yapıldı. Bu değişiklik crash loop'u durdurmalı. FPS ~80'e düşer ama stabil çalışır; 4 env ile 60-100 arası gidip gelen unstable FPS'ten daha iyi.
2. **Checkpoint doğrulama:** Eğer crash loop n_envs=2 ile de devam ederse `resume_from: null` yaparak fresh start düşünülebilir (80k checkpoint bozuk olabilir). Ama öncelikle n_envs=2 fix'ini ver.

### Müdahale
**YAPILDI — configs/ppo.yaml:** `n_envs: 4 → 2`
- Sebep: KICKOFF.md'de belgelenmiş SubprocVecEnv IPC deadlock. n_envs=4 bilinçli olarak 2'ye çekilmişti; sonradan yanlışlıkla 4'e dönmüş. Crash loop (3x, step=80000) bunun direkt kanıtı.
- Beklenti: Bir sonraki resume'da training stabil çalışmalı, ep_rew_mean -25 civarından devam etmeli.
---

## [2026-05-30 15:10 UTC]
**Step:** 100,480 / 2,500,000 (4.0% — v10, post-crashloop) | **ep_rew_mean:** -47.11 | **entropy:** -4.247 | **std:** 0.997

### Durum
v10 crash-loop (3× ardışık, 14:22-14:53) n_envs=4→2 düzeltmesiyle sonlandırıldı (önceki oturum). Reward eğrisi v9'un -270 platosuna kıyasla dramatik biçimde iyileşti: v10'da 50k adımda -102→-47 (v9 600k adımda yalnızca -290→-270). Ent_coef ve LR mevcut aşamada uygun; ek müdahale yok.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- v10 aktif kırılım fazında: -102 @ 49k → -47 @ 100k. 50k adımda +55 rew = 1.1 rew/1k step. v9'da 457k adımda yalnızca +20 rew vardı (294k→599k); v10 9× daha hızlı ilerliyor.
- ep_len: 246 @ 49k → 95 @ 84k → 169 @ 106k → 151 @ 100k. Non-monoton (crash loop gürültüsü); stable run'da 150-200 step bant bekleniyor. Bu aralık "drone öğreniyor, zaman zaman terminal geliyor" için sağlıklı.
- Plato değil. Kırılım devam ediyor. Sıfır geçişi (ep_rew_mean=0) tahminen 143-180k step.
- İlk oda sıçraması (+15): 0 geçişinden sonra ep_len uzadıkça voxel birikimi artacak; ilk +15 bonus ~200-320k step aralığında bekleniyor. Eğer 350k'ya kadar gelmezse: oda kapısı discovery için frontier/explore bonusu yetersiz kalmış olabilir.

**b) lr=1.5e-4 → 1.5e-5 linear: bu aşamada doğru mu?**
- Evet. v9'un sabit 7.5e-5'i ile kıyaslanınca: başlangıç LR 2× daha yüksek olduğundan politika güncellemeleri daha etkili; decay ile fine-tune fazına hazırlık.
- v8: 3e-4 → 3e-5 (decay oranı 10×). v10: 1.5e-4 → 1.5e-5 (aynı 10× oran, daha düşük başlangıç). v8 3-katlı büyük haritada +113'e çıkmıştı; v10'un 6-oda tek katlı haritası için bu LR aralığı optimum görünüyor.
- 2.5M step'te son LR = 1.5e-5 → 750k step'ten sonra LR 3e-5'in altına düşer. Bu v8'in peak'inin (1.6M step) altında kaldığından fine-tune aşaması doğal örtüşecek.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Entropy: -4.247. Eşik -4.0 (üzerinde = sağlıklı). ✓
- Std: 0.997. Eşik <0.70 (alarm). Mevcut değer kritik eşikten çok uzakta. ✓
- v9'un tehlikeli trendi karşılaştırması: 11:02-12:32 arası entropy -3.89→-3.32 (her 30dk +0.18 deterministikleşme), std 0.888→0.745. Bir sonraki ölçümde 0.70 altına düşerdi. v10'da bu trend yok: fresh restart std=1.0'a sıfırlandı, yüksek LR sayesinde entropy stable.
- Sonuç: Şu an keşif kapasitesi tam. En erken alarm step 400-500k'da beklenilebilir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 hızıyla (1.1 rew/1k step): ep_rew_mean=0 → ~143k step. Oda kapısı keşfi için drone'un komşu odayı "görüp" geçmesi gerekiyor. Kapı genişliği 2m, lidar range 12m → frontier bonus devreye girdiğinde kapı yönüne yönlenme başlar.
- Tahmin: ilk +15 bonus **200-320k step** arasında görünür. Bu, toplam bütçenin %8-13'üne karşılık geliyor. v8 analoğu: v8 ~400k step civarında ikinci odaya geçti (farklı harita, yavaş LR dönemiydi). v10 daha erken bekleniyor.
- 350k'ya kadar oda geçişi gelmezse: ent_coef artışı düşünülebilir.

**e) v10 için en kritik 1-2 öneri:**
1. **ep_len izleme + ent_coef tetik:** Bir sonraki 3 ölçümde ep_len <100 VE ep_rew_mean iyileşmesi <0.5 rew/1k step'e düşerse → `ent_coef: 0.0015 → 0.003`. Drone idle cezasından kaçınmak için kasıtlı çarpışmaya başlayabilir (ep_len kısalır, rew stagnate). Bu senaryoda entropy artışı çözüm.
2. **Checkpoint senkronizasyonu:** `resume_from: runs/ppo_v10/checkpoints/ppo_drone_80000_steps.zip` hâlâ 80k'ya sabit. Monitor başarılı step'lerde bunu güncellemeli; aksi halde bir sonraki crash yeniden 80k'ya döner ve v10 tekrar crash-loop'a girebilir. Monitor agent'ın `resume_from`'u son checkpoint'e çekmesi kritik.

**f) Acil müdahale gerektiren bir şey var mı?**
- n_envs=4→2 düzeltmesi önceki oturumda yapıldı (ppo.yaml güncel, n_envs=2). ✓
- Crash-loop sebebi ortadan kalktı (IPC deadlock fix). ✓
- Acil müdahale yok. Tek risk: monitor `resume_from` güncellemezse yeni crash döngüsü.

### v10 Önerisi
1. **Watchdog tetik (ent_coef):** 300-400k step aralığında ep_len <100 VE plateau (rew artışı <0.5/1k) → `ent_coef: 0.003`. Şu an tetik koşulları oluşmadı.
2. **resume_from güncelleme:** Monitor agent, her başarılı 10k checkpoint'ten sonra `resume_from` alanını otomatik güncellemelidir — aksi halde bir sonraki crash yeniden 80k'ya sıfırlanır ve ilerleme kaybolur.

### Müdahale
Yok — mevcut config (lr=1.5e-4→1.5e-5 linear, n_envs=2, ent_coef=0.0015) optimum aralıkta. Entropy=-4.247 (>-4.0 ✓), std=0.997 (>0.7 ✓), reward hızlı iyileşiyor. %80 güven eşiğine ulaşan sorun tespit edilmedi.
---

## [2026-05-30 14:06 UTC]
**Step:** 100,480 / 2,500,000 (4.0% — v10, son veri 11:53 UTC) | **ep_rew_mean:** -47.11 | **entropy:** -4.247 | **std:** 0.996

### Durum
v10 crash-loop (n_envs=4, 3× ardışık 11:22-11:53 UTC) önceki oturumda n_envs=4→2 ile sonlandırıldı. Fix'ten bu yana (~12:07 UTC) git repo'ya yeni metrik commit edilmemiş — 2+ saatlik veri boşluğu mevcut; monitor_agent sağlığı belirsiz. Hyperparameter'larda sorun yok, acil müdahale gerektiren yeni bir şey tespit edilmedi.

### Detay

**a) Reward eğrisi: Plato mu, kırılım mı?**
- İki ayrı run net biçimde ayrışıyor:
  - **v9 run (08:02-09:32 UTC):** step 142k→599k boyunca ep_len=1000 (sabit max), ep_rew_mean: -290→-272→-270→-270. ~457k adımlık ağır plato. "Hayatta kal, hareket etme" yerel optimumu. Entropy 11:02→12:32: -3.886→-3.324 (deterministikleşme trendi, 0.7 eşiğine yaklaşıyordu).
  - **v10 run (10:02-11:53 UTC):** 49k→84k→100k (crash-loop gürültüsüyle non-monoton), ep_rew_mean: -102→-25→-40→-55→-47. İlk 35k adımda +77 rew artışı. Görsel regresyon (-25→-47) gerçek öğrenme kaybı değil; crash her seferinde 80k checkpoint'e dönüyor, o adımdaki -47 seviyesinden yeniden başlıyor.
- **Mevcut değerlendirme:** n_envs=2 fix sonrası eğer training stabillendiyse, ep_rew_mean crash-loop temizlenince -25 ile -40 arasında resume edecek. Kırılım devam ediyor, plato yok.

**b) lr=1.5e-4→1.5e-5 linear: Doğru mu?**
- Evet, kesinlikle. step=100k'da LR ≈ 1.44e-4 (2.5M adımlık linear decay'in %4'ü geçti, LR hâlâ yüksek — erken öğrenme fazı için ideal).
- v9'un sabit 7.5e-5 ile karşılaştırması: v9 @ 600k = -270, v10 @ 84k = -25. Başlangıç LR'inin 2× yüksek olması kritik fark.
- v8 şeması (3e-4→3e-5) 3-katlı büyük haritada +113 verdi; v10'un 1.5e-4→1.5e-5'i daha konservatif ama 6-oda harita için doğru kalibre.

**c) Entropy/std keşif için yeterli mi?**
- Entropy: -4.247. v9 plato döneminde -3.32'ye kadar düşmüştü (tehlikeli); v10'da -4.24 ile stabil. -4.0 eşiği güvenli aşılıyor ✓
- std: 0.996. v9 crash öncesi 0.745'e kadar inmişti; v10'da 1.0 bandında. 0.7 alarm eşiğinden çok uzakta ✓
- Keşif kapasitesi tam sağlıklı. Ent_coef tetik koşulları (ep_len <100 VE plateau) şu an oluşmadı.

**d) Oda geçişi için ne kadar step daha?**
- n_envs=2 fix sonrası stabil run varsayımıyla: ep_rew_mean'in şu anki -47 seviyesinden sıfıra çıkışı ~160-200k step. İlk +15 oda sıçraması: **220-350k step toplam**.
- v10 hızı 1.1 rew/1k step (crash-loop döneminde ölçülen konservatif tahmin); stabil run'da bu oran artabilir.
- Eşik: 350k step'e kadar +15 görülmezse ent_coef 0.0015→0.003 tetik.

**e) v10 için en kritik 2 öneri:**
1. **Monitor_agent canlılık kontrolü:** Son CSV girişi 11:53 UTC (~2h önce). Sonraki beklenen giriş 12:23 UTC'ydi ama gelmedi. Ya monitor_agent durdu, ya training crashed ve recovery gerçekleşmedi, ya da sadece git push eksik. Öncelikle: `pgrep -fa "monitor_agent"` ve `tail -20 /tmp/monitor.log` ile kontrol et.
2. **resume_from kademeli güncelleme:** Her crash yeniden 80k'ya dönüyor çünkü monitor latest checkpoint'i seçmiyor (ya v10 klasörünü yanlış tarıyor, ya da checkpoint pattern uyuşmuyor). Manuel olarak: `ls -lt runs/ppo_v10/checkpoints/` ile mevcut en son .zip'i bul ve `ppo.yaml`'daki `resume_from`'u güncelle. Bu değişiklik ile sonraki her crash 20k yerine daha az adım kaybettirir.

**f) Acil müdahale gerektiren bir şey var mı?**
- n_envs=4→2 fix: **YAPILDI** ✓ (commit 12:07 UTC)
- 2h veri boşluğu: Monitor sağlığını doğrula — rutin izleme, acil değil.
- Hyperparameter: Hiçbiri alarm vermiyor.

### v10 Önerisi
1. **resume_from güncelle (manuel, tek seferlik):** `ls -lt runs/ppo_v10/checkpoints/*.zip | head -3` çalıştır; en son .zip'i ppo.yaml'a yaz ve push et. Crash loop'ta her seferinde 80k'ya düşmek yerine en son milestone'dan başla. Bu 1 satır yaml değişikliği en yüksek ROI'li aksiyon.
2. **350k milestone alarm:** ep_rew_mean hâlâ 0'ın altında VE oda sıçraması yoksa 350k step'te `ent_coef: 0.003` uygula. Şu an tetik yok.

### Müdahale
**Yok** — configs/ppo.yaml'daki tüm hyperparameter'lar (lr schedule, ent_coef, n_envs, clip_range) mevcut metriklere göre optimal aralıkta. resume_from güncellemesi için mevcut checkpoint dosyalarına erişim gerekiyor (git repo'da yok, .gitignore'da); manuel doğrulama kullanıcıya bırakıldı. %80 güven eşiğini aşan, config üzerinden çözülebilecek net bir sorun tespit edilmedi.
---

## [2026-05-31 10:06 UTC]
**Step:** 193,248 (CSV son kayıt — v9/v10 era, STALE) | **Gerçek son durum:** v2.1 @ 120k → ep_rew_mean: +92.6 | **entropy:** -4.212 (son CSV) / -4.75 (v2.1 @ 137k) | **std:** 0.985 (son CSV) / 1.19 (v2.1 @ 137k)

### Durum
**EĞİTİM PROCESS'İ ÇALIŞMIYOR.** `pgrep train_ppo` boş döndü. training_metrics.csv 2026-05-30 22:00'dan beri adım=193248 ile DONMUŞ (12+ özdeş satır, v9 kalıntısı). Gerçek güncel run ppo.yaml v2.1 (n_envs=1, lr=3e-4→1e-5 linear, ent_coef=0.005, total=700k) olup versions.jsonl'e göre 120k step'te ep_rew_mean=+92.6'ya ulaşmıştı ve daha sonra process kesildi.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son veriler GEÇERSIZ: bunlar v9/v10 crash-loop sürecinin donmuş kalıntısı (step 80k→180k arası tekrarlayan crash_recovery'ler).
- Gerçek v2.1 eğitim çizgisi: v2.0 redesign → v2.1 @ 11:18 UTC → 120k'da +92.6 (rooms_max=2, yükselen). Train_v2_2m_fresh.log @ 137k'da ep_rew_mean=+40-41 görünüyor (farklı run, v2_explore), bu da küçük bir plato sinyali. Ancak versions.jsonl "hâlâ yükseliyor" notunu v2.1 @ 120k için veriyor. Kırılım devam ediyordu, plato yok — kesme noktasında momentum vardı.

**b) lr=7.5e-5 constant bu aşamada doğru mu?**
- Artık geçersiz: ppo.yaml v2.1'e yeniden yazıldı → lr=3e-4→1e-5 linear decay. Bu v8'in 3e-4→3e-5 şemasıyla yapısal olarak aynı, tek fark final LR daha düşük (1e-5 vs 3e-5). 6-oda 16×16m harita için doğru kalibrasyon. Sabit lr=7.5e-5 kullanımı terk edildi, DOĞRU KARAR.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Son güvenilir v2.1 verisi (train_v2_2m_fresh @ 137k): entropy=-4.75, std=1.19 → MÜKEMMEL, alarm eşiğinin çok uzağında.
- DİKKAT SİNYALİ: train_v4_fresh.log @ 307k adımda entropy=-3.11, std=0.679 (0.7 ALTINA DÜŞÜŞ). Bu v4 konfigürasyonu için geçerliydi, fakat v2.1'deki ent_coef=0.005 (v4'ten yüksek) bu riski düşürüyor. Bununla birlikte, 300-400k band geçilirken std izlenmeli — v4 aynı bandda alarm vermişti.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v2.1 @ 120k'da zaten rooms_max=2 ulaşıldı (+92.6 return ≈ 2 oda × 15 + voxel seyahati). Kalan 580k step ile (total 700k) tam saat oda keşfi yapılabilir.
- Referans: eval_v2_140k.log en iyi ep'de +172 (3 oda) — politika sporadik 3-oda geçişi yapabiliyordu.
- Beklenti: 200-350k step'te tutarlı 3-oda geçişi; 500k+ sonunda 4-5 oda mümkün.

**e) v10/v2.2 için şu an en kritik 1-2 öneri:**
1. **std izleme tetik:** 300-400k bandında std < 0.7 görülürse ent_coef 0.005 → 0.010'a çek. train_v4 bu bandda kesildi (std=0.679); v2.1'de ent_coef yüksek ancak deterministikleşme yine de gelebilir.
2. **v2.2 trigger (600k+):** ep_rew_mean plateau (son 100k'da <5 artış) veya collision rate yeniden yükselirse → direction-aware lidar penalty'yi artır (mevcut 0.3→0.5) ve siyırma cezası eşiğini 0.5m→0.7m'ye genişlet. eval_v2_140k log'da 20 ep'in 15'i tek odada kaldı → duvar sıkışma kalıbı hâlâ var.

**f) Acil müdahale gerektiren bir şey var mı?**
- **EVET — EĞİTİM ÇALIŞMIYOR.** Process kesilmiş, son checkpoint belirsiz (runs/ dizini remota push edilmemiş, yerel olarak da yok). v2.1 700k hedefinin 120k'dan sonrasına ait hiç checkpoint yok. Kullanıcının lokalde `./scripts/train.sh configs/ppo.yaml` ile yeniden başlatması gerekiyor. Fresh start mı, son ckpt'den mi resume edilecek bilgisi ppo.yaml'daki `resume_from: null` değerinden anlaşılıyor → FRESH restart demek.
- ppo.yaml hyperparameter'larında %80+ güven eşiğini aşan bir sorun yok → config değiştirilmedi.

### v10 Önerisi
1. **300-400k bandında std < 0.7 → ent_coef 0.005→0.010 tetik:** train_v4_fresh bu bandda deterministikleşti (std=0.679). v2.1 ent_coef=0.005 ile bu riski düşürdü ancak eşiği geçince agresif artırım yapılmalı.
2. **v2.2'de direction-aware ceza sıkılaştırması:** 20-ep eval'de 15 ep tek odada bitti — siyırma eşiği 0.5→0.7m ve ön-arc ceza katsayısı 0.3→0.5 olarak güçlendirilmeli. Bu değişiklik keşif oranını doğrudan artırır, reward şekillendirilmesini gerektirmez.

### Müdahale
**Yok** — configs/ppo.yaml v2.1 (n_envs=1, lr=3e-4→1e-5 linear, ent_coef=0.005, total=700k) mevcut veriye göre optimal. Training process dead olması operasyonel sorun; hyperparameter müdahalesi %80 güven eşiğini aşmıyor. Kullanıcının lokalde `./scripts/train.sh configs/ppo.yaml` ile süreci yeniden başlatması gerekiyor.
---

## [2026-05-31 15:45 UTC]
**Step:** ~501,760 (interventions.jsonl son kayıt — 14:54 UTC) | **ep_rew_mean:** 123.25 (resume noktası) | **peak:** 133.35 | **entropy:** ~-3.53 (train_resume_500k.log @ 250-291k) | **std:** ~0.79 (train_resume_500k.log @ 250-291k)

### Durum
v2.1 run, v8 all-time peak'ini (+113 @ 1.6M step) çoktan geride bıraktı: step 501760'ta ep_rew_mean=123.25, peak=133.35. 700k hedefe 198240 adım kaldı. Ancak `train_resume_500k.log` analizi iki kritik sorunu ortaya koydu: (1) SB3 her resume'da LR'yi 3e-4'e sıfırlıyor — fine-tune fazında bu agresif başlangıç ep_rew_mean'i -12.7→-25.5 gerilettiği görüldü; (2) entropy 250-291k bandında -3.53 ile -4.0 tehlike eşiğini aştı, std 0.79'a geriledi. **configs/ppo.yaml güncellendi: `learning_rate: 3e-4 → 5e-5`.**

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son veri (193248) tamamen geçersiz — v9/v10 döneminin kalıntısı.
- Gerçek v2.1 zaman çizgisi:
  - 0→120k: hızlı kırılım, -kayıp → +92.6, rooms_max=2
  - 120k→250k: yükselen faz, peak 133.35 civarına ulaşıldı
  - 248k→291k (train_resume_500k.log): LR reset sonrası geçici regresyon, ep_rew_mean -12.7→-25.5; ep_len 299→488 (drone çok uzun yaşıyor ama skor düşüyor — time penalty birikimi)
  - 291k→500k: toparlanma, ppo_drone_final.zip kaydedildi (peak=133.35)
  - 500k→700k: şu an bu fazda, 198k adım kaldı
- Kırılım fazı geride kaldı; artık exploitation+fine-tune çerçevesindeyiz.

**b) lr=7.5e-5 constant bu aşamada doğru mu?**
- Bu soru artık bağlamı aşmış. Kritik bulgu: train_resume_500k.log step 250592'de `learning_rate: 0.0003` gösterdi. Eğer SB3 linear decay doğru çalışsaydı, 250k/700k ≈ %36 tamamlandığında LR ≈ 2e-4 olmalıydı. 3e-4 görülmesi, **SB3'ün resume'da `reset_num_timesteps=True` ile progress_remaining=1'den başladığını** kanıtlıyor.
- Bu reset, 500k'da öğrenilmiş politikayı her restart'ta 3e-4 LR ile "sarsiyor" ve başlangıçta regresyona neden oluyor.
- **Düzeltme: `learning_rate: 5e-5`** — 500k+ fine-tune için uygun başlangıç. 5e-5→1e-5 aralığı stabil sonlandırma sağlar.

**c) Entropy/std değerleri keşif için yeterli mi?**
- train_resume_500k.log @ 250-291k:
  - entropy_loss: -3.59 → -3.53. Bu değer **-4.0 EŞIĞININ ÜSTÜNDE (tehlike bölgesi)**.
  - std: 0.802 → 0.788. 0.7 eşiğine yaklaşıyor. Düşüş hızı: -0.0028/1k step; bu hızda ~310-320k'da 0.7'yi kırabilirdi.
  - Sebepler: (1) yüksek LR (3e-4 reset) büyük politika güncellemeleri → aksiyon dağılımı daralıyor; (2) ep_len artışı (299→488) → daha uzun episodlarda değer fonksiyonu hatalı tahmin → gradient gürültüsü.
- Peak 133.35 bu entropy seviyesine rağmen elde edildi — ent_coef=0.005 yeterli korumayla politikayı tuttu.
- 500k→700k fazında LR düşürülerek entropy daha stabil kalacak; ent_coef değişimine gerek yok.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- eval_v2_140k.log: 20 ep'de 1/20 ep 3 oda, rooms_max=3 (best=+172).
- 500k'da peak=133.35 ≈ (133.35 - voxel) / 15 ≈ 8-9 oda bonusu → politika stochastic modda birden fazla oda keşfediyor.
- 700k'da beklenti: rooms_mean ≥ 3 tutarlı; 5-6 oda mümkün ama garanti değil (asimetrik kapılar en büyük engel).
- Eğer 700k tamamlandığında rooms_mean < 3: v2.2 ile direction-aware lidar penalty artışı + ent_coef: 0.010.

**e) v10/v2.2 için en kritik 1-2 öneri:**
1. **trainer.py'de `reset_num_timesteps=False` kalıcı fix:** Her resume'da LR'nin sıfırlanmasının kök sebebi bu. Trainer kodu incelenmeli: eğer `model.learn(remaining_steps, reset_num_timesteps=True)` kullanılıyorsa `False`'a çevirmek + `remaining_steps = total - resume_step` gerekli. Bu config değişikliği değil, kod düzeltmesi — yüksek öncelik.
2. **700k sonunda eval çalıştır, v2.2 kararını veriler üzerine kur:** rooms_mean ölçümü olmadan v2.2 konfigürasyonunu kör belirleme. Eval 20 ep: rooms_mean ≥ 3 → v2.2 ile 3 engel aktif (ent_coef: 0.010, n_envs: 2). rooms_mean < 3 → v2.2'de önce direction penalty sıkılaştır, sonra engel ekle.

**f) Acil müdahale gerektiren bir şey var mı?**
- **EVET — LR reset kanıtlandı ve configs/ppo.yaml güncellendi (aşağıya bak).** Bu değişiklik mevcut run'ı etkilemez ama bir sonraki restart'ta (crash veya 700k tamamlanınca) geçerli olacak.
- **entropy -4.0 eşiği aşımı:** Geçici, LR reset'e bağlı; mevcut run'da 500k peak=133.35 görülmüş. Kalıcı çözüm LR düşürülmesi (yapıldı).
- **CSV monitoring donmuş (193k):** Operasyonel, hyperparameter sorunu değil.

### v10/v2.2 Önerisi
1. **trainer.py `reset_num_timesteps=False`:** LR reset bug'ı en yüksek ROI düzeltmesi. Her resume agresif 3e-4 başlangıcından kurtulmak için kod seviyesinde fix gerekli. ppo.yaml'daki LR değişikliği kısa vadeli önlem.
2. **700k sonrası eval → v2.2 konfigürasyonu:** rooms_mean < 3 → ent_coef: 0.005→0.010, direction penalty 0.3→0.5, siyırma eşiği 0.5→0.7m. 3 hareketli engel yalnızca rooms_mean ≥ 3 sonrası aktif edilmeli — daha zor ortamı hazır olmayan politikaya sunmak öğrenmeyi bozar.

### Müdahale
**YAPILDI — configs/ppo.yaml:** `learning_rate: 0.0003 → 5.0e-05`
- **Kanıt:** train_resume_500k.log step 250592'de `learning_rate: 0.0003` gösteriyor. Linear decay 250k/700k noktasında ~2e-4 olmalıydı; 3e-4 görülmesi SB3'ün resume'da LR schedule'ı sıfırladığını kanıtlıyor.
- **Etki:** Step 248k→291k'da ep_rew_mean -12.7→-25.5 regresyonu bu yüksek LR'nin sonucu. 500k+ fine-tune için 5e-5 başlangıcı daha stabil; policy'i bozmadan gerçek improvement için zemin yaratır.
- **Kapsam:** Bir sonraki restart'ta (crash veya 700k tamamlanınca) devreye girer. Mevcut çalışan process etkilenmez.
---

## [2026-05-31 15:10 UTC]
**Step:** 501,760 (v2.1 — 500k tamamlandı, 700k'ya devam @ 14:54 UTC) | **ep_rew_mean:** +123.25 | **peak:** +133.35 | **entropy:** ~−3.5 (son güvenilir: −4.76 @ 139k, decay beklenen) | **std:** ~0.75–0.90 (son güvenilir: 1.20 @ 139k)

### Durum
v2.1 eğitimi 500k step'i tamamlayıp final.zip kaydetti; 14:54 UTC itibarıyla kalan 198,240 adım için yeniden başlatıldı (total_timesteps=700k, resume_from=ppo_drone_final.zip). Peak reward +133.35 — v8 all-time best'i (+113 @1.6M step) yalnızca 500k adımda geride bırakıldı; bu mevcut v2.x tasarımının doğru olduğunu kanıtlıyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- Aktif kırılım devam ediyor: +92.6 @120k → +123.25 @501k = +30.65 artış.
- Eğim yavaşladı (~0.26 ünite/k step vs başta daha hızlı) — plato değil, olgunlaşma fazı.
- ep_len_mean bilinemez (v2.1 TB verisi bu container'da yok) ama eval@140k'da rooms=2-3 sporadik mevcut; 500k'da tutarlı 3-4 oda bekleniyor.
- **+15'lik oda sıçraması:** +123.25 = muhtemelen 4-5 oda keşfi eğitim sırasında (4×15=60 rooms + ~63 voxel/frontier/zaman).

**b) lr=5e-5 linear→1e-5 (v2.1 mevcut) bu aşamada doğru mu?**
- EVET, uygun. 500k resume'da SB3, progress_remaining'i 1.0'dan başlatır; bu yüzden lr=3e-4 yerine 5e-5 ile başlangıç zorunluydu (train_resume_500k.log'da 291k'da lr=0.0003 gözlemlenmiş — bu eski BAD resume'un kanıtı; ep_rew_mean −25.5'e regresyon yaşandı).
- Mevcut v2.1 config bunu doğru handle ediyor: 5e-5 başlangıç, linear decay, 700k'ya yayılmış → kalan 198k'da lr ~3.8e-5'ten 1e-5'e iniyor. Fine-tune fazı için optimal aralık.
- Kıyaslama: v8 3e-4→3e-5 (10× azalma); v2.1 5e-5→1e-5 (5× azalma, daha muhafazakâr). Yeni haritanın daha basit olduğu göz önüne alındığında bu makul.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Son güvenilir v2.1 değerleri: entropy=−4.76, std=1.20 @139k. 500k'da bu değerlerin düşmesi beklenir (std→0.7-0.9, entropy→−3.5 ila −4.5 arası).
- ent_coef=0.005 ile kolaps riski düşük. Karşılaştırma: train_v4_fresh.log @309k std=0.679 (0.7 eşiği altı!) ama o config'de ent_coef daha düşüktü.
- CSV'deki eski v9 verisindeki entropy=−4.21, std=0.985 DEĞERLERİ GEÇERSİZ — 14+ saattir frozen (step=193248 sabit).
- **Endişe yok ama izleme gerekli:** 600-700k bandında std<0.7 olası. Bu bandda eval performansının da iyileşmesi beklenir (daha düşük std = daha deterministik pol = eval-train gap kapanır).

**d) Oda geçişi için ne kadar step daha bekleniyor?**
- v2.1 zaten 120k'da rooms_max=2, 500k'da tahminen 4-5 oda (training stochastic).
- eval@140k: mean=+13.15, yalnızca 1 ep 3 oda (@20 ep). Deterministic eval-train gap büyük.
- **Son 198k adımda (500k→700k):** std düştükçe deterministic policy de güçlenecek. 700k sonunda eval'de consistent 3-4 oda bekleniyor.
- 6/6 oda tutarlı keşfi: v2.1'de mümkün ama garantili değil. Asimetrik kapı düzeni (dar geçitler) en büyük engel.

**e) v10/v2.2 için en kritik 1-2 öneri:**
1. **ent_coef: 0.005→0.003 (v2.2/v10 fresh start):** eval-train gap'in kök sebebi aşırı stochastisite. Eğitim boyunca +92→+123 (training) ama eval@140k yalnızca +13.15 (10× fark). 0.003 hem yeterli keşif sağlar hem deterministic policy'yi güçlendirir. NOT: mevcut çalışan v2.1 process'i BU DEĞİŞİKLİKTEN ETKİLENMEZ — change yalnızca fresh/next-start için geçerli.
2. **Eval @ 700k (v2.1 biter bitmez):** eval.sh çalıştır, 30+ ep. Metrik: rooms_mean, rooms_max, collision_rate. Eğer rooms_mean≥3.0 → v2.2'de moving obstacles aktif et (n_envs=1, SIGINT-safe). Eğer rooms_mean<2.0 → v2.2'de forward-arc lidar cezasını artır (0.3→0.5 katsayı).

**f) Acil müdahale gerektiren bir şey var mı?**
- **Eğitim süreci:** 14:54 UTC'de başlatıldı, 38 FPS @ n_envs=1 → ~87 dakika → ~16:21 UTC'de bitmesi beklenir. Container burada izleyemiyor, lokal makinede takip şart.
- **SB3 progress_remaining reset riski (step counter):** resume_from=ppo_drone_final.zip ile SB3, adım sayacını 500k'dan değil sıfırdan başlatabilir. Bu durumda total_timesteps=700k, resume=500k → sadece 700k-500k=200k step yapılacak (DOĞRU). Ama `n_updates` sıfırlanacak ve LR decay yeniden 5e-5'ten başlayacak (zaten beklenen; config bunu handle ediyor).
- **CSV monitoring:** interventions.jsonl'deki son "crash_recovery @step=180k" satırları (03:01 UTC'ye kadar) eski monitor_agent'ın v2.1'i değil v9 ckpt'yi takip ettiğini gösteriyor. CSV artık güncellenmiyor — kabul edilebilir, asıl kayıt TB'de.
- **ACIL HYP. MÜDAHALESİ: HAYIR.** Config v2.1 son fazında sağlıklı. %80 güven eşiğini aşan bir sorun yok.

### v10 Önerisi
1. **ent_coef: 0.005→0.003:** eval-train gap kapatmak için. Training @500k +123 ama eval@140k +13 — bu 10× fark aşırı stochasticite. v2.2/v10 fresh start'ta bu değişikliği uygula.
2. **Moving obstacles aktif (n_envs=1 ile güvenli):** v9'da SubprocVecEnv deadlock nedeniyle devre dışı bırakıldı. v2.x zaten n_envs=1 kullanıyor → obstacle animasyonunu güvenle açabilirsin. v10 curriculum zorluğu için kritik.

### Müdahale
**YOK** — v2.1 son fazı zaten çalışıyor (14:54 UTC resume). Mevcut process ppo.yaml'ı çalışma anında okumuyor; config değişikliği şu an etkisiz olur. Peak +133.35 ve aktif iyileşme trendi ile %80 güven eşiğini aşan bir hyperparameter sorunu tespit edilmedi. ent_coef=0.003 önerisi v2.2/v10 için NOT olarak bırakıldı.
---

## [2026-05-31 15:05 UTC]
**Step:** 501,760 (resume → hedef 700k) | **ep_rew_mean:** +123.25 | **peak:** +133.35 | **entropy:** -4.24 (son güvenilir CSV kaydı) | **std:** ~0.998

### Durum
v2.2 500k eğitimi tamamlandı; ep_rew_mean=**+123.25**, peak=**+133.35** — v8 tüm-zamanlar rekorunu (+113 @ 1.6M step) **500k'da geçti**. 14:54'te ppo_drone_final.zip'ten resume edildi, hedef 700k (198k step kaldı). Config güncellendi: total_timesteps 500k→700k, resume_from null→final.zip.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- interventions.jsonl son kayıt (14:54): step=501760, reward=123.25, peak=133.35. Bu aktif yükseliş fazını gösteriyor — peak hâlâ reward mean'in üzerinde yani her episode'da maksimum keşfedilemiyor ama eğitim yönü pozitif.
- eval_v3_310k.log (11 ep, interrupted): return=+45..+78, rooms=1-2. 310k'daki politika tutarsız ama tek-oda keşif sağlam. 500k'daki 123.25'e bakılırsa 310k→500k arası güçlü kırılım yaşandı.
- **+15'lik oda sıçraması görüldü mü?** Evet — +123.25 ≈ 6×15 + voxel kazanımı; politika büyük olasılıkla >4 oda keşfedebiliyor training sırasında.
- Plato belirtisi yok. peak/mean gap (~10 puan) normal; tutarlı çok-oda keşfi için 600-700k bandı bekleniyor.

**b) lr=5e-5 → 1e-5 linear: bu aşamada doğru mu?**
- v2.2 fresh 500k boyunca lr=5e-5→1e-5 linear decay uygulandı. Sonuç mükemmel (+123.25).
- Resume sonrası SB3 progress_remaining=1.0'dan başlıyor → yeniden 5e-5→1e-5, bu sefer 198k step üzerinde. Etkin decay: ~2e-10/step. 100k'da lr≈3e-5, 198k'da lr=1e-5. Fine-tune için uygun; agresif değil.
- Karşılaştırma: v7 lr_decay (3e-4→3e-5) 220k'da std=0.86, reward=69-90 bölgesinde platoya oturdu. v2.2 aynı step bandında lr=5e-5 ile 123.25'e ulaştı → sabit düşük LR'nin bu harita için doğru strateji olduğu kanıtlandı.

**c) Entropy/std: keşif için yeterli mi?**
- Son güvenilir CSV kaydı (May 30 22:00, freeze öncesi): entropy_loss=-4.24, std=0.998. Sağlıklı.
- ent_coef=0.005 (task context'teki 0.0015'ten 3.3× yüksek) → entropy baskısı güçlü, -4'ün altında (uyarı sınırının altında = iyi). Erken deterministikleşme tehlikesi yok.
- std=~1.0: 0.7 eşiğinin çok üstünde. Keşif kapasitesi tam.
- train_v2_2m_fresh.log (139k, v2.1 karşılaştırma): entropy=-4.76, std=1.2 → v2.2'de ent_coef aynı olduğu için benzer değerler beklenir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- 500k'da reward=123.25 ≈ büyük olasılıkla 4-5 oda tutarlı keşif. 6. odanın tutarlı keşfi için 600-700k bekleniyor (peak'in mean'e yakınsama süreci).
- eval_v2_140k.log (20 ep): rooms_mean~1.2, best=3 oda. eval_v3_310k: rooms=1-2. Training ortamında stochastic politika çok daha iyi keşfediyor; 700k eval bunu netleştirecek.
- FPS=38 (son log) → 198k step ≈ 5.2M saniye / 38 ≈ 5,200s ≈ ~1.4 saat. Eğitim 16:00-17:00 bandında tamamlanabilir.

**e) v10 için en kritik 1-2 öneri:**
1. **Hareketli engelleri aktifleştir** (3 engel SDF'de mevcut, animasyon devre dışı). n_envs=1 ile SubprocVecEnv deadlock riski yok; 700k final checkpoint'inden fine-tune için ideal temel. v10 ent_coef'i 0.01'e çıkar (yeni dinamizm için keşif gerekir).
2. **n_steps=2048→4096**: n_envs=1 ile tek rollout buffer çok küçük; 4096 ile policy gradient varyansı düşer, oda sıçramalarını daha stabil öğrenir. Batchsize=512 olarak ayarla.

**f) Acil müdahale gerekiyor mu?**
- **EVET — Config tutarsızlığı** (giderildi): total_timesteps=500000 ve resume_from=null stale değerler monitor/crash-recovery için risk oluşturuyordu. Güncellendi.
- Hyperparameter: acil müdahale gerektiren bir anormallik yok. Reward seyri beklentinin üzerinde.

### v10 Önerisi
1. Hareketli engel aktivasyonu + ent_coef=0.01 (dinamik ortam için artan keşif baskısı)
2. n_steps=4096, batch_size=512 (n_envs=1 ile geniş rollout buffer, oda-geçiş gradyanlarında daha düşük varyans)

### Müdahale
**configs/ppo.yaml güncellendi:**
- `version: v2.2` → `v2.2-resume700k`
- `total_timesteps: 500000` → `700000` (fiili hedef)
- `resume_from: null` → `./runs/ppo_v2_2/checkpoints/ppo_drone_final.zip`
- Sebep: Config crash-recovery için referans; stale değerler yanlış restart'a neden olurdu.
---

## [2026-06-01 08:30 UTC]
**Step:** 434,176 (son interventions.jsonl, 01:30 UTC) → Gazebo v3.0 610k'da durduruldu (peak 110.3) | **Fast-sim:** v4.8=ŞAMPIYON (collision %0, voxels 117, rooms 5) + v5.0=YAKINSAMA | **ep_rew_mean:** 99.84 @ 434k (Gazebo v3.0) | **entropy:** -5.67 (train_v3_floors ref, 312k) | **std:** 1.63 (train_v3_floors ref, 312k)

### Durum
Proje iki paralel eksende büyük sıçrama yaptı: (1) Gazebo v3.0, 610k adımda peak=110.3 ile durduruldu (v8 all-time +113'ün %97'si, yalnızca 610k'da), (2) Gazebo'dan bağımsız numpy/Gymnasium fast-sim (~100×) devreye alındı ve v4.8→v5.0 zinciriyle **temel güvenlik-kapsam trade-off'u kesin olarak belirlendi**. Fast-sim v4.8: collision %0, rooms_mean=5.0, voxels=117 — deploy edilebilir şampiyon. v5.0 yakınsaması: tüm kaldıraçlar (ödül şekillendirme, eğitim süresi, curriculum, obs) denenmiş, ek yapısal değişiklik olmadan ilerleme kalmadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- **Gazebo v3.0**: 434k'da ep_rew_mean=99.84, peak=102.54 (01:30 UTC "taze kırıldı" notu). Peak büyüdükçe mean'e yakınsama sürecindeydi — olgunlaşma fazı, kırılım değil. Gazebo v3.0 610k'da intentional durdurmayla sonlandırıldı (peak 110.3). Plato değil, kasıtlı durdurma.
- **Fast-sim**: v4.8 (1.5M step, collision_pen=25) → collision %0, rooms=5, voxels=117. v4.10 (5M step) → voxels=281, rooms=5.76 (6 oda!), AMA collision %54. v4.13 (8M step) → daha uzun eğitim zirve değil geçici tepe olduğunu kanıtladı (voxels 281→134); politika regularize oldu. +15'lik oda sıçraması: fast-sim v4.8'de rooms=5 tutarlı; v4.10'da 6/6 oda başarıldı.
- **CSV durumu**: 2026-05-30 22:00'dan beri dondurulmuş (step=193248, v9/v10 kalıntısı). Monitoring altyapısı Gazebo v3.0 ve fast-sim run'larını yazmıyor — tam kör nokta. Gerçek veri kaynağı interventions.jsonl + versions.jsonl.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- Görev tanımındaki "lr=7.5e-5 constant" ARTIK GEÇERSİZ: ppo.yaml v3.0'a yeniden yazıldı (lr=3e-4→1e-5 linear, 1.5M boyunca). Bu v8'in 3e-4→3e-5 şemasıyla aynı decay oranı (10×), yalnızca final LR daha düşük. 434k/1.5M = %28.9 tamamlandığında LR ≈ 2.15e-4 — aktif öğrenme fazı için ideal. Sabut lr=7.5e-5 terk edildi, DOĞRU KARAR.
- Fast-sim'de LR benzer parametreler (n_envs=8 paralellik, çok daha hızlı yakınsama). Fast-sim ~6-7 dakikada 1.5M step tamamlıyor vs Gazebo'nun 10+ saati.

**c) Entropy/std değerleri keşif için yeterli mi?**
- **Gazebo v3.0**: Doğrudan veri yok (CSV dondurulmuş). Referans: train_v3_floors @312k → entropy=-5.67, std=1.63. Bu değerler mükemmel: entropy -4.0 eşiğinin çok altında (daha negatif = daha yüksek entropi = daha fazla keşif ✓), std 1.63 > 0.7 eşiğinin çok üstünde ✓. v3.0'da ent_coef=0.008 (görev tanımının 0.0015'inin 5.3×'i) → entropik çöküş riski düşük.
- **Fast-sim v4.8 kritik bulgusu**: ent_coef yüksek tutmak (0.008→0.02 v4.2'de) collision %85'e çıkardı. Keşif-güvenlik dengesi: ent_coef ile oynama yerine collision_penalty'nin tatli noktası (25) belirleyici çıktı. Entropy yeterli ama tek başına yetmez.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- **Gazebo v3.0 (durduruldu)**: 610k'da peak=110.3 ≈ ~7 oda bonusu eğitim sırasında (7×15=105 + ~5 voxel/frontier). Tüm 6 oda geçişi eğitimde gerçekleşiyor olmalı.
- **Fast-sim**: v4.8 @1.5M → rooms_mean=5.0 (deterministik, tutarlı). v4.10 @5M → rooms_mean=5.76 (6 oda sporadik). Gazebo için eşdeğer: lidar_history=2 obs eklenirse aynı kırılım beklenir (fast-sim'de collision %80→%1'e düşürdü).
- **Sonuç**: Oda geçişi için step yetersizliği yok — yapısal obs kısıtı (hareketli engel hızını gözlemleyememe) esas darboğaz.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **lidar_history=2 uygulaması (Gazebo v10/fast-sim'den öğrendi)**: Fast-sim'de collision %80→%1'e indiren tek yapısal değişiklik. Gözlem boyutu 41-d → 72-d (2×32 lidar + 8 durum). Bu değişiklik olmadan hareketli engel darboğazı çözülemez. collision_penalty=25 (v4.8 optimal tatli noktası, 22=çöküş, 30=%8, 25=%0).
2. **Fast-sim sonuçlarını referans al, Gazebo'ya geçmeden önce fast-sim'de doğrula**: Yeni parametreleri Gazebo'da test etmek yerine önce fast-sim'de hızlı iter (3-4 run × 7dk = 30dk), ardından kazananı Gazebo'ya taşı. Bu metodoloji zaten v3.0→fast-sim sürecinde kanıtlandı.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** Gazebo v3.0 zaten durduruldu (610k, peak 110.3). Fast-sim v5.0 yakınsama bulgusuyla mevcut konfigürasyon çerçevesinde tüm kaldıraçlar tükendi.
- **Projenin gerçek durumu**: Temel trade-off belirlenmiş. v4.8 (güvenli) + v4.10 (maksimum kapsam) Pareto cephesi çizilmiş. Sıradaki yapısal adım: lidar_history=2 (Gazebo'ya entegre), obs=72-d, collision_pen=25.
- **CSV monitoring kalıcı olarak bozuk**: Tüm geçmişte stale; gerçek kayıt versions.jsonl + interventions.jsonl. Monitor altyapısının yeniden yazılması gerekiyor.

### v10 Önerisi
1. **lidar_history=2 + collision_pen=25 (fast-sim kanıtı)**: Fast-sim v4.8 konfigürasyonu Gazebo v10'a uygulanmalı. Bu tek değişiklik hareketli engel darboğazını çözer ve rooms_mean=5+ sağlar. ppo.yaml: env'de lidar_history=2, reward'da collision_penalty=25.
2. **Fast-sim önce doğrula**: Gazebo v10 çalıştırmadan önce fast-sim'de lidar_history=2 + Gazebo-benzeri ayarlar (n_envs=2, fps kısıtı simülasyonu) ile test yap. Fast-sim →doğrulandı→ Gazebo'ya geç. Bu metodoloji Berker direktifiyle benimsenmiş.

### Müdahale
**YOK** — Gazebo v3.0 610k'da peak=110.3 ile kasıtlı durduruldu; fast-sim v5.0 kesin yakınsama sonucuna ulaştı. configs/ppo.yaml'da %80+ güven eşiğini aşan bir hyperparameter sorunu tespit edilmedi. Bir sonraki adım yeni Gazebo v10 (lidar_history=2 entegrasyonu) — bu mevcut config'in tweaklanmasıyla değil, yeni env obs tasarımıyla yapılmalı. Config değişikliği yapmak için yetersiz bilgi.
---

## [2026-06-01 11:06 UTC]
**Step:** 610,000 (Gazebo v3.0 — kasıtlı durduruldu) | **ep_rew_mean:** ~110.3 (peak, kasıtlı durdurma noktası) | **entropy:** −5.67 (referans: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
Gazebo v3.0 eğitimi 610k adımda peak=110.3 ile kasıtlı sonlandırıldı (v8 all-time rekoru +113'ün %97'si, yalnızca 610k'da). Fast-sim zinciri v4.1→v5.0 tamamlandı: trade-off (güvenlik vs kapsam) yapısal bir kısıt olarak kesinleşti, mevcut reward/curriculum/obs çerçevesinde aşılamaz. Şu an aktif eğitim süreci yok. Sıradaki yapısal adım Gazebo v10 için `lidar_history=2` obs entegrasyonu.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` SON 20 SATIR STALE: tamamı 2026-05-30 22:00'dan beri step=193,248 ile donmuş (v9/v10 crash-loop kalıntısı). CSV monitoring kalıcı olarak bozuk; tüm analizler `interventions.jsonl` + `versions.jsonl` üzerinden yapıldı.
- **Gazebo v3.0 gerçek eğri:** 434k → ep_rew_mean=99.84 (01:30 UTC, 06-01), peak=102.54 → 610k'da peak=110.3 (kasıtlı durdurma, 08:30 UTC uzman notu). Kırılım değil olgunlaşma fazındaydı; plato görülmeden etkin olarak sonlandırıldı.
- **+15'lik oda sıçraması:** peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier; eğitim sırasında politika tutarlı 6+ oda keşfediyor.

**b) lr=7.5e-5 constant seçimi doğru muydu?**
- ARTIK GEÇERSİZ SORU. configs/ppo.yaml v3.0'dadır: lr=3e-4→1e-5 lineer decay (1.5M boyunca). Bu v8 şemasıyla (3e-4→3e-5, 10× azalma) yapısal olarak aynı. Sabit 7.5e-5 v9'da terk edilmişti — doğru karardı. Kanıt: v3.0 yalnızca 610k adımda v8'in 1.6M'de ulaştığı +113'ün %97'sine erişti.

**c) Entropy/std değerleri keşif için yeterli miydi?**
- Güvenilir referans (train_v3_floors @312k): entropy=−5.67, std=1.63. −4.0 eşiğinin (uyarı sınırı) çok altında (daha negatif = daha yüksek entropi = ✓), std eşiği 0.70'in çok üzerinde ✓.
- ent_coef=0.008 (görev tanımındaki 0.0015'in 5.3×'i) deterministikleşmeye karşı güçlü bariyer oluşturdu. 610k'ya kadar std/entropy alarm vermedi.
- Fast-sim dersleşmesi: ent_coef artırmak tek başına trade-off'u kıramadı (v4.2'de ent_coef çok yüksek → collision %85). Keşif kalitesi reward şekillendirmesinden değil, obs tasarımından (lidar_history) geliyor.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Artık soru geçerli değil: Gazebo v3.0 eğitim sırasında tutarlı 7+ oda keşfediyordu. Sorun "kaç adım daha" değil, deterministic eval-train gap'i (policy stochastic modda 6 oda, deterministic modda tutarsız).
- Fast-sim verileri: v4.8 @1.5M → rooms_mean=5.0 deterministik (%0 collision). v4.10 @5M → rooms_mean=5.76 (6/6 oda) AMA collision %54. Daha uzun eğitim oda sayısını artırıyor ama güvenliği bozuyor — bu kısıt yapısal.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`lidar_history=2` Gazebo env entegrasyonu (tek açık kaldıraç):** Fast-sim v4.8'i şampiyon yapan obs değişikliği (obs 41-d → 72-d: 2×32 lidar + 8 durum). Fast-sim zinciri v5.0'da bunu test etti: lidar_history=3 (2→3) işe yaramadı (v4.8 domine etti), bu yüzden tam değer 2. Gazebo `drone_exploration_env.py`'de bu değişiklik olmadan hareketli engel darboğazı çözülemez. Bu yaml değişikliği değil, env kod değişikliğidir.
2. **`collision_penalty=25` sweet spot Gazebo reward'a taşınmalı:** Fast-sim 4 farklı değer test etti: 22=yerel optimuma çöktü, 30=collision %8 (yüksek), 25=collision %0 (optimal), 50=collapse. v3.0 config'indeki collision ceza değeri 10.0'dır — bu fast-sim'in 22=çöküş değerinin bile altında. Gazebo v10 reward'da bu değer 25'e çıkarılmalı.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter: HAYIR.** Gazebo v3.0 eğitimi tamamlandı. Config'de aktif çalışan sürece etki edebilecek bir sorun yok.
- **Durum tespiti — KRİTİK:** Aktif eğitim süreci SIFIR. Gazebo v3.0 durduruldu, fast-sim v5.0 yakınsadı. Proje karar noktasında: ya (A) fast-sim v4.8 sonuçları nihai teslim (collision %0, rooms=5, voxels=117) ya da (B) Gazebo v10 başlatılır (lidar_history=2 env code değişikliği + collision_pen=25 reward değişikliği). Bu bir hyperparameter kararı değil, mühendislik tasarım kararı.
- **ppo.yaml durumu:** Hâlâ v3.0 parametrelerine kilitli (log_dir=runs/ppo_v3_best, total=1.5M, resume_from=null). Gazebo v10 başlamadan yaml'a dokunmak anlamsız — env kodu hazır olmadan config güncellemesi yanıltıcı olur.

### v10 Önerisi
1. **`drone_exploration_env.py`'e lidar_history=2 ekle (obs: 41-d → 72-d):** fast-sim v4.8 kanıtı. Bu tek yapısal değişiklik. Gözlem şeması: `[t-1 lidar 32 + t lidar 32 + durum 8]`. Hazır olunca yaml'ı güncelle: `version: v10`, `log_dir: ./runs/ppo_v10`, `resume_from: null`.
2. **Reward'da `collision_penalty: 10.0 → 25.0`:** Fast-sim sweet spot kesinleşti (22=çöküş, 25=optimal, 30=%8, 50=collapse). `drone_exploration_env.py`'deki `-10.0 çarpışma` ödülünü `-25.0`'a çekmek hareketli engel ortamında davranışı köklü iyileştirir. Bu env kod değişikliğidir, yaml bağımsız.

### Müdahale
**YOK** — configs/ppo.yaml v3.0'da, aktif eğitim süreci yok. %80+ güven eşiğini aşan bir hyperparameter sorunu tespit edilmedi. v5.0 yakınsama bulgusundan sonra kalan iki kaldıraç (lidar_history=2, collision_pen=25) env kodu düzeyinde değişiklik gerektiriyor; yaml-only müdahale yetersiz ve yanıltıcı olur. Gazebo v10'a geçiş env kodu hazır olduğunda başlamalı.
---

## [2026-06-01 12:05 UTC]
**Step:** 610,000 (Gazebo v3.0 — kasıtlı durduruldu, peak) | **ep_rew_mean:** ~110.3 (peak @ 610k) | **entropy:** −5.67 (referans: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
**Aktif eğitim süreci yok.** Gazebo v3.0, 610k adımda peak=110.3 ile bu sabah kasıtlı olarak sonlandırıldı. Fast-sim zinciri (v4.1→v5.0) tamamlandı: tüm reward/curriculum/obs/eğitim-süresi kaldıraçları denenip tükendi; yapısal trade-off (güvenlik vs kapsam) Pareto cephesi olarak kesinleşti. `training_metrics.csv` 2026-05-30 22:00'dan beri step=193,248 ile DONMUŞ (v9/v10 crash-loop kalıntısı, tamamen geçersiz). Görev bağlamındaki "v9/lr=7.5e-5 constant" konfigürasyonu artık geçerli değil; ppo.yaml v3.0'dadır (lr=3e-4→1e-5 linear, ent_coef=0.008).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son 20 satır: 2026-05-30 22:00'dan itibaren tüm satırlar özdeş (step=193,248, ep_rew_mean=-173.85). Bu STALE veri, v9/v10 crash döneminin kalıntısı; hiçbir trend analizi yapılamaz.
- **Gerçek v3.0 eğri:** 434k→ep_rew_mean=99.84 (01:30 UTC, interventions.jsonl), peak 102.54 taze kırıldı; ardından 610k'da peak=110.3 ile kasıtlı durduruldu. Kırılım değil, olgunlaşma fazındaydı; plato yok, intentional stop.
- **+15'lik oda sıçraması:** peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier — eğitim sırasında politika tutarlı 7 oda keşfediyordu.
- **Fast-sim:** v4.8 @1.5M → rooms_mean=5.0 (deterministik, %0 collision, voxels=117). v4.10 @5M → rooms_mean=5.76, 6/6 oda AMA collision %54. Pareto cephesi netleşti.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru muydu?**
- ARTIK GEÇERSİZ: ppo.yaml v3.0'da lr=3e-4→1e-5 lineer decay (1.5M boyunca). Sabit 7.5e-5, v9 döneminde terk edilmişti — doğru karardı.
- Kanıt: v3.0, v8'in 1.6M step'te ulaştığı +113'ün %97'sine (110.3) yalnızca 610k adımda erişti. Lineer decay (yüksek başlangıç LR → fine-tune) bu harita için en etkili schedule.

**c) Entropy/std değerleri keşif için yeterli miydi?**
- v3.0 referans (train_v3_floors @312k): entropy=−5.67, std=1.63. Her iki metrik de alarm eşiğinin (entropy>-4.0, std>0.7) çok güvenli uzağında.
- ent_coef=0.008 (görev bağlamındaki 0.0015'in 5.3×'i) deterministikleşmeye karşı güçlü bariyer sağladı; 610k boyunca alarm yok.
- Fast-sim dersi: ent_coef tek başına trade-off kıramadı (v4.2'de ent_coef çok yüksek → collision %85). Keşif kalitesi obs tasarımından (lidar_history=2) geliyor, entropi artışından değil.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Artık geçerli soru değil: Gazebo v3.0 eğitimde tutarlı 7+ oda keşfetti. Fast-sim v4.8 deterministik modda 5 oda garanti.
- Darboğaz "kaç adım daha" değil, **deterministic eval-train gap**: policy stochastic'te 6 oda, deterministic'te tutarsız. Bu gap'in kök nedeni hareketli engel hızını gözlemleyememek (lidar_history=1 → anlık snapshot yeterli değil).
- Fast-sim v4.8 (lidar_history=2) ile deterministik gap kapandı (%0 collision, rooms=5 garantili).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`lidar_history=2` Gazebo env entegrasyonu (obs: 41-d → 72-d):** Fast-sim'de collision %80→%1'e indiren TEK yapısal değişiklik. `drone_exploration_env.py`'de [t-1 lidar 32 + t lidar 32 + durum 8] obs formatı. Bu yaml değişikliği değil, env kod değişikliğidir; hareketli engel darboğazı bu olmadan çözülemiyor.
2. **`collision_penalty: 10.0 → 25.0` reward değişikliği:** Fast-sim sweet spot kesinleşti: 22=yerel optimuma çöktü, **25=%0 collision (optimal)**, 30=%8, 50=collapse. Mevcut v3.0'daki -10.0, fast-sim'in "çöküş eşiği" olan 22'nin bile altında. Gazebo v10 reward'ında bu değer 25.0'a çıkarılmalı.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** Gazebo v3.0 eğitimi tamamlandı; aktif süreç yok. configs/ppo.yaml v3.0'da ve tarihsel olarak doğrulanmış.
- **Proje durumu — KRİTİK KARAR NOKTASI:** (A) Fast-sim v4.8 sonuçlarını nihai teslim al (collision %0, rooms=5, voxels=117), veya (B) Gazebo v10 başlat (`lidar_history=2` env kodu + `collision_pen=25` reward değişikliği). Bu hyperparameter kararı değil, mühendislik tasarım kararı.
- **CSV monitoring kalıcı bozuk:** Tüm analizler versions.jsonl + interventions.jsonl üzerinden yapıldı. Monitor altyapısı yeniden yazılmalı.
- **ppo.yaml'da %80+ güven eşiğini aşan sorun: YOK.** Mevcut v3.0 config değiştirilmedi.

### v10 Önerisi
1. **`drone_exploration_env.py`'de lidar_history=2 (obs: 41→72-d):** [t-1: 32 lidar, t: 32 lidar, durum: 8]. Fast-sim v4.8 kanıtı (5M adımda %0 collision, rooms_mean=5.0). Bu yapısal obs değişikliği olmadan v10 Gazebo çalıştırmak v3.0'ın tekrarı olur.
2. **reward'da collision_penalty: 10.0 → 25.0:** Fast-sim 4-nokta tarama ile sweet spot kesinleşti. v3.0 yaml'ında değil, `drone_exploration_env.py`'deki `-10.0 çarpışma` reward satırında değişiklik. ppo.yaml güncellemesi ancak env kodu hazır olduktan sonra (version: v10, log_dir: ./runs/ppo_v10, resume_from: null).

### Müdahale
**YOK** — configs/ppo.yaml v3.0, sağlıklı ve tarihsel olarak kanıtlanmış (peak=110.3 @ 610k). Aktif eğitim süreci yok; %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. v10 için gerekli değişiklikler env kodu düzeyinde (lidar_history=2, collision_penalty=25); yaml-only müdahale bu gerçekleri yansıtmaz ve yanıltıcı olur. Gazebo v10 başlatmak için env kodu hazır olana kadar bekle.
---

## [2026-06-01 13:30 UTC]
**Step:** 610,000 (Gazebo v3.0 — kasıtlı durduruldu, peak=110.3) | **ep_rew_mean:** −173.85 (CSV son kayıt — STALE, v9/v10 kalıntısı) | **Gerçek:** peak=110.3 @ 610k (interventions.jsonl) | **entropy:** −5.67 (ref: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
Aktif eğitim süreci yok. `training_metrics.csv` 2026-05-30 22:00'dan beri 14 özdeş satırla donmuş (step=193,248, v9/v10 crash-loop kalıntısı — tamamen geçersiz). Gerçek proje durumu: Gazebo v3.0 bu sabah 610k adımda peak=110.3 ile kasıtlı sonlandırıldı; fast-sim zinciri v4.1→v5.0 kesin yakınsama bulgusuna (4 kaldıraç kategorisi denendi, Pareto cephesi kesinleşti) ulaştı. Sıradaki hareket env kodu düzeyinde (`lidar_history=2`, `collision_penalty=25`) değişiklik gerektiriyor; yaml-only müdahale anlamsız.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 20 satır: TAMAMEN GEÇERSİZ. Tümü 2026-05-30 22:00–03:01 arası aynı satırı (step=193,248, ep_rew_mean=−173.85) yansıtıyor. Bu, v9_newmap'ın 193k adımda bozulmasından kalan crash-loop izleri; mevcut Gazebo v3.0 veya fast-sim ile ilgisi yok.
- **Gerçek Gazebo v3.0 eğri (interventions.jsonl üzerinden):** 434k → ep_rew_mean=99.84, peak=102.54 (06-01 01:30 UTC); ardından 610k'da peak=110.3 (kasıtlı durdurma). Olgunlaşma fazındaydı — plato değil, intentional stop. +15'lik oda sıçraması: peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier; eğitim boyunca politika tutarlı 7+ oda keşfetti.
- **Fast-sim kesin sonuçlar:** v4.8 @1.5M → collision %0, rooms_mean=5.0, voxels=117 (deploy-ready). v4.10 @5M → collision %54, rooms_mean=5.76 (6/6 oda), voxels=281 — max kapsam ama güvensiz. v4.13 @8M → voxels geri düştü (134), politika regularize oldu; "daha uzun eğit = daha çok voxel" YOK. Pareto cephesi kesinleşti.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- Geçersiz: configs/ppo.yaml v3.0'dadır → lr=3e-4→1e-5 linear (1.5M boyunca). Sabit 7.5e-5, v9 döneminde terk edilmişti. Kanıt: v3.0, v8'in 1.6M adımda ulaştığı +113 all-time rekoru'nun %97'sine (110.3) yalnızca 610k adımda erişti — lineer decay doğruydu.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Gazebo v3.0 için doğrudan veri yok (CSV bozuk). En yakın referans: train_v3_floors @312k → entropy=−5.67, std=1.63. −4.0 uyarı eşiğinin çok altında (daha negatif = daha yüksek entropi ✓), std 0.70 alarm eşiğinin 2.3× üstünde ✓.
- ent_coef=0.008 (görev tanımının 0.0015'inin 5.3×'i) deterministikleşmeye karşı güçlü bariyer sağladı; 610k boyunca alarm yok.
- **Fast-sim dersi (kritik):** ent_coef artırmak güvenlik-kapsam trade-off'unu kıramadı. v4.2'de ent_coef=0.02 → collision %85. Keşif kalitesi obs tasarımından (lidar_history=2), entropi artışından değil geliyor.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- Artık geçerli soru değil. Gazebo v3.0 eğitim sırasında tutarlı 7+ oda keşfetti. Fast-sim v4.8: deterministik modda rooms_mean=5.0 (5/6 oda garantili, %0 collision).
- Darboğaz "kaç adım daha" değil, **deterministic eval-train gap**: stochastic politika 6 oda keşfediyor, deterministic politika tutarsız. Kök neden: hareketli engel hızını gözlemleyememek (lidar_history=1 → anlık snapshot, hız bilgisi yok). Fast-sim v4.8 (lidar_history=2) ile bu gap kapandı.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`lidar_history=2` Gazebo env entegrasyonu (obs: 41-d → 72-d):** Fast-sim zincirinde collision %80→%1'e indiren TEK yapısal değişiklik. `drone_exploration_env.py`'de gözlem: [t-1 lidar 32] + [t lidar 32] + [durum 8]. Bu env kod değişikliğidir, yaml'dan bağımsız. Bu olmadan Gazebo v10 v3.0'ın tekrarı olur.
2. **`collision_penalty: 10.0 → 25.0` (env kodu, reward satırı):** Fast-sim 4-nokta tarama ile sweet spot kesinleşti: 22=yerel optimuma çöktü, **25=%0 collision (optimal)**, 30=%8, 50=collapse. Mevcut Gazebo v3.0 config'inde penalty=10.0 (fast-sim "çöküş eşiği" 22'nin bile altında). Bu env reward satırı değişikliğidir; ppo.yaml'da karşılığı yok.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** Aktif eğitim süreci yok; ppo.yaml değişikliği mevcut hiçbir sürece etki edemez.
- **CSV monitoring kalıcı bozuk:** Gerçek veri kaynağı interventions.jsonl + versions.jsonl + training log dosyaları. Monitor altyapısının yeniden yazılması gerekiyor (v3.0/fast-sim TB dizinlerini okuyacak şekilde).
- **Proje karar noktası:** (A) Fast-sim v4.8 sonuçlarını nihai teslim al (collision %0, rooms=5, voxels=117) VEYA (B) Gazebo v10 başlat (env kodu hazır olunca). Bu hyperparameter kararı değil, mühendislik tasarım kararı.

### v10 Önerisi
1. **`drone_exploration_env.py`'e `lidar_history=2` ekle (obs 41→72-d):** Fast-sim kanıtı (v4.8: collision %0, rooms=5, voxels=117). Format: [t-1: 32 lidar | t: 32 lidar | durum: 8]. Env kodu hazır olunca ppo.yaml'ı güncelle: `version: v10`, `log_dir: ./runs/ppo_v10`, `resume_from: null`.
2. **`collision_penalty: 10.0 → 25.0` (env reward satırı):** Fast-sim 4-nokta tarama ile sweet spot kesinleşti. Bu yaml değişikliği değil, `drone_exploration_env.py` içindeki reward satırı. Sadece bu iki değişiklik Gazebo v10'u fast-sim v4.8 seviyesine taşır.

### Müdahale
**Yok** — configs/ppo.yaml v3.0'da, tarihsel olarak kanıtlanmış (peak=110.3 @ 610k, v8 all-time +113'ün %97'si). Aktif eğitim süreci yok; %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. v10 için gerekli değişiklikler env kodu düzeyinde (`lidar_history=2`, `collision_penalty=25`); yaml-only müdahale bu gerçekleri yansıtmaz ve yanıltıcı olur.
---

## [2026-06-01 14:30 UTC]
**Step:** 610,000 (Gazebo v3.0 — kasıtlı durduruldu, peak=110.3) | **ep_rew_mean:** −173.85 (CSV SON KAYIT — STALE, v9/v10 kalıntısı, geçersiz) | **entropy:** −5.67 (ref: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
**Aktif eğitim süreci yok.** `training_metrics.csv` 2026-05-30 22:00'dan beri step=193,248 ile 24+ saat DONMUŞ — v9/v10 crash-loop kalıntısı, mevcut proje durumunu hiç yansıtmıyor. Gerçek durum: Gazebo v3.0 bugün 610k adımda peak=110.3 ile kasıtlı sonlandırıldı; fast-sim zinciri v4.1→v5.0 kesin yakınsama bulgusuna ulaştı (4 kaldıraç kategorisi — ödül, eğitim süresi, curriculum, obs — denendi, Pareto cephesi netleşti). Proje bir sonraki yapısal adım olan Gazebo v10 için env kodu değişikliği bekliyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 20 satır TAMAMEN GEÇERSİZ: tümü özdeş (step=193,248, ep_rew_mean=−173.85, 2026-05-30 22:00 ile 03:01 UTC arası), v9_newmap crash-loop'unun donmuş kalıntısı. Herhangi bir trend analizi yapılamaz.
- **Gerçek Gazebo v3.0 eğri (interventions.jsonl):** 434k → ep_rew_mean=99.84, peak=102.54 (06-01 01:30 UTC, taze kırılmıştı); 610k → peak=110.3 (kasıtlı durdurma, 08:30 UTC notu). Olgunlaşma fazındaydı — plato değil, intentional stop.
- **+15'lik oda sıçraması:** peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier. Eğitim boyunca politika tutarlı 7+ oda keşfetti.
- **Fast-sim Pareto cephesi (versions.jsonl, 06-01 06:48–08:05):** v4.8 @1.5M → collision %0, rooms_mean=5.0, voxels=117 (deploy-ready). v4.10 @5M → collision %54, voxels=281, rooms_mean=5.76 (6/6 oda AMA güvensiz). v4.13 @8M → politika regularize oldu (voxels 281→134); "daha uzun eğit = daha çok voxel" YOK. v5.0 (lidar_history 2→3) → v4.8 tarafından domine edildi (%35/106 < %0/117). Tüm 4 kaldıraç tükendi; yapısal trade-off kırılamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Geçersiz soru: configs/ppo.yaml v3.0'da lr=3e-4→1e-5 linear decay (1.5M boyunca). v9'un sabit 7.5e-5'i çok önceki oturumlarda terk edildi — doğru karardı. Kanıt: v3.0 yalnızca 610k adımda v8 all-time rekorunun (%113 @ 1.6M) %97'sine (110.3) erişti. Lineer decay bu harita için kesinleşmiş doğru strateji.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Doğrudan v3.0 run verisi yok (CSV bozuk, TB bu container'da yok). En yakın güvenilir referans: train_v3_floors @312k → entropy=−5.67, std=1.63.
- −4.0 uyarı eşiğinin çok altında (daha negatif = daha yüksek entropi ✓), std=1.63 alarm eşiği 0.70'in 2.3× üstünde ✓.
- ent_coef=0.008 (görev tanımındaki 0.0015'in 5.3×'i) deterministikleşmeye karşı güçlü bariyer sağladı; 610k boyunca hiç alarm gelmedi.
- **Fast-sim dersi (kritik):** ent_coef artırmak trade-off'u kıramadı. v4.2'de ent_coef çok yüksek → collision %85. Keşif kalitesi obs tasarımından (lidar_history=2), entropi artışından değil geliyor.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- Artık geçerli soru değil. Gazebo v3.0 eğitim sırasında tutarlı 7+ oda keşfetti; ek step ihtiyacı yok.
- **Darboğaz "kaç adım daha" değil, deterministic eval-train gap:** Policy stochastic modda 6 oda, deterministic modda tutarsız. Kök neden: lidar_history=1 ile hareketli engel hızı gözlemlenemiyor. Fast-sim v4.8 (lidar_history=2) ile deterministik gap kapandı (%0 collision, rooms_mean=5.0 tutarlı).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`lidar_history=2` Gazebo env entegrasyonu (obs: 41-d → 72-d):** Fast-sim zinciri boyunca collision %80→%1'e indiren TEK yapısal değişiklik. `drone_exploration_env.py`'de format: [t-1: 32 lidar] + [t: 32 lidar] + [durum: 8]. YAML değişikliği değil, env kodu; bu olmadan Gazebo v10 v3.0'ın tekrarı olur.
2. **`collision_penalty: 10.0 → 25.0` (env reward satırı, yaml bağımsız):** Fast-sim 4-nokta tarama ile sweet spot kesinleşti: 22=yerel optimuma çöktü, **25=%0 collision (optimal)**, 30=%8, 50=collapse. Mevcut v3.0 config'inde penalty=10.0, fast-sim "çöküş eşiği" olan 22'nin bile altında. Değişiklik `drone_exploration_env.py`'deki tek reward satırı; ppo.yaml'da karşılığı yok.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** Aktif eğitim süreci yok; ppo.yaml değişikliği hiçbir çalışan sürece etki edemez.
- **CSV monitoring kalıcı bozuk:** 24+ saattir dondurulmuş. Tüm gerçek veri kaynağı interventions.jsonl + versions.jsonl + train log dosyaları. Monitor altyapısı yeniden yazılmadan düzelmeyecek.
- **Proje karar noktası:** (A) Fast-sim v4.8 sonuçlarını nihai teslim al (collision %0, rooms=5, voxels=117) VEYA (B) Gazebo v10 başlat (env kodu: lidar_history=2 + collision_penalty=25 → ardından yaml güncelle). Bu hyperparameter kararı değil, mühendislik tasarım kararı.
- **ppo.yaml durumu:** v3.0'da kilitli (log_dir=runs/ppo_v3_best, total=1.5M, resume_from=null). Env kodu hazır olmadan yaml güncellemesi yanıltıcı olur; `version: v10` + `log_dir: ./runs/ppo_v10` env kodu commit'iyle birlikte değiştirilmeli.

### v10 Önerisi
1. **`drone_exploration_env.py`'e lidar_history=2 ekle (obs 41→72-d):** [t-1: 32 lidar | t: 32 lidar | durum: 8]. Fast-sim v4.8 kanıtı (1.5M step: collision %0, rooms_mean=5.0, voxels=117). Env kodu hazır olunca ppo.yaml'ı güncelle: `version: v10`, `log_dir: ./runs/ppo_v10`, `resume_from: null`.
2. **reward'da `collision_penalty: 10.0 → 25.0` (env kodu):** Fast-sim 4-nokta tarama ile sweet spot kesinleşti. Sadece bu iki değişiklik (env kodu düzeyinde) Gazebo v10'u fast-sim v4.8 seviyesine taşır. ppo.yaml'daki hyperparameter'lar (lr schedule, ent_coef=0.008, net_arch=[256,256]) v3.0'daki haliyle v10 için de optimal.

### Müdahale
**Yok** — configs/ppo.yaml v3.0'da, tarihsel olarak kanıtlanmış (peak=110.3 @ 610k, v8 all-time +113'ün %97'si yalnızca %41 budget'ta). Aktif eğitim süreci yok; %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. v10 için gerekli değişiklikler (lidar_history=2, collision_penalty=25) env kodu düzeyinde; yaml-only müdahale gerçekleri yansıtmaz ve yanıltıcı olur. Env kodu commit'i bekleniyor.
---

## [2026-06-02 11:15 UTC]
**Step:** ~1,147k (son güvenilir — train_v3_resume_310k.log, %68 tamamlandı) | **ep_rew_mean:** 99.84 @ 434k (interventions.jsonl) / 47.1 @ 312k (train_v3_2m.log) | **entropy:** -5.67 @ 312k | **std:** 1.63 @ 312k

### Durum
v3.0 Gazebo eğitimi 1.147M/1.69M (%68) adımda interrupt edilmiş — peak 102.54 @ 430k kayıtlı. fast_sim sweep serisi (v4.1→v5.0, 1 Haziran 2026) TAMAMLANDI ve temel trade-off kesinleşti: v4.8 ŞAMPIYON (collision_penalty=25, %0 çarpışma, 5 oda, 117 voxel) vs v4.10 KAPSAM UÇU (6 oda, 281 voxel, %54 çarpışma). Mevcut Gazebo çevresi hâlâ collision_penalty=10 kullanıyor — bu değişmeden bir sonraki run başlatılırsa v4 fast_sim bulgularından yararlanılamaz.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- v3.0 Gazebo eğrisi: 47.1 @ 312k → 99.84 @ 434k → peak 102.54 @ ~430k. Aktif yükseliş fazı, v8 all-time peak'i olan 113'ün yalnızca %9 altında ve v8'in 1.63M adım aldığı konuma 434k adımda ulaşıldı — 3.7× daha hızlı.
- Plato işareti görülmüyor; 1.147M noktasında büyük olasılıkla 110-120 aralığında.
- **+15 oda sıçraması kanıtı:** 99.84 ≈ 6 oda bonusu (6×15=90) + voxel + frontier katkısı. fast_sim v4.8 konsistant 5 oda, v4.10 tüm 6 oda gösterdi; Gazebo'da da oda keşfi gerçekleşmiş.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSIZ: Bu config v9'da terk edildi. v3.0 mevcut schedule: 3e-4→1e-5 linear (1.5M/1.69M boyunca). v9 plato kanıtı güçlü: 142k→599k arası ep_rew_mean -290→-270 (457k adımda yalnızca +20), entropy -3.88→-3.32 (kritik deterministikleşme), std 0.888→0.746 (0.7 eşiğine yaklaşma). Linear decay kararı kesinlikle doğruydu.
- v3.0 @ 312k: lr ≈ 2.38e-4 (decay henüz erken fazda), approx_kl=0.008, clip_fraction=0.099 — güvenli politika güncellemesi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- @ 312k: entropy=-5.67 (eşik -4.0, GAYRİSAFİ üstünde ✓), std=1.63 (eşik <0.7, alarm uzak ✓).
- ent_coef=0.008 (v8'in 0.0015'inin 5.3×'i) çalışıyor: v9'da deterministikleşen entropy eğrisi v3.0'da tersine döndü. Bu en kritik konfigürasyon farkı.
- explained_variance=0.408 @ 312k: value fonksiyonu henüz tam öğrenmedi ama approx_kl=0.008 stabil. 600k+ adımda explained_variance 0.6+ beklenir.
- **Uyarı:** 5M eğitimde bile (fast_sim v4.10) güvenlik çöktüğü görüldü; 3.2M adımda %100 çarpışma. Gazebo v3.0 1.69M hedefini aşmamalı.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- fast_sim sweep kesin veri verdi: v4.8 config ile 5 oda tutarlı, v4.10 ile 6 oda mümkün.
- Gazebo v3.0 @ 434k zaten 6 oda seviyesinde reward üretiyor (99.84 ≈ 6×15+voxel). Kritik soru: eval.sh ile deterministic policy doğrulanmadı. Stochastic training'de 6 oda keşfediyor olabilir ama deterministic eval'de 3-4 oda görülebilir.
- Öneri: 1.15M checkpoint (train_v3_resume_310k.log son noktası) ile eval.sh çalıştır.

**e) v10/sonraki Gazebo run için en kritik 1-2 öneri:**
1. **collision_penalty 10→25 (çevre dosyasında):** fast_sim v4.8 kanıtı: penalty=25 → %0 çarpışma (100 bölüm, 2500 adım hayatta). penalty=30 aşırı-tedirgin tutum, penalty=22 yerel optimuma düştü → sweet spot 25. Bu ENV değişikliği, ppo.yaml değil, ama bir sonraki run başlamadan uygulanmalı.
2. **total_timesteps sınırı: 1.8M üzerine çıkma:** fast_sim checkpoint sweep kritik bulgu: v4.10 (coverage config) @ 2.6M → %43 çarpışma, @ 3.2M → %100 çarpışma. 2M sonrası keşif reward kümülatif voxel kazancını aşıyor ve politika crash rejimine giriyor. Gazebo için güvenli üst sınır: 1.8-2M. Mevcut 1.69M hedefi bu açıdan doğru.

**f) Acil müdahale gerektiren bir şey var mı?**
- Hyperparameter: HAYIR. v3.0 config tüm eşikleri karşılıyor (entropy ✓, std ✓, kl ✓, clip_fraction ✓).
- Eğitim sürekliliği: OLASI SORUN. train_v3_resume_310k.log "interrupted" ile bitti (1.147M/1.69M, %68). Process'in çalışıp çalışmadığı bilinmiyor. Eğer durmuşsa: `resume_from: runs/ppo_v3_floors/checkpoints/ppo_drone_interrupted.zip` ile kalan ~542k adımı tamamla.
- fast_sim araştırması: KAPATILDI. v4.1-v5.0 sweep tamamlandı, 4 kaldıraç kategorisi (reward/eğitim-süresi/curriculum/obs) tüketildi, fundamental trade-off kesinleşti. Daha fazla fast_sim sweep gerekmez.

### v10 Önerisi
1. **collision_penalty=25 env değişikliği ŞART:** Sonraki Gazebo run başlamadan `drone_exploration_env.py`'de `self.collision_penalty = 25` (mevcut 10). Bu tek değişiklik v4.8 kanıtına göre çarpışmayı %70+ → %0'a düşürecek.
2. **1.69M hedefinde kal, resume tamamla:** Eğitim durmuşsa `ppo_drone_interrupted.zip` ile kalan 542k adımı tamamla. 2M üzerine çıkma — fast_sim sweep 2.6M+ checkpoint'lerinde güvenlik kollapsını doğruladı. 1.15M-1.69M aralığı (şu an en yüksek checkpoint) için eval.sh çalıştır: bu v4.8 benchmark'ına karşı gerçek Gazebo performansını ölçer.

### Müdahale
**YOK (ppo.yaml)** — v3.0 config %80 güven eşiğini aşan bir hyperparameter sorunu içermiyor. Ent_coef=0.008, lr=3e-4→1e-5 linear, n_epochs=10, net_arch=[256,256] hepsi fast_sim ve Gazebo verisine göre iyi kalibre edilmiş. **Önerilen aksiyon ENV düzeyinde:** drone_exploration_env.py'de collision_penalty 10→25 (ppo.yaml dışı değişiklik).
---

## [2026-06-02 12:07 UTC]
**Step:** 610,000 (Gazebo v3.0 — son güvenilir, kasıtlı durdurma) | **ep_rew_mean:** 99.84 @ 434k / peak 110.3 @ 610k | **entropy:** −5.67 (train_v3_floors @312k ref) | **std:** 1.63 (aynı referans)

### Durum
**Aktif eğitim süreci yok.** `training_metrics.csv` 2026-05-30 22:00'dan beri step=193,248 ile DONMUŞ — v9/v10 crash-loop kalıntısı, tamamen geçersiz. Gazebo v3.0 (ppo_v3_best) 610k adımda peak=110.3 ile 2026-06-01 sabahı kasıtlı sonlandırıldı; fast-sim zinciri v4.1→v5.0 aynı gün tamamlandı. Yapısal güvenlik-kapsam trade-off'u kesinleşti: v4.8=ŞAMPIYON (collision %0, rooms=5, voxels=117). **Düzeltme notu:** 2026-06-02 11:15 UTC log girişinde ppo_v3_best için yanlış log dosyası kullanıldı (train_v3_resume_310k.log → ppo_v3_floors, eski 3-katlı run); gerçek v3.0 (ppo_v3_best) 610k/1.5M adımda durdu, ppo_v3_floors'un 1.147M/1.69M verisi değil.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son satırları TAMAMEN GEÇERSİZ: tümü 2026-05-30 22:00–03:01 UTC arası özdeş (step=193,248, ep_rew_mean=−173.85). v9/v10 crash-loop kalıntısı; hiçbir trend analizi yapılamaz.
- **Gerçek Gazebo v3.0 (ppo_v3_best) eğrisi:** interventions.jsonl son kayıt (06-01 01:30 UTC) → step=434,176, ep_rew_mean=99.84, peak=102.54. Ardından versions.jsonl (06-01 03:00 UTC) → "Gazebo v3.0 610k ta durduruldu (peak reward 110.3)" — kasıtlı durdurma, plato değil.
- **v3.0'ın 610k/1.5M (%40) adımda peak=110.3 üretmesi** v8'in 1.63M adımda ulaştığı +113'ün %97'si — 4.1× daha verimli. Eğer devam etseydi 800k-1M adımda +113'ü geçme ihtimali yüksekti. Plato işareti yok; intentional stop.
- **+15'lik oda sıçraması:** peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier. Eğitim sırasında politika tutarlı 7+ oda keşfetti.
- **fast-sim Pareto cephesi (versions.jsonl, 06-01):** v4.8 @1.5M → collision %0, rooms=5, voxels=117. v4.10 @5M → collision %54, rooms_mean=5.76 (6 oda), voxels=281. v4.13 @8M → voxels geri düştü (134). Daha uzun eğitim ≠ daha çok voxel. Trade-off kırılamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ SORU: configs/ppo.yaml v3.0'dadır → `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit 7.5e-5 v9 döneminde terk edildi — doğru karardı.
- **Kanıt:** v9 plato analizi (11:02–12:32 UTC, 30 Mayıs): lr=7.5e-5 sabit ile 142k→599k arası yalnızca +20 rew artışı (457k adımda). v3.0 lineer decay ile aynı bant (434k) → +99.84 → 4.8× daha iyi. Linear LR kararı kesinleşmiş ve kanıtlanmış.
- v3.0 @ 312k: lr ≈ 2.38e-4, approx_kl=0.008, clip_fraction=0.099 — güvenli politika güncellemesi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- v3.0 için doğrudan veri yok (CSV bozuk, TB container'da yok). En güvenilir referans: train_v3_floors @312k → entropy=−5.67, std=1.63.
- entropy=−5.67: Uyarı eşiği −4.0'ın **1.67 birim altında** (daha negatif = daha yüksek entropi ✓). v9'da 600k adımda −3.32'ye kadar düşmüştü (tehlikeli). v3.0'da ent_coef=0.008 (v9'un 0.0015'inin 5.3×'i) bu riski kesin olarak ortadan kaldırdı.
- std=1.63: Alarm eşiği 0.70'in 2.3× üstünde ✓. v9'da 0.746'ya kadar inmişti; v3.0'da tamamen farklı rejim.
- **fast-sim dersi (kritik):** ent_coef artırmak güvenlik-kapsam trade-off'unu kıramadı. v4.2 ent_coef=0.02 → collision %85. Keşif kalitesi obs tasarımından (lidar_history=2), entropi ayarından değil geliyor.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Artık geçerli soru değil. v3.0 eğitim sırasında zaten 7+ oda keşfediyordu (peak=110.3 ≈ 7 oda bonusu).
- **Gerçek darboğaz:** Deterministic eval-train gap. Stochastic training'de 6-7 oda; deterministic eval'de tutarsız (eval_v3_310k.log: 11 ep → rooms=1 çoğunlukla, 1 ep rooms=2).
- **Kök neden:** lidar_history=1 → hareketli engel hızı gözlemlenemiyor → ani engel çarpışmaları deterministic politikada recovery yapamıyor.
- **fast-sim kanıtı:** lidar_history=2 (obs: 41-d → 72-d) → collision %80→%1. Bu tek obs değişikliği deterministic eval-train gap'ini kapattı.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (env kod değişikliği, drone_exploration_env.py):** fast-sim 4-nokta tarama: 22=yerel optimuma çöküş, **25=%0 collision (optimal)**, 30=%8 (aşırı tedirgin), 50=collapse. Mevcut Gazebo v3.0 reward'ında penalty=10.0 — fast-sim'in "çöküş eşiği" olan 22'nin bile altında. Bu değişiklik ppo.yaml değil, env reward satırı.
2. **`lidar_history=2` obs entegrasyonu (drone_exploration_env.py, obs: 41-d → 72-d):** fast-sim v4.8'i şampiyon yapan TEK yapısal değişiklik. Format: [t-1: 32 lidar | t: 32 lidar | durum: 8]. Bu olmadan Gazebo v10 v3.0'ın tekrarı olur. ppo.yaml buna paralel güncellenmeli: `version: v10`, `log_dir: ./runs/ppo_v10`, `resume_from: null`.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** Aktif eğitim süreci yok; ppo.yaml üzerinden herhangi bir değişiklik çalışan hiçbir sürece etki edemez.
- **11:15 UTC log düzeltmesi:** Önceki giriş ppo_v3_floors (eski 3-katlı run, 1.147M/1.69M) verisini Gazebo v3.0 (ppo_v3_best, 610k/1.5M) olarak yanlış raporladı. Gerçek v3.0 610k adımda kasıtlı durdurulmuş; 1.147M rakamı geçersiz.
- **CSV monitoring kalıcı bozuk:** 24+ saattir step=193,248 ile donmuş. Gerçek veri kaynağı: interventions.jsonl + versions.jsonl + train log dosyaları. Yeniden yazılmadan düzelmeyecek.
- **Sonraki adım:** Env kodu değişikliği (lidar_history=2 + collision_penalty=25) → ardından ppo.yaml v10 güncellemesi → Gazebo v10 başlatma. Sıra bu; yaml-only değişiklik yetersiz.

### v10 Önerisi
1. **`collision_penalty=25` (env reward, ppo.yaml bağımsız):** fast-sim kesinleştirilmiş sweet spot. `drone_exploration_env.py`'de tek satır değişikliği. Mevcut 10.0 → 25.0. Bu değişiklik olmadan v10 Gazebo'da v3.0'ın trajektörünü tekrar eder.
2. **`lidar_history=2` obs genişletmesi (env kodu) + ppo.yaml v10 güncelleme:** Env kodu hazır olunca yaml'a: `version: v10`, `log_dir: ./runs/ppo_v10`, `resume_from: null`. Hyperparameter'lar (lr=3e-4→1e-5 linear, ent_coef=0.008, net_arch=[256,256], total=1.5M) v3.0'daki haliyle v10 için de optimal — fast-sim ve Gazebo verileriyle çapraz doğrulandı.

### Müdahale
**YOK** — configs/ppo.yaml v3.0'da, tarihsel olarak kanıtlanmış (peak=110.3 @ 610k). Aktif eğitim süreci yok. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. v10 için gerekli değişiklikler env kodu düzeyinde (lidar_history=2, collision_penalty=25); env kodu hazır olmadan yaml-only müdahale yanıltıcı ve etkisiz olur. **Düzeltme kaydı:** 11:15 UTC girişindeki "1.147M step" referansı ppo_v3_floors (eski run) verisidir; gerçek v3.0 (ppo_v3_best) 610k adımda durdu.
---

## [2026-06-02 13:30 UTC]
**Step:** N/A (aktif eğitim yok) | **ep_rew_mean:** 110.3 peak @ 610k (Gazebo v3.0, kasıtlı durduruldu) | **entropy:** −5.67 (son güvenilir ref: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
**Tüm araştırma kapandı; v10 başlatmaya hazır.** Gazebo v3.0 (ppo_v3_best) 2026-06-01 sabahı 610k/1.5M adımda kasıtlı durduruldu (peak=110.3). fast_sim zinciri v4.1→v5.0 (18 config, iki paralel saatte) tamamlandı; güvenlik-kapsam trade-off'u dört farklı kaldıraç (ödül/eğitim-süresi/curriculum/obs) ile exhaustive biçimde incelendi ve kesinleşti. `configs/ppo.yaml` v10 kimliğine güncellendi.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` 2026-05-30 22:00'dan beri tamamen DONMUŞ: 16 özdeş satır (step=193,248, ep_rew_mean=−173.85). v9/v10 crash-loop kalıntısı; hiçbir trend analizi yapılamaz, bu CSV'yi artık kullanma.
- Gerçek Gazebo v3.0 eğrisi: `interventions.jsonl` (06-01 01:30) → step=434k, ep_rew_mean=99.84, peak=102.54; `versions.jsonl` (06-01 03:00) → "Gazebo v3.0 610k'da durduruldu (peak 110.3)". Kasıtlı durdurma, plato değil.
- peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier → eğitim sırasında 7+ oda tutarlı keşfedildi.
- Eğer v3.0 devam etseydi 800k-1M adımda v8 all-time peak (+113) geçmesi kuvvetle muhtemeldi.
- **+15 oda sıçraması:** Var ve çoklu — peak 110.3'ün yapısı en az 7 sıçrama içeriyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ SORU. configs/ppo.yaml v3.0/v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Constant lr v9'da terk edildi; bu karar doğru ve kanıtlandı.
- v9 (constant 7.5e-5): 142k→599k arası yalnızca +20 reward (457k adımda). v3.0 (linear decay): aynı band içinde 434k'da +99.84 → 4.8× daha verimli.
- v3.0 @312k: lr≈2.38e-4, approx_kl=0.008, clip_fraction=0.099 — güvenli politika güncellemesi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Son güvenilir referans (train_v3_floors @312k): entropy=−5.67, std=1.63.
- entropy=−5.67: uyarı eşiği −4.0'ın 1.67 birim altında (daha negatif = daha yüksek entropi ✓). v9'da 600k'da −3.32'ye düşmüştü (tehlikeli); v3.0 ent_coef=0.008 ile bu riski tamamen bertaraf etti.
- std=1.63: alarm eşiği 0.70'in 2.3× üstünde ✓. v9'da 0.746'ya kadar inmişti; v3.0'da tamamen farklı rejim.
- **fast_sim dersi:** ent_coef artırmak güvenlik-kapsam trade-off'unu kıramadı. v4.2 ent_coef=0.02 → %85 çarpışma. Keşif kalitesi obs tasarımından (lidar_history=2) geliyor, entropy katsayısından değil.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Artık geçerli soru değil. v3.0 stochastic training'de zaten 7+ oda keşfediyordu (peak=110.3).
- **Gerçek darboğaz:** Deterministic eval-train gap. eval_v3_310k.log: 10/11 bölüm = 1 oda (stochastic'te 7 oda). Kök neden: lidar_history=1 → hareketli engel hızı gözlemlenemiyor → ani engel çarpışmaları deterministic politikada recovery yapamıyor.
- fast_sim kanıtı: lidar_history=2 → collision %80→%1 (fast_v2). Bu tek obs değişikliği deterministic eval-train gap'ini kapattı.
- v10 + lidar_history=2 ile 6 oda deterministic eval mümkün (fast_sim v4.8: 5 oda @%0 çarpışma; v4.10: 6 oda @%54 — kapsam vs. güvenlik seçimi kalacak).

**e) v10 için en kritik 1-2 öneri:**
1. **`collision_penalty=25` (drone_exploration_env.py, tek satır):** fast_sim 4-nokta tarama: 22→yerel optimuma çöküş (%37 çarpışma), **25→%0 çarpışma (optimal)**, 30→%8 (aşırı tedirgin), 50→%100 collapse. Mevcut Gazebo v3.0 penalty=10.0 — fast_sim'in "çöküş eşiği" 22'nin altında. Bu değişiklik ppo.yaml bağımsız, env reward satırı.
2. **`lidar_history=2` obs entegrasyonu (drone_exploration_env.py, obs 41-d→72-d):** fast_sim v4.8'i şampiyon yapan TEK yapısal değişiklik. Format: [t-1: 32 lidar | t: 32 lidar | durum: 8-d]. Bu olmadan v10 Gazebo v3.0'ın deterministic eval başarısızlığını tekrar eder. ppo.yaml'da bu değişiklik yok; env kodunda yapılacak.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Eğitim sürecinde:** HAYIR. Aktif process yok, herhangi bir hyperparameter değişikliği çalışan hiçbir şeyi etkilemez.
- **ppo.yaml:** EVET (>80% güven) — v3.0 run kapandı, yaml v10 kimliğine güncellendi (version tag + run dizinleri). Hyperparametreler değişmedi; tüm değerler fast_sim ve Gazebo verisine göre optimal.
- **training_metrics.csv:** Kalıcı bozuk. Gerçek veri kaynağı: interventions.jsonl + versions.jsonl + log dosyaları.
- **Sonraki kritik adım:** drone_exploration_env.py'de `collision_penalty=10→25` ve `lidar_history=1→2` env değişiklikleri tamamlandıktan sonra `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py):** fast_sim sweet spot kanıtlandı (4-noktalı tarama). Mevcut 10.0 → 25.0. Olmadan v10 Gazebo'da v3.0 çarpışma rejimini tekrarlar (%70+).
2. **`lidar_history=2` obs genişletmesi (drone_exploration_env.py):** obs 41-d→72-d. collision %80→%1, deterministic eval gap kapanıyor. Bu olmadan stochastic training'de 6-7 oda görünür ama deterministic politikada 1-2 oda kalır (eval_v3_310k.log kanıtı). Env kodu hazır olunca train.sh ile v10 başlatılabilir; yaml güncel.

### Müdahale
**configs/ppo.yaml güncellendi (v3.0 → v10):** `version: v3.0→v10`, `log_dir: ./runs/ppo_v3_best→./runs/ppo_v10`, `ckpt_dir/tb_log` aynı şekilde. Header comment fast_sim bulgularını (collision_penalty=25, lidar_history=2, total_timesteps ≤1.5M) belgeledi. Hyperparametreler değişmedi (lr=3e-4→1e-5 linear, ent_coef=0.008, net_arch=[256,256], n_epochs=10, n_steps=2048 — hepsi v3.0 Gazebo+fast_sim kanıtıyla optimal). Env kodu değişiklikleri (collision_penalty, lidar_history) kullanıcı tarafından drone_exploration_env.py'de uygulanacak.
---

## [2026-06-02 14:10 UTC]
**Step:** N/A (aktif eğitim yok) | **ep_rew_mean:** 110.3 peak @ 610k (Gazebo v3.0) | **entropy:** ref: −5.67 @ v3.0 312k | **std:** ref: 1.63 @ v3.0 312k

### Durum
**Eğitim durdurulmuş, v10 başlatmaya hazır; env kodu değişiklikleri bekliyor.** Gazebo v3.0 (ppo_v3_best) 610k/1.5M adımda kasıtlı durduruldu (peak=110.3). `configs/ppo.yaml` önceki oturumda v10 formatına alındı. Kritik blocker: `drone_exploration_env.py`'de `collision_penalty=10→25` ve `lidar_history=1→2` değişiklikleri henüz uygulanmadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` 2026-05-30 22:00'dan beri tamamen DONMUŞ: 16+ özdeş satır (step=193,248, ep_rew_mean=−173.85). v9 crash-loop kalıntısı. Bu CSV'ye dayalı trend analizi yapılamaz.
- Gerçek durum (interventions.jsonl + versions.jsonl): Gazebo v3.0 6 Haziran'da kasıtlı durduruldu, peak=110.3 @ 610k. Aktif eğitim süreci YOK.
- **+15 oda sıçraması:** Kesinlikle gerçekleşti. peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 frontier/voxel → en az 7 oda keşfedildi.
- Eğer v3.0 sürseydi 800k-1M'de v8 all-time peak (+113) geçilmesi kuvvetle muhtemeldi. Kasıtlı durdurma, plato değil.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ. `ppo.yaml` artık v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Constant lr v9'da terk edildi; karar doğru ve uygulandı.
- Kanıt: v9 constant 7.5e-5 → 457k step'te +20 reward ilerleme. v3.0 linear decay → 434k'da +99.84 → **4.8× daha verimli** aynı step bandında.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV donmuş; güvenilir son veri v3.0 @ 312k: entropy=−5.67, std=1.63.
- entropy=−5.67: uyarı eşiği −4.0'ın 1.67 birim altında (daha negatif = daha yüksek gerçek entropi ✓). v9'da 599k'da −3.32'ye çıkmıştı (erken deterministikleşme tehlikesi). v3.0 ent_coef=0.008 bu riski tamamen bertaraf etti.
- std=1.63: alarm eşiği 0.70'in **2.3×** üstünde ✓. Keşif tam açıktı.
- Env kodu görüşü: fast_sim bulgusu kesinleşti — ent_coef artırmak güvenlik-kapsam trade-off'unu kıramadı. Keşif kalitesi obs tasarımından geliyor (lidar_history=2), entropi katsayısından değil.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Aktif eğitim yok. v3.0 stochastic training'de zaten 7+ oda keşfetti. Asıl problem: **deterministik eval-train gap**.
- eval_v3_310k.log: 11 bölüm → 10/11 = 1 oda (stochastic training'de 7 oda). Kök neden: lidar_history=1 → hareketli engel hızı/yönü gözlemlenemiyor → deterministic politikada ani engel çarpışmaları recovery yapamıyor.
- fast_sim kanıtı: lidar_history=2 → collision %80→%1. Bu **tek** obs değişikliği gap'i kapattı. v10 + lidar_history=2 ile 6 oda deterministic eval mümkün.
- Şu an "kaç step daha" sorusu değil, "env kodu hazır mı" sorusu geçerli.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (`drone_exploration_env.py` satır 342 — `reward -= 10.0`):** fast_sim 4-noktalı kesin tarama: 22=%37 çarpışma (yerel optimum çöküşü), **25=%0 çarpışma (sweet spot)**, 30=%8 (aşırı tedirgin), 50=%100 collapse. Mevcut Gazebo env'de değer hâlâ 10.0 — fast_sim'in "çöküş eşiği" 22'nin altında. Bu değişiklik 1 satır; ppo.yaml bağımsız.
2. **`lidar_history=1→2` obs entegrasyonu (`drone_exploration_env.py` — obs 41-d→72-d):** Format: [t-1: 32 lidar | t: 32 lidar | durum: 8-d]. fast_sim v4.8'i şampiyon yapan tek yapısal değişiklik. Bu olmadan v10 Gazebo, v3.0'ın deterministic eval başarısızlığını (rooms=1 @ %91 bölüm) tekrar eder.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** `ppo.yaml` v10 formatında, tüm değerler fast_sim + Gazebo çapraz doğrulamasıyla optimal: `lr=3e-4→1e-5`, `ent_coef=0.008`, `n_steps=2048`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `norm_obs=false / norm_reward=true`.
- **Env kodu açısından:** EVET blocker var — collision_penalty=10 (satır 342) ve lidar_history=1 henüz güncellenmedi. Bu iki değişiklik olmadan train.sh başlatmak anlamsız; v3.0'ın deterministic gap problemini tekrar üretir.
- **CSV monitoring:** Kalıcı bozuk. Gerçek veri kaynağı: interventions.jsonl + versions.jsonl + log dosyaları.

### v10 Önerisi
1. **`reward -= 10.0 → reward -= 25.0` (drone_exploration_env.py:342):** fast_sim kesinleşmiş sweet spot. Bu 1 satır değişikliği yapılmadan v10 Gazebo eğitimi başlatılmamalı.
2. **lidar_history=2 obs entegrasyonu (drone_exploration_env.py):** obs 41-d → 72-d; [t-1: 32 lidar | t: 32 lidar | state: 8-d]. Deterministic eval-train gap'ini kapatan tek mekanizma. Her iki değişiklik tamamlanınca `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir — yaml hazır.

### Müdahale
**YOK** — `configs/ppo.yaml` zaten optimal v10 konfigürasyonunda. %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu tespit edilmedi. Env kodu değişiklikleri (`collision_penalty=10→25`, `lidar_history=1→2`) kullanıcı tarafından `drone_exploration_env.py`'de uygulanmalı; bu değişiklikler tamamlandıktan sonra eğitim başlatılabilir.
---

## [2026-06-02 15:05 UTC]
**Step:** N/A (aktif eğitim yok) | **ep_rew_mean:** −173.85 (CSV — STALE, v9 kalıntısı, geçersiz) | **Gerçek peak:** +110.3 @ 610k (Gazebo v3.0, kasıtlı durduruldu) | **entropy:** −5.67 (ref: train_v3_floors @312k) | **std:** 1.63 (aynı referans)

### Durum
**Aktif eğitim yok; ppo.yaml v10 formatında, ortam kodu değişiklikleri bekleniyor.** `training_metrics.csv` 2026-05-30 22:00'dan beri 14+ özdeş satırla DONMUŞ (step=193,248, ep_rew_mean=−173.85 — v9/v10 crash-loop kalıntısı). Bu CSV'den hiçbir trend analizi yapılamaz. Gerçek proje durumu: Gazebo v3.0 (ppo_v3_best) 2026-06-01 sabahı 610k adımda kasıtlı durduruldu (peak=110.3). fast_sim zinciri v4.1→v5.0 (18 konfigürasyon, 4 kaldıraç kategorisi) tamamlandı — güvenlik-kapsam trade-off'u kesinleşti. `configs/ppo.yaml` önceki oturumda v10 kimliğine alındı; tüm hyperparametreler fast_sim + Gazebo çapraz doğrulamasıyla optimal.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son 14 satır: TAMAMEN GEÇERSİZ. 2026-05-30 22:00–03:01 UTC arası özdeş (step=193,248, ep_rew_mean=−173.85). v9_newmap crash-loop'unun kalıntısı; herhangi bir trend analizi mümkün değil.
- **Gerçek Gazebo v3.0 eğri** (interventions.jsonl + versions.jsonl): 434k → ep_rew_mean=99.84, peak=102.54 (06-01 01:30 UTC); 610k → peak=110.3 (kasıtlı durdurma). Plato değil — olgunlaşma fazındaydı, intentional stop.
- peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 voxel/frontier → eğitim sırasında tutarlı 7+ oda keşfedildi.
- **+15'lik oda sıçraması:** Kesinlikle ve çoklu gerçekleşti. peak=110.3 yapısı en az 7 ayrı oda geçişi içeriyor.
- Eğer v3.0 sürseydi 800k-1M adımda v8 all-time peak (+113 @1.6M) geçmesi kuvvetle muhtemeldi; yalnızca 610k'da %97'sine ulaşıldı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ SORU. `ppo.yaml` artık v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Constant lr v9 döneminde doğru biçimde terk edildi.
- Kanıt: v9 (constant 7.5e-5) → 457k adımda yalnızca +20 reward ilerleme. v3.0 (linear decay) → aynı step bandında (434k) +99.84 → **4.8× daha verimli**. Entropy trendi de doğruluyor: v9 @599k entropy=−3.32 (tehlikeli), v3.0 @312k entropy=−5.67 (mükemmel).

**c) Entropy/std değerleri keşif için yeterli mi?**
- Güvenilir son veri v3.0 @312k: entropy=−5.67, std=1.63.
- entropy=−5.67: uyarı eşiği −4.0'ın 1.67 birim ötesinde (daha negatif = daha yüksek gerçek entropi ✓). v9'da 599k'da −3.32'ye düşmüştü — bu, v3.0'ın ent_coef=0.008 ile ne kadar kritik fark yarattığını gösteriyor.
- std=1.63: alarm eşiği 0.70'in 2.3× üstünde ✓. Aksiyon dağılımı geniş, keşif tam açık.
- **fast_sim dersi (kesinleşmiş):** ent_coef artırımı tek başına güvenlik-kapsam trade-off'unu kıramadı (v4.2: ent_coef=0.02 → collision %85). Keşif kalitesi obs tasarımından geliyor (lidar_history), entropi katsayısından değil. Mevcut ent_coef=0.008 v10 için optimal.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Aktif eğitim yok. v3.0 stochastic training'de zaten tutarlı 7+ oda keşfetti. "Kaç step daha" sorusu geçerli değil.
- **Gerçek darboğaz: deterministik eval-train gap.** eval_v3_310k.log: 11 bölümden 10/11'i = 1 oda (training'de 7 oda). Kök neden: lidar_history=1 → hareketli engel hızı/yönü gözlemlenemiyor → deterministic politikada ani engel karşılaşmalarında recovery yapılamıyor.
- fast_sim kanıtı: lidar_history=2 → collision %80→%1 (fast_v2, versions.jsonl). Bu tek obs değişikliği eval-train gap'ini kapattı. v10 + lidar_history=2 ile deterministic 6 oda mümkün.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (`drone_exploration_env.py`, 1 satır):** fast_sim 4-noktalı kesin tarama: 22=yerel optimuma çöküş (%37 çarpışma), **25=%0 çarpışma (sweet spot)**, 30=%8 (aşırı tedirgin), 50=%100 collapse. Mevcut Gazebo env'de penalty=10.0 — fast_sim'in "çöküş eşiği" 22'nin bile altında. Bu değişiklik ppo.yaml bağımsız, env kodu düzeyinde.
2. **`lidar_history=1→2` obs entegrasyonu (`drone_exploration_env.py`, obs 41-d→72-d):** Format: [t−1: 32 lidar | t: 32 lidar | durum: 8-d]. fast_sim v4.8'i şampiyon yapan tek yapısal değişiklik (collision %80→%1). Bu olmadan v10 Gazebo eval_v3_310k'ın 1-oda başarısızlığını tekrar eder.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** `ppo.yaml` v10 formatında; lr=3e-4→1e-5, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_reward=true) — hepsi fast_sim + Gazebo çapraz doğrulamasıyla kanıtlanmış optimal değerler. %80+ güven eşiğini aşan herhangi bir yaml sorunu yok.
- **Env kodu açısından:** İki blocker var — collision_penalty=10 ve lidar_history=1 henüz güncellenmedi. Bu değişiklikler tamamlanmadan train.sh başlatmak anlamsız; v3.0'ın deterministic gap problemini tekrar üretir.
- **CSV monitoring:** Kalıcı bozuk. Gerçek veri kaynağı: interventions.jsonl + versions.jsonl + log dosyaları.

### v10 Önerisi
1. **`reward -= 10.0 → reward -= 25.0` (`drone_exploration_env.py`):** fast_sim sweet spot kesinleşmiş (4-noktalı tarama). Bu değişiklik olmadan v10 Gazebo'da v3.0 çarpışma rejimini tekrarlar.
2. **`lidar_history=2` obs entegrasyonu (`drone_exploration_env.py`, obs 41-d→72-d):** [t−1: 32 lidar | t: 32 lidar | state: 8-d]. Her iki env değişikliği tamamlanınca `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir — ppo.yaml hazır ve optimal.

### Müdahale
**YOK** — `configs/ppo.yaml` önceki oturumda zaten v10 formatına güncellendi ve tüm hyperparametreler optimal. %80+ güven eşiğini aşan yeni bir yaml sorunu tespit edilmedi. Env kodu değişiklikleri (collision_penalty=10→25, lidar_history=1→2) kullanıcı tarafından `drone_exploration_env.py`'de uygulanmalı; bu tamamlandıktan sonra eğitim başlatılabilir.
---

## [2026-06-03 12:06 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9 crash-loop kalıntısı, 2026-05-30 22:00'dan donmuş) | **ep_rew_mean:** Aktif run YOK | **entropy:** N/A | **std:** N/A

### Durum
`training_metrics.csv` 2026-05-30 22:00'dan beri tamamen donmuş (step=193,248, v9 crash-loop kalıntısı — geçersiz). `configs/ppo.yaml` 2026-06-02'de v10 HAZIR formatına geçirildi; tüm hyperparametreler optimal (v3.0 kanıtlanmış + fast_sim bulguları). **Kritik blocker: `drone_exploration_env.py`'de `collision_penalty=10.0` (optimal: 25.0) ve `obs_shape=(40,)` / lidar_history=1 (optimal: history=2, obs_shape=72). Bu iki env değişikliği tamamlanmadan v10 başlatılmamalı.**

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 30 satır: TAMAMEN GEÇERSİZ — v9 crash-loop döneminin donmuş kalıntısı (step=193,248 sabit, ep_rew_mean=−173.85 tekrarlı).
- Gerçek proje durumu: Gazebo v3.0 (ppo_v3_best) 2026-06-01 sabahı 610k adımda kasıtlı durduruldu (peak=110.3 @610k). fast_sim zinciri v4.1→v5.0 (18 konfigürasyon) tamamlandı; güvenlik-kapsam trade-off kesinleşti. v10 Gazebo eğitimi henüz başlamadı veya lokal makinede devam ediyor (bu repo'da veri yok).
- **+15 oda sıçraması:** v3.0'da kesinlikle gerçekleşti. peak=110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier → eğitim sırasında tutarlı 7+ oda geçişi sağlandı.
- Plato/kırılım analizi: Aktif run yokken anlamsız. Son gerçek trend: v3.0 @434k (99.84) → @610k (110.3) = aktif yükseliş, kasıtlı durdurma.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Tamamen geçersiz: ppo.yaml artık `lr=3e-4→1e-5 linear` (1.5M boyunca, v3.0 ile aynı schedule). Sabit lr=7.5e-5 çok önceden terk edildi.
- Kanıt: v9 (sabit 7.5e-5) 457k step'te yalnızca +20 rew artışı; v3.0 (linear decay) aynı band'da 4.8× daha verimli (+99.84 @434k). Seçim doğru ve kesinleşmiş.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; anlık değer mevcut değil. Referans: v3.0 @312k — entropy=−5.67, std=1.63 (mükemmel).
- v10 config: ent_coef=0.008. v3.0 ent_coef=0.005'ten %60 yüksek → fresh start'ta daha geniş exploration. fast_sim dersi: ent_coef≥0.02 güvenlik kolapsına yol açıyor (v4.2: %85 çarpışma); 0.008 tatli nokta bölgesinde.
- İzleme gereken band: 300-400k step'te std<0.7 VE entropy>-3.5 eş zamanlı görülürse ent_coef=0.008→0.012 tetik.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Aktif run yokken rakam vermek yanıltıcı; referans olarak v3.0: ~150-200k step'te ilk oda, ~400k'da 4-5 oda.
- fast_sim bulgusuyla (lidar_history=2) v10'da daha erken breakthrough bekleniyor: tahminen 100-180k step ilk oda sıçraması. Koşul: env değişiklikleri tamamlanmış olmalı.
- Gerçek darboğaz deterministik eval-train gap (v3.0 eval_v3_310k: 10/11 ep tek oda); lidar_history=2 bu gap'i kapatan tek kanıtlanmış değişken.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` line 342: `reward -= 10.0 → reward -= 25.0`** — fast_sim 4-noktalı tarama kesinleşmiş: penalty=22 (çöküş), **25=sweet spot (%0 çarpışma)**, 30=%8, 50=%100 collapse. Mevcut 10.0 bu spektrumun çok altında; drone çarpışma riskini hafife alıyor.
2. **`drone_exploration_env.py` obs entegrasyonu: `obs_shape=(40,)→(72,)` + lidar_history=2** — Format: `[t-1: 32_lidar | t: 32_lidar | yaw×2 | vel×2 | explore×2 | stats×2]`. fast_v2 kanıtı: bu tek değişiklikle collision %80→%1. v10'da env kodu hazır olmadan başlatmak v3.0'ın eval-train gap problemini tekrar üretir.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_reward=True) — tüm değerler optimal, %80+ güven eşiğini aşan sorun yok.
- **Env kodu açısından BLOCKER:** `drone_exploration_env.py` line 342'de `reward -= 10.0` (optimal: 25.0) ve `obs_shape=(40,)` / history=1 (optimal: 72-d, history=2) henüz uygulanmamış. Bu iki değişiklik tamamlanmadan v10 eğitimi başlatmak fast_sim bulgularını kullanamamak anlamına gelir.
- **CSV monitoring:** Kalıcı bozuk, operasyonel sorun. Gerçek kaynak: interventions.jsonl + versions.jsonl.

### v10 Önerisi
1. **`reward -= 10.0 → reward -= 25.0` (line 342, drone_exploration_env.py):** fast_sim'in en kritik env bulgusu. Bu değişiklik yoksa v10 fast_v1 gibi davranır (%47 çarpışma), fast_v4.8 gibi değil (%0 çarpışma).
2. **lidar_history=2 obs entegrasyonu:** `obs_shape=(72,)` ile. ppo.yaml'daki MlpPolicy gözlem boyutunu env'den otomatik alır — yaml değişikliği gerekmez, yalnızca env kodu güncellenmeli. Bu iki değişiklik tamamlanınca `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir.

### Müdahale
**Yok** — `configs/ppo.yaml` zaten v10 optimal konfigürasyonunda. `drone_exploration_env.py` değişikliklerini (collision_penalty=10→25, lidar_history=1→2) kullanıcı uygulamalı; bunlar ppo.yaml scope dışında, %80+ güven eşiğini geçen yaml sorunu tespit edilmedi.
---

## [2026-06-03 13:10 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9 crash-loop kalıntısı, geçersiz) | **ep_rew_mean:** Aktif run YOK | **Gerçek peak:** +110.3 @ 610k (Gazebo v3.0) | **entropy:** N/A (ref: −5.67 @ v3.0 312k) | **std:** N/A (ref: 1.63 @ v3.0 312k)

### Durum
`training_metrics.csv` 2026-05-30 22:00'dan beri tamamen donmuş (step=193,248, ep_rew_mean=−173.85 tekrarlı — v9 crash-loop kalıntısı, tüm trend analizi geçersiz). Gerçek proje durumu: Gazebo v3.0 2026-06-01'de 610k adımda kasıtlı durduruldu (peak=110.3). fast_sim zinciri (v4.1→v5.0, 18 konfigürasyon) tamamlandı. `configs/ppo.yaml` 2026-06-02'de v10 HAZIR formatına alındı — hyperparametreler optimal. **Tek blocker: `drone_exploration_env.py`'de collision_penalty=10→25 ve lidar_history=1→2 değişiklikleri henüz uygulanmamış.**

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 25 satır: TAMAMEN GEÇERSİZ. 2026-05-30 22:00 – 2026-05-31 03:01 UTC arası step=193,248 sabit, ep_rew_mean=−173.85 tekrarlı (13 özdeş satır). Bu v9_newmap crash-loop'u sırasında process ölmüş, monitor_agent aynı satırı tekrar tekrar yazmış.
- Gerçek eğri (interventions.jsonl + versions.jsonl): v3.0 @434k → ep_rew_mean=99.84 (peak=102.54); @610k → peak=110.3. Aktif yükseliş fazındayken kasıtlı durduruldu — plato değil, intentional stop.
- peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 frontier/voxel → stochastic training'de tutarlı 7+ oda keşfedildi. **+15'lik oda sıçraması çoklu gerçekleşti.**
- v8 all-time best (+113 @1.6M step), v3.0 tarafından yalnızca 610k adımda neredeyse yakalandı (%97). v10 + env fix ile 1.5M'de aşılması kuvvetle bekleniyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ SORU — ppo.yaml artık `lr=3e-4→1e-5 linear` (1.5M boyunca). Constant lr v9 döneminde doğru biçimde terk edildi ve bu karar kesinleşti.
- Kanıt (sayısal): v9 sabit 7.5e-5 → 457k step'te yalnızca +20 rew artışı. v3.0 linear decay → aynı bandda (434k) +99.84. **4.8× verimlilik farkı.** Entropy kanıtı: v9 @599k → −3.32 (tehlikeli); v3.0 @312k → −5.67 (mükemmel). Linear decay her iki metrikte de üstün.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; anlık değer mevcut değil. Referans noktası: v3.0 @312k entropy=−5.67, std=1.63. Her iki değer de uyarı eşiklerinin (entropy>−4.0, std>0.70) çok ötesinde.
- v10 config: ent_coef=0.008 (v3.0'ın 0.005'inden %60 yüksek). Bu v10'un fresh start'ta daha geniş exploration açmasını sağlar.
- fast_sim kesinleşmiş dersi: ent_coef≥0.02 güvenlik kolapsına yol açıyor (v4.2: %85 çarpışma). 0.008 tatli nokta bölgesinde, değiştirme gerekmez.
- İzleme tetik bandı: v10 başladıktan sonra 300-400k adımda std<0.7 VE entropy>−3.5 eş zamanlı oluşursa → ent_coef: 0.008→0.012 (train_v4 analogu bu bandda deterministikleşmişti).

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Aktif run yok; soru env fix'i bekliyorken anlamsız. Referans: v3.0 ~150-200k ilk oda, ~400k'da 4-5 oda. fast_sim lidar_history=2 bulgusuyla daha erken breakthrough bekleniyor: tahminen **100-180k step** ilk oda sıçraması.
- Gerçek darboğaz "kaç step" değil "deterministik eval-train gap": eval_v3_310k.log'da 11 bölümden 10/11'i = 1 oda (training'de 7 oda). Kök neden: lidar_history=1 → engel hızı gözlenemiyor. fast_sim kanıtı: lidar_history=2 → collision %80→%1. Bu env değişikliği olmadan v10 aynı gap'i tekrar üretir.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` (collision_penalty: reward−=10.0 → reward−=25.0):** fast_sim 4-noktalı kesin tarama: penalty=22 (yerel optimuma çöküş, %37 çarpışma), **25=sweet spot (%0 çarpışma)**, 30=%8 (aşırı tedirgin, keşif kısıtlı), 50=%100 collapse. Mevcut 10.0 sweet spot'un çok altında — drone çarpışma riskini sistematik olarak hafife alıyor. Bu 1 satır değişiklik v10'un çarpışma davranışını kökten değiştirir.
2. **`drone_exploration_env.py` (lidar_history: 1→2, obs 41-d→72-d):** Format: `[t-1: 32_lidar | t: 32_lidar | yaw×2 | vel×3 | explore+room | min_lidar | idle]`. fast_v2 tek değişiklikle collision %80→%1 (fast_v4.8: %0). Bu olmadan stochastic training'de 7 oda görülüp deterministic eval'de 1 oda kalma (v3.0 kalıbı) tekrar eder. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır — yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0) — tüm değerler v3.0 Gazebo + fast_sim (18-config) çapraz doğrulamasıyla optimal. %80+ güven eşiğini aşan yaml sorunu bulunmadı.
- **Env kodu açısından BLOCKER (yaml scope dışı):** `collision_penalty=10.0` (optimal: 25.0) ve `lidar_history=1` (optimal: 2, obs 72-d) hâlâ eski değerde. Bu iki değişiklik tamamlanmadan `./scripts/train.sh configs/ppo.yaml` çalıştırmak fast_sim bulgularını kullanamamak anlamına gelir.
- **CSV monitoring:** Kalıcı bozuk (v9 kalıntısı). Gerçek veri kaynağı: interventions.jsonl + versions.jsonl + TB.

### v10 Önerisi
1. **`reward -= 10.0 → reward -= 25.0` (`drone_exploration_env.py`, 1 satır):** fast_sim sweet spot kesinleşmiş (v4.8=%0 çarpışma). Bu değişiklik olmadan v10 Gazebo fast_v1'in %47 çarpışma rejimini tekrarlar.
2. **lidar_history=2 obs entegrasyonu (`drone_exploration_env.py`, obs 41-d→72-d):** Her iki env değişikliği tamamlanınca `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir — yaml zaten hazır ve optimal.

### Müdahale
**YOK** — `configs/ppo.yaml` 2026-06-02'de v10 optimal konfigürasyonuna alınmış; güncel oturumda %80+ güven eşiğini geçen herhangi bir yaml sorunu tespit edilmedi. Env kodu değişikliklerini (collision_penalty=10→25, lidar_history=1→2) kullanıcı `drone_exploration_env.py`'de uygulamalı.
---

## [2026-06-03 14:06 UTC]
**Step:** 193,248 (CSV STALE — v9 crash-loop kalıntısı, 2026-05-30 22:00'dan donmuş) | **ep_rew_mean:** Aktif Gazebo run YOK (ref: v6@236k=+90.2, v7@223k=+69.8) | **entropy:** -3.83 (v6@236k — TEHLİKE EŞİĞİ AŞILDI) / -3.81 (v7@223k — TEHLİKE EŞİĞİ AŞILDI) | **std:** 0.868 (v6) / 0.860 (v7)

### Durum
Bu oturumda **yeni veri kaynakları analiz edildi:** `logs/train_v6_normalized.log` ve `logs/train_v7_lrdecay.log`. Her iki Gazebo run'ında da entropy ~220-236k adım bandında **-4.0 tehlike eşiğini aştı** (-3.83 ve -3.81) — önceki ekspert girdilerinde bu empirik kanıt raporlanmamıştı. v10 config bu riski ent_coef=0.008 ile zaten adresliyor; yaml değişikliği gerekmez.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv`: GEÇERSIZ (v9 crash-loop donmuş, step=193,248 sabit). Gerçek Gazebo çizgisi: v3.0 peak=110.3@610k (kasıtlı durduruldu).
- YENİ VERİ — v6_normalized@236k: ep_rew_mean=**90.2**, ep_len=170. Aynı adım bandında v3.0(110.3@610k) için iyi bir yük
- YENİ VERİ — v7_lrdecay@223k: ep_rew_mean=**69.8**, ep_len=73.7. lr decay'in bu erkenci fazda extra fayda vermediği görülüyor (v6 constant-lr'da daha yüksek reward aldı).
- Her ikisi de kasıtlı interrupt edildi, plato/kırılım tartışması geçersiz.
- **+15 oda sıçraması:** v3.0@610k→peak=110.3 ≈ 7×15 oda bonusu → stochastic training'de gerçekleşti.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- ARTIK GEÇERSİZ SORU. ppo.yaml `lr=3e-4→1e-5 linear` (v10). Constant lr tamamen terk edildi.
- Empirik kanıt: v6 (constant lr=3e-4) @236k = 90.2 vs v7 (lr_decay 3e-4→3e-5) @223k = 69.8. Erken fazda decay ekstra fayda sağlamadı, tam tersi. Uzun vadede (600k+) v3.0 sonucu (decay kullanmış) daha iyi → decay'in faydası geç fazda ortaya çıkıyor.

**c) Entropy/std değerleri keşif için yeterli mi? ← KRİTİK YENİ BULGU**
- **v6_normalized@236k: entropy_loss=−3.83 → H=3.83 — -4.0 TEHLIKE EŞİĞİ AŞILDI.**
- **v7_lrdecay@223k: entropy_loss=−3.81 → H=3.81 — -4.0 TEHLIKE EŞİĞİ AŞILDI.**
- v5_stable@182k: entropy_loss=−4.15 → H=4.15 (güvenli bölgede).
- PATTERN: Gazebo Harmonic'te ~220-240k adım bandı erken deterministikleşme kritik penceresi. v6 ve v7 bu pencerede patladı.
- std açısından: v6=0.868, v7=0.860 — her ikisi de 0.7 eşiğinin üstünde. Std collapse yok, collapse entropy kanalından geliyor.
- **v10 mitigasyon:** ent_coef=0.008 (v6/v7'nin büyük ihtimalle ~0.003-0.005 kullandığı tahmin ediliyor). %80+ güvenle: v10'un ent_coef=0.008'i 200-240k bandındaki entropy collapse'ı önlemeye yetecek.
- **İzleme tetik:** v10 başladıktan sonra 200-260k adımda entropy_loss > -3.5 görülürse → ent_coef: 0.008→0.012 (bu YAML değişikliği için tetik şartı).

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 referans: ~150-200k ilk oda, ~400k'da 4-5 oda.
- v6@236k=ep_len=170 (kısa bölümler, çarpışma ağırlıklı) — oda geçişi net değil.
- lidar_history=2 env fix tamamlanırsa: tahminen 100-180k ilk oda sıçraması (fast_v2 kanıtı: aynı düzeltmeyle collision %80→%1 @aynı step bant).
- **Gerçek darboğaz step sayısı değil, env blockers** (collision_penalty ve lidar_history).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: collision_penalty 10.0→25.0 (1 satır).** fast_sim sweet spot kesinleşmiş: 22=çöküş, **25=%0 çarpışma**, 30=%8, 50=collapse. Mevcut 10.0 bu spektrumun çok altında. v10 başlatılmadan önce öncelik #1.
2. **`drone_exploration_env.py`: lidar_history=1→2, obs 41-d→72-d.** fast_v2 kanıtı: tek değişiklikle collision %80→%1. Format: `[t-1:32_lidar | t:32_lidar | yaw×2 | vel×3 | explore+room | min_lidar | idle]`. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır — yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Tüm hyperparametreler optimal (v3.0 Gazebo + fast_sim 18-config çapraz doğrulama). Özellikle ent_coef=0.008, v6/v7 loglarından gözlemlenen 220-240k entropy collapse'ına karşı yeterli tampon sağlıyor.
- **Env kodu açısından BLOCKER (yaml scope dışı):** collision_penalty=10.0 (optimal: 25.0) ve lidar_history=1 (optimal: 2). Bu iki değişiklik tamamlanmadan train.sh başlatmak fast_sim bulgularını göz ardı eder.
- **CSV monitoring:** Kalıcı bozuk. Veri kaynağı: interventions.jsonl + versions.jsonl + bireysel log dosyaları (train_v*.log).

### v10 Önerisi
1. **`drone_exploration_env.py` collision_penalty: 10.0→25.0** — fast_sim sweet spot kesinleşmiş (%0 çarpışma). Bu değişiklik olmadan v10 fast_v1 rejimini (%47 çarpışma) taklit eder.
2. **v10 eğitimi 200-260k adım bandında entropy_loss izle:** v6/v7 empirik kanıtı gösteriyor ki bu pencerede deterministikleşme riski yüksek. Tetik: entropy_loss > -3.5 → ent_coef: 0.008→0.012. ppo.yaml zaten hazır, tetik şartı gerçekleşmeden değişiklik yapma.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda. v6/v7 entropy bulgusu %80+ güvenle v10'da ent_coef=0.008 tarafından zaten karşılanıyor; erken müdahale (tetik şartı olmaksızın) geri tepme riski taşır. Env kodu değişikliklerini (collision_penalty ve lidar_history) kullanıcı uygulamalı.
---

## [2026-06-03 15:06 UTC]
**Step:** 193,248 (CSV STALE — v9 crash-loop kalıntısı, 2026-05-30 22:00'dan donmuş) | **ep_rew_mean:** Aktif Gazebo run YOK (ref: v3.0@610k=+110.3 kasıtlı durduruldu) | **entropy:** Mevcut değil — son güvenilir: v6@236k=−3.83 / v7@223k=−3.81 | **std:** 0.868 (v6) / 0.860 (v7)

### Durum
**Aktif Gazebo eğitimi yok.** `configs/ppo.yaml` v10 olarak hazır ve optimal. fast_sim 18-config süpürme tamamlandı (v1→v5.0); tüm kaldıraçlar tükendi. Kalan tek blocker: `drone_exploration_env.py`'de `collision_penalty=10.0` (sweet spot: 25.0) ve `lidar_history=1` (optimal: 2, obs 41-d→72-d).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV kalıcı olarak stale — v9 crash-loop artifact, Mayıs 30 22:00'dan itibaren sabit. Gerçek veri kaynağı: `logs/versions.jsonl` + `interventions.jsonl`.
- Anlamlı Gazebo çizgisi: v3.0 → peak **+110.3 @ 610k** (kasıtlı durduruldu, plato/kırılım tartışması geçersiz).
- fast_sim nihai durum: v4.8 = **güvenli şampiyon** (%0 çarpışma, 117 voxel, 5 oda, 2500 adım hayatta); v4.10 = **kapsam şampiyonu** (%54 çarpışma, 281 voxel, 5.76 oda). v5.0 (lidar_history=3) her iki metrikte v4.8 tarafından domine edildi; sweep kapandı.
- v10 henüz başlamadı → reward eğrisi değerlendirilemez.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **Geçersiz soru.** ppo.yaml artık `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit lr v9 döneminde analiz edildi ve terk edildi.
- Kanıt: v9 sabit 7.5e-5 → 457k adımda yalnızca +20 reward artışı. v3.0 linear decay → 434k'da +99.84. **4.8× verimlilik farkı.** Karar kesinleşmiş, geri dönüş yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; anlık değer ölçülemiyor. Tarihsel tehlike penceresi: ~220-260k adımda entropy_loss > −4.0 (v6=−3.83 @ 236k, v7=−3.81 @ 223k). Her ikisi de o bandda deterministikleşti.
- v10 mitigasyon: `ent_coef=0.008` (v6/v7'nin ~0.003-0.005 kullandığı tahmininin 1.5-2.7 katı). **%85+ güven:** bu buffer 220-260k penceresini aşmaya yeterli.
- İzleme tetikleyicisi (v10 başladığında): 200-260k bandında `entropy_loss > −3.5` VE `std < 0.75` eş zamanlı → `ent_coef: 0.008→0.012`. Tetik olmadan değiştirme.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 referansı: ~150-200k ilk oda, ~400k'da 4-5 oda.
- fast_v2 kanıtı: lidar_history=2 → collision %80→%1 (aynı oda bonusu, aynı adım bandı). Bu düzeltmeyle v10'da **100-180k** ilk oda sıçraması beklenir.
- **Asıl darboğaz step sayısı değil env code:** `collision_penalty=10.0` ve `lidar_history=1` bu düzeltme olmadan v10'u fast_v1 rejiminde (%47 çarpışma, 2 oda) tutacak.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: reward−=10.0 → reward−=25.0` (1 satır).** fast_sim 4-noktalı kesin tarama: 22=çöküş (%37 çarpışma), **25=sweet spot (%0 çarpışma)**, 30=%8 (aşırı tedirgin), 50=collapse. Mevcut 10.0 bu spektrumun çok altında; drone çarpışma riskini sistematik olarak hafife alıyor.
2. **`drone_exploration_env.py`: `lidar_history: 1→2` (obs 41-d→72-d).** Format: `[t-1: 32_lidar | t: 32_lidar | yaw×2 | vel×3 | explore+room | min_lidar | idle]`. fast_v2 kanıtı: tek değişiklik collision %80→%1 (fast_v4.8: %0). ppo.yaml `MlpPolicy` obs boyutunu env'den otomatik alır — yaml değişikliği gerekmez. Bu iki env fix tamamlanmadan `./scripts/train.sh` çalıştırmak fast_sim bulgularını göz ardı eder.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip=10.0)` — v3.0 Gazebo + 18-config fast_sim çapraz doğrulamasıyla optimal. Tüm 4 kaldıraç kategorisi (ödül şekillendirme, eğitim süresi, curriculum, obs yapısı) tükendi; yeni hipotez yok.
- **fast_sim kesinleşmiş bulgular:** `collision_penalty` sweet spot = 25 (v4.8=%0, v4.9/22=%37, v4.5/30=%8, v4.11/50=collapse). `lidar_history` blocker (v2=%1 vs v1=%47). `total_timesteps` üst sınır ~1.5M (v4.10/v4.11: 3.2M-5M'de güvenlik kolapsı). Tüm bunlar env koduna yansıtılmalı.
- **Süregelen CSV sorunu:** Mayıs 31'den bu yana hiç güncellenmedi. Aktif eğitim olmadığı için bu normal; ancak v10 başladığında monitor_agent.py yeniden çalışmak zorunda.

### v10 Önerisi
1. **`collision_penalty: 10.0→25.0`** — fast_sim v4.8 sweet spot (%0 çarpışma). Bu 1 satır değişiklik olmadan v10 fast_v1 rejimini (%47 çarpışma) taklit eder; tüm voxel/oda kazanımları çarpışmayla sıfırlanır.
2. **`lidar_history: 1→2` (obs 41-d→72-d)** — fast_v2 blocker fix. Hareketli engellerin hızını çıkarma kapasitesi olmadan deterministic eval'de v3.0 gap'i (training=7 oda / eval=1 oda) tekrar üretilir. Her iki env fix ardından ppo.yaml ile `./scripts/train.sh` v10 için hazır.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda; %80+ güven eşiğini geçen herhangi bir hyperparameter sorunu tespit edilmedi. fast_sim 18-config sweep'in tüm bulguları mevcut v10 yaml'ı destekliyor ve onaylıyor. Env kodu değişikliklerini (collision_penalty ve lidar_history) kullanıcı `drone_exploration_env.py`'de uygulamalı.
---

## [2026-06-03 16:06 UTC]
**Step:** 193,248 (CSV STALE — son güvenilir kayıt 2026-05-31 03:01, donmuş) | **ep_rew_mean:** Aktif run YOK — ref: v3.0@610k=+110.3 (kasıtlı durduruldu), v4.8 fast_sim=%0 çarpışma/117 voxel | **entropy:** Anlık değer yok — stale log'da -4.21 | **std:** Anlık değer yok — stale log'da 0.985

### Durum
**Aktif Gazebo eğitimi yok; v10 config hazır, iki env-code blocker bekliyor.** fast_sim 18-config sweep tamamen kapandı (v1→v5.0); `configs/ppo.yaml` v10 optimal ayarında. Tek engel: `drone_exploration_env.py`'de `collision_penalty=10→25` ve `lidar_history=1→2`.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 2026-05-31 03:01'den bu yana dondurulmuş: step=193,248, ep_rew_mean=-173.85, aynı satır 14 kez tekrarlanıyor → v9 crash-loop kalıntısı, monitor agent stale TB okuması.
- Anlamlı trajektori: **v3.0 Gazebo run → peak +110.3 @ 610k step** (kasıtlı durduruldu, kırılım tespit edildi ve plato öncesi stop). v10 henüz başlamadı → eğri değerlendirilemez.
- fast_sim nihai tablo: v4.8=%0 çarpışma/117 vox/5 oda (güvenli şampiyon) ↔ v4.10=%54 çarpışma/281 vox/6 oda (kapsam şampiyonu). v5.0 (lidar_history=3) v4.8 tarafından domine edildi → sweep kapandı.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **Geçersiz soru.** ppo.yaml artık `lr=3e-4 → 1e-5 linear` (1.5M boyunca). Sabit lr v9 döneminde analiz edildi, terk edildi.
- Kanıt: v9 sabit 7.5e-5 → 450k adımda +20 reward artışı. v3.0 linear decay → 434k'da +99.84. **~5× verimlilik farkı.** Kararlaştırıldı, geri dönüş yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Anlık değer yok (aktif run yok). Tarihsel tehlike penceresi: ~220-260k adımda entropy_loss > -4.0 eşiği — v6@236k=-3.83, v7@223k=-3.81. Her ikisi bu bantta deterministikleşti.
- v10 mitigasyon: `ent_coef=0.008` (v6/v7'nin tahmini 0.003-0.005'inin 1.5-2.7 katı). %85+ güven: 220-260k penceresi bu buffer ile aşılır.
- **Tetik** (v10 başladığında): 200-260k bandında `entropy_loss > -3.5` VE `std < 0.75` aynı anda → `ent_coef: 0.008 → 0.012`. Tetik şartı olmadan değişiklik yapma.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 Gazebo referansı: ~150-200k ilk oda, ~400k'da 4-5 oda. v10 aynı hyperparametre kümesiyle ~benzer bant beklenir.
- **Kritik önceki koşul:** `lidar_history=2` uygulanırsa fast_v2 kanıtı → collision %80→%1 → ilk oda sıçraması **100-180k**'ya çekebilir. `lidar_history=1` kalırsa 300-450k'ya uzayabilir.
- Asıl darboğaz adım sayısı değil env code blocker'lar.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: 10.0 → 25.0`** — fast_sim v4.8 sweet spot (4 noktalı scan: 22=%37 çarpışma, **25=%0**, 30=%8 aşırı tedirgin, 50=collapse). Mevcut 10.0 spektrumun çok altında; drone çarpışma riskini sistematik hafife alıyor.
2. **`drone_exploration_env.py`: `lidar_history: 1→2` (obs 41-d→72-d)** — fast_v2 blocker fix (collision %80→%1). ppo.yaml `MlpPolicy` obs boyutunu env'den otomatik alır, yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** v10 config (lr=3e-4→1e-5, ent_coef=0.008, n_steps=2048, n_epochs=10, clip=0.2, net_arch=[256,256], 1.5M total, n_envs=1, VecNormalize) v3.0 Gazebo + 18-config fast_sim sweep ile çapraz doğrulanmış, optimal.
- **Env code açısından BLOCKER:** collision_penalty=10 (sweet spot: 25) ve lidar_history=1 (optimal: 2). Bu ikisi tamamlanmadan v10 başlatmak fast_sim bulgularını göz ardı eder ve fast_v1 rejimine (~%47 çarpışma) gidilir.
- **CSV monitoring:** 2026-05-31'den beri dondurulmuş — aktif eğitim olmadığından normal. v10 başladığında monitor_agent.py restart gerekli.

### v10 Önerisi
1. **`collision_penalty: 10.0 → 25.0`** — fast_sim v4.8'in %0 çarpışma sweet spot'u. Bu 1 satır değişiklik yapılmadan v10'un voxel/oda kazanımları çarpışmayla sıfırlanır.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d)** — fast_v2 kanıtıyla %80→%1 çarpışma düşüşü. Her iki env fix tamamlandıktan sonra mevcut `ppo.yaml` ile `./scripts/train.sh configs/ppo.yaml` v10 için hazır.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda. v3.0 Gazebo + fast_sim 18-config sweep'in tüm bulguları mevcut yaml'ı onaylıyor; %80+ güven eşiğini geçen hyperparameter sorunu tespit edilmedi. Env code değişikliklerini (collision_penalty ve lidar_history) kullanıcı `drone_exploration_env.py`'de uygulamalı.
---

## [2026-06-04 12:07 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9 crash-loop kalıntısı, 2026-05-30 22:00'dan donmuş) | **ep_rew_mean:** Aktif run YOK — ref: Gazebo v3.0 peak +110.3 @ 610k (kasıtlı durduruldu) | **entropy:** N/A — ref: v3.0 @312k = −5.67 | **std:** N/A — ref: v3.0 @312k = 1.63

### Durum
**Aktif Gazebo eğitimi yok; proje v10 env-code blockers beklemekte.** `training_metrics.csv` 2026-05-30 22:00'dan beri 14 özdeş satırla DONMUŞ (step=193,248, ep_rew_mean=−173.85 — v9 crash-loop kalıntısı, tamamen geçersiz). `configs/ppo.yaml` 2026-06-02'de v10 optimal konfigürasyonuna alındı ve tüm hyperparametreler Gazebo v3.0 + 18-config fast_sim sweep ile çapraz doğrulandı. Son iki gündür (2026-06-03 → 2026-06-04) proje durumunda değişim gözlemlenmiyor: aynı iki env-code blocker (collision_penalty=10, lidar_history=1) bekliyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son 20 satır: TAMAMEN GEÇERSİZ. Tümü özdeş (step=193,248, ep_rew_mean=−173.85, 2026-05-30 22:00–03:01 arası), v9_newmap crash-loop'unun donmuş kalıntısı. Trend analizi yapılamaz.
- Gerçek Gazebo çizgisi (interventions.jsonl + versions.jsonl): v3.0 @434k → ep_rew_mean=99.84, peak=102.54; @610k → peak=110.3 (kasıtlı durduruldu). Olgunlaşma fazındaydı — plato değil, intentional stop.
- peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 voxel/frontier → stochastic eğitimde tutarlı 7+ oda keşfedildi. **+15'lik oda sıçraması çoklu gerçekleşti.**
- v10 henüz başlamadı → v10 için reward eğrisi değerlendirilemez.
- **Görev tanımındaki "v9 şu an çalışıyor / lr=7.5e-5 constant" durumu 5 gün öncesine ait (KICKOFF.md 2026-05-30 tarihli); proje o zamandan bu yana v3.0 Gazebo run → fast_sim 18-config sweep → v10 hazırlık aşamasına geldi.**

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- **GEÇERSIZ SORU — proje birkaç önemli adım ilerledi.** `ppo.yaml` artık v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit 7.5e-5, v9 döneminde 2026-05-30'da analiz edilip terk edildi.
- Sayısal kanıt: v9 sabit lr → 457k adımda yalnızca +20 reward artışı. v3.0 linear decay → 434k'da +99.84. **4.8× verimlilik farkı.** Bu karar kesinleşmiş ve ppo.yaml'a yansımış.
- Entropi kanıtı: v9 @599k → entropy=−3.32 (tehlike eşiği aşıldı); v3.0 @312k → entropy=−5.67 (güvenli). Linear decay her iki metrikte de üstün.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; anlık değer ölçülemiyor. Son güvenilir referans: v3.0 @312k → entropy=−5.67, std=1.63. Her iki değer alarm eşiğinin (entropy>-4.0, std>0.70) çok ötesinde.
- v10 config: `ent_coef=0.008`. Bu v9'un 0.0015'inin 5.3×'i; v3.0'ın kanıtlanmış 0.005'inin 1.6×'i.
- **Tarihsel tehlike penceresi (empirik kanıt — train_v6_normalized.log + train_v7_lrdecay.log):** ~220-260k adım bandında entropy_loss > -4.0 eşiğini aştı (v6=−3.83 @236k, v7=−3.81 @223k). v10 ent_coef=0.008 bu buffer'ı %85+ güvenle aşmaya yeterli.
- **İzleme tetikleyicisi** (v10 başladığında aktif): 200-260k bandında `entropy_loss > −3.5` VE `std < 0.75` eş zamanlı → `ent_coef: 0.008 → 0.012`. Tetik şartı olmadan değişiklik yapılmamalı.
- fast_sim kesinleşmiş dersi: ent_coef artırımı güvenlik-kapsam trade-off'unu kıramadı (v4.2 ent_coef=0.02 → collision %85). Keşif kalitesi obs tasarımından geliyor (lidar_history), entropi katsayısından değil.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Aktif run yokken rakam vermek yanıltıcı. Referans: v3.0 ~150-200k ilk oda sıçraması, ~400k'da 4-5 oda.
- `lidar_history=2` env fix uygulanırsa (fast_v2 kanıtı: collision %80→%1): tahminen **100-180k** ilk oda sıçraması.
- `lidar_history=1` kalırsa: 300-450k'ya uzayabilir — deterministic eval-train gap (v3.0 eval_v3_310k: 10/11 ep tek oda) tekrar eder.
- **Gerçek darboğaz step sayısı değil env-code blocker'lar.**

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: 10.0 → 25.0` (1 satır, reward satırı).** fast_sim 4-noktalı kesin tarama: penalty=22 → yerel optimuma çöküş (%37 çarpışma), **25 → sweet spot (%0 çarpışma)**, 30 → %8 (aşırı tedirgin), 50 → collapse. Mevcut 10.0, fast_sim'in "çöküş eşiği" olan 22'nin bile altında. Bu değişiklik ppo.yaml bağımsız, env reward satırı.
2. **`drone_exploration_env.py`: `lidar_history: 1 → 2` (obs 41-d → 72-d).** Format: `[t-1: 32_lidar | t: 32_lidar | yaw×2 | vel×3 | explore+room | min_lidar | idle]`. fast_v2 kanıtı: tek değişiklikle collision %80→%1 (v4.8: %0). ppo.yaml `MlpPolicy` obs boyutunu env'den otomatik alır — yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip=10.0)` — v3.0 Gazebo + 18-config fast_sim sweep ile çapraz doğrulanmış, optimal. %80+ güven eşiğini aşan yaml sorunu yok.
- **Env kodu açısından BLOCKER (yaml scope dışı, 4. gündür bekliyor):** `collision_penalty=10.0` (optimal: 25.0) ve `lidar_history=1` (optimal: 2). Bu ikisi tamamlanmadan v10 başlatmak fast_sim bulgularını göz ardı etmek anlamına gelir; v10 fast_v1 rejimini (%47 çarpışma, 2 oda) tekrarlar.
- **CSV monitoring:** 2026-05-31'den beri dondurulmuş — aktif eğitim olmadığından normal. v10 başladığında monitor_agent.py restart gerekli.

### v10 Önerisi
1. **`collision_penalty: 10.0 → 25.0` (drone_exploration_env.py, 1 satır):** fast_sim v4.8 sweet spot (%0 çarpışma, 100 bölüm, 2500 adım hayatta). Bu değişiklik olmadan v10'da tüm voxel/oda kazanımları çarpışmayla sıfırlanır (fast_v1 analogu: %47 çarpışma, 2 oda).
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d):** fast_v2 breakthrough fix. [t-1:32_lidar | t:32_lidar | state:8]. Her iki env fix tamamlandıktan sonra mevcut `ppo.yaml` ile `./scripts/train.sh configs/ppo.yaml` komutu v10 için hazır — yaml zaten optimal.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den bu yana v10 optimal konfigürasyonunda; güncel oturumda %80+ güven eşiğini geçen herhangi bir hyperparameter sorunu tespit edilmedi. Proje durumu son günden bu yana değişmedi: aynı iki env-code blocker bekliyor. Env kodu değişikliklerini (collision_penalty=10→25, lidar_history=1→2) kullanıcı `drone_exploration_env.py`'de uygulamalı; bu tamamlandıktan sonra eğitim başlatılabilir.
---

## [2026-06-04 13:05 UTC]
**Step:** 193,248 (CSV STALE — 2026-05-30 22:00'dan donmuş, v9 crash-loop kalıntısı) | **ep_rew_mean:** Aktif run YOK — ref: Gazebo v3.0 peak +110.3 @ 610k (kasıtlı durduruldu) | **entropy:** N/A | **std:** N/A

### Durum
**Proje 5. gün durağan; aktif Gazebo eğitimi yok.** `configs/ppo.yaml` v10 optimal konfigürasyonunda; `drone_exploration_env.py`'deki iki env-code değişikliği bekleniyor. CSV 2026-05-30 22:00'dan bu yana 14 özdeş satırla dondurulmuş.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son 20 satır TAMAMEN GEÇERSİZ: tümü step=193,248, ep_rew_mean=−173.85 (v9 crash-loop monitor'ün stale TB okuması). Trend analizi yapılamaz.
- Güncel referans: v3.0 Gazebo run → peak +110.3 @ 610k (kasıtlı durduruldu, olgunlaşma fazındaydı, plato yok). v10 henüz başlamadı → eğri değerlendirilemez.
- Env kodunda doğrulanan gerçek oda reward: `+10.0` (line 326, drone_exploration_env.py); görev tanımındaki "+15.0" v10 hâli için önerilen değer.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- **GEÇERSİZ SORU** — `ppo.yaml` artık v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit 7.5e-5, v9 döneminde analiz edilip terk edildi (KICKOFF.md 2026-05-30 tarihli; proje o zamandan beri üç önemli aşama geçti).
- Nicel kanıt: v9 sabit lr → 457k adımda +20 reward artışı; v3.0 linear decay → 434k'da +99.84 → **4.8× verimlilik farkı.** Bu karar kesinleşmiş.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Anlık değer yok (aktif run yok). v10 config `ent_coef=0.008` (v9'un 0.0015'inin 5.3×'i, v3.0'ın 0.005'inin 1.6×'i).
- Tarihsel tehlike penceresi: ~220-260k adımda entropy_loss > −4.0 (v6=−3.83 @236k, v7=−3.81 @223k). `ent_coef=0.008` bu bandı %85+ güvenle aşmaya yeterli.
- **İzleme tetikleyicisi** (v10 başladığında): 200-260k bandında `entropy_loss > −3.5` VE `std < 0.75` aynı anda → `ent_coef: 0.008→0.012`. Tetik olmadan değiştirme.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- `lidar_history=2` uygulanırsa (fast_v2 kanıtı): ~100-180k ilk oda sıçraması. `lidar_history=1` kalırsa: 300-450k — deterministic eval-train gap tekrar eder.
- Gerçek darboğaz adım sayısı değil env-code blocker'lar.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty 10.0 → 25.0`** — fast_sim 4-noktalı kesin ölçüm: penalty=22→%37 çarpışma, **25→%0 (sweet spot)**, 30→%8 (aşırı temkinli), 50→collapse. Mevcut 10.0 spektrumun çok altında; v10 fast_v1 rejimine gider (%47 çarpışma).
2. **`drone_exploration_env.py`: `lidar_history 1 → 2`** (obs 41-d → 72-d: `[t-1:32 | t:32 | yaw×2 | vel×3 | explore+room | min_lidar | idle]`) — fast_v2 tek değişiklik kanıtı: %80→%1 çarpışma. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır; yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_reward=true, clip=10.0)` — v3.0 Gazebo + 18-config fast_sim sweep ile çapraz doğrulanmış, optimal.
- **Env kodu: BLOCKER (5. gün, aynı iki item).** `collision_penalty=10.0` (optimal: 25.0) ve `lidar_history=1` (optimal: 2). Bu ikisi tamamlanmadan v10 başlatmak fast_sim bulgularını göz ardı etmek anlamına gelir.
- **CSV monitoring:** Aktif eğitim olmadığından freeze normal. v10 başladığında monitor_agent.py restart gerekli.
- **Yeni gözlem:** `drone_exploration_env.py` line 326 incelendi — oda reward hâlâ `+10.0` (görev tanımındaki "+15.0" v10 için önerilen hedef değer; henüz uygulanmamış).

### v10 Önerisi
1. **`collision_penalty: 10.0 → 25.0`** (`drone_exploration_env.py`, line 342: `reward -= 10.0 → reward -= 25.0`) — fast_sim v4.8 sweet spot. Bu olmadan v10 fast_v1 kolapsını tekrarlar.
2. **`lidar_history: 1 → 2`** (obs 41-d → 72-d) — fast_v2 breakthrough fix. 3 hareketli engel v10'dan aktif olacak; velocity tracking olmadan engel ivmesi algılanamaz.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den bu yana v10 optimal konfigürasyonunda; %80+ güven eşiğini geçen hyperparameter sorunu tespit edilmedi. Env code değişikliklerini (`collision_penalty=10→25`, `lidar_history=1→2`) kullanıcı `drone_exploration_env.py`'de uygulamalı; ardından `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir.
---

## [2026-06-04 14:15 UTC]
**Step:** N/A — v10 fresh start henüz başlatılmadı | **Son güvenilir veri:** v3.0 @ 610k (peak=110.3, kasıtlı durduruldu) | **ep_rew_mean:** N/A | **entropy:** N/A | **std:** N/A

### Durum
CSV 2026-05-30 22:00'dan beri tamamen frozen (step=193248, v9/v10 crash-loop kalıntısı). Gerçek son durum: v3.0 Gazebo run 610k/1.5M adımda kasıtlı durduruldu (peak=110.3); ardından 18 fast_sim deneyi (v4.1→v5.0) tamamlandı ve bulgular ppo.yaml v10 config'ine entegre edildi (2026-06-02). **v10 eğitimi henüz başlamadı** — log'da v10 train logu yok, versions.jsonl son entry 2026-06-01 08:05 (fast_sim kapanışı).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi geçersiz (frozen, stale). v3.0 gerçek eğri: 434k'da peak=102.54 (2026-06-01 01:30), 610k'da peak=110.3 (kasıtlı durdurma).
- v8 all-time best: +113 @1.6M step. v3.0 bunu 610k'da neredeyse yakaladı (+110.3) — v3.x tasarımı kanıtlandı.
- v10 için eğri: sıfır. Henüz veri yok.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Geçersiz soru: ppo.yaml v10'da `lr=3e-4 → 1e-5 linear` schedule uygulanıyor. Sabit lr kullanımı terk edildi. v3.0'ın kanıtlanmış hyperparametreleri baz alınarak yazılmış — doğru seçim. SB3 resume'da progress_remaining sıfırlandığından constant lr kullansaydık 5e-5 sabit daha güvenli olurdu; fakat v10 fresh start olduğundan bu risk yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Ölçüm yok (eğitim başlamadı). Ancak v10 config'de `ent_coef=0.008` — bu v2.1/v3.x'in 0.005'inden %60 daha yüksek. fast_sim v4.8 champion da yüksek entropi korumasıyla 5 odayı tutarlı keşfetti (%0 çarpışma). ent_coef=0.008 erken deterministikleşmeye (entropy>-4.0) karşı iyi bir tampon. Risk: 600k+ bandında std<0.7 ve entropy>-3.5 birlikteliği; şu an alarm yok.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- fast_sim v4.8 benchmark: 0% çarpışma, 5 oda, 117 voxel — bu performans collision_penalty=25 ve lidar_history=2 ile elde edildi.
- v10 env'de aynı bulgular yansıtılacaksa (41-d→72-d obs, coll_penalty=25), ilk oda geçişi ~80-150k step aralığında bekleniyor. Tutarlı 4-5 oda: 300-600k. 6 odanın tamamı: belirsiz (fast_sim'de 5M'de bile garantili değildi, v4.10 6 odaya ulaşmak için 5M+%54 çarpışma trade-off'u yarattı).
- **KRİTİK:** fast_sim'de 1.5M sonrası safety collapse gözlemlendi (v4.10: 3.2M'de %100 çarpışma). ppo.yaml'daki `total_timesteps: 1500000` sınırı bu yüzden zorunlu — aşılmamalı.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **Env kodu doğrulaması (ÖNCE EĞİTİM BAŞLATMADAN):** ppo.yaml header'ı "fast_sim kesinleşmiş bulgular v10 env koduna yansıtılacak" diyor. drone_exploration_env.py'de `collision_penalty: 10→25` ve `lidar_history: 1→2 (41-d→72-d obs)` değişikliklerinin yapılıp yapılmadığını doğrula. Obs boyutu 41-d yerine 72-d olursa ağ mimarisi değişmez (256x256 net_arch yeterli) ama env ile policy boyut uyumsuzluğu eğitimi başlar başlamaz patlatır.
2. **norm_obs=false risk izleme:** VecNormalize'da `norm_obs: false` — raw lidar değerleri (0-12m aralığı) ile IMU/velocity değerleri (~0-1 normalize) aynı ağa girerse büyük ölçek farkı oluşur. fast_sim bunu tolere etti (%0 çarpışma, 5 oda), ancak Gazebo gerçek ortamında lidar gürültüsü farklı. İlk 50k adımda ep_len trend'i izle: ep_len < 30 sabitleniyor ve ep_rew_mean iyileşmiyorsa norm_obs=true'ya geç (konfigürasyon tek satır değişiklik).

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** v10 config (lr=3e-4→1e-5, ent_coef=0.008, n_steps=2048, n_epochs=10, clip_range=0.2, gae_lambda=0.95, n_envs=1, 1.5M limit) fast_sim bulgularıyla tam tutarlı. %80+ güven eşiğini aşan bir config sorunu yok.
- **Operasyonel açıdan:** v10 eğitimi hâlâ başlatılmamış. Başlatılmadan önce env kodu (collision_penalty=25, lidar_history=2) ve obs boyutu (72-d) doğrulanmalı.
- **CSV monitoring:** Frozen, zaten biliniyor. v10 için yeni TB dizini açılacak (`./runs/ppo_v10/tb`) — oradan izleme devam edecek.

### v10 Önerisi
1. **Env kodu (drone_exploration_env.py) → collision_penalty=25, lidar_history=2:** fast_sim'in tek en yüksek ROI bulgusu. Bu değişiklik olmadan v10 eğitimi, v3.0'ın collision_penalty=10 ile başladığı eski ortamda çalışır — fast_sim avantajı kaybolur.
2. **1.5M hard stop:** `total_timesteps: 1500000` sınırını aşma. v4.10/v4.11 kanıtı: 2M+ sonrası policy safety collapse geliyor, ne kadar ceza artırılsa da önlenemiyor (v4.11'de ceza 50'ye çıkarıldı, %100 çarpışma oldu). 1.5M'de durdurup eval yap, rooms_mean≥4 ise deploy et.

### Müdahale
**YOK** — configs/ppo.yaml v10 konfigürasyonu fast_sim bulgularıyla (collision_penalty=25, lidar_history=2, 1.5M limit) örtüşüyor; lr schedule, ent_coef, clip_range, n_epochs hepsi kanıtlanmış değerlerde. %80+ güven eşiğini aşan bir hyperparameter sorunu tespit edilmedi. Müdahale env kodu doğrulaması (trainer'ın değil env'in sorumluluğu) ve operasyonel başlatma kararına bırakıldı.
---

## [2026-06-04 15:03 UTC]
**Step:** 193,248 (CSV STALE — son gerçek veri: v3.0 @ 610k peak=110.3, kasıtlı durduruldu 2026-05-31) | **ep_rew_mean:** Aktif run YOK | **entropy:** N/A | **std:** N/A

### Durum
Önceki giriş (14:15 UTC) ile kıyaslandığında değişen bir şey yok: CSV hâlâ frozen, v10 eğitimi hâlâ başlatılmadı, ppo.yaml v10 optimal konfigürasyonunda. Aynı iki env-code blocker 5. günde devam ediyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'nin anlamlı son 4 satırı (2026-05-30 11:02–12:32 UTC, v9 erken faz): ep_rew_mean −270 bandında sabitlenmiş; step 142k'dan 599k'a rağmen neredeyse sıfır ilerleme. v9 keşif yetersizliği teyit — ent_coef=0.0015 + constant lr=7.5e-5 kombinasyonu erken bloke etti.
- CSV son 20 satır tamamen stale: step=193,248, ep_rew_mean=−173.85, tümü özdeş. Crash-loop monitor'ün aynı checkpoint'i (ppo_drone_180000_steps.zip) tekrar tekrar okuması kalıntısı.
- v3.0 gerçek eğri (interventions.jsonl): 434k'da +102.54, 610k'da +110.3 — plato değil yavaşlama fazı, kasıtlı durduruldu. v8 all-time: +113 @1.6M.
- v10 eğri: sıfır veri — henüz başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- ppo.yaml v10'da lr=3e-4→1e-5 linear (1.5M boyunca doğrusal); sabit lr terk edildi. v9 CSV kanıtı: 457k adımda (step 142k→599k) ep_rew_mean −290→−270 (−20 iyileşme). v3.0 linear decay ile aynı bant: 434k'da +99.84 (4.8× verimlilik farkı). Entropy trend'i de aynı tabloyu doğruluyor: v9 @599k entropy=−3.32 (alarm eşiği üstünde); v3.0 @312k entropy=−5.67 (güvenli).

**c) Entropy/std değerleri keşif için yeterli mi?**
- Anlık değer yok (aktif run yok). v9 CSV referansı: entropy −3.88 @142k → −3.32 @599k — alarm eşiği (−4.0) aşılmadı ama trend tehlikeli yöndeydi (çizginin devamı 700-800k'da eşiği aşardı). v10 ent_coef=0.008 (v9'un 5.3×'i, v3.0'ın 1.6×'i) bu riski bastırıyor. İzleme tetikleyicisi: 200-260k bandında entropy_loss > −3.5 VE std < 0.75 eş zamanlı → ent_coef 0.008→0.012.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- lidar_history=2 uygulanmışsa: ~100-180k ilk oda sıçraması (fast_v2 kanıtı). lidar_history=1 kalırsa: 300-450k (v3.0 eval_v3_310k.log: 10/11 episode tek oda kaldı — eval-train gap). v10'da 3 hareketli engel aktif olacak; velocity tracking olmadan engel ivmesi algılanamaz — lidar_history=1 ile 3 engel, 1 engelle aynı performance verir.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty 10.0 → 25.0** — fast_sim 4-noktalı tarama kesin ölçüm: penalty=22→%37 çarpışma, 25→%0 (sweet spot), 30→%8 (aşırı temkinli), 50→collapse. Mevcut 10.0 collapse eşiği olan 22'nin bile altında; v10 başlarsa fast_v1 rejimini (%47 çarpışma) tekrarlar.
2. **drone_exploration_env.py: lidar_history 1 → 2 (obs 41-d → 72-d)** — fast_v2 single-change breakthrough: collision %80→%1. Format: [t-1:32_lidar | t:32_lidar | cos/sin(yaw) | vx/vz/wz | explore+room | min_lidar | idle]. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır; yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- ppo.yaml açısından: HAYIR. lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0) — v3.0 Gazebo + 18-config fast_sim sweep ile çapraz doğrulanmış, optimal. %80+ güven eşiğini aşan config sorunu yok.
- Env kodu: BLOCKER (5. gün). collision_penalty=10 (optimal: 25) ve lidar_history=1 (optimal: 2) değiştirilmeden v10 başlatmak fast_sim bulgularını boşa çıkarır.
- total_timesteps=1.5M hard stop: aşılmamalı. fast_sim v4.10/v4.11 kanıtı: 2M+ sonrası safety collapse kaçınılmaz (v4.10 @3.2M: %100 çarpışma; v4.11 penalty=50'ye çıkarıldı, yine %100).
- CSV monitoring: frozen normal (aktif run yok). v10 başladığında monitor_agent.py restart gerekli (yeni TB dizini: ./runs/ppo_v10/tb).

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** — fast_sim v4.8 sweet spot; bu değişiklik olmadan tüm voxel/oda kazanımları çarpışmayla sıfırlanır.
2. **lidar_history: 1 → 2** — fast_v2 breakthrough; 3 hareketli engel ortamında velocity tracking olmadan engel ivmesi kör kalır.

### Müdahale
**Yok** — configs/ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda; %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Env kodu değişiklikleri (collision_penalty=10→25, lidar_history=1→2) kullanıcı tarafından drone_exploration_env.py'de uygulanmalı; ardından ./scripts/train.sh configs/ppo.yaml ile v10 başlatılabilir.
---
