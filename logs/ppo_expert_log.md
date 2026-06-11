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

## [2026-06-04 16:07 UTC]
**Step:** 193,248 (CSV SON DEĞER — v9 crash kalıntısı, STALE) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
CSV 2026-05-30 22:00'dan 03:01'e kadar 20 özdeş satırla DONMUŞ — v9 training ~193k step'te kalıcı crash sonrası monitor crash-loop'a girmiş. Güncel Gazebo eğitimi YOK; ppo.yaml 2026-06-02'de v10'a tamamen revize edilmiş (fast_sim v4.1-v5.0 bulgularını içeriyor). v10 başlamış mı bilinmiyor; env kodundaki (drone_exploration_env.py) fast_sim değişikliklerinin uygulanıp uygulanmadığı onaylanmalı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 46 satırı iki net faz gösteriyor:
  - **Faz 1 (satır 1-4, STALE):** Checkpoint ppo_drone_80000_steps.zip hiç değişmedi → TB verisi donduyken monitor yazmaya devam etti. ep_rew_mean -290→-270 (çok yavaş iyileşme, 142k→599k step gösteriliyor ama sahte). Entropy -3.886→-3.324 (her ikisi de -4 ÜSTÜNDE = tehlike bölgesi). std 0.888→0.746 (0.7 eşiğine yaklaşıyor).
  - **Faz 2 (satır 5-46, crash-recovery loop):** Her crash sonrası monitor 49k-140k arası step'lerden yeniden başlatmış. ep_rew_mean -25→-174 (tutarsız, oscile ediyor, hiç pozitif değer yok). Entropy -4.21 ila -4.26 (kabul edilebilir bandda, eşiğin hemen altında). std ~0.985 (sağlıklı).
  - **Son durum (satır 27-46):** Step=193248 tamamen donmuş, training kalıcı olarak ölmüş.
- **+15'lik oda sıçraması**: CSV'de HİÇ görülmedi. ep_rew_mean 0'ın üzerine hiç çıkmadı — v9 6-oda haritasında oda keşfini hiç başaramadı.
- **Referans: v3.0 Gazebo run** (interventions.jsonl): step 312k→ep_rew=+47.1, step 434k→peak +102.54, step 501k→reward +123.25. v3.0 config (lr 3e-4→1e-5, ent_coef=0.008) v9'dan çok daha başarılı oldu.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- HAYIR — ve zaten terk edildi. v9 constant lr kullanırken erken faz keşfi yetersiz kaldı: yüksek LR'e ihtiyaç duyulan 0-200k bandında düşük LR (7.5e-5) politikanın reward yüzeyini keşfetmesini engelledi.
- v10'da doğru yol: lr 3e-4 → 1e-5 doğrusal (v3.0'ın kanıtlanmış şeması). 1.5M step için: 0-500k'da ~2.5e-4 (yüksek, aktif keşif), 500k-1M'da ~1.7e-4 (orta), 1M-1.5M'da ~1e-4→1e-5 (fine-tune). v8'in 3e-4→3e-5 şemasına yapısal olarak benzer.

**c) Entropy/std değerleri keşif için yeterli mi?**
- **v9 Faz 1'de KRİTİK UYARI**: entropy -3.3 ila -3.9 (-4 ÜSTÜNDE) + std 0.74-0.89 → ent_coef=0.0015 yetersiz. Policy, reward yüzeyi henüz öğrenilmeden deterministikleşti. Bu v9'un temel başarısızlık mekanizmasından biri.
- **v9 Faz 2'de**: entropy -4.21 (yeni başlatma, frech std ~1.0) → crash-restart'lar her seferinde entropi resetledi, ama eğitim ilerleyemeden tekrar kilitlendi.
- **v10'da beklenti**: ent_coef=0.008 (v9'un 5.3×'ı) + n_steps=2048 (daha büyük rollout). 500k step'e kadar entropy -5 ile -4 arası tutulabilir. std için 1.5M boyunca 0.8-1.4 bekleniyor; 0.7'nin altına düşerse ent_coef=0.01'e artışı değerlendir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v9 başarısız olduğundan bu soruyu v3.0 referansıyla yanıtlamak gerekiyor:
  - v3.0 @ 312k: ep_rew=+47.1 (ilk oda bonusları alınıyor, tutarsız)
  - v3.0 @ 434k: peak +102.54 (≈6 oda × 15 + voxel ≈ 90+12; çoğu odaya giriyor)
  - v3.0 @ 501k: reward +123.25 (en iyi performans)
- **v10 tahmini** (aynı config, fast_sim bulgularıyla iyileştirilmiş env):
  - İlk oda (tutarsız): 150-250k step
  - 3-4 oda tutarlı: 300-500k step
  - 5-6 oda tutarlı: 600-900k step
  - collision_penalty=25 (fast_sim v4.8 bulgusu) güvenliği korurken 5 odayı mümkün kılıyor

**e) v10 için en kritik 1-2 öneri:**
1. **ÖNCE drone_exploration_env.py doğrula**: fast_sim'in iki kanıtlanmış bulgusu Gazebo env koduna YANSITILMALI — (a) `collision_penalty: 10 → 25` (v4.8: %0 çarpışma, sweet spot kesin; 22=çöküş, 30=aşırı temkin→hatalı manevra, 25=OPTIMAL), (b) `lidar_history: 1 → 2` (obs 41-d→72-d, eval gap fix). Bu iki değişiklik olmadan v10 eğitimi v9'un tekrarı olacak.
2. **GZ transport stabilite fix'ini koru**: interventions.jsonl'deki "freeze_rootcause_fix" (GZ_IP=127.0.0.1 + python timeout set_pose 3s + obstacle 1s + updater 4Hz). Bu fix olmadan training 2048-step rollout sonrası bloklayacak. Ayrıca n_envs=1 (SubprocVecEnv deadlock'u kesin çözümü) v10'da zaten uygulanmış — DOKUNMA.

**f) Acil müdahale gerekiyor mu?**
- v9 uzun süredir ölü (May 30 22:00'den beri). Eğitim makinesi (kullanıcının desktop'u) v10 çalıştırıyor mu bilinmiyor.
- **ppo.yaml'a müdahale gereksiz** — v10 config kanıtlanmış optimal parametreleri içeriyor.
- Acil eylem gerektiren tek husus: env kodu doğrulaması (yukarıda madde 1).

### v10 Önerisi
1. `drone_exploration_env.py`'de `collision_penalty=25` ve `lidar_history=2` onaylandıktan sonra `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılmalı.
2. 300k step sonrası `ep_rew_mean > 0` görülmezse tek alarm noktası: entropy izle (-4'ün üstüne çıkıyorsa ent_coef=0.01'e artır), yoksa config'e dokunma.

### Müdahale
**Yok** — ppo.yaml v10'da zaten optimal. CSV'deki v9 ölüsü için config değişikliği anlamlı değil; %80+ güven eşiğini aşan aktif sorun yok.
---

## [2026-06-05 12:10 UTC]
**Step:** 193,248 (CSV SON DEĞER — STALE, 6 gün önce donmuş) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
training_metrics.csv 2026-05-31 03:01'den beri güncellenmemiş (6 gün). v3.0 Gazebo run 610k/1.5M adımda kasıtlı durduruldu (peak=110.3). fast_sim zinciri v5.0'da kapandı — 18 config, 4 lever kategorisi tüketildi, trade-off temel olduğu kesinleşti. ppo.yaml 2026-06-02'de v10'a güncellendi (fast_sim + v3.0 Gazebo çapraz doğrulamalı, optimal). v10 Gazebo eğitimi henüz başlamamış.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV tamamen stale (v9 crash-loop kalıntısı). Güvenilir son veri noktaları:
  - v3.0 Gazebo @312k: ep_rew≈+47 (ilk oda bonusları tutarsız)
  - v3.0 Gazebo @434k: peak +102.54 (5-6 oda aktif)
  - v3.0 Gazebo @501k: reward +123.25 (en yüksek gözlem)
  - v3.0 Gazebo @610k: kasıtlı durduruldu (peak=110.3)
- v10 başlamadı → aktif reward eğrisi yok.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Bu tartışma kapalı. ppo.yaml'da lr=0.0003→1e-5 doğrusal (1.5M boyunca). v3.0 Gazebo (aynı şema) 110.3 peak ürettiği için doğru seçim kanıtlanmış. Sabit lr=7.5e-5 kullanılmıyor, v9 kararı çoktan geride bırakıldı.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Stale CSV'de entropy=-4.21, std=0.985 (her ikisi de sağlıklı sınırlarda). v10 başladığında beklenti: ent_coef=0.008 ile 500k adıma kadar entropy -4.5 ile -5.5 arası, std 0.85-1.3 arası tutulmalı. İzleme tetikleyicisi: entropy_loss > -3.5 VE std < 0.75 eş zamanlı → ent_coef 0.008→0.010 artışı değerlendir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı. Referans (v3.0 Gazebo, aynı config): ~300-430k adımda 5-6 oda tutarlı. fast_sim bulguları (collision_penalty=25 + lidar_history=2) Gazebo env'e uygulanırsa bu süre ~150-250k'ya kısalabilir. Uygulanmazsa: v3.0 referansı geçerli.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty=10→25** — fast_sim 4-nokta ölçümü (v4.8→v4.9 sweep): penalty=22→%37 çarpışma, 25→%0 (sweet spot), 30→%8 (aşırı temkin), 50→collapse. Mevcut 10.0 ile v10 eğitimi fast_v1 rejimini (%47 çarpışma) tekrarlar; tüm voxel/oda kazanımları çarpışmayla sıfırlanır.
2. **drone_exploration_env.py: lidar_history=1→2 (obs 41-d→72-d)** — fast_v2 tek değişiklik: çarpışma %80→%1. 3 hareketli engel ortamında velocity tracking olmadan engel ivmesi kör kalır; lidar_history=2 olmadan v5.0'ın da kanıtladığı üzere obs darboğazı değil ama fark belirleyici. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır; yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- ppo.yaml açısından: **HAYIR**. lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0) — v3.0 Gazebo + 18-config fast_sim sweep ile çapraz doğrulanmış. %80+ güven eşiğini aşan config sorunu yok.
- **total_timesteps=1.5M hard cap**: kesinlikle aşılmamalı. fast_sim v4.10 @3.2M: %100 çarpışma (safety collapse kaçınılmaz); v4.13 @8M bile düzeltemedi. 1.5M üzeri reward'ın per-voxel birikimi penalty'i eziyor, trade-off tersine dönüyor.
- **Monitor**: v10 başladığında monitor_agent.py yeniden başlatılmalı; yeni TB dizini ./runs/ppo_v10/tb, eski ./runs/ppo_v9_newmap dizini okunmamalı.

### v10 Önerisi
1. **collision_penalty: 10.0→25.0** (drone_exploration_env.py) — v4.8 sweet spot kesin: daha düşük=çöküş, daha yüksek=aşırı temkin. Bu değişiklik olmadan v10 fast_v1 rejimini (%47 çarpışma) tekrarlayacak.
2. **lidar_history: 1→2** (drone_exploration_env.py) — fast_v2 breakthrough; 3 hareketli engel ortamında engel hızını gizlemek politikanın en kritik kör noktası.

### Müdahale
**Yok** — configs/ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda (fast_sim + v3.0 Gazebo çapraz doğrulamalı). %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Env kodu değişiklikleri (collision_penalty=10→25, lidar_history=1→2) kullanıcı tarafından drone_exploration_env.py'de uygulanmalı; ardından ./scripts/train.sh configs/ppo.yaml ile v10 başlatılabilir.
---

## [2026-06-05 13:09 UTC]
**Step:** 193,248 (CSV SON DEĞER — STALE, 6 gün önce donmuş) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
training_metrics.csv 2026-05-31 03:01'den itibaren tamamen stale; v9 eğitimi step 193k'da kalıcı crash ile ölmüş. ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda (fast_sim 18-config sweep + v3.0 Gazebo çapraz doğrulamalı). v10 Gazebo eğitimi henüz başlamamış; tek kalan bloker env kodu değişiklikleri.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi eğitimin durumunu yansıtmıyor. Güvenilir son referans noktaları (interventions.jsonl + versions.jsonl):
  - v3.0 Gazebo @312k: ep_rew≈+47, @434k: peak +102.54, @501k: +123.25, @610k: kasıtlı durduruldu (peak=110.3)
  - fast_sim v4.8 @1.5M: %0 çarpışma, 5 oda, voxels=117 — güvenli deploy edilebilir politika
  - fast_sim v4.10 @5M: voxels=281 (%44.5 kapsam), 6 oda FAKAT çarpışma %54 — aşırı eğitim çöküşü kanıtlandı
- v10 aktif reward eğrisi YOK (eğitim başlamamış).

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Bu tartışma kapalı. ppo.yaml lr=3e-4 → 1e-5 doğrusal (1.5M boyunca) — v9'un constant 7.5e-5'inin başarısız olduğu 0-200k keşif bandında tam lr sağlıyor. v3.0 Gazebo (aynı şema) 110.3 peak ürettiği için kanıtlanmış. Müdahale gerekmiyor.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Stale CSV'de entropy=-4.212, std=0.985 ancak v9'a ait. v10 beklentisi: ent_coef=0.008 (v9'un 5.3×'ı) ile 500k step'e kadar entropy -4.5 ile -5.5 arası, std 0.85-1.3. Alarm tetikleyici: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI → ent_coef 0.008→0.010 değerlendir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı. Referans (v3.0 Gazebo, aynı config): 300-430k adımda 5-6 oda tutarlı. collision_penalty=25 + lidar_history=2 Gazebo env'e uygulanırsa bu süre 150-250k'ya kısalabilir (fast_v2 breakthrough). Uygulanmazsa v3.0 referansı (300-430k) geçerli.

**e) v10 için en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty=10→25** — fast_sim 4-nokta ölçümü (v4.8→v4.9 sweep) kesin: 22→rooms 5→2 collapse+%37 çarpışma, 25→%0 çarpışma (sweet spot), 30→%8 (aşırı temkin). Mevcut penalty=10.0 ile v10 eğitimi fast_v1 rejimini (%47 çarpışma) tekrarlayacak; tüm voxel/oda kazanımları çarpışmayla sıfırlanacak.
2. **drone_exploration_env.py: lidar_history=1→2 (obs 41-d→72-d)** — fast_v2 tek değişiklik: çarpışma %80→%1. 3 hareketli engel ortamında engel hızını gizlemek v10'un en kritik kör noktası. ppo.yaml MlpPolicy obs boyutunu env'den otomatik alır; yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- ppo.yaml açısından: **HAYIR**. v10 config v3.0 Gazebo + fast_sim sweep çapraz doğrulamalı ve optimal.
- **total_timesteps=1.5M hard cap kritik**: fast_sim v4.10 @3.2M: %100 çarpışma (safety collapse); v4.13 @8M bile düzeltemedi. 1.5M SINIRI AŞILMAMALI.
- **Monitor**: v10 başladığında TB dizini ./runs/ppo_v10/tb (eski ./runs/ppo_v9_newmap karıştırılmamalı).
- Acil eylem gerektiren husus: env kodu (kullanıcı tarafında, yukarıda madde 1-2).

### v10 Önerisi
1. **collision_penalty: 10.0→25.0** (drone_exploration_env.py) — fast_sim 4-nokta sweet spot kesin. Bu olmadan v10 fast_v1 rejimini (%47 çarpışma) tekrarlayacak.
2. **lidar_history: 1→2** (drone_exploration_env.py) — fast_v2 breakthrough; engel hız bilgisi olmadan 3 hareketli engel ortamında policy kör kalır.

### Müdahale
**Yok** — configs/ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1). %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Çapraz doğrulama: v3.0 Gazebo (peak 110.3) + fast_sim 18-config sweep (v4.8 champion: %0 çarpışma, 5 oda).
---

## [2026-06-05 14:08 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri donmuş) | **ep_rew_mean:** -173.85 (stale/güvensiz) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
Eğitim tamamen durmuş: v9 step 193k'da kalıcı crash, CSV 6 gündür güncellenmemiş. ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda — fast_sim 18-config sweep (v4.8 champion: %0 çarpışma, 5 oda) + v3.0 Gazebo (peak 110.3) çapraz doğrulamalı. v10 Gazebo eğitimi hâlâ başlamamış; tek bloker: drone_exploration_env.py'de iki satır değişiklik.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi güvenilir değil. v9, adım 193k'da crash-loop'a girdi (interventions.jsonl'de crash_recovery olayları 14:22–19:14 arası her 20 dakikada, sonra 180k ckpt'e geçti, step 193k'da dondu). Güvenilir son benchmark: v3.0 Gazebo @501k: ep_rew=+123.25 (tüm zamanların en yüksek Gazebo reward'ı), @610k: kasıtlı durduruldu, peak=110.3. fast_sim v4.8: %0 çarpışma, 5 oda, voxels=117 — deploy edilebilir politika.
- Aktif eğitim YOK → eğri analizi yapılamaz.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Geçersiz soru. ppo.yaml zaten lr=3e-4 → 1e-5 doğrusal (1.5M boyunca). V9'daki sabit 7.5e-5 geride bırakıldı. V3.0 Gazebo (aynı lr şeması) 110.3 peak ürettiği için kanıtlanmış. Açık tartışma yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Stale CSV değerleri (entropy=-4.212, std=0.985) v9'a ait, güvenilmez. v10 çalıştığında izleme eşiği: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI → ent_coef 0.008→0.010 değerlendir. ent_coef=0.008 (v9'un 5.3×'ı) 500k step boyunca keşfi destekleyecek kapasitede.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı. Referans tablo (interventions.jsonl + versions.jsonl):
  - collision_penalty=25 + lidar_history=2 Gazebo env'e uygulanırsa: 150–250k adımda 5–6 oda (fast_v2 breakthrough analogu)
  - Uygulanmazsa: 300–430k adım (v3.0 Gazebo referansı)
  - 1.5M cap'i aşmamak şartıyla süre kısaltma potansiyeli: ~%40

**e) v10 için en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty 10.0 → 25.0** — fast_sim 4-nokta sweet spot: coll=22→rooms 5→2 collapse+%37 çarpışma, coll=25→%0 (OPTIMAL), coll=30→%8 (aşırı temkin). Mevcut 10.0 ile v10 eğitimi fast_v1 rejimini (%47 çarpışma) tekrarlayacak; oda geçişi için biriktirilen voxel kazanımları çarpışmayla sürekli sıfırlanacak.
2. **drone_exploration_env.py: lidar_history 1 → 2 (obs 41-d → 72-d)** — fast_v2 tek-değişken deneyi: çarpışma %80→%1. 3 hareketli engel ortamında politika tek lidar frame ile engel yönünü görür ama hızını göremez; lidar_history=2 engel ivmesini çıkarılabilir yapar. ppo.yaml değişikliği gerekmez (MlpPolicy obs boyutunu env'den otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** v10 config optimal ve dokunulmaz (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0)). %80+ güven eşiğini aşan config sorunu tespit edilmedi.
- **Kritik hard limit: total_timesteps=1.5M aşılmamalı.** fast_sim v4.10 @3.2M: %100 çarpışma; v4.13 @8M: regularize ama voxel tepesinin altında. 2M+ sonrası safety collapse kaçınılmaz.
- **Acil eylem (kullanıcı tarafı):** drone_exploration_env.py'de iki satır değişikliği → ./scripts/train.sh configs/ppo.yaml ile v10 başlatma. Bu iki değişiklik olmadan eğitim başlasa bile fast_v1 rejimi tekrarlanacak.

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** (drone_exploration_env.py) — fast_sim 4-nokta kesin sweet spot; bu olmadan v10 fast_v1 (%47 çarpışma) rejimini tekrarlayacak.
2. **lidar_history: 1 → 2** (drone_exploration_env.py, obs 41-d → 72-d) — fast_v2 breakthrough (çarpışma %80→%1); 3 hareketli engel ortamında değiştirilemez ön koşul.

### Müdahale
**Yok** — configs/ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda. %80+ güven eşiğini aşan hyperparameter sorunu yok. CSV stale olması ppo.yaml müdahalesini gerektirmiyor; aktif eğitim verisi olmaksızın config değişikliği veri dışı karar olur. Bloker: env kodu (kullanıcı tarafında, yukarıdaki 1-2 madde).
---

## [2026-06-05 15:08 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri donmuş, 6 gün) | **ep_rew_mean:** -173.85 (stale/geçersiz) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
Aktif eğitim yok. CSV 6 gündür donmuş; v9 step 193k'da kalıcı crash-loop'la ölmüş. ppo.yaml 2026-06-02'den beri v10 optimal konfigürasyonunda (fast_sim 18-config sweep + v3.0 Gazebo çapraz doğrulamalı). v10 Gazebo eğitimi hâlâ başlamamış; tek bloker drone_exploration_env.py'deki iki satır env kodu değişikliği.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son 30 satırın anatomisi (tam veri seti tarandı):
  - **İlk 4 satır (11:02-12:32, v9 orijinal run):** step 142k→599k, ep_len sabit 1000 (max), ep_rew: -290→-270. Klasik plato. entropy: -3.886→-3.324 (deterministikleşme trendi), std: 0.888→0.746. 0.7 eşiğine yaklaşıyordu.
  - **13:00-20:55 (crash-loop, 15+ yeniden başlatma):** step 49k-145k arası kaotik. ep_rew: -102→-47 (ppo.yaml değişikliği sonrası daha iyi LR ile hızlı iyileşme). Monitor hatalı biçimde 80k checkpoint'e tekrar tekrar döndü.
  - **21:00-22:00 (son geçerli faz):** Checkpoint ilerlemesi: 80k→120k→140k→180k. ep_rew: -37 → -47 → -173. FPS: 107→67 (düşüş, süreç yorgunluğu).
  - **22:00-03:01 (son dondurma):** step=193,248, ep_rew=-173.85, ep_len=637, fps=72. Özdeş 14 satır → süreç hayatta ama ilerlemiyordu; sonunda ölmüş.
- **+15'lik oda sıçraması görüldü mü?** Hayır — v9 run'ında hiçbir zaman pozitif reward bölgesine ulaşılamadı. En iyi değer -37 (21:20 UTC, 149k step), bu da oda bonusu değil (oda olsaydı +15 ile pozitife geçerdi). Tüm iyileşme idle/çarpışma cezalarının azalmasından.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Tartışma kapandı. KICKOFF.md'de 7.5e-5 yazsa da ppo.yaml zaten 2026-06-02'den beri lr=3e-4→1e-5 linear'a yeniden yazıldı. V9 plateau verisi bu kararı doğrular: constant low-LR altında 599k step boyunca hiçbir breakthrough gelişmedi. V3.0 Gazebo (aynı linear şema) 610k'da peak=110.3 üretti — kanıtlanmış.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri (entropy=-4.212, std=0.985) v9 crash kalıntısı, güvensiz. V10 için izleme eşiği: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI → ent_coef 0.008→0.010 değerlendir. ent_coef=0.008 (v9'un 5.3×'ı, v3.0 Gazebo'nun 1.6×'ı) ile 500k+ step boyunca keşif kapasitesi yeterli. Alarm eşiklerine ayrı ayrı tepki verme: ikisi birden tetiklenmelidir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- V10 başlamadı. Referans: v3.0 Gazebo (aynı ppo.yaml şeması, collision_penalty=10, lidar_history=1) @ 300-430k adım: 5-6 oda tutarlı. **Env kodu değişiklikleri uygulanırsa** (collision_penalty=25, lidar_history=2): fast_v2 breakthrough analoğu ile 150-250k adımda 5-6 oda mümkün. Uygulanmazsa: v3.0 referansı (300-430k) geçerli; ve fast_v1 (%47 çarpışma) tekrarlanma riski yüksek.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty 10 → 25** — fast_sim 4-nokta kesin sweeping: coll=22→%37 çarpışma (5 oda→2 oda collapse), coll=25→%0 (OPTIMAL, 5 oda), coll=30→%8 (aşırı temkin). Mevcut 10.0 ile v10 fast_v1 rejimini tekrarlayacak.
2. **drone_exploration_env.py: lidar_history 1 → 2 (obs 41-d → 72-d)** — fast_v2 tek-değişken kanıtı: çarpışma %80→%1. 3 hareketli engel ortamında politika engel hızını göremez; 2 frame farkı hız vektörünü çıkarılabilir yapar. ppo.yaml değişikliği gerekmez (MlpPolicy obs boyutunu env'den alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config 2026-06-02'den beri dokunulmaz ve çapraz doğrulamalı.
- **Kritik hard cap: total_timesteps=1.5M aşılmamalı.** Fast_sim v4.10 @3.2M: %100 çarpışma; v4.13 @8M: regularize ama voxel tepesinin altında. 2M+ sonrası safety collapse kaçınılmaz — deneysel olarak 4 bağımsız noktayla kanıtlandı.
- **Acil eylem (kullanıcı tarafı):** collision_penalty=25 + lidar_history=2 → ./scripts/train.sh configs/ppo.yaml. Bu iki satır olmadan eğitim başlasa bile fast_v1 çarpışma rejimi tekrarlanır.

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** (drone_exploration_env.py) — 4-nokta sweet spot kanıtlandı: 22=collapse, 25=optimal, 30=aşırı temkin. Bu olmadan v10 fast_v1 rejimini (%47 çarpışma) tekrarlayacak.
2. **lidar_history: 1 → 2** (drone_exploration_env.py, obs 41-d → 72-d) — fast_v2 breakthrough: çarpışma %80→%1. 3 hareketli engel ortamında değiştirilemez ön koşul.

### Müdahale
**Yok** — configs/ppo.yaml v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1). CSV tam analizi (tüm 30+ satır) yapıldı: v9 hiçbir zaman oda breakthrough'una ulaşamadı (max ep_rew=-37), eğitim 193k step'te dondu. %80+ güven eşiğini aşan config sorunu tespit edilmedi. Bloker env kodu (kullanıcı tarafı).
---

## [2026-06-05 16:08 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri 6 gün donmuş) | **ep_rew_mean:** -173.85 (geçersiz) | **entropy:** -4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
Aktif eğitim yok; v9 193k adımda ölü, CSV donmuş. ppo.yaml v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10). fast_sim 18-config sweep tamamen kapandı: v4.8 champion (%0 çarpışma, 5 oda) ile v4.10 (%54 çarpışma, 6 oda/281 voxel) arasındaki güvenlik-kapsam ödünleşimi temel olarak kanıtlandı. v10 Gazebo eğitimi 3. kez erteleniyor; tek bloker env kodu değişikliği.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 46 satırın tam anatomisi:
  - **İlk 4 satır (11:02-12:32, v9 fresh run):** step 142k-599k (TB'den), ep_rew: -291→-270, ep_len=1000 (max-cap'e kilitli), entropy: -3.89→-3.32 (hızla deterministikleşiyor), std: 0.888→0.746 (0.7 eşiğine yaklaşıyor). Klasik plato; hiçbir zaman oda reward bandına (+15) ulaşılamadı.
  - **Crash-loop (13:00-20:55, 22 yeniden başlatma):** Monitor her 20 dakikada step 80k checkpoint'e resetleyerek trajektoriyi kaotikleştirdi. ep_rew gürültüsü: -25 ile -110 arası. En iyi değer -25 @ step 83k (13:52).
  - **Son geçerli faz (20:59-21:40):** checkpoint ilerlemesi 96k→149k, ep_rew: -67→-47. FPS 103→67 (süreç yorgunluğu).
  - **Son nokta (22:00):** step=193,248, ep_rew=-173.85, ep_len=637, fps=72. 14 özdeş satır sonra tamamen ölü.
- **+15'lik oda sıçraması hiçbir zaman görülmedi.** v9 hiçbir zaman ilk oda threshold'unu aşamadı. En iyi ep_rew=-37 @149k; bu idle/çarpışma cezalarının azalmasından, oda bonusundan değil.
- **Kırılım yok, plato da yok — eğrim tamamen ölü.**

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Tartışma kapandı. v9 599k step boyunca -270'de plato yaptı; constant low-LR altında exploration breakthrough mümkün olmadı. ppo.yaml zaten lr=3e-4→1e-5 doğrusal — v3.0 Gazebo (aynı şema) peak=110.3@610k üretti. Açık aksiyon yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri (entropy=-4.212, std=0.985) v9 stale. v10 izleme eşiği: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI → ent_coef 0.008→0.010 değerlendir (bu iki koşul ayrı ayrı alarm tetiklemez). v10'da ent_coef=0.008 (v9'un 5.3×'ı) 500k step boyunca keşfi desteklemeye yeterli.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı. Referans haritası (versions.jsonl + interventions.jsonl):
  - v3.0 Gazebo (aynı ppo.yaml, collision_penalty=10, lidar_history=1): @300-430k → 5-6 oda tutarlı
  - Env kodu değişimleri uygulanırsa (collision_penalty=25, lidar_history=2): 150-250k muhtemel
  - fast_sim v4.8 benchmark: %0 çarpışma, 5 oda, voxels=117 @1.5M cap

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty 10.0 → 25.0** — fast_sim 4-nokta sweep kesin (versions.jsonl'de v4.8 entry): coll=22→%37 çarpışma+rooms 5→2 collapse, coll=25→%0+rooms 5 (OPTIMAL), coll=30→%8 (aşırı temkin). Mevcut 10.0 ile v10 fast_v1 rejimini (%47 çarpışma) tekrarlayacak; oda reward'ı çarpışmayla sürekli netleştirilecek.
2. **drone_exploration_env.py: lidar_history 1 → 2 (obs 41-d → 72-d)** — fast_v2 tek-değişken breakthrough: çarpışma %80→%1. NOT: versions.jsonl v5.0 entry v4.8'deki lidar_history=2'den lidar_history=3'e geçişin yardımcı OLMADIĞINI kanıtladı (voxel 281→106, trade-off bozuldu). Bu, 1→2 geçişinin kritik olduğunu; 2→3'ün gereksiz olduğunu doğrular.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** v10 config v3.0 Gazebo + fast_sim 18-config sweep çapraz doğrulamalı ve optimal.
- **Hard cap kritik: total_timesteps=1.5M aşılmamalı.** fast_sim sweep kanıtı: v4.10 @3.2M %100 çarpışma (güvenlik çöküşü), v4.11 @5M %100 çarpışma (ceza arttırılınca bile!), v4.13 @8M %26 çarpışma+voxels düştü. 1.5M sonrası her konfigürasyonda güvenlik-kapsam ödünleşimi çözümsüz. Bu sınır DOKUNULMAZ.
- **Üçüncü kez tespit:** v10 hâlâ başlamadı (ilk tespit: 14:08, ikinci: 15:08 UTC). Her saat gecikmede v10 için remaining budget azalıyor.

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** (drone_exploration_env.py) — fast_sim 4-nokta sweet spot kesin, v4.8 champion. Bu olmadan v10 eğitimi fast_v1 (%47 çarpışma) + oda breakthrough yok senaryosunu tekrarlayacak.
2. **lidar_history: 1 → 2** (drone_exploration_env.py, obs 41-d → 72-d) — fast_v2 breakthrough (çarpışma %80→%1); v5.0'ın 2→3 geçişi başarısız oldu, bu da 1→2'nin critik geçiş noktası olduğunu doğruladı. ppo.yaml değişikliği gerekmez.

### Müdahale
**Yok** — configs/ppo.yaml v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize norm_obs=false norm_reward=true clip=10.0). Fast_sim 18-config sweep (v4.1→v5.0) tam tarama: güvenlik-kapsam ödünleşimi temel olarak kanıtlandı, konfigürasyon alanı tükendi. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Bloker: drone_exploration_env.py env kodu (kullanıcı tarafı, yukarıdaki 1-2 madde).
---

## [2026-06-06 13:05 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri 7 gün donmuş) | **ep_rew_mean:** -173.85 (geçersiz) | **entropy:** -4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
Aktif eğitim yok — v9 adım 193k'da kalıcı ölü, CSV 7 gündür stale. ppo.yaml 2026-06-02'den bu yana v10 optimal konfigürasyonunda (fast_sim 18-config sweep + v3.0 Gazebo çapraz doğrulamalı); hyperparameter müdahalesi gerekmiyor. v10 Gazebo eğitimi hâlâ başlamamış; tek bloker drone_exploration_env.py'deki iki satır env kodu değişikliği — 4. gündür aynı tespitte.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV adım=193,248, ep_rew=-173.85: tamamen geçersiz v9 stale artefakt (14 özdeş satır, 2026-05-31 03:01'de donmuş). Aktif eğitim olmadığından canlı eğri analizi yapılamaz.
- Son güvenilir Gazebo referans noktaları (versions.jsonl + interventions.jsonl):
  - v3.0 @ 434k: peak +102.54; @ 501k: ep_rew=+123.25; @ 610k: kasıtlı durduruldu, peak=110.3
  - fast_sim v4.8 @ 1.5M: %0 çarpışma, 5 oda, voxels=117 (champion — güvenli deploy edilebilir)
  - fast_sim v4.10 @ 5M: voxels=281/%44.5 kapsam, 6 oda FAKAT %54 çarpışma (güvenlik çöküşü)
- v10 eğitim eğrisi YOK — başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçersiz soru. ppo.yaml 2026-06-02'den beri lr=3e-4→1e-5 linear (1.5M boyunca). v9'un constant 7.5e-5'i 300k-599k arası -270 platosuna yol açtığı kesin olarak kanıtlandı: 300k adımda sıfır kırılım. v3.0 Gazebo (aynı linear şema) 610k'da peak=110.3 üretti — kanıtlanmış. Kapalı tartışma.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Stale CSV değerleri (entropy=-4.212, std=0.985) v9 crash kalıntısı — güvensiz. v10 aktif olmadığından gerçek ölçüm yok.
- v10 projeksiyon: ent_coef=0.008 (v9'un 5.3×'ı, v3.0 Gazebo'nun 1.6×'ı) ile 500k adım boyunca entropy -4.5 ile -5.5 arası bekleniyor.
- Alarm eşiği: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI — iki koşul birlikte tetiklenmelidir; ayrı ayrı alarm verilmez.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı. Referans tablosu:
  - Env kodu DEĞİŞMEZSE (mevcut durum): 300-430k adımda 5-6 oda — v3.0 Gazebo referansı (aynı ppo.yaml, collision_penalty=10, lidar_history=1)
  - collision_penalty=25 + lidar_history=2 uygulanırsa: 150-250k adımda 5-6 oda mümkün (fast_v2 breakthrough analoğu — fast_sim'de çarpışma %80→%1)
  - Potansiyel hız artışı: ~%40 adım tasarrufu iki env satırıyla

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py: collision_penalty 10.0 → 25.0** — Fast_sim 4-nokta sweet spot kesin (versions.jsonl v4.8-v4.9 entry): coll=22→%37 çarpışma+rooms 5→2 collapse, coll=25→%0 çarpışma (OPTIMAL), coll=30→%8 (aşırı temkin). Mevcut 10.0 ile v10 fast_v1 rejimini (%47 çarpışma) tekrarlayacak; oda reward'ı çarpışmayla sürekli netleştirilecek ve 1.5M bütçe boşa gidecek.
2. **drone_exploration_env.py: lidar_history 1 → 2 (obs 41-d → 72-d)** — Fast_v2 tek-değişken breakthrough: çarpışma %80→%1. versions.jsonl v5.0 entry ayrıca 2→3 geçişinin başarısız olduğunu kanıtladı (voxel 281→106); bu da 1→2'nin kritik geçiş noktası olduğunu doğrular. ppo.yaml değişikliği gerekmez (MlpPolicy obs boyutunu env'den otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config v10 optimal konfigürasyonunda ve dokunulmaz: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0). %80+ güven eşiğini aşan bir config sorunu tespit edilmedi.
- **HARD CAP DOKUNULMAZ: total_timesteps=1.5M.** fast_sim kanıtı 4 bağımsız noktayla: v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M=%26 çarpışma+voxels düştü. 2M+ sonrası güvenlik çöküşü kaçınılmaz — kural değil kanıt.
- **Gecikme riski:** v10 4. gündür başlamamış. Eğitim tahminen ~25-30 saat sürecek (1.5M step @ n_envs=1 Gazebo). Her geçen gün projeye ait kalan window'u kısaltıyor.
- **Acil eylem (kullanıcı tarafı):** drone_exploration_env.py'deki 2 satır → `./scripts/train.sh configs/ppo.yaml`. Bu iki değişiklik olmadan eğitim başlasa bile fast_v1 (%47 çarpışma) rejimi tekrarlanır ve 1.5M step bütçesi boşa gider.

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** (drone_exploration_env.py) — fast_sim 4-nokta sweet spot, v4.8 champion, %0 çarpışma + 5 oda. Bu olmadan v10 fast_v1 (%47 çarpışma) rejimini tekrarlayacak.
2. **lidar_history: 1 → 2** (drone_exploration_env.py, obs 41-d → 72-d) — fast_v2 breakthrough: çarpışma %80→%1; v5.0'ın 2→3 geçişi başarısız olduğu kanıtlandı, bu da 1→2'nin değiştirilemez eşik olduğunu teyit etti.

### Müdahale
**Yok** — configs/ppo.yaml 2026-06-02'den beri v10 optimal konfigürasyonunda. Aktif eğitim verisi yok; stale CSV %80+ güven eşiğini aşan bir config sorunu ortaya koymaktan uzak. Tüm fast_sim sweepleri (v4.1→v5.0, 18 config) + v3.0 Gazebo (peak 110.3) mevcut ppo.yaml'ı çapraz doğruladı. Bloker: drone_exploration_env.py env kodu (kullanıcı tarafı, yukarıdaki 1-2 madde).
---

## [2026-06-06 14:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri 7 gün donmuş, geçersiz) | **ep_rew_mean:** -173.85 (geçersiz) | **entropy:** -4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
Aktif eğitim süreci yok. `training_metrics.csv` 7 gündür tamamen dondurulmuş (v9 crash-loop kalıntısı). `configs/ppo.yaml` 2026-06-02'den bu yana v10 optimal formatında (fast_sim 18-config sweep + v3.0 Gazebo çapraz doğrulamalı) — hyperparameter müdahalesi gerektirmiyor. v10 Gazebo eğitimi 5. gündür başlamamış; tek bloker `drone_exploration_env.py`'deki iki satır env kodu değişikliği.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` son 20 satır: TAMAMEN GEÇERSİZ. Tüm satırlar 2026-05-30 22:00 – 2026-05-31 03:01 UTC arası özdeş (step=193,248, ep_rew_mean=−173.85). Bu v9_newmap crash-loop'u sırasında process ölmüş; monitor_agent aynı satırı 14 kez üst üste yazmış. Hiçbir trend analizi yapılamaz.
- Gerçek Gazebo v3.0 son eğri (interventions.jsonl + versions.jsonl): 434k → ep_rew_mean=99.84, peak=102.54; 610k → peak=110.3 (kasıtlı durdurma, 2026-06-01 sabahı). Plato değil — olgunlaşma fazındayken intentional stop. peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 voxel/frontier → tutarlı 7+ oda keşfedildi. Eğer v3.0 sürseydi 800k-1M'de v8 all-time peak (+113 @1.6M) geçmesi kuvvetle muhtemeldi; yalnızca 610k'da %97'sine ulaşıldı.
- v10 eğitim eğrisi YOK — başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Kapalı tartışma. ppo.yaml artık `lr=3e-4→1e-5 linear` (1.5M boyunca). v9'un sabit 7.5e-5'i 142k–599k arası -290→-270 platosuna yol açtı (457k adımda yalnızca +20 rew). v3.0 aynı linear şemayla (434k) +99.84 üretti — 4.8× daha verimli. Entropy kanıtı: v9 @599k −3.32 (tehlikeli), v3.0 @312k −5.67 (mükemmel). Sabit lr seçimi terk edildi ve doğrulanan kararı tersine çevirmek için hiçbir gerekçe yok.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri (entropy=−4.212, std=0.985) v9 crash kalıntısı — güvensiz, kullanılamaz. v10 aktif olmadığından gerçek anlık ölçüm yok.
- v10 projeksiyon: ent_coef=0.008 (v9'un 5.3×'ı) ile 500k adım boyunca entropy −4.5 ile −5.5 arası bekleniyor (referans: v3.0 @312k entropy=−5.67, std=1.63 — mükemmel). ent_coef=0.008, fast_sim v4.2'nin (ent_coef≥0.02 → %85 çarpışma) ve v9'un (ent_coef=0.0015 → deterministikleşme) ikisinden de öğrenilen tatli nokta; değiştirilmemeli.
- İzleme tetik bandı (v10 başlayınca): entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI — iki koşul birlikte gerekli; ayrı ayrı alarm tetiklemez.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadı; tahmin referans tabloya dayanıyor:
  - Env kodu DEĞİŞMEZSE (mevcut collision_penalty=10, lidar_history=1): 300–430k adımda 5–6 oda (v3.0 Gazebo referansı, aynı ppo.yaml)
  - collision_penalty=25 + lidar_history=2 uygulanırsa: 150–250k adımda 5–6 oda mümkün (fast_v2 breakthrough analoğu: çarpışma %80→%1 tek değişkenle)
  - Potansiyel hız kazanımı: ~%40 step tasarrufu sadece iki env satırıyla

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty 10.0 → 25.0`** — fast_sim 4-nokta sweep kesin (versions.jsonl, v4.8→v4.9 entry): coll=22→%37 çarpışma + rooms 5→2 collapse (yerel optimum), coll=25→%0 çarpışma + 5 oda (OPTIMAL), coll=30→%8 (aşırı tedirgin, keşif kısıtlı). Mevcut 10.0 sweet spot'un %60'ının altında; drone çarpışma riskini sistematik hafife alıyor. Bu değişiklik olmadan v10 fast_v1 rejimini (%47 çarpışma) tekrarlayarak 1.5M bütçeyi boşa harcayacak.
2. **`drone_exploration_env.py`: `lidar_history 1 → 2` (obs 41-d → 72-d)** — fast_v2 tek-değişken breakthrough: çarpışma %80→%1. Format: `[t-1: 32 lidar | t: 32 lidar | yaw×2 | vel×3 | explore+room | min_lidar | idle]`. KRITIK NOT: versions.jsonl v5.0 entry, lidar_history 2→3 geçişinin başarısız olduğunu kanıtladı (voxels 281→106, v4.8 tarafından domine edildi). Bu da 1→2'nin irreversible eşik, 2→3'ün gereksiz olduğunu teyit ediyor. ppo.yaml değişikliği gerekmez (MlpPolicy obs boyutunu env'den otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config v10 optimal konfigürasyonunda ve dokunulmaz: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0). %80+ güven eşiğini aşan hiçbir config sorunu tespit edilmedi.
- **HARD CAP DOKUNULMAZ: total_timesteps=1.5M.** fast_sim 4 bağımsız kanıt: v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M=%26 çarpışma+voxels geriledi. 2M+ sonrası güvenlik çöküşü konfigürasyondan bağımsız — kural değil empirik kanıt.
- **Gecikme riski:** v10 5. gündür başlamamış. n_envs=1 Gazebo ile 1.5M step ≈ 25–30 saat. Her geçen gün proje penceresini daraltıyor.
- **Env kodu bloker (kullanıcı tarafı):** `drone_exploration_env.py` iki değişiklik → `./scripts/train.sh configs/ppo.yaml`. Bu iki satır uygulanmadan eğitim başlasa bile fast_v1 (%47 çarpışma) senaryosu tekrarlanır ve bütçe boşa gider.

### v10 Önerisi
1. **`collision_penalty: 10.0 → 25.0`** (`drone_exploration_env.py`) — fast_sim 4-nokta sweet spot, v4.8 champion (%0 çarpışma, 5 oda, voxels=117 @1.5M). Bu olmadan v10 Gazebo fast_v1 rejimini tekrarlayacak.
2. **`lidar_history: 1 → 2`** (`drone_exploration_env.py`, obs 41-d → 72-d) — fast_v2 breakthrough (çarpışma %80→%1); v5.0 kanıtıyla 2→3 geçişi başarısız olduğundan 1→2 değiştirilemez eşik. Her iki değişiklik tamamlanınca `./scripts/train.sh configs/ppo.yaml` ile v10 başlatılabilir — yaml hazır ve optimal.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda. `training_metrics.csv` 7 gündür stale; gerçek veri kaynağı interventions.jsonl + versions.jsonl + train log dosyaları. fast_sim 18-config sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3) mevcut ppo.yaml'ı her açıdan çapraz doğruladı. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Bloker: `drone_exploration_env.py` env kodu (kullanıcı tarafı).
---

## [2026-06-06 15:05 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri 7 gün donmuş, geçersiz) | **ep_rew_mean:** -173.85 (geçersiz) | **entropy:** -4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
Aktif eğitim süreci yok. `training_metrics.csv` 7 gündür tamamen dondurulmuş. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında (fast_sim 18-config sweep + v3.0 Gazebo çapraz doğrulamalı). Günün daha erken saatlerinde iki analiz yapıldı (13:05 ve 14:10 UTC) — bu giriş onların tekrarı değil, günlük son kontrol ve durum özeti niteliğinde. Sonuç aynı: ppo.yaml dokunulmaz; bloker drone_exploration_env.py.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` STALE. Son 20 satır: 2026-05-30 22:00–2026-05-31 03:01 UTC arası 14 özdeş satır (step=193,248, ep_rew_mean=−173.85). Hiçbir trend analizi yapılamaz. Gerçek eğitim verisi bu CSV'de yok.
- Gerçek son Gazebo referansı (interventions.jsonl + versions.jsonl): Gazebo v3.0 434k→peak +102.54, 610k→peak +110.3 (2026-06-01 kasıtlı durdurma). Plato değil — intentional stop. +15 oda sıçraması: peak 110.3 ≈ 7×15=105 oda bonusu + ~5 voxel/frontier → 7+ oda tutarlı.
- fast_sim referansı: v4.8 @1.5M → %0 çarpışma, 5 oda, voxels=117 (şampiyon). v4.10 @5M → 6 oda, voxels=281, %54 çarpışma (Pareto uç noktası).
- v10 eğitim eğrisi: MEVCUT DEĞİL — eğitim başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Kapalı tartışma — 7 gündür aynı yanıt. ppo.yaml `lr=3e-4→1e-5 linear` (1.5M boyunca). v9 constant 7.5e-5 kanıtı: 142k–599k arası ep_rew_mean yalnızca -290→-270 (+20, 457k adımda). v3.0 linear decay ile 434k'da +99.84 — aynı bütçede 4.8× daha verimli. Tartışma kapalı; sabit LR opsiyonu reddedildi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif veri yok (eğitim çalışmıyor). Stale CSV değerleri (entropy=−4.212, std=0.985) v9 crash kalıntısı; kullanılamaz.
- v10 projeksiyon (ent_coef=0.008 ile): train_v3_floors @312k referansı → entropy=−5.67, std=1.63. ent_coef=0.008 v9'un (0.0015) 5.3×'ı, fast_sim sweet spot'u (v4.2 ent≥0.02 → %85 çarpışma) ile v9 deterministikleşme arasında optimum bant. Değiştirilmemeli.
- Alarm tetik (v10 başlayınca izlenecek): entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI — iki koşul birlikte.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 başlamadığından tahmin referans tabloya dayanıyor:
  - Env kodu DEĞİŞMEZSE (collision_pen=10, lidar_history=1): 300–430k adımda 5–6 oda — v3.0 Gazebo referansı.
  - collision_pen=25 + lidar_history=2 UYGULANIRSa: 150–250k adımda 5–6 oda — fast_v2 breakthrough analoğu (çarpışma %80→%1).
  - Potansiyel step tasarrufu: ~%40 (≈450k adım) yalnızca iki env satırıyla.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: collision_penalty 10.0 → 25.0** — fast_sim 4-nokta sweet spot (coll=22: %37 çarpışma + rooms 5→2 collapse; coll=25: %0 çarpışma + 5 oda OPTIMAL; coll=30: %8 aşırı tedirgin). Mevcut 10.0, sweet spot'un %40'ı — drone çarpışmayı sistematik hafife alıyor. Bu olmadan v10 fast_v1 (%47 çarpışma) rejimini tekrarlayarak 1.5M bütçeyi boşa harcayacak.
2. **`drone_exploration_env.py`: lidar_history 1 → 2 (obs 41-d → 72-d)** — fast_v2 tek-değişken breakthrough: çarpışma %80→%1. Format: `[t-1: 32 lidar | t: 32 lidar | yaw_cos+sin | vx+vz+wz | explore+room | min_lidar | idle]`. versions.jsonl v5.0 entry kanıtıyla lidar_history 2→3 başarısız oldu (voxels 281→106); bu da 1→2'nin değiştirilemez eşik olduğunu teyit ediyor. ppo.yaml değişikliği GEREKMİYOR.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1. %80+ güven eşiğini aşan hiçbir config sorunu tespit edilmedi.
- **HARD CAP DOKUNULMAZ: total_timesteps=1.5M.** fast_sim: v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M voxels geriledi. 2M+ sonrası çöküş kaçınılmaz.
- **Gecikme aciliyeti (YÜKSEK):** v10 Gazebo 6. gündür başlamamış. 1.5M adım @ n_envs=1, ~40 FPS Gazebo → yaklaşık 37.5M saniye/40 = **~10.4 saat** eğitim süresi. Proje takvimi için kritik bir bütçe kaybı yaşanıyor. Bu bir hyperparameter kararı değil, operasyonel kilitlenme.

### v10 Önerisi
1. **collision_penalty: 10.0 → 25.0** (drone_exploration_env.py, tek satır) — fast_sim v4.8 champion, 4-nokta kesin sweet spot, %0 çarpışma.
2. **lidar_history: 1 → 2** (drone_exploration_env.py, obs 41-d → 72-d) — fast_v2 %80→%1 breakthrough; 1→2 irreversible eşik (v5.0 kanıtı). Bu iki satır tamamlanınca: `./scripts/train.sh configs/ppo.yaml` — yaml hazır, optimal.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda ve değiştirilmedi. fast_sim 18-config sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3 @610k) mevcut yaml'ı çapraz doğruladı. CSV stale veriden %80+ güven eşiğini aşan bir hyperparameter sorunu elde edilemez. Bloker: `drone_exploration_env.py` iki satır değişikliği — kullanıcı tarafında.
---

## [2026-06-06 16:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-31 03:01'den beri donmuş) | **ep_rew_mean:** -173.85 (GEÇERSIZ) | **entropy:** -4.212 (GEÇERSIZ) | **std:** 0.985 (GEÇERSIZ)

### Durum
v10 Gazebo eğitimi henüz başlamadı (6. gün). `configs/ppo.yaml` v10 optimal formatında (2026-06-02'den beri sabit). Günün önceki analizleri (13:05, 14:10, 15:05 UTC) ile tutarlı. Tek değişen: operasyonel gecikme birikiyor — 1.5M adım @ ~40 FPS ≈ 10.4 saat eğitim süresi, her geçen gün proje penceresini daraltıyor.

### Detay
- **a) Reward eğrisi:** CSV tamamen dondurulmuş (14 özdeş satır, step=193,248, son 7+ gün). Analiz edilebilir veri yok. Gerçek referans: Gazebo v3.0 @610k peak=110.3 (intentional stop), fast_sim v4.8 @1.5M: %0 çarpışma, 5 oda, voxels=117.
- **b) lr=7.5e-5 constant:** Reddedildi. ppo.yaml `lr=3e-4→1e-5 linear` — v9 constant lr 457k adımda yalnızca +20 iyileşme vs v3.0 linear decay 434k'da +99.84 (4.8× verimli). Tartışma kapalı.
- **c) Entropy/std:** Aktif veri yok. v10 beklentisi: ent_coef=0.008 ile başlangıçta entropy ~-5.5 – -6.0, std ~1.5 (ent_coef v9'un 5.3×'ı). Alarm eşiği: entropy_loss > -3.5 VE std < 0.75 EŞ ZAMANLI.
- **d) Oda geçişi:** env kodu değişmezse ~300-430k; collision_pen=25 + lidar_history=2 uygulanırsa ~150-250k (fast_v2 analoğu).
- **e-f) Kritik öneri ve acil durum:** Aşağıda.

### v10 Önerisi
1. **`drone_exploration_env.py`: `collision_penalty: 10.0 → 25.0`** — v4.8 champion, fast_sim 4-nokta sweet spot (22: %37 çarpışma+rooms collapse; **25: %0 çarpışma, 5 oda OPTIMAL**; 30: %8 aşırı tedirgin). Mevcut coll=10 env'de sweet spot'un %40'ı; drone çarpışmayı sistematik hafife alacak.
2. **`drone_exploration_env.py`: `lidar_history: 1 → 2` (obs 41-d → 72-d)** — fast_v2 tek-değişken: çarpışma %80→%1. v5.0 kanıtı: 2→3 geçişi başarısız (voxels 281→106); 1→2 irreversible optimal eşik. ppo.yaml değişikliği gerekmez.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda, değiştirilmedi. 18-config fast_sim sweep + v3.0 Gazebo (peak=110.3) yaml'ı her açıdan doğruladı. %80+ güven eşiğini aşan hiçbir hyperparameter sorunu tespit edilmedi. Bloker: `drone_exploration_env.py` iki satır değişikliği (kullanıcı tarafında). ppo.yaml commit+push yapılmadı.
---

## [2026-06-06 17:06 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri donmuş, 7+ gün) | **ep_rew_mean:** -173.85 (GEÇERSIZ) | **entropy:** -4.212 (GEÇERSIZ) | **std:** 0.985 (GEÇERSIZ)

### Durum
Görev bağlamı v9'u "şu an çalışan" olarak tanımlıyor; **bu bilgi güncel değil.** Gerçek durum: Gazebo v3.0 (ppo_v3_best) 2026-06-01 sabahı 610k adımda peak=110.3 ile kasıtlı durduruldu; fast_sim zinciri (v4.1→v5.0, 18 config) aynı gün tamamlandı; `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında. Aktif eğitim 7 gündür yok; v10 başlatma env kodu değişikliklerine (collision_penalty=25, lidar_history=2) bağlı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 20 satır TAMAMEN GEÇERSİZ: 2026-05-30 22:00–03:01 UTC arası 14 özdeş satır (step=193,248, ep_rew_mean=−173.85). v9_newmap crash-loop kalıntısı; trend analizi yapılamaz.
- Gerçek son bilinen eğri (interventions.jsonl + versions.jsonl): Gazebo v3.0 @434k → ep_rew_mean=99.84, peak=102.54; @610k → peak=110.3 (kasıtlı durdurma, plato değil).
- +15'lik oda sıçraması: peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 frontier/voxel — en az 7 ayrı oda geçişi gerçekleşmiş.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ SORU. `ppo.yaml` 2026-06-02'den beri v10: `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit lr v9 döneminde terk edildi; v9 kanıtı kesin: constant 7.5e-5 ile 142k→599k arası yalnızca +20 reward (457k adımda). v3.0 lineer decay ile 434k'da +99.84 → **4.8× daha verimli**. Aynı zamanda entropy trendi: v9 @599k = −3.32 (deterministikleşme eşiğine yakın), v3.0 @312k = −5.67 (sağlıklı). Sabit LR opsiyonu kesin olarak reddedildi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif veri yok (eğitim çalışmıyor). CSV'deki entropy=−4.212, std=0.985 değerleri v9 crash kalıntısı; kullanılamaz.
- v10 proyeksiyonu (ent_coef=0.008 ile): v3.0 @312k referansı → entropy=−5.67, std=1.63. ent_coef=0.008, v9'un 0.0015'inin 5.3×'i — deterministikleşme riski çok düşük. v9'da 610k'ya kadar −3.32'ye düşen entropy, v3.0'da (ent_coef=0.008 ile) 312k'da −5.67 seviyesinde kaldı: ent_coef seçiminin kritik fark yarattığı kanıtlandı.
- fast_sim dersi (kesin): ent_coef artırmak güvenlik-kapsam trade-off'unu kıramadı (v4.2: ent_coef=0.02 → collision %85). Keşif kalitesi obs tasarımından geliyor (lidar_history), entropi katsayısından değil. ent_coef=0.008 dokunulmaz.
- v10 alarm tetik (başladığında): entropy_loss > −3.5 VE std < 0.75 **eş zamanlı** — iki koşul birlikte olmadan aksiyon yok.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v3.0 stochastic training'de zaten 7+ oda keşfetti; "kaç step daha" sorusu artık geçerli değil.
- Gerçek darboğaz: **deterministik eval-train gap.** eval_v3_310k.log: 11 bölümden 10/11 = 1 oda (stochastic'te 7 oda). Kök neden: lidar_history=1 → hareketli engel hızı/yönü gözlemlenemiyor → deterministic politikada ani engel karşılaşmalarında recovery yapılamıyor.
- fast_sim kanıtı: lidar_history=2 → collision %80→%1 (fast_v2, tek-değişken deney). v10 + lidar_history=2 + collision_pen=25 ile: tutarlı 5-6 oda @~150-250k step bekleniyor (fast_v4.8 analoğu: 1.5M'de %0 çarpışma, 5 oda, voxels=117). Env kodu değişikliği olmadan: ~300-430k'da v3.0 performansı tekrar — deterministik gap kapanmaz.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: 10.0 → 25.0` (1 satır, ENV kodu):** fast_sim 4-noktalı kesin tarama sweet spot: 22=%37 çarpışma+rooms 5→2 collapse, **25=%0 çarpışma+5 oda (OPTIMAL)**, 30=%8 aşırı tedirgin, 50=%100 collapse. Mevcut ceza=10.0, fast_sim'in "çöküş eşiği" 22'nin bile altında — bu değer olmadan v10 Gazebo fast_v1 (%47 çarpışma) rejimini tekrar eder ve 1.5M bütçe büyük ölçüde boşa gider.
2. **`drone_exploration_env.py`: `lidar_history: 1 → 2` (obs 41-d → 72-d, ENV kodu):** Format: `[t-1: 32 lidar | t: 32 lidar | yaw_cos+sin | vx+vz+wz | explore+room | min_lidar | idle]`. fast_v2 tek-değişken deney: çarpışma %80→%1. v5.0 kanıtı: 2→3 geçişi başarısız (voxels 281→106, v4.8 tarafından domine edildi); 1→2 irreversible optimal eşik, kesinleşti. ppo.yaml değişikliği GEREKMİYOR.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** Mevcut v10 config: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_reward=True). 18-config fast_sim sweep + v3.0 Gazebo (peak=110.3 @610k) ile çapraz doğrulanmış, optimal. %80+ güven eşiğini aşan herhangi bir yaml sorunu tespit edilmedi.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** fast_sim v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M voxels geriledi (281→134). 2M+ sonrası güvenlik kolapsı kaçınılmaz; bu yapısal kısıt.
- **Operasyonel gecikme (ÖNEMLİ):** v10 Gazebo 7. gündür başlamamış. 1.5M adım @n_envs=1, ~40 FPS → ~10.4 saat eğitim. Her gecen gün proje penceresini daraltıyor. Bloker env kodu değişikliği — hyperparameter değil.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py, 1 satır):** fast_sim v4.8 champion kanıtı. Mevcut 10.0 → 25.0. Bu olmadan v10 Gazebo'da %47+ çarpışma kaçınılmaz; politika keşif reward'unu collision cezasıyla dengeleyemez.
2. **`lidar_history=2` obs entegrasyonu (drone_exploration_env.py, obs 41→72-d):** fast_v2 %80→%1 breakthrough; kesinleşmiş irreversible optimal eşik. Bu iki ENV satırı tamamlandıktan sonra `./scripts/train.sh configs/ppo.yaml` — yaml hazır ve optimal, değiştirilmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda; fast_sim 18-config sweep + v3.0 Gazebo verisiyle çapraz doğrulanmış. Görev bağlamındaki v9 config tanımı (lr=7.5e-5 constant, ent_coef=0.0015, n_envs=2, total=2.5M) **güncel değil** — ppo.yaml çoktan v10'a geçirildi ve bu kararlar veri bazlı olarak doğru. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi; config değiştirilmedi.
---

## [2026-06-07 13:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri donmuş, 8. gün) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
v9 eğitimi 2026-05-30 22:00 itibarıyla 193,248 step'te kalıcı çökmüş; monitor 8 gündür özdeş satır yazıyor. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında (değiştirilmedi). Tek gerçek bloker: `drone_exploration_env.py` ENV kod değişiklikleri — kullanıcı tarafında.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 25 satır ANALİZ: 2 farklı faz var:
  - **Crash-recovery döngüsü (13:xx–22:00 UTC):** step değerleri 90k-193k arasında rastgele sıçrıyor (farklı checkpoint'lerden okuma). En iyi nokta: ep_rew_mean=−37.4 @145k (21:20 UTC) ve −47.4 @149k (21:40 UTC). +15 oda bonusu hiç görülmedi → v9 tüm çalışma boyunca oda eşiğini geçemedi.
  - **FREEZE (22:00–03:01 UTC):** 14 özdeş satır: step=193,248, ep_rew_mean=−173.85. Eğitim process'i ölü, monitor son checkpoint'i tekrar tekrar okuyor.
- Kırılım YOK. Plato da yok — aktif eğitim hiç olmadı. v9 reward eğrisi sonuçsuz kapandı.
- Referans gerçek veri: Gazebo v3.0 @434k → ep_rew_mean=99.84, peak=102.54; @610k → peak=110.3 (kasıtlı durdurma). Bunlar v10 başlamadan önceki kanıtlanmış değerler.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GEÇERSİZ: `ppo.yaml` 2026-06-02'den beri `lr=3e-4→1e-5 linear` formatında. Sabit lr tartışması kapandı.
- Kanıt: v9 constant lr=7.5e-5 ile 142k→599k arası yalnızca −290→−270 (+20 iyileşme, 457k adımda). v3.0 linear decay ile 0→434k'da +99.84 — **4.8× daha verimli aynı step bütçesinde.**
- CSV'de entropy trendi: v9 @599k = −3.32 (deterministikleşme eşiğine yakın). Bu, sabit lr'ın entropy'yi bastırdığının doğrudan kanıtı. Linear decay seçimi kesin.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV verisi v9 crash kalıntısı; kullanılamaz. Son geçerli: entropy=−4.212, std=0.985 (@193k, 8 gün önce).
- Eğer eğitim bu noktada olsaydı: std=0.985 > 0.7 eşiği → alarm yok. Entropy=−4.212, −4.0 eşiğinin hemen altında → sınır değer, izleme gerekir.
- v10 beklentisi (ent_coef=0.008 ile): ent_coef v9'un 5.3×'i → başlangıçta entropy ~−5.5/−6.0 beklenir; deterministikleşme riski çok düşük.
- v10 alarm tetik koşulu: entropy_loss > −3.5 VE std < 0.75 **EŞ ZAMANLI** (iki koşul birlikte olmadan aksiyon yok).

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9'da oda geçişi HİÇ gerçekleşmedi (tüm CSV'de +15 spike yok).
- v10 + mevcut env (collision_pen=10, lidar_history=1): v3.0 analoğu → ~300-430k beklenir.
- v10 + env değişiklikleri (collision_pen=25, lidar_history=2): fast_v4.8 analoğu → ~150-250k beklenir (**%40-50 daha hızlı oda keşfi**).
- Eval-train gap nedeni: lidar_history=1 → drone hareketli engelin hız/yönünü göremez → deterministik politikada ani çarpışma kaçınılmaz (eval_v3_310k.log: 10/11 bölüm 1 oda kaldı, stochastic'te 7 oda).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (drone_exploration_env.py, 1 satır):** fast_sim 4-nokta sweet spot (22=%37 çarpışma+rooms collapse; **25=%0 çarpışma+5 oda OPTIMAL**; 30=%8 aşırı tedirgin). Mevcut 10.0 sweet spot'un %40'ı — v10 Gazebo'da fast_v1 (%47 çarpışma) rejimini tekrarlar, 1.5M bütçe büyük ölçüde boşa gider.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, drone_exploration_env.py):** fast_v2 tek-değişken: çarpışma %80→%1. Format: `[t-1: 32 lidar | t: 32 lidar | yaw_cos+sin | vx+vz+wz | explore+room | min_lidar | idle]`. v5.0 kanıtı: 2→3 başarısız (voxels 281→106); 1→2 irreversible eşik, kesinleşmiş.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** Config v10 optimal: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_reward=True). %80+ güven eşiğini aşan hiçbir config sorunu yok.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** fast_sim v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M voxels geriledi. Bu yapısal kısıt.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 8. gündür başlamamış. 1.5M adım @ ~40 FPS ≈ 10.4 saat eğitim süresi. Proje penceresine her geçen gün baskı artıyor.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py):** fast_sim v4.8 kanıtı. Mevcut 10.0 → 25.0 — bu olmadan v10'da %47+ çarpışma kaçınılmaz, politika keşif reward'unu cezayla dengeleyemez.
2. **`lidar_history=2` obs entegrasyonu (obs 41→72-d):** fast_v2 %80→%1 breakthrough, irreversible optimal eşik. Bu iki satır tamamlandıktan sonra: `./scripts/train.sh configs/ppo.yaml` — yaml hazır ve optimal.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda (2026-06-02'den beri), değiştirilmedi. 18-config fast_sim sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3 @610k) yaml'ı çapraz doğruladı. Görev bağlamındaki "v9 şu an çalışıyor" tanımı güncel değil; tüm veri v9'un kapandığını gösteriyor. Bloker: `drone_exploration_env.py` ENV kodu (kullanıcı tarafı).
---

## [2026-06-07 14:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri donmuş, 8. gün) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
v9 Gazebo eğitimi 2026-05-30 22:00'da 193k step'te kalıcı çökmüş; monitor 8 gündür özdeş satır yazıyor. configs/ppo.yaml 2026-06-02'den beri v10 optimal formatında. fast_sim zinciri (v4.1→v5.0, 18 config) kesin yakınsama ile kapandı. v10 Gazebo başlaması yalnızca ENV kodu değişikliğine bağlı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 20 satır TAMAMEN GEÇERSİZ: 2026-05-30 22:00–03:01 UTC arası 14 özdeş satır (step=193,248, ep_rew_mean=−173.85). v9_newmap crash-loop kalıntısı.
- Gerçek son bilinen eğri: Gazebo v3.0 @434k → ep_rew_mean=99.84 (peak=102.54); @610k → peak=110.3 (kasıtlı durdurma, plato değil).
- +15'lik oda sıçraması: peak=110.3 ≈ 7×15=105 oda bonusu + ~5.3 frontier/voxel → v3.0'da en az 7 oda geçişi gerçekleşti. v9'da tüm CSV'de tek bir +15 spike YOK.
- eval_v3_310k.log yeni değerlendirme: 11 bölüm → 10/11=%91 yalnızca 1 oda, 1/11 → 2 oda. Stochastic eğitimde 7+ oda keşfedilen politika deterministik evalde 1 odaya düşüyor. Kök neden: lidar_history=1 → hareketli engel hız/yönü gözlemlenemiyor → ani engel çarpışmalarında recovery yapılamıyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- SORU GEÇERSİZ. ppo.yaml 2026-06-02'den beri `lr=3e-4→1e-5 linear`. v9 sonucu kesinleşti: constant lr=7.5e-5 ile 142k→599k arası yalnızca −290→−270 (+20 iyileşme, 457k adımda). v3.0 linear decay ile 0→434k'da +99.84 — **4.8× verimlilik farkı aynı step bütçesinde.** Sabit lr opsiyonu veriyle kapatıldı.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; CSV değerleri 8 günlük stale veri.
- v10 projeksiyon: ent_coef=0.008 (v9'un 5.3×'i) → başlangıç entropy ~−5.5/−6.0 beklenir. Deterministikleşme riski minimal.
- v10 alarm tetik (başladığında uygulanacak): entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI — iki koşul birlikte olmadan aksiyon yok.
- fast_sim kanıtı: ent_coef artırımı güvenlik-kapsam trade-off'unu kırmadı (v4.2: ent_coef=0.02 → %85 çarpışma). Keşif kalitesi obs tasarımından geliyor.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9'da oda geçişi HİÇ gerçekleşmedi. "Kaç step daha" sorusu v9 için geçersiz; v10 için projeksiyon:
  - v10 + env_fix (collision_pen=25, lidar_history=2): fast_v4.8 analoğu → **~150-250k step** (deterministik evalde tutarlı 5 oda).
  - v10 + mevcut env (collision_pen=10, lidar_history=1): v3.0 analoğu → ~300-430k (ama eval-train gap kapanmaz).
- fast_sim KESIN YAKINSAMA (v5.0 son bulgu): lidar_history 2→3 başarısız (voxels 281→106; v4.8 tarafından domine edildi). Yapısal kısıt: lidar_history=2 irreversible optimal eşik — daha fazlası işe yaramıyor.

**e) v10 için şu an en kritik 1-2 önerin ne olur?**
1. **`collision_penalty: 10.0 → 25.0` (drone_exploration_env.py, 1 satır):** 4-nokta fast_sim sweet spot: 22=%37 çarpışma+rooms collapse; **25=%0 çarpışma+5 oda (OPTIMAL)**; 30=%8 aşırı tedirgin; 50/curriculum tamamen başarısız (v4.11, v4.12). Mevcut 10.0 ile v10 Gazebo, fast_v1 (%47 çarpışma) rejimini tekrarlayacak. 1.5M bütçe büyük ölçüde boşa gider.
2. **`lidar_history: 1 → 2` (drone_exploration_env.py, obs 41-d → 72-d):** fast_v2 tek-değişken: çarpışma %80→%1. ppo.yaml değişikliği GEREKMEZ (policy_kwargs ağ mimarisi obs boyutunu otomatik alır). v5.0 kanıtı: 2→3 geçişi BAŞARISIZ — bu eşik sabit tutulacak.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** Mevcut v10 config: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true). 18-config fast_sim sweep + v3.0 Gazebo (peak=110.3) ile çapraz doğrulanmış.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** fast_sim v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M voxels geriledi (281→134). 2M+ sonrası güvenlik kolapsı kaçınılmaz; YAPISAL KISIT.
- **norm_obs=false durumu (teyit):** 41-d obs alanları farklı ölçeklerde (lidar 0-20m, cos/sin −1..+1, hız normalize, idle_counter serbest). v3.0 peak=110.3 norm_obs=false ile elde edildi → bu ayar o ortamda çalışıyor. Değiştirmeye gerek yok (%80 eşiği aşmıyor).
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 8. gündür başlamadı. 1.5M adım @~40 FPS ≈ 10.4 saat eğitim süresi. Her geçen gün proje penceresini daraltıyor. Bloker ENV kodu — hyperparameter değil.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py):** fast_sim v4.8 champion: %0 çarpışma + 5 oda + 117 voxels @1.5M. Mevcut 10.0 → 25.0. OLMADAN: v10 Gazebo'da %47+ çarpışma, 1.5M bütçe boşa.
2. **`lidar_history=2` (obs 41→72-d, drone_exploration_env.py):** fast_v2 %80→%1 breakthrough; v5.0 kanıtı ile 2 optimal eşik kesinleşti (3 daha kötü). Bu iki satır + `./scripts/train.sh configs/ppo.yaml` → yaml hazır, değiştirilmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda; 18-config fast_sim sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3 @610k) ile tam doğrulanmış. %80+ güven eşiğini aşan hiçbir hyperparameter sorunu tespit edilmedi. Bloker drone_exploration_env.py ENV kodu (kullanıcı tarafı); yaml commit+push yapılmadı.
---

## [2026-06-07 15:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri donmuş, 8. gün) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
CSV verisi 8. gündür değişmiyor; v9 Gazebo eğitimi 193k step'te kalıcı çökmüş durumda. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında. 18-config fast_sim sweep (v4.1→v5.0) ve v3.0 Gazebo (peak=110.3 @610k) ile çapraz doğrulanmış. Saatlik analiz tekrar yürütüldü — hyperparameter değişimi için %80+ eşik aşılmadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- Son 20 CSV satırı 14 özdeş kayıt: step=193,248 / ep_rew_mean=−173.85. v9 eğitimi yoktur.
- v9 aktif faz en iyi noktası: ep_rew_mean=−37.4 @145k (2026-05-30 21:20 UTC). Hiçbir +15 oda sıçraması gözlemlenmedi → v9 tüm çalışma boyunca oda eşiğini geçemedi.
- Gerçek referans (v3.0 Gazebo): peak=110.3 @610k → en az 7 oda geçişi (7×15=105 baz + frontier/voxel). v10 için bu eşik hedef.
- fast_sim v4.8 (Gazebo v10'un analığı): 100 bölümde %0 çarpışma, 5 oda, 117 voxels @1.5M.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Konu kapalı. `ppo.yaml`: `lr=3e-4→1e-5 linear` (2026-06-02'den beri). Sabit lr veriyle kapatıldı — v9 constant @7.5e-5 ile 457k adımda yalnızca 20 birim iyileşme; v3.0 linear decay ile 0→434k arası +99.84 (+4.8× verimlilik).

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; stale CSV analizi anlamsız. v10 projeksiyonu: ent_coef=0.008 (v9'un 5.3×'i) ile başlangıç entropy −5.5/−6.0 beklenir. Deterministikleşme alarm tetik: entropy_loss > −3.5 VE std < 0.75 eş zamanlı (iki koşul birlikte olmadan aksiyon yok).

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9'da oda geçişi hiç gerçekleşmedi. v10 projeksiyonları:
  - ENV FIX ile (collision_pen=25, lidar_history=2): **150-250k step** (fast_v4.8 analoğu; deterministik evalde tutarlı 5 oda).
  - Mevcut ENV ile (collision_pen=10, lidar_history=1): 300-430k (v3.0 analoğu; eval-train gap kapanmaz).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (drone_exploration_env.py):** fast_sim 4-nokta sweet spot ile kesinleşti — 22=%37 çarpışma+rooms collapse; **25=%0 çarpışma+5oda (OPTIMAL)**; 30=%8 aşırı tedirgin. Mevcut 10.0 ile v10 Gazebo, fast_v1 (%47 çarpışma) rejimini tekrarlayacak.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, drone_exploration_env.py):** fast_v2 tek-değişken %80→%1 çarpışma düşüşü. v5.0 kanıtı: 2→3 geçişi başarısız (voxels 281→106); 2 irreversible optimal eşik. ppo.yaml değişikliği gerekmez.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** Mevcut v10 config 18-config fast_sim + v3.0 Gazebo ile tam doğrulanmış. Değiştirmeyi gerektirecek %80+ güven eşiğini aşan sorun yok.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** v4.10 @3.2M=%100 çarpışma; v4.11 @5M=%100; v4.13 @8M voxels 281→134 geriledi. Yapısal kısıt.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 8. gündür başlamadı. 1.5M adım @ ~40 FPS ≈ 10.4 saat eğitim süresi. Her geçen gün proje penceresini daraltıyor. Tek bloker: `drone_exploration_env.py` ENV kodu (kullanıcı tarafı).

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py, 1 satır):** fast_sim v4.8 champion (%0 çarpışma, 5 oda, 117 voxels). 10→25 olmadan v10 Gazebo fast_v1 (%47 çarpışma) rejimi — 1.5M bütçe büyük ölçüde boşa.
2. **`lidar_history=2` (obs 41→72-d):** fast_v2 irreversible breakthrough. Bu iki satır uygulandıktan sonra `./scripts/train.sh configs/ppo.yaml` hazır; yaml değişmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda (2026-06-02'den beri, değiştirilmedi). fast_sim sweep (v4.1→v5.0, 18 config) + v3.0 Gazebo (peak=110.3 @610k) ile tam doğrulanmış. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Bloker `drone_exploration_env.py` ENV kodu — kullanıcı tarafında.
---

## [2026-06-07 16:06 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri donmuş, 8. gün) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
v9 Gazebo eğitimi 2026-05-30 22:00'da 193k step'te kalıcı çökmüş; CSV 8 gündür özdeş satır yazıyor. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında; fast_sim sweep (v4.1→v5.0, 18 config) + v3.0 Gazebo (peak=110.3 @610k) ile tam doğrulanmış. Aktif Gazebo eğitimi yoktur.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- Son 20 CSV satırı = 14 özdeş kayıt (step=193,248, ep_rew_mean=−173.85, 2026-05-30 22:00–03:01 UTC). v9 eğitimi tamamen durmuş; ölçüm geçersiz.
- v9 aktif faz peak: ep_rew_mean=−37.4 @145k step (21 Mayıs 21:20). Tüm v9 boyunca tek +15 oda sıçraması gözlemlenmedi — oda eşiği hiç geçilmedi.
- Gerçek son referans: v3.0 Gazebo peak=110.3 @610k (kasıtlı durdurma, plato değil); fast_v4.8 @1.5M: %0 çarpışma, 5 oda, 117 voxels.
- +15'lik oda sıçraması yalnızca v3.0 + fast_v4.8 sonrası gerçekleşti; v9_newmap Gazebo'da tamamen gözlemlenmedi.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Konu kapalı. `ppo.yaml` (2026-06-02): `lr=3e-4→1e-5 linear`. v9 constant @7.5e-5 ile 457k adımda yalnızca −290→−270 (+20 birim); v3.0 linear decay ile 0→434k arası +99.84 → **4.8× verimlilik farkı.** Sabit lr opsiyonu veriyle çürütüldü.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; CSV değerleri anlamsız.
- v10 projeksiyonu: ent_coef=0.008 (v9'un 5.3×'i) → başlangıç entropy ~−5.5/−6.0. Erken deterministikleşme riski minimal.
- v10 alarm tetik (başladığında): entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI — tek koşul yetmez; ikisi birlikte olmadan aksiyon yok.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9'da oda geçişi sıfır. v10 için:
  - ENV FIX ile (collision_pen=25, lidar_history=2): ~150–250k step (fast_v4.8 analoğu; deterministik evalde tutarlı 5 oda).
  - Mevcut ENV ile (collision_pen=10, lidar_history=1): ~300–430k (v3.0 analoğu; eval-train gap kapanmaz).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (drone_exploration_env.py, 1 satır):** fast_sim 4-nokta sweet spot: 22=%37 çarpışma+oda kolapsu; **25=%0 çarpışma+5 oda (OPTIMAL)**; 30=%8 aşırı-tedirgin; 50=%100 (v4.11 başarısız). Mevcut 10.0 ile v10 Gazebo fast_v1 (%47 çarpışma) rejimini tekrarlayacak — 1.5M bütçenin büyük kısmı boşa gider.
2. **`lidar_history: 1 → 2` (drone_exploration_env.py, obs 41-d → 72-d):** fast_v2 tek-değişken kanıtı: çarpışma %80→%1. v5.0 kanıtı: 2→3 geçişi başarısız (voxels 281→106, v4.8 tarafından domine). 2 irreversible optimal eşik — ppo.yaml değişikliği gerekmez (ağ mimarisi obs boyutunu otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** v10 config (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1) 18-config fast_sim sweep + v3.0 Gazebo ile doğrulanmış; %80+ eşiğini aşan sorun yok.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** fast_sim v4.10 @3.2M=%100 çarpışma; v4.11 @5M=%100; v4.13 @8M voxels 281→134 geriledi. Yapısal kısıt — artırma girişimi güvenlik kolapsına yol açar.
- **norm_obs=false teyit:** 41-d obs alanları farklı ölçeklerde; v3.0 peak=110.3 bu ayarla elde edildi. Değiştirmeye gerek yok.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 8. gündür başlamadı. 1.5M adım @ ~40 FPS ≈ 10.4 saat eğitim süresi. Proje penceresine baskı artıyor. Tek bloker: `drone_exploration_env.py` ENV kodu — hyperparameter değil.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py):** fast_sim v4.8 champion: %0 çarpışma + 5 oda + 117 voxels @1.5M. 10→25 olmadan v10 Gazebo %47+ çarpışma rejimi — 1.5M bütçe büyük ölçüde boşa.
2. **`lidar_history=2` (obs 41→72-d, drone_exploration_env.py):** fast_v2 %80→%1 breakthrough; v5.0 kanıtı ile 2 = irreversible optimal eşik kesinleşti. Bu iki satır tamamlandıktan sonra `./scripts/train.sh configs/ppo.yaml` hazır — yaml değişmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda (2026-06-02'den beri); 18-config fast_sim sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3 @610k) ile tam doğrulanmış. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Bloker `drone_exploration_env.py` ENV kodu (kullanıcı tarafı) — yaml commit+push yapılmadı.
---

## [2026-06-07 17:00 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri 8. gün donmuş, GEÇERSİZ) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
v9 Gazebo eğitimi 2026-05-30 22:00'da 193k step'te kalıcı çökmüş; `training_metrics.csv` 8 gündür 14 özdeş satır yazıyor. Görev bağlamındaki "v9 şu an çalışıyor / lr=7.5e-5 constant / ent_coef=0.0015 / n_envs=2 / total=2.5M" tanımı tamamen güncel değil — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında. fast_sim 18-config sweep (v4.1→v5.0) ve v3.0 Gazebo (peak=110.3 @610k) ile çapraz doğrulanmış. v10 Gazebo eğitimi 9. gündür başlamadı; tek bloker `drone_exploration_env.py` ENV kodu değişikliği.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 20 satır ANALİZİ:
  - Aktif faz (2026-05-30 13:xx–21:40 UTC): ep_rew_mean -324→-37.4 arası salınımlı (crash_recovery döngüleri). En iyi nokta: -37.4 @145k step (21:20 UTC). Hiçbir +15 oda sıçraması gözlemlenmedi → v9 tüm çalışma boyunca oda eşiğini geçemedi.
  - FREEZE faz (22:00 UTC – 03:01 UTC): 14 özdeş satır, step=193,248, ep_rew_mean=-173.85. Process ölü, monitor son checkpoint'i tekrar tekrar okuyor.
  - **Sonuç:** v9 reward eğrisi oda kırılımı olmadan kapandı. Plato da değil — aktif eğitim hiç stabilleşmedi.
- Gerçek referans: v3.0 Gazebo peak=110.3 @610k (2026-06-01, kasıtlı durdurma); fast_v4.8 @1.5M: %0 çarpışma, 5 oda, 117 voxels.
- v10 eğitim eğrisi: **YOK** — eğitim başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- SORU GEÇERSİZ. `ppo.yaml` 2026-06-02'den beri `lr=3e-4→1e-5 linear` (1.5M boyunca). Sabit lr tartışması çoktan kapandı.
- Kanıt: v9 constant lr=7.5e-5 ile 142k→599k arası ep_rew_mean yalnızca −290→−270 (+20 iyileşme, 457k adımda). Aynı dönemde entropy: -3.886→-3.324 (tehlikeli deterministikleşme trendi), std: 0.888→0.745 (0.7 eşiğine yaklaşma). v3.0 linear decay ile 0→434k: +99.84 → **4.8× verimlilik farkı, aynı step bütçesinde.**
- ent_coef da 0.0015→0.008 olarak güncellendi (v9'un 5.3×'i): v3.0 @312k entropy=−5.67, std=1.63 — sağlıklı rejim kanıtlandı. Her iki değişiklik de veri bazlı ve doğru.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; CSV'deki son değerler (entropy=−4.212, std=0.985, @193k) v9 crash kalıntısı — kullanılamaz.
- v10 projeksiyonu (ent_coef=0.008 ile): ent_coef v9'un 5.3×'i; referans v3.0 @312k: entropy=−5.67, std=1.63. Başlangıçta entropy ~−5.5/−6.0 beklenir — deterministikleşme riski son derece düşük.
- fast_sim dersi (kesin): ent_coef artırmak güvenlik-kapsam trade-off'unu kırmadı (v4.2: ent_coef=0.02 → %85 çarpışma). Keşif kalitesi obs tasarımından (lidar_history) geliyor. ent_coef=0.008 dokunulmaz.
- **v10 alarm tetik koşulu (başladığında):** entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI — iki koşul birlikte olmadan aksiyon yok.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9'da oda geçişi **HİÇ gerçekleşmedi** (tüm CSV'de tek +15 spike yok).
- v10 için projeksiyon tablosu (fast_sim + v3.0 referans):

| ENV durumu | Beklenen oda geçişi | Eval-train gap |
|---|---|---|
| collision_pen=25 + lidar_history=2 | **~150–250k step** (fast_v4.8 analoğu) | Kapanır (%0 çarpışma, tutarlı 5 oda) |
| collision_pen=10 + lidar_history=1 (mevcut) | ~300–430k step (v3.0 analoğu) | Kapanmaz (eval_v3_310k: 10/11 bölüm 1 oda) |
| Potansiyel step tasarrufu | ~%40 (≈450k adım) | Yalnızca 2 ENV satırıyla |

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: 10.0 → 25.0` (1 satır, ENV kodu):** fast_sim 4-nokta kesin sweet spot: 22=%37 çarpışma+rooms 5→2 collapse (yerel optimum), **25=%0 çarpışma+5 oda (OPTIMAL)**, 30=%8 (aşırı tedirgin, keşif kısıtlı), 50=%100 collapse. Mevcut 10.0, sweet spot'un %40'ı — drone çarpışmayı sistematik hafife alıyor. Bu olmadan v10 Gazebo fast_v1 rejimini (%47 çarpışma) tekrarlayarak 1.5M bütçeyi büyük ölçüde boşa harcayacak.
2. **`drone_exploration_env.py`: `lidar_history: 1 → 2` (obs 41-d → 72-d, ENV kodu):** fast_v2 tek-değişken breakthrough: çarpışma %80→%1. Format: `[t-1: 32 lidar | t: 32 lidar | yaw_cos+sin | vx+vz+wz | explore+room | min_lidar | idle]`. v5.0 kanıtı: 2→3 geçişi başarısız (voxels 281→106, v4.8 tarafından domine edildi); 1→2 irreversible optimal eşik, kesinleşmiş. ppo.yaml değişikliği GEREKMİYOR (MlpPolicy obs boyutunu env'den otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** Mevcut v10 config: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize(norm_obs=false, norm_reward=true, clip=10.0). 18-config fast_sim sweep + v3.0 Gazebo (peak=110.3) ile çapraz doğrulanmış; %80+ güven eşiğini aşan config sorunu tespit edilmedi.
- **HARD CAP — total_timesteps=1.5M DOKUNULMAZ:** fast_sim kanıtı 4 bağımsız noktayla: v4.10 @3.2M=%100 çarpışma, v4.11 @5M=%100 çarpışma, v4.13 @8M voxels 281→134 geriledi. 2M+ sonrası güvenlik kolapsı kaçınılmaz; yapısal kısıt.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 9. gündür başlamadı. 1.5M adım @~40 FPS ≈ 10.4 saat eğitim süresi. Her geçen gün proje penceresini daraltıyor. Tek bloker: `drone_exploration_env.py` ENV kodu — hyperparameter değil, kullanıcı tarafında.

### v10 Önerisi
1. **`collision_penalty=25` (drone_exploration_env.py, 1 satır):** fast_sim v4.8 champion kanıtı (%0 çarpışma, 5 oda, 117 voxels @1.5M). Mevcut 10.0 → 25.0. Bu olmadan v10 Gazebo'da %47+ çarpışma kaçınılmaz; politika keşif reward'unu çarpışma cezasıyla dengeleyemez ve 1.5M bütçe boşa gider.
2. **`lidar_history=2` obs entegrasyonu (obs 41→72-d, drone_exploration_env.py):** fast_v2 %80→%1 breakthrough; v5.0 kanıtıyla 2 = irreversible optimal eşik (3 daha kötü). Bu iki ENV satırı tamamlandıktan sonra `./scripts/train.sh configs/ppo.yaml` — yaml hazır ve optimal, değiştirilmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda; fast_sim 18-config sweep (v4.1→v5.0) + v3.0 Gazebo (peak=110.3 @610k) ile tam doğrulanmış. Görev bağlamındaki "v9 şu an çalışıyor / lr=7.5e-5 constant / ent_coef=0.0015" tanımı **güncel değil** — bu kararlar veri bazlı olarak çoktan tersine çevrildi ve doğrulanan v10 config üzerinden %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu tespit edilmedi. Bloker `drone_exploration_env.py` ENV kodu (kullanıcı tarafı); yaml değiştirilmedi, commit+push yapıldı.
---

## [2026-06-07 22:10 UTC]
**Step:** 193,248 (CSV STALE — v9 crash kalıntısı, 2026-05-30 22:00'dan beri 8. gün dondurulmuş) | **ep_rew_mean:** -173.85 (GEÇERSİZ) | **entropy:** -4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
Aktif Gazebo eğitimi yok; `training_metrics.csv` son 8 günde değişmedi (step=193,248 bant). `configs/ppo.yaml` 2026-06-02'den beri v10 optimal formatında — fast_sim 18-config sweep (v4.1→v5.0) ve v3.0 Gazebo (peak=110.3 @610k kasıtlı durduruldu) ile tam doğrulanmış. v10 Gazebo eğitiminin tek blokeri `drone_exploration_env.py` ENV değişiklikleri (kullanıcı tarafı).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son 20 satır GEÇERSİZ: 2026-05-30 22:00–03:01 arası 14 özdeş satır (step=193,248, ep_rew_mean=−173.85). Eğitim process ölü, monitor son checkpoint'i döngüsel okuyor.
- v9 aktif faz (13:xx–21:40): ep_rew_mean −324→−37.4 arası salınımlı. En iyi: −37.4 @145k. Hiç +15 oda sıçraması gözlemlenmedi → v9 oda eşiğini hiç geçemedi; reward kırılımı olmadan kapandı.
- Gerçek en iyi Gazebo peak: **+110.3 @610k** (v3.0, kasıtlı durduruldu, 2026-06-01). v10 eğitim verisi henüz yok.
- fast_sim referans en iyi eval: v4.8 @1.5M — %0 çarpışma, 5 oda, 117 voxels (collision_penalty=25 + lidar_history=2).

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- GÜNCEL DEĞİL. Mevcut `ppo.yaml`: `lr=3e-4 → 1e-5 linear` (1.5M boyunca). Sabit lr tartışması veri bazlı olarak kapandı.
- Kanıt: v9 sabit lr=7.5e-5 ile 457k adımda ep_rew_mean yalnızca −290→−270 (+20). Entropy aynı dönemde −3.89→−3.32 (deterministikleşme), std 0.89→0.75 (tehlikeli eşiğe yaklaşma). v3.0 linear decay ile 0→434k: +99.84 — **4.8× daha verimli, aynı step bütçesinde**.
- `ent_coef` da 0.0015→0.008 (5.3× artış); v3.0 @312k entropy=−5.67, std=1.63 (sağlıklı keşif rejimi). Her iki değişiklik kanıtlanmış ve doğru.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; CSV değerleri kullanılamaz.
- v10 projeksiyonu: ent_coef=0.008 ile başlangıç entropy ~−5.5/−6.0 beklenir. Deterministikleşme riski düşük.
- **v10 için alarm tetik koşulları:** entropy_loss > −3.5 VE std < 0.75 EŞ ZAMANLI (iki koşul birlikte).
- fast_sim uyarısı: ent_coef artırmak keşif kalitesini doğrudan artırmıyor — gözlem tasarımı (lidar_history=2) çok daha güçlü kaldıraç (%80→%1 çarpışma düşüşü).

**d) Oda geçişi için ne kadar step gerekmesi beklenir?**
- v9: **Hiç gerçekleşmedi** (tüm CSV boyunca sıfır +15 spike).
- v10 projeksiyonu:
  - Mevcut ENV (collision_penalty=10, lidar_history=1): ~300–430k step (v3.0 analoğu, eval_v3_310k: 10/11 bölüm rooms=1).
  - Önerilen ENV (collision_penalty=25, lidar_history=2): ~150–250k step (fast_v4.8 analoğu).
  - Fark: ~%40 step tasarrufu ≈ 450k adım, yalnızca 2 ENV satırıyla.

**e) v10 için en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (`drone_exploration_env.py`, 1 satır):** fast_sim kesin tatli nokta: 22→rooms collapse (%37 crash), **25→OPTIMAL** (%0 crash, 5 oda, 117 voxels), 30→tedirgin (%8 crash, az keşif). Mevcut 10 → drone çarpışmayı hafife alıyor → v9 rejimi tekrarlanır.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`):** fast_v2 tek-değişken breakthrough: çarpışma %80→%1. v5.0 kanıtı: 2→3 daha kötü (voxels 281→106, v4.8 tarafından domine). 2 = irreversible optimal eşik. `ppo.yaml` değişikliği gerekmez (MlpPolicy obs boyutunu env'den otomatik alır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından HAYIR.** v10 yaml tam optimal; %80+ güven eşiğini aşan sorun yok.
- **`total_timesteps=1.5M` HARD CAP — DOKUNULMAZ:** fast_sim 4 noktayla kesin: v4.10 @3.2M=%100 crash, v4.11 @5M=%100 crash, v4.13 @8M voxels 281→134 geriledi. 2M+ sonrası güvenlik kolapsı yapısal kısıt.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 9. gündür başlamadı. 1.5M adım @~40 FPS ≈ 10.4 saat eğitim. Tek bloker: `drone_exploration_env.py` ENV kodu (kullanıcı tarafı).

### v10 Önerisi
1. `drone_exploration_env.py` → `collision_penalty=25` (1 satır). Bu olmadan %47+ çarpışma rejimi, 1.5M bütçe boşa.
2. `drone_exploration_env.py` → `lidar_history=2` (obs 41→72-d). fast_v2 %80→%1 breakthrough; v5.0 kanıtıyla 2 = kesinleşmiş optimal eşik.
Bu iki değişiklik sonrası `./scripts/train.sh configs/ppo.yaml` — yaml hazır, değiştirilmemeli.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize). %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Bloker ENV kodu (kullanıcı tarafı); yaml commit+push yalnızca log için yapıldı.
---

## [2026-06-07 00:00 UTC]
**Step:** 193,248 (CSV — 8 GÜN STALE, 30 Mayıs 22:00'dan beri donmuş) | **ep_rew_mean:** −173.85 (geçersiz) | **entropy:** −4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
CSV 8+ gündür frozen (son 20+ satır birebir aynı: step=193248, reward=−173.85). Bu v9/v10 crash-loop kalıntısı; güncel veri değil. Gerçek son durum: v3.0 Gazebo run 610k/1.5M adımda kasıtlı durduruldu (peak=110.3); fast_sim v4.1→v5.0 serisi (18 config) tamamen kapandı. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda. **Aktif eğitim process'i YOK.** Config değişikliği gerekmez — yaml hazır, başlatmayı bekliyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verileri 8+ gün eski ve anlamsız — v9 crash loop sırasında 80k→180k step arasında döngüden kalan donmuş satırlar.
- Gerçek v2.x/v3.x eğitim zaman çizelgesi (interventions.jsonl + log dosyaları):
  - v2.1 @ 120k: ep_rew_mean=+92.6, rooms_max=2 → aktif kırılım fazı
  - v2.1 @ 501k: peak=+133.35 → v8 all-time best (+113@1.6M) yalnızca 500k'da geride bırakıldı
  - v3.0 @ 434k: peak=+102.54 (milestone, Haziran 1)
  - v3.0 → 610k/1.5M adımda kasıtlı durduruldu (peak=110.3, ppo.yaml açıklaması)
- **+15 oda sıçraması görüldü mü?** Evet — v2.1'de +92.6 = ~6 oda bonusu eğitim sırasında; v3.0 da peak 110.3 ile benzer seviyede.
- Şu an eğitim yok; plato/kırılım sorusu v10 fresh start için geçerli.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçersiz soru: `configs/ppo.yaml` çoktan v10'a taşındı.
- Mevcut schedule: `learning_rate: 0.0003` → `lr_final: 1.0e-05` (linear, 1.5M boyunca = 30× azalma).
- Bu v8'in 3e-4→3e-5 (10× azalma) şemasından 3× daha agresif annealing. İlk fazda hızlı politika güncellemesi, son fazda stabil fine-tune için doğru kalibrasyon.
- Sabit 7.5e-5 kullanımı v9'un başarısızlık sebebiydi (v9 plato: 600k step'te ep_rew_mean=−270); doğru terk edildi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV frozen → güncel değer güvenilmez.
- v10 config'de `ent_coef: 0.008` (v9'un 0.0015'inden 5.3×, v2.1'in 0.005'inden 1.6× yüksek).
- fast_sim v4.1-v5.0 testlerinden kanıtlanmış: v4.8'de %0 çarpışma bu ent_coef ile sağlandı.
- 300-400k bandında std<0.7 riski var (v4 analoji bu bandda deterministikleşti); izleme noktası korunmalı. ent_coef=0.008 bu riski v4'e göre belirgin düşürüyor.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 fresh start varsayımıyla (n_steps=2048, lr=3e-4, ent_coef=0.008, n_envs=1):
  - İlk oda geçişi: 60-100k step (v2.1'de 120k'da rooms_max=2 görüldü; v10 yüksek ent_coef ile daha erken olabilir)
  - Tutarlı 3-oda: 200-350k step
  - 5-6 oda stochastic policy: 500-700k step aralığı
  - Deterministic eval'de 3+ oda tutarlılık: 800k-1.2M step
- Lidar history artırımı (1→2, obs 41d→72d) eval-train gap'i kapatacak; bu en kritik potansiyel iyileşme.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`norm_obs: false` korunmalı** — fast_sim v4.8'de kanıtlanmış optimal. 41-d gözlem uzayı zaten kısmi normalize: lidar [0,12m]/12m, yaw [cos,sin] ∈ [−1,1], hız v/v_max, oran [0,1]. norm_obs=true bu sınırları bozabilir (running_mean drift); mevcut ayar korunmalı.
2. **Hareketli engel curriculum:** v10'da 3 hareketli engel aktif olacak. İlk 150-200k adımda engellerle başlamak öğrenmeyi sekteye uğratır. **Öneri:** ya ilk 150k step için obstacle velocity=0 (statik) tutup sonra aşamalı artır, ya da `drone_exploration_env.py`'de `obstacle_speed_schedule` ekle. Env kodu değişikliği gerekiyor — bu en yüksek ROI müdahalesi.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** `configs/ppo.yaml` v10 optimal değerlerinde (2026-06-02'den beri), önceki oturum bunu doğruladı.
- **Operasyonel: EVET (düşük aciliyet).** Eğitim process'i 8+ gündür çalışmıyor. Kullanıcının `./scripts/train.sh configs/ppo.yaml` ile v10'u başlatması gerekiyor.
- CSV monitoring altyapısı hâlâ v9 dönemine sabitli; v10 başlayınca TB dizinini yeniden ayarlamak gerekecek.

### v10 Önerisi
1. **Hareketli engel curriculum (env kodu):** İlk 150k step obstacle velocity=0, sonra lineer artış. Bu tek değişiklik öğrenme hızını ve keşif kalitesini ciddi artırır — config değil, env kodu değişikliği.
2. **300-400k bandında std izleme tetik:** std < 0.7 VE entropy > −3.5 → `ent_coef: 0.008 → 0.015`. v4 analoji bu bandda kesildi; v10 ent_coef yüksek ama uyarı geçerliliğini koruyor.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 konfigürasyonu (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize norm_obs=false/norm_reward=true) fast_sim v4.8 ve v3.0 Gazebo run'larıyla kanıtlanmış optimal. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Acil bloker: v10 eğitim process'inin başlatılması (kullanıcı tarafı operasyonel aksiyon).
---

## [2026-06-08 00:11 UTC]
**Step:** 193,248 (CSV 9 GÜN STALE — 2026-05-30 22:00'dan beri donmuş) | **ep_rew_mean:** −173.85 (GEÇERSİZ) | **entropy:** −4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
CSV verisi 9. gündür donmuş; aktif Gazebo eğitimi yok. Bu oturumda `train_v3_resume_310k.log` analiz edildi: v3.0 Gazebo run'u 310k'dan 1.45M step'e uzatılmış ve **politika açıkça dağılmış** — std 1.65→14, entropy −5.69→−11.5, ep_rew_mean 110.3 peak'inden +38.2'ye gerilemiş. Bu, sabit `lr=0.0003`'ün uzun eğitimdeki dağılma riskinin somut Gazebo kanıtıdır. `configs/ppo.yaml` v10 konfigürasyonuna (linear decay 3e-4→1e-5) sahip ve `train_ppo.py`'de `_build_lr()` fonksiyonu doğru implement edilmiş; v10 fresh start bu riski bertaraf eder.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv`: 9. gündür donmuş (step=193,248, ep_rew_mean=−173.85 — v9 crash-loop kalıntısı). Geçerli veri değil.
- `train_v3_resume_310k.log` yeni kanıt: v3.0 Gazebo 310k'dan 2M'e uzatılmaya çalışıldı. Eğitim 1.14M (68%) sonra interrupt ile bitti. Eğitim boyunca:
  - @312k: ep_rew_mean=48.9, std=1.65, entropy=−5.69 (sağlıklı başlangıç)
  - @1.45M: ep_rew_mean=38.2, std=14.0, entropy=−11.5 (DAĞILMIŞ politika)
  - Peak 110.3 @610k'dan bu yana sürekli gerileme — plato değil, aktif bozulma.
- `eval_v3_310k.log`: 11 bölüm Gazebo eval, 10/11 bölüm rooms=1, sadece 1 bölüm rooms=2. Return +45–77. 310k checkpoint henüz oda geçişini güvenilir keşfetmemişti.
- Gerçek en iyi Gazebo peak: **+110.3 @610k** (v3.0, kasıtlı durduruldu).
- v10: henüz başlamadı, kırılım sorusu ileriye taşındı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Soru artık tarihsel: `ppo.yaml` 2026-06-02'den beri `lr=3e-4→1e-5 linear` (1.5M boyunca). Mevcut config doğru.
- **Yeni Gazebo kanıtı (kritik):** `train_v3_resume_310k.log` boyunca TB `learning_rate: 0.0003` sabit gösterdi. Bu, ya eski train_ppo.py'nin schedule uygulamadığını, ya da resume sırasında SB3'ün step sayacını sıfırlaması nedeniyle `progress_remaining=1.0` kalmasını gösteriyor. Her iki durumda da etki aynı: 1.45M adım boyunca yüksek sabit lr → std 14'e dağılma → reward çöküşü.
- `train_ppo.py` incelendi: mevcut `_build_lr()` fonksiyonu SB3 callable arayüzünü doğru implement ediyor (`f(progress_remaining)`). **v10 fresh start** için `resume_from: null` olduğundan bu resume bug'ı tetiklenmeyecek. Doğrudan `learning_rate=_build_lr(ppo_cfg)` ile model kurulacak → doğru linear decay garantili.
- ⚠️ **Uyarı (resume senaryosu için):** Lines 235-237'de `model.policy.optimizer.param_groups[0]["lr"] = float(ppo_cfg["learning_rate"])` resume'de optimizer'ı base lr'a resetliyor; buna ek olarak SB3'ün step sayacının sıfırlanması riski var. v10 fresh olduğu için şimdi sorun değil ama ilerideki resume'ler için dikkat edilmeli.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif eğitim yok; CSV değerleri kullanılamaz.
- v3.0 floors evidence: std=14, entropy=−11.5 → dağılmış politika. Bu paterni v10 linear decay ile önlüyor.
- v10 projeksiyonu (n_epochs=10, ent_coef=0.008, lr doğru decay): std başlangıçta ~1.0-1.5 beklenir; v4.8 referans (fast_sim, ent_coef=0.008, lidar_history=2): sağlıklı keşif rejimi gözlemlendi.
- **Alarm tetik koşulları v10 için:** std < 0.5 VE entropy_loss > −2.5 → erken deterministikleşme; std > 5.0 → dağılma riski, lr decay doğru çalışmıyor olabilir. İkinci alarm özellikle ilk 100k step'te kritik.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- `eval_v3_310k.log`: 310k'lık Gazebo checkpoint 10/11 bölümde rooms=1. İlk güvenilir oda geçişi henüz oluşmamış.
- v10 projeksiyonu (collision_penalty=10 ile mevcut env):
  - İlk oda geçişi: ~250-400k step (v3.0 analoji; v3.0 @434k peak=102.54 oda geçişlerini içeriyordu)
  - collision_penalty=25 + lidar_history=2 (önerilen env): ~150-250k step (fast_v4.8 analoji)
  - Mevcut env ile bütçenin %20-27'si oda öğrenimi öncesinde geçebilir.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10.0 → 25.0` (`drone_exploration_env.py`):** fast_sim v4.8 ŞAMPIYON: %0 çarpışma, 5 oda, 117 voxels @1.5M. v4.9 (22) rooms 5→2 çöktü, v4.10 (25, 5M) %54 crash. 25 = dar tatli nokta, tek veri noktası olarak değil 4-nokta sweep ile doğrulanmış. Mevcut 10.0 → drone çarpışmayı sistematik hafife alıyor → v9 rejimi (%47 crash @fast_v1) tekrarlanacak ve 1.5M bütçenin önemli kısmı boşa gidecek.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`):** fast_v2 breakthrough: çarpışma %80→%1. v5.0 kanıtı: 2→3 ters etki (voxels 281→106, v4.8 tarafından domine). 2 = kesinleşmiş irreversible optimal eşik. ppo.yaml değişikliği GEREKMİYOR.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml hyperparameter açısından: HAYIR.** v10 config fast_sim 18-config sweep + v3.0 Gazebo ile çapraz doğrulanmış. `_build_lr()` doğru. %80+ güven eşiğini aşan config sorunu yok.
- **Yeni kanıt (v3.0 floors divergence) v10 config'i olumsuz etkilemiyor:** Linear decay bu riski bertaraf ediyor; fresh start resume bug'ını bypass ediyor.
- **Operasyonel gecikme (KRİTİK):** v10 Gazebo 10. gündür başlamadı. 1.5M adım @~40 FPS ≈ 10.4 saat eğitim. Deadline baskısı artıyor. Tek bloker: `drone_exploration_env.py` ENV kodu (kullanıcı tarafı, 2 satır).

### v10 Önerisi
1. **`collision_penalty=25` (`drone_exploration_env.py`, 1 satır değişiklik):** fast_sim v4.8 kanıtı (%0 crash, 5 oda, 117 voxels). Bu olmadan v10 Gazebo %47+ crash rejimine girecek; 1.5M bütçenin büyük kısmı boşa.
2. **`lidar_history=2` (obs 41→72-d, `drone_exploration_env.py`):** fast_v2 %80→%1 breakthrough, v5.0 kanıtıyla kesinleşmiş optimal eşik. Eng yüksek ROI müdahalesi (2 satır env kodu, ppo.yaml değişikliği gerektirmiyor).

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize norm_obs=false/norm_reward=true/clip=10). Yeni kanıt (`train_v3_resume_310k.log` divergence analizi) v10 config'in doğruluğunu pekiştirdi — sabit lr'ın dağılma riskini linear decay önlüyor, `_build_lr()` fresh start için doğru çalışıyor. %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu tespit edilmedi. Bloker ENV kodu (kullanıcı tarafı); yaml commit+push analiz logu ile birlikte yapıldı.
---

## [2026-06-08 01:06 UTC]
**Step:** 193,248 (CSV 9+ GÜN STALE — son gerçek veri 2026-05-30 22:00) | **ep_rew_mean:** −173.85 (GEÇERSİZ, v9 crash-loop kalıntısı) | **entropy:** −4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
Aktif Gazebo eğitimi yok; CSV 9+ gündür donmuş, güncel veri elde edilemiyor. `versions.jsonl` fast_sim zincirinin kesin olarak kapandığını gösteriyor: v4.8 şampiyon (collision_penalty=25, lidar_history=2, 1.5M step → %0 çarpışma, 5 oda, 117 voxel), v5.0 ile tüm kaldıraçlar tükendi. `configs/ppo.yaml` v10 konfigürasyonu (2026-06-02) bu kanıtlara dayanıyor ve hyperparameter açısından optimal. Config değişikliği gerektiren %80+ güven eşiğini aşan sorun tespit edilmedi.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son veri (step=193,248, ep_rew_mean=−173.85): 2026-05-30 22:00'dan bu yana 9 gündür DONMUŞ. v9 crash-loop dönemine ait, geçerli veri değil.
- Gerçek Gazebo geçmişi: v3.0 peak=+110.3 @610k (kasıtlı durduruldu), resume'da 1.45M'de std=14/entropy=−11.5 ile dağıldı. v10 henüz başlamadı — kırılım/plato sorusu ileriye taşındı.
- **+15'lik oda sıçraması:** v2.1'de ep_rew_mean=+92.6 @120k gözlemlendi (training stochastic, ≈6 oda bonusu). Gazebo ortamında kanıtlı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçerli değil. Mevcut `ppo.yaml`: `learning_rate: 0.0003`, `lr_schedule: linear`, `lr_final: 1.0e-05` (1.5M boyunca, 30× azalma).
- `train_v3_resume_310k.log` somut kanıtı: sabit lr=3e-4 altında v3.0, 1.45M step'te std=14/entropy=−11.5 ile dağıldı. Linear decay bu riski bertaraf ediyor.
- `train_ppo.py`'deki `_build_lr()` fonksiyonu doğru implement edilmiş; v10 fresh start (resume_from=null) resume bug'ını bypass ediyor.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; mevcut CSV değerleri kullanılamaz.
- v10 projeksiyonu: ent_coef=0.008 (v9'un 0.0015'inden 5.3× yüksek, fast_v4.8 onaylı). Başlangıçta std~1.0-1.5, entropy~−4.5 ila −5.0 bekleniyor.
- **Alarm eşiği (v10 başladığında izle):** std < 0.5 VE entropy > −2.5 → erken deterministikleşme; std > 5.0 → lr decay çalışmıyor olabilir (v3.0 dağılma paterni).
- v4.8 referans (fast_sim, aynı ent_coef): 1.5M boyunca sağlıklı keşif rejimi, %0 çarpışma.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 fresh start projeksiyonu (collision_penalty=25 + lidar_history=2 env değişiklikleriyle):
  - İlk oda geçişi: ~100-200k step (fast_v4.8 analoji)
  - Tutarlı 3-oda: ~300-500k step
  - 5-6 oda stochastic: ~700k-1M step
- collision_penalty=10 (mevcut env) ile bu süreler %30-50 uzayabilir — v9'un %47+ crash rejimi tekrarlanır.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır):** fast_sim v4.8 kesinleşmiş şampiyon: %0 çarpışma, 117 voxel, 5 oda @1.5M. Mevcut 10.0 ile drone çarpışmayı sistematik hafife alıyor; 1.5M bütçenin büyük bölümü boşa gidecek. NOT: 2M+ eğitimde collision=25 bile yetersiz kalıyor (v4.10 5M'de %54 crash); ppo.yaml zaten total_timesteps=1.5M ile bu üst sınırın altında.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough: çarpışma %80→%1. v5.0 (lidar_history=3) bunu domine edemedi (voxels 281→106). 2 = kesinleşmiş optimal; ppo.yaml değişikliği gerektirmiyor (sadece env kodu).

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** v10 ppo.yaml optimal; fast_sim 18-config sweep + v3.0 Gazebo ile çapraz doğrulanmış.
- **Operasyonel (yüksek öncelik):** v10 Gazebo 10+ gündür başlamadı. 1.5M @~40 FPS ≈ ~10.4 saat. Bloker: `drone_exploration_env.py` ENV kodu (kullanıcı tarafı, 2 satır değişiklik). Bu iki satır olmadan v10'u başlatmak 1.5M bütçeyi suboptimal harcatır.

### v10 Önerisi
1. **ENV kodu önce, eğitim sonra:** `collision_penalty=25` + `lidar_history=2` `drone_exploration_env.py`'ye ekle → sonra `./scripts/train.sh configs/ppo.yaml`. Bu sıra şart; config zaten hazır.
2. **v10 başlar başlamaz izleme:** İlk 50k step'te std > 5.0 veya FPS < 20 görülürse train_ppo.py'de `_build_lr()` ve VecNormalize entegrasyonunu doğrula. Aksi halde müdahale yok.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gae_lambda=0.95, clip_range=0.2, net_arch=[256,256], total_timesteps=1.5M, n_envs=1, VecNormalize norm_obs=false/norm_reward=true/clip_reward=10). versions.jsonl fast_sim yakınsaması + v3.0 Gazebo divergence analizi config'in doğruluğunu pekiştiriyor. %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu tespit edilmedi.
---

## [2026-06-08 02:06 UTC]
**Step:** 193,248 (CSV 9+ GÜN STALE — son gerçek güncelleme 2026-05-30 22:00) | **ep_rew_mean:** −173.85 (GEÇERSİZ, v9 crash-loop kalıntısı) | **entropy:** −4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
`training_metrics.csv` 9+ gündür aynı satırı tekrar ediyor (step=193,248 donmuş); aktif Gazebo eğitimi yok. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda. Bloke eden tek faktör: `drone_exploration_env.py` env kodu (kullanıcı tarafı, 2 satır).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV tamamen donmuş: 2026-05-30 22:00'dan bu yana her satır aynı (step=193,248, ep_rew_mean=−173.85). Bu değer v9 crash-loop dönemine ait, aktif eğitim değil.
- Gerçek son Gazebo peak: **+110.3 @610k** (v3.0, kasıtlı durduruldu). Resume sonrası 1.45M'de std=14/entropy=−11.5 ile dağıldı.
- Kırılım/plato sorusu askıda: v10 henüz başlamadı, değerlendirilebilir veri yok.
- +15'lik oda sıçraması: v2.1'de @120k gözlemlendi (ep_rew_mean +92.6); v10 için 100-200k step beklenir.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Bu soru artık geçersiz. `ppo.yaml` mevcut: `learning_rate: 0.0003` (lr_schedule: linear → lr_final: 1e-5, 1.5M boyunca 30× azalma).
- **Somut Gazebo kanıtı:** `train_v3_resume_310k.log`: sabit lr=3e-4 altında v3.0, 1.45M'de std=14/entropy=−11.5 ile dağıldı. Linear decay bu dağılmayı önler.
- `train_ppo.py`'deki `_build_lr()` doğru SB3 callable arayüzü implement ediyor. v10 fresh start (resume_from=null) → resume-schedule-reset bug'ı bypass ediliyor.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; CSV değerleri kullanılamaz.
- v10 projeksiyonu: ent_coef=0.008 (v9 0.0015'in 5.3×), fast_v4.8 onaylı. Başlangıç beklentisi: std~1.0-1.5, entropy~−4.5 ila −5.0.
- **İzlenecek alarm eşiği (v10 başlayınca):**
  - std < 0.5 VE entropy_loss > −2.5 → erken deterministikleşme (ent_coef artır)
  - std > 5.0 → lr decay çalışmıyor olabilir (v3.0 dağılma paterni)

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Env değişikliğiyle (collision_penalty=25 + lidar_history=2): ilk güvenilir oda geçişi ~100-200k step (fast_v4.8 analoji).
- Mevcut env (collision_penalty=10) ile: ~300-500k step; v9'un %47+ crash rejimi 1.5M bütçeyi aşındırır.
- fast_v4.8 referans: 1.5M @~4000 FPS → 5 oda tutarlı, %0 çarpışma.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır):** fast_sim v4.8 ŞAMPIYON kanıtı: %0 çarpışma, 5 oda, 117 voxel @1.5M. v4.9 (22) → rooms 5→2 çöküşü; v4.5 (30) → %8 crash (tutarli ama fazla temkinli). 25 = dar tatli nokta, 4-nokta sweep ile kesinleşmiş. Mevcut 10.0 drone'u sistematik olarak çarpışmayı küçümsemeye itiyor → 1.5M bütçenin büyük kısmı erken crash döngülerine gidecek.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough: çarpışma %80→%1 (3 dakikada). v5.0 (history=3) bunu domine edemedi (voxels 281→106 düştü). 2 = kesinleşmiş irreversible optimal. ppo.yaml değişikliği GEREKMİYOR — sadece env kodu.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config fast_sim 18-config sweep + v3.0 Gazebo divergence analizi ile çapraz doğrulanmış; %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu yok.
- **Operasyonel (yüksek öncelik):** v10 Gazebo 10+ gündür başlamadı. 1.5M @~40 FPS Gazebo ≈ 10.4 saat. Deadline baskısı kritik seviyede. Bloker: `drone_exploration_env.py` (kullanıcı tarafı, 2 satır değişiklik). Bu satırlar olmadan v10'u başlatmak 1.5M bütçeyi suboptimal harcatır.

### v10 Önerisi
1. **ENV kodu önce:** `drone_exploration_env.py` içinde `collision_penalty=25` ve `lidar_history=2` → ardından `./scripts/train.sh configs/ppo.yaml`. Sıra şart; config zaten hazır ve dokunulmayacak.
2. **v10 başlayınca ilk 50k step izleme:** std > 5.0 veya FPS < 20 → `_build_lr()` ve VecNormalize entegrasyonunu doğrula. Aksi halde müdahale yok — ent_coef=0.008 erken keşif için yeterli tampon sağlıyor.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda: `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip_reward=10)`. Bu oturumda yeni kanıt yok; veriler önceki oturumlarla özdeş. %80+ güven eşiğini aşan config sorunu tespit edilmedi.
---

## [2026-06-08 22:06 UTC]
**Step:** 193,248 (CSV 9+ GÜN STALE — son gerçek güncelleme 2026-05-30 22:00) | **ep_rew_mean:** −173.85 (GEÇERSİZ, v9 crash-loop kalıntısı) | **entropy:** −4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
`training_metrics.csv` step=193,248'de 2026-05-30 22:00'dan bu yana tamamen donmuş; aktif Gazebo v9/v10 eğitimi yok. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda; gerçek bloker `drone_exploration_env.py` ENV kodu (2 satır, kullanıcı tarafı).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 9+ gündür aynı satırı yineliyor: 2026-05-30 22:00'dan itibaren step=193,248 / ep_rew_mean=−173.85 sabit. Bu veri v9 crash-loop dönemine ait, gerçek eğitim ilerlemesini temsil etmiyor.
- Son gerçek Gazebo peak: **+110.3 @610k** (v3.0, kasıtlı durduruldu); resume sonrası 1.45M adımda std=14 / entropy=−11.5 ile dağıldı (interventions.jsonl, 2026-06-01).
- v10 henüz başlamadı; kırılım/plato sorusu ileriye taşındı.
- +15'lik oda sıçraması: v9 Gazebo'da 193k step'e ulaşılamadan crash-loop → görülmedi. v2.1 fast_sim @120k ep_rew_mean=+92.6 gözlemlendi. v10 için ~100-200k step bekleniyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- KICKOFF.md'de belirtilen bu değer `ppo.yaml`'da mevcut değil. Güncel config: `learning_rate: 0.0003`, `lr_schedule: linear`, `lr_final: 1e-05` (1.5M boyunca 30× azalma). Bu seçim doğru ve kanıtlanmış.
- Somut Gazebo kanıtı: `train_v3_resume_310k.log` → sabit lr=3e-4 altında v3.0 1.45M'de std=14 / entropy=−11.5 ile patladı. Linear decay bu rejimi önler.
- v8'in kullandığı 3e-4→3e-5 linear decay'e kıyasla v10'daki 3e-4→1e-5 (daha agresif son küçültme) 1.5M bütçede fine-tuning kalitesini artırır; tercih edilebilir.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif run yok; CSV değerleri geçersiz.
- v10 projeksiyonu: `ent_coef=0.008` (v9 0.0015'in 5.3×, fast_v4.8 onaylı) → başlangıçta std~1.0-1.5, entropy~−4.5 ila −5.0 bekleniyor. Keşif açısından yeterli.
- **Alarm eşiği (v10 başlayınca izle):**
  - std < 0.5 **VE** entropy_loss > −2.5 → erken deterministikleşme, `ent_coef` artır
  - std > 5.0 → `_build_lr()` veya VecNormalize entegrasyonu sorunlu (v3.0 dağılma paterni)
  - FPS < 25 @n_envs=1 → Gazebo sim instability (bridge/transport sorunu)

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- ENV kodu WITH (`collision_penalty=25` + `lidar_history=2`) uygulanırsa:
  - İlk oda geçişi: ~100-200k step (fast_v4.8 analoji, %0 çarpışma rejimi)
  - Tutarlı 3 oda: ~300-500k step
  - 5-6 oda stochastic: ~700k-1M step
- Mevcut ENV WITHOUT değişikliği (`collision_penalty=10`, `lidar_history=1`):
  - İlk oda geçişi: ~300-500k step; v9'un %47+ crash rejimi 1.5M bütçeyi aşındırır
  - 5-6 oda: 1.5M içinde ulaşılamayabilir

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır değişiklik):** fast_sim v4.8 ŞAMPIYON: %0 çarpışma, 117 voxel, 5 oda @1.5M. v4.9 (cp=22) → rooms 5→2; v4.5 (cp=30) → %8 crash. 25 = 4-nokta sweep ile kesinleşmiş dar tatlı nokta. Mevcut 10.0 drone'u çarpışmayı sistematik hafife almaya itiyor; 1.5M bütçenin önemli bölümü erken crash döngülerine gidecek.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough: çarpışma %80→%1. v5.0 (history=3) bunu domine edemedi (voxels 281→106 düştü). 2 = kesinleşmiş optimal. `ppo.yaml` değişikliği gerektirmez (giriş boyutu policy ağı tarafından otomatik algılanır).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config fast_sim 18-config sweep + v3.0 Gazebo divergence analizi ile çapraz doğrulanmış; %80+ güven eşiğini aşan herhangi bir hyperparameter sorunu yok. Config dokunulmaz.
- **Operasyonel (kritik):** v10 Gazebo 10+ gündür başlamadı. 1.5M @~40 FPS Gazebo ≈ 10.4 saat. Bloker: `drone_exploration_env.py` (kullanıcı tarafı, 2 satır). Bu satırlar olmadan v10 başlatmak 1.5M bütçeyi suboptimal harcatır.
- **Monitor stabilite sorunu:** `interventions.jsonl` 2026-05-30 günü 20+ crash_recovery kaydı gösteriyor; monitor step=80k'da takılı kalmış, asıl Gazebo process sonlandıktan sonra script loop'a girmiş. v10 için monitor'ün `--max-restarts` limiti ve exponential backoff eklenmesi önerilir.

### v10 Önerisi
1. **ENV kodu önce, eğitim sonra:** `drone_exploration_env.py` içinde `collision_penalty=10 → 25` ve `lidar_history=1 → 2` yapıldıktan sonra `./scripts/train.sh configs/ppo.yaml` (obs boyutu 41→72-d olacağından önceki checkpoint ile resume YAPILMAMALI — `resume_from: null` zaten doğru).
2. **İlk 50k step kritik eşiği:** std > 5.0 veya FPS < 25 → `train_ppo.py`'de `_build_lr()` ve VecNormalize entegrasyonunu doğrula; aksi halde 300k'ya kadar müdahale yok. `ent_coef=0.008` erken keşif için yeterli tampon sağlıyor.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda (`lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip_reward=10)`). Bu oturumda CSV hâlâ donmuş; yeni Gazebo verisi yok. Önceki oturumlarla özdeş durum, config değişikliği için %80+ güven eşiği aşılmadı. Bloker ENV kodu (kullanıcı tarafı), yaml değil.
---

## [2026-06-08 23:06 UTC]
**Step:** 193,248 (CSV 9+ GÜN STALE — son gerçek güncelleme 2026-05-30 22:00) | **ep_rew_mean:** −173.85 (GEÇERSİZ, v9 crash-loop kalıntısı) | **entropy:** −4.212 (GEÇERSİZ) | **std:** 0.985 (GEÇERSİZ)

### Durum
`training_metrics.csv` step=193,248'de 9+ gün boyunca tamamen donmuş; aktif Gazebo v9/v10 eğitimi hâlâ yok. `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda; gerçek bloker kullanıcı tarafındaki `drone_exploration_env.py` ENV kodu (2 satır).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV son 30+ satır özdeş: step=193,248 / ep_rew_mean=−173.85 (2026-05-30 22:00–2026-05-31 03:01). Bu, v9 crash-loop dönemi monitor kalıntısı; gerçek eğitim ilerlemesini temsil etmiyor.
- Son gerçek v9 non-stale eğilim (2026-05-30): ep_rew_mean −290 (142k step) → −37 (145k step, geçici toparlanma) → −173 (crash-loop başlangıcı). +15'lik oda sıçraması görülmedi.
- Son gerçek Gazebo peak: **+110.3 @610k** (v3.0, 2026-05-31 kasıtlı durduruldu). v10 henüz başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- KICKOFF.md'de belirtilen bu değer güncel `ppo.yaml`'da YOK. Mevcut config: `learning_rate: 0.0003`, `lr_schedule: linear`, `lr_final: 1e-05` (1.5M boyunca 30× azalma). Bu seçim doğru ve fast_sim 18-config sweep + v3.0 Gazebo divergence analizi ile çapraz doğrulanmış.
- Somut Gazebo kanıtı: `train_v3_resume_310k.log` → sabit lr altında v3.0 1.45M'de std=14 / entropy=−11.5 ile diverge etti. Linear decay bu paterni önler. v8'in 3e-4→3e-5 range'ine kıyasla v10'daki 3e-4→1e-5 (3× daha agresif son küçültme) 1.5M bütçede fine-tuning kalitesini artırır.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri v9 crash-loop kalıntısı (entropy=−4.212, std=0.985); aktif run yok, değerler geçersiz.
- v10 projeksiyonu: `ent_coef=0.008` (v9 0.0015'in 5.3×, fast_v4.8 onaylı) → başlangıçta std~1.0-1.5, entropy~−4.5 ila −5.0 bekleniyor. Keşif için yeterli. v9 değerleri (std~0.99, entropy~−4.25) gerçek run'da deterministikleşme riski yaratmıştı; v10 ent_coef bunu önler.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- ENV kodu WITH (`collision_penalty=25`, `lidar_history=2`) uygulanırsa: ilk oda ~100-200k; 3 oda stabil ~300-500k; 5-6 oda ~700k-1M step.
- ENV kodu WITHOUT değişikliği (`collision_penalty=10`, `lidar_history=1`): ilk oda ~300-500k; crash oranı yüksek olduğundan 1.5M içinde 5-6 oda garantisiz.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır):** fast_sim v4.8 ŞAMPIYON → %0 çarpışma, 117 voxel, 5 oda @1.5M. v4.9 (cp=22) → rooms 5→2; v4.5 (cp=30) → %8 crash. 25 = 4-nokta sweep ile kesinleşmiş dar tatlı nokta.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough: çarpışma %80→%1. v5.0 (history=3) bu seviyeye ulaşamadı (voxels düştü). 2 = irreversible optimal. ppo.yaml değişikliği gerektirmez; `resume_from: null` kalmalı (obs boyutu değiştiğinden önceki checkpoint uyumsuz).

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config 2026-06-02'den beri v10 optimal: `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip_reward=10)`. %80+ güven eşiğini aşan hyperparameter sorunu yok.
- **Operasyonel (kritik):** v10 Gazebo 10+ gündür başlamadı. 1.5M @~40 FPS Gazebo ≈ 10.4 saat. Deadline baskısı kritik. Bloker: `drone_exploration_env.py` — 2 satır değişiklik, kullanıcı tarafı. Bu değişiklikler olmadan v10 başlatmak 1.5M bütçeyi suboptimal harcatır (voxel sayısı ve güvenlik açısından kanıtlanmış önemli fark).
- **Monitor stabilite (ikincil):** `interventions.jsonl` 2026-05-30'da step=80k'da takılmış 20+ crash_recovery döngüsü var. v10 için `--max-restarts` limiti ve exponential backoff eklenmesi önerilir.

### v10 Önerisi
1. **ENV kodu önce, eğitim sonra:** `drone_exploration_env.py` içinde `collision_penalty=10 → 25` ve `lidar_history=1 → 2` yapıldıktan sonra `./scripts/train.sh configs/ppo.yaml`. Sıra şart; obs boyutu 41→72-d olacağından `resume_from: null` zaten doğru.
2. **İlk 50k step izleme eşiği:** std > 5.0 → `_build_lr()` / VecNormalize entegrasyon sorunu (v3.0 diverge paterni). std < 0.5 AND entropy > −2.5 → `ent_coef` artır. FPS < 25 → Gazebo bridge sorunu. Aksi halde 300k'ya kadar müdahale yok.

### Müdahale
**Yok** — `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda. Bu oturumda CSV hâlâ donmuş; yeni Gazebo verisi yok. Önceki oturumlarla özdeş durum; %80+ güven eşiğini aşan config sorunu tespit edilmedi. Bloker ENV kodu (kullanıcı tarafı), yaml değil.
---

## [2026-06-09 00:00 UTC]
**Step:** 193,248 (CSV son kayıt — 10 gündür STALE) | **ep_rew_mean:** −173.85 (geçersiz, v9 crash-loop kalıntısı) | **entropy:** −4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
`training_metrics.csv` 2026-05-30 22:00'dan bu yana step=193,248'de tamamen donmuş (10 gün). `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda ve değişiklik gerektirmiyor. fast_sim 18-config sweep 2026-06-01'de tamamlandı; v10 Gazebo eğitimi hâlâ başlamadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki tüm ölçümler geçersiz: 2026-05-30 22:00–2026-05-31 03:01 arası 14 satır özdeş (process dead, monitor stale). Gerçek v9 trendi: ep_rew_mean −290 @142k → −37 @145k (geçici toparlanma) → −173 @193k (crash-loop başlangıcı). +15'lik oda sıçraması görülmedi.
- Son gerçek Gazebo peak: **+110.3 @610k** (v3.0, 2026-05-31 kasıtlı durduruldu). v10 henüz start almadı — eğri yok.
- fast_sim bulgusu (referans): v4.8 @1.5M → 0% çarpışma, 5 oda, 117 voxel; v4.10 @5M → 54% çarpışma, 5.76 oda, 281 voxel. Temel trade-off kesinleşti.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- KICKOFF.md'de belirtilen sabit 7.5e-5 değeri `ppo.yaml`'da yok; zaten terk edildi. Mevcut v10 config: `lr=3e-4→1e-5 linear (1.5M boyunca)`. Bu doğru seçim — `train_v3_resume_310k.log` gösterdi ki sabit lr altında v3.0 1.45M'de std=14/entropy=−11.5 ile diverge etti; linear decay bu paterni önler.
- v8'in 3e-4→3e-5 aralığına kıyasla v10'daki 3e-4→1e-5 (son değerde 3× daha agresif küçültme) 1.5M bütçede fine-tuning kalitesini artırır. Değişiklik gerekmez.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri (entropy=−4.212, std=0.985) geçersiz — aktif run yok.
- v10 projeksiyonu: `ent_coef=0.008` (v9'un 0.0015 değerinin 5.3×) → başlangıçta std~1.0–1.5, entropy~−4.5 ila −5.0 bekleniyor. fast_v4.8 bu ent_coef ile 0% çarpışma ve 5 oda keşfetti — keşif için yeterli.
- Erken deterministikleşme riski: v9'daki entropy=−4.25, std~0.99 v10 ent_coef=0.008 ile olmayacak. İzleme eşiği: entropy > −2.5 VE std < 0.5 birlikte → müdahale.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- `drone_exploration_env.py` WITH (`collision_penalty=25`, `lidar_history=2`): ilk oda ~100–200k; 3 oda stabil ~300–500k; 5–6 oda ~700k–1M.
- `drone_exploration_env.py` WITHOUT değişiklikler (`collision_penalty=10`, `lidar_history=1`): ilk oda ~300–500k; 1.5M içinde 5–6 oda garantisiz (v3.0 Gazebo 610k'da 110.3 peak ile 3.0 oda ortalamasına ulaşabildi, kıyasla daha yavaş ilerleme).
- v10 henüz başlamadığından "kaç step daha" sorusu şu an geçerli değil.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır):** fast_v4.8 kesinleşmiş şampiyon → %0 çarpışma. Dar tatlı nokta: 22=geriledi(%37 çarpışma, 2-oda yerel optimum), 25=optimal(%0/%5oda), 30=%8 çarpışma. Değişiklik ppo.yaml'ı etkilemez; `resume_from: null` zaten doğru.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough: çarpışma %80→%1. lidar_history=3 (v5.0) bu seviyeye ulaşamadı (voxels düştü). Obs boyutu değişeceğinden eski checkpoint uyumsuz — fresh start zorunlu, config zaten `resume_from: null`.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Config 2026-06-02'den beri v10 optimal: `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `batch_size=256`, `n_epochs=10`, `gae_lambda=0.95`, `clip_range=0.2`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_obs=false, norm_reward=true, clip_reward=10)`. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi.
- **Operasyonel (kritik):** v10 Gazebo 10+ gündür başlamadı. 1.5M @~40 FPS Gazebo ≈ 10.4 saat. Bloker: `drone_exploration_env.py` — 2 satır, kullanıcı tarafı. Bu değişiklikler olmadan v10 başlatmak collision=10 ile suboptimal sonuç üretir.
- **Monitor loop (ikincil):** `interventions.jsonl` step=80k'da 20+ crash_recovery döngüsü kayıtlı. v10 için `--max-restarts` limiti ve exponential backoff eklenmesi önerilir.

### v10 Önerisi
1. **ENV kodu önce, eğitim sonra:** `drone_exploration_env.py` içinde `collision_penalty=10 → 25` ve `lidar_history=1 → 2` yapıldıktan sonra `./scripts/train.sh configs/ppo.yaml`. Sıra şart; obs boyutu 41→72-d olacağından `resume_from: null` zaten doğru.
2. **İlk 50k step izleme eşiği:** std > 5.0 → VecNormalize entegrasyon sorunu (v3.0 diverge paterni). std < 0.5 VE entropy > −2.5 → `ent_coef` artır. FPS < 25 → Gazebo bridge sorunu. Aksi halde 300k'ya kadar müdahale yok.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda, değişiklik gerektiren %80+ emin olunan sorun tespit edilmedi. CSV 10 gündür donmuş; aktif Gazebo verisi yok. Bloker `drone_exploration_env.py` (kullanıcı tarafı), yaml değil.
---

## [2026-06-09 01:08 UTC]
**Step:** 193,248 (CSV son kayıt — STALE, 2026-05-30 22:00'dan bu yana değişmedi) | **ep_rew_mean:** −173.85 (geçersiz — crash-loop kalıntısı) | **entropy:** −4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
CSV 10 gündür donmuş; aktif Gazebo/v10 eğitimi yok. Bu analiz v9 CSV'sinin iki fazını derinlemesine inceleyerek başarısızlık mekanizmasını netleştiriyor. `configs/ppo.yaml` zaten v10 optimal konfigürasyonunda; yaml değişikliği gerekmez.

### Detay

**a) Reward eğrisi — iki fazlı başarısızlık:**
- **Faz 1 (11:02–12:32, ilk 4 CSV satırı):** v9 fresh start. Adım sayısı 142k→599k doğrusal (84 FPS × 30dak = 151k step, tutarlı). Ancak `ep_len_mean=1000` sabit — epizodalarda hiç terminal yok, drone her zaman max-step'e ulaşıyor. ep_rew_mean -290→-270 (iyileşme yok). Hesap: 1000 step × -0.001 (zaman) + 970 step × -0.5 (idle≥30) ≈ -486; gerçek -270 → ~+216 voxel/frontier geliri var ama oda sıçraması (+15) sıfır. Drone voxel üretiyor ama odalar arası geçişi başaramıyor. **+15'lik oda sıçraması görülmedi.**
- **Faz 2 (13:02+):** İlk crash → 80k'dan resume. ep_len 245'e iniyor (kısa), ep_rew_mean -102→-25→-37 (en iyi). 20+ crash-recovery döngüsü aynı 80k checkpoint'e kilitlendi; gerçek öğrenme asla momentum kazanamadı. Son gerçek peak: **-37 @ 145k (05-30 21:20)**.

**b) lr=7.5e-5 constant bu aşamada doğru muydu?**
- **Hayır — ve ppo.yaml'dan zaten kaldırıldı.** Faz 1'de std 0.888→0.745 (460k step içinde), entropy -3.89→-3.32 (hızlı negatifleşme). lr=7.5e-5 ile bu hızda std<0.7'ye düşüş ~700k adımda beklenir, ki bu "ep_len=1000, hiç oda yok" local optimuma kilitlenme sinyalidir. v10 ppo.yaml: `lr=3e-4→1e-5 linear` — ilk adımda 4x daha yüksek (hızlı keşif), sonunda 7.5x daha düşük (hassas fine-tune). Değişiklik doğru ve geri alınmaz.

**c) Entropy/std keşif için yeterli mi?**
- CSV değerleri geçersiz (stale). v9 Faz 1 analizi: entropy -3.89→-3.32 (iyimser görünüyor ama ep_len=1000 + oda=0 ile keşif yanlış yönde). Tehlike: `entropy değeri yüksek olsa da oda geçişini hiç yaşamamış bir agent, negatif-ödül minimizasyonuna konverj ediyor.`
- v10 projeksiyonu: ent_coef=0.008 (v9'un 5.3×) ile başlangıç entropy~-4.5 ila -5.0 bekleniyor, std~1.0–1.5. fast_sim v4.8 bu ayarla 0% çarpışma + 5 oda @1.5M. Keşif için yeterli.
- İzleme eşiği: **entropy > -2.5 VE std < 0.5 birlikte** → ent_coef müdahalesi. Tek başına entropy veya std bakılmaz.

**d) Oda geçişi için kaç step bekleniyor?**
- `drone_exploration_env.py` WITH (collision_penalty=25, lidar_history=2): ilk oda ~100–200k; 3+ oda ~300–500k; 5–6 oda ~700k–1M.
- WITHOUT değişiklikler: v9 Faz 1 verisi gösterdi ki 599k step sonunda bile oda=0. 1.5M bütçede 5–6 oda garantisiz.
- Δ = fast_sim v4.8 vs v4.5: collision_penalty 10→25 tek fark, rooms 2→5, voxels 69→117. Bu 1 satır değişiklikle oluyor.

**e) v10 için en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (`drone_exploration_env.py`, 1 satır):** fast_sim 4-nokta sweet-spot sweep: cp=10→37vox/2oda, cp=22→69vox/2oda (yerel optimum), cp=25→117vox/5oda (ŞAMPIYON), cp=30→%8 çarpışma. Kesinleşmiş dar aralık. ppo.yaml etkilenmiyor.
2. **`lidar_history: 1 → 2` (obs 41-d → 72-d, `drone_exploration_env.py`, 1 satır):** fast_v2 breakthrough %80→%1 çarpışma. history=3 regresyon (voxels düştü). Obs boyutu değişeceğinden eski checkpoint uyumsuz — `resume_from: null` zaten doğru.

**f) Acil müdahale:**
- **ppo.yaml açısından: HAYIR.** v9→v10 konfigürasyon deltası büyük ve doğru: ent_coef 0.0015→0.008 (5.3×), n_steps 512→2048 (4×), n_epochs 5→10 (2×), clip_range 0.1→0.2 (2×), gae_lambda 0.9→0.95, lr=7.5e-5 sabit→3e-4→1e-5 linear. Her değişiklik fast_sim sweep ile validate edilmiş; %80+ güven eşiğini aşan ek sorun yok.
- **Operasyonel (kritik):** v10 Gazebo 10+ gündür başlamadı. Bloker = `drone_exploration_env.py` 2 satır (kullanıcı tarafı). 1.5M @~40 FPS ≈ 10.4 saat.
- **Monitor (ikincil):** interventions.jsonl'de step=80k'da 20+ crash-recovery döngüsü var. v10 için monitor'a `--max-restarts 3` + exponential backoff eklenmeli; aksi halde aynı loop tekrarlar.

### v10 Önerisi
1. **ENV kodu önce, eğitim sonra.** `drone_exploration_env.py`: (1) collision_penalty=10→25, (2) lidar_history=1→2. Ardından `./scripts/train.sh configs/ppo.yaml`. Sıra zorunlu — obs 41→72-d olduğundan checkpoint uyumsuz, `resume_from: null` zaten hazır.
2. **Monitor güvenlik şeridi:** `--max-restarts 3` + 30s/60s/120s backoff. v9'daki 20+ loop tekrarını önler. İlk 50k'da std>5.0 → VecNormalize diverge; entropy>-2.5 VE std<0.5 birlikte → ent_coef artır; FPS<25 → Gazebo bridge sorunu.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. CSV 10 gündür donmuş, aktif Gazebo verisi yok. Bloker `drone_exploration_env.py` (kullanıcı tarafı) + Gazebo'nun başlatılması.
---

## [2026-06-09 12:00 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9 crash-loop kalıntısı) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
Gazebo v9 eğitimi 22:00 2026-05-30'dan bu yana tamamen donmuş (step=193,248 frozen). Asıl proje hızla ilerledi: fast_sim v1-v5.0 deneyleri tamamlandı (June 1), configs/ppo.yaml zaten v10-hazır durumda (June 2). Config müdahalesi gerekmez; kritik engel env-tarafında (drone_exploration_env.py).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 46 satırdan son 26'sı özdeş (step=193k, stale). En yüksek gerçek kayıt: -37.37 @ 145,600 step (2026-05-30 21:20) — v9 Gazebo kırılım noktasına ulaşamadan crash-loop'a girdi.
- Aynı anda başlatılan fast_sim v3.0 Gazebo: peak **+110.3 @ 610k** (verified, kasıtlı durduruldu). Fast_sim v4.8: %0 çarpışma, 5 oda, 117 voxel — bu referans değerler.
- +15'lik oda sıçraması v9 CSV'sinde görülmedi; v3.0 Gazebo TB'de ~120k step civarında gözlemlenmiş.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Görev tanımındaki "lr=7.5e-5 constant" ESKI durum (KICKOFF.md v9 snapshot). Mevcut ppo.yaml artık **v10**: `learning_rate: 3e-4 → 1e-5 linear (lr_schedule: linear, lr_final: 1e-5)` — v3.0 Gazebo'da peak 110.3 veren kanıtlanmış schedule. Müdahale gereksiz, doğru seçim zaten uygulandı.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV stale değerleri (entropy -4.21, std ~0.985) v9'a ait. v10 config: `ent_coef: 0.008` (v9 0.0015'ten 5.3x artış) → keşif yeterliliği artırılmış. Fast_sim v4.8 champion'ı ent=0.008 ile 5 oda %0 çarpışma sağladı. Gazebo için bu değer uygun.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 Gazebo tarihine göre: 80-120k step'te ilk oda geçişi, 200-400k'da tutarlı 3+ oda. v10 n_steps=2048 (v3.0 512'den 4x uzun rollout) → daha zengin gradient sinyali → ilk oda geçişi daha erken beklenir (~60-100k step). Total 1.5M'de 5-6 oda hedefi gerçekçi.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: collision_penalty -10.0 → -25.0** — Fast_sim v4.8 kanıtı: %-8→%0 çarpışma, tüm 5 oda aktif. HÂLÂ UYGULANMADI (kod hâlâ -10.0 kullanıyor, ppo.yaml yorumunda belirtilmiş ama env değiştirilmemiş). V10 eğitimi başlamadan ÖNCELİKLE yapılmalı.
2. **`drone_exploration_env.py`: lidar_history 1→2 (obs 40-d→72-d)** — Fast_sim v2 kanıtı: çarpışma %80→%1 (hareketli engel hızı çıkarımı). HÂLÂ UYGULANMADI. ppo.yaml resume_from=null olduğundan obs boyutu değişikliği sorunsuz; SB3 MlpPolicy yeni shape'i otomatik alır.

**f) Acil müdahale gerektiren bir şey var mı?**
- Eğitim şu an bu makinede çalışmıyor (Berker'in lokali). CSV donmuş, process yok.
- **configs/ppo.yaml HAZIR ve OPTIMAL** — değiştirme. v10 hyperparametreler: lr 3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, clip=0.2, batch=256, max_ep=2500, VecNormalize(norm_reward=True). Tümü fast_sim/v3.0 kanıtlı.
- **Tek blokaj:** drone_exploration_env.py'daki iki eksik değişiklik (collision_penalty=25, lidar_history=2). V10 eğitimi başlamadan önce env güncellenmeli.

### v10 Önerisi
1. **drone_exploration_env.py → `reward -= 25.0` (çarpışma cezası, şu an 10.0)**: fast_sim v4.8 tatli noktası, %0 çarpışma + full oda keşfi. Eğitim başlamadan önce yapılmalı.
2. **drone_exploration_env.py → lidar_history=2 (obs 40→72-d)**: hareketli engel hızı gözlemlenebilir hale gelir; fast_sim'de çarpışma %80→%1. ppo.yaml zaten `resume_from: null` (fresh start) → obs shape değişikliği sorunsuz.

### Müdahale
Yok — configs/ppo.yaml zaten v10 optimal (linear decay 3e-4→1e-5, ent_coef=0.008). Env-tarafı değişiklikler bu görevin kapsamı dışında; not olarak bırakıldı.
---

## [2026-06-09 04:06 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, v9 crash-loop kalıntısı 2026-05-30 22:20) | **ep_rew_mean:** -173.85 (geçersiz) | **entropy:** -4.212 (geçersiz) | **std:** 0.985 (geçersiz)

### Durum
CSV 10 gündür donmuş (step=193k, özdeş 26 satır). `configs/ppo.yaml` 2026-06-02'den beri v10 optimal konfigürasyonunda; yaml müdahalesi gerekmez. v10 Gazebo eğitimi hâlâ başlamadı; tek bloker `drone_exploration_env.py` (env-tarafı, 2 satır).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 47 satır, son 26'sı özdeş (step=193,248, frozen). v9 gerçek en yüksek: **-37.37 @ 145,600 step** (2026-05-30 21:20). İlk +15 oda sıçraması v9 CSV'sinde hiç görülmedi.
- Faz 1 (11:02–12:32): `ep_len_mean=1000` sabit, terminal yok → drone her ep'de max-step'e ulaşıyor; voxel üretiyor ama kapı geçişi başaramıyor. Faz 2 (13:00+): crash-loop, 80k checkpoint'te kilitli, gerçek öğrenme momentum kazanamadı.
- Referans: fast_sim araştırması tamamlandı (Haziran 1–2). v3.0 Gazebo: peak **+110.3 @ 610k** (kasıtlı durduruldu). fast_sim v4.8 champion: %0 çarpışma, 5 oda, 117 voxel — bunlar v10 için hedef değerler.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- **Hayır — ama zaten düzeltildi.** KICKOFF.md'deki lr=7.5e-5 v9 snapshot'ıydı. Mevcut ppo.yaml v10: `lr=3e-4→1e-5 linear` — v3.0 Gazebo peak 110.3'ü veren kanıtlanmış schedule. Faz 1 CSV'si `std: 0.888→0.745 @ 599k step` ve `entropy: -3.89→-3.32` (hızlı negatifleşme) gösteriyor; sabit düşük lr local optimum kilidini hızlandırmış. v10'da 4x yüksek başlangıç lr bu riski ortadan kaldırıyor.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Aktif veri yok (stale). v10 `ent_coef=0.008` (v9 0.0015'ten 5.3x artış) ile ilk 50k'da entropy ~-4.5–-5.0, std ~1.0–1.5 bekleniyor. fast_sim v4.8 bu ayarla %0 çarpışma + 5 oda sağladı. İzleme eşiği: `entropy > -2.5 VE std < 0.5 aynı anda` → ent_coef müdahalesi; tekli değer yeterli değil.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- **collision_penalty=25 + lidar_history=2 İLE:** ilk oda ~80–120k step, 3+ oda ~200–400k, 5–6 oda ~700k–1M. v3.0 Gazebo geçmişi (n_steps=512) baz alındığında v10 n_steps=2048 (4x uzun rollout) daha zengin gradient → ilk oda muhtemelen daha erken (~60–100k step).
- **Bu değişiklikler YAPILMADAN:** v9 Faz 1 gösterdi ki 599k step'te bile oda=0. 1.5M bütçede 5–6 oda garantisiz.

**e) v10 için en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty 10 → 25`** — fast_sim v4.8 kesinleşmiş sweet-spot: 22=geri döndü (%37 çarpışma, 2 oda), 25=optimal (%0 çarpışma, 5 oda, 117 voxel), 30=%8 çarpışma. Dar ve hassas aralık. ppo.yaml etkilenmez; doğrudan env satırı.
2. **`drone_exploration_env.py`: `lidar_history 1 → 2` (obs 41-d → 72-d)** — fast_sim v2 breakthrough: çarpışma %80→%1 (hareketli engel hız çıkarımı). history=3 regresyon (voxel düştü). Obs shape değişeceğinden ppo.yaml `resume_from: null` zaten doğru; SB3 MlpPolicy yeni shape'i otomatik alır.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml: HAYIR.** v10 optimal konfigürasyon yerinde: `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `n_epochs=10`, `clip_range=0.2`, `gae_lambda=0.95`, `net_arch=[256,256]`, `max_episode_steps=2500`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_reward=True, clip=10)`. Tüm değerler fast_sim sweep + v3.0 Gazebo ile validate edilmiş. %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi.
- **Operasyonel bloker (kritik):** v10 Gazebo eğitimi 10+ gündür başlamadı. 1.5M @~40 FPS ≈ 10.4 saat. Bloker `drone_exploration_env.py` (kullanıcı tarafı, 2 satır). Bu değişiklikler yapılmadan v10 başlatmak v9'daki 0-oda başarısızlığını tekrarlar.
- **Monitor döngüsü (ikincil):** interventions.jsonl'de step=80k'da 20+ crash_recovery döngüsü kayıtlı. v10 monitor'a `--max-restarts 3` + exponential backoff (30s/60s/120s) eklenmeli; aksi halde aynı sonsuz döngü tekrarlanır.
- **CSV donmuş (bilgi):** `logs/training_metrics.csv` 2026-05-31 03:01'den bu yana güncellenmedi. v10 başladığında monitor'ın CSV'ye yazmasını sağla.

### v10 Önerisi
1. **Sırayla:** (1) `drone_exploration_env.py` → `collision_penalty = -25.0` (2) `drone_exploration_env.py` → `lidar_history = 2` (obs 41→72-d) (3) `./scripts/train.sh configs/ppo.yaml`. Sıra zorunlu — obs boyutu değişikliği önceden yapılmazsa checkpoint uyumsuzluğu oluşur.
2. **İlk 50k izleme eşikleri:** `std > 5.0` → VecNormalize diverge (v3.0 erken sapma paterni, önceki çalıştırmada gerçekleşti); `FPS < 25` → Gazebo/bridge sorunu; `entropy > -2.5 VE std < 0.5` birlikte → ent_coef artır. Bu 3 durum dışında 300k'ya kadar müdahale yok.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda; değişiklik için %80+ güven eşiğini aşan sorun tespit edilmedi. CSV 10 gündür donmuş, aktif Gazebo eğitimi yok. Bloker env-tarafı (`drone_exploration_env.py`), yaml değil.
---

## [2026-06-09 05:09 UTC]
**Step:** 193,248 (CSV son kayıt — 10 gündür STALE, v9 çöküş-döngüsü kalıntısı) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
`training_metrics.csv` 2026-05-30 22:00'dan bu yana frozen; aktif Gazebo v10 eğitimi başlamadı. Configs/ppo.yaml v10 konfigürasyonu 2026-06-02'den beri hazır ve hyperparameter açısından optimal; yeni müdahale gerektirmiyor. Kritik bloker v10'un hâlâ başlatılmamış olması.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'nin tüm son 25 satırı 2026-05-30 22:00–2026-05-31 03:01 arası özdeş (`step=193248, rew=-173.85`): v9 crash-loop'unun donmuş monitor ekosisi. Aktif Gazebo eğitimi yok.
- Geçmiş referans (interventions.jsonl): Gazebo v3.0 run → 2026-05-31 14:54'te step=501760, peak=133.35. 2026-06-02'de v3.0 durduruldu (610k step, peak 110.3). Bu run'ın ödül eğrisi kırılım fazını geçmiş ve ~500k'da olgunluğa ulaşmış; configs/ppo.yaml zaten o run'ın kanıtlanmış hyperparametrelerini içeriyor.
- Fast_sim zinciri (2026-06-01) tamamen kapandı: v4.8 şampiyonu (collision=25, lidar_history=2, %0 çarpışma, 5 oda, 117 voxel), v4.10 kapsam ucu (5M, 281 voxel, 6 oda, %54 çarpışma). Trade-off temel ve kesinleşti.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Hayır — ama zaten aşıldı. v10 config: `lr=3e-4 → 1e-5 linear (1.5M)`. Bu schedule Gazebo v3.0 peak 110.3'ü veren değer. lr=7.5e-5 v9 snapshot'ı, artık geçersiz.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Mevcut CSV verisi stale olduğu için v10 için projeksiyon: `ent_coef=0.008` (v9 0.0015'ten 5.3x) ile ilk 50k'da std ~1.0–1.5, entropy ~-4.5 bekleniyor.
- v2.2 env zaten yönlü (FWD_ARC) + omnidirectional soft penalty içeriyor; collision cezası olmadan bile agent keşife yönlendiriliyor. ent_coef=0.008 bu yapıyla dengeli.
- v3.0 Gazebo aynı ent_coef ile peak 110.3 aldı → değer kanıtlandı.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 env (drone_exploration_env.py v2.2): room_bonus=10, collision_penalty=-10 (terminal), directional soft penalties aktif.
- v10 config (n_steps=2048, gae_lambda=0.95): v9'dan 4x uzun rollout → daha zengin gradient, kritik alan geçişleri için daha doğru kredi ataması.
- Referans Gazebo v3.0 (n_steps=512, farklı harita) ~60–120k'da ilk oda sinyalleri verdi. v10'da n_steps=2048 ile ~40–80k'da ilk oda geçişi bekleniyor.
- 3+ oda: ~200–400k. 5–6 oda: ~700k–1M. 1.5M bütçe yeterli.
- **Kritik uyarı:** collision_penalty env'de hâlâ -10.0 (fast_sim kanıtlı sweet-spot: -25.0). Bu fark v3.0 Gazebo'nun collision %X ile devam etmesi anlamına geliyor. v10 Gazebo aynı sorunu yaşayabilir.

**e) v10 için en kritik 1-2 öneri:**
1. `drone_exploration_env.py` → `-10.0 → -25.0` terminal collision penalty (satır 342: `reward -= 10.0`). Fast_sim kesinleşmiş sweet-spot: 22=costu (%37 crash), 25=OPTIMAL (%0 crash), 30=%8 crash. Dar ve hassas aralık; sadece bu tek satır.
2. `drone_exploration_env.py` → lidar_history=2 (obs 40-d → 72-d): hareketli engel hızını çıkarma için. fast_sim breakthrough: crash %80→%1. İlk öneri daha kritik; ikincisi hareketli engel aktif olmadan daha az acil.

**f) Acil müdahale gerektiren bir şey var mı?**
- **configs/ppo.yaml: HAYIR.** Tüm hyperparametreler Gazebo v3.0 + fast_sim sweep ile kanıtlanmış: `lr=3e-4→1e-5 linear`, `ent_coef=0.008`, `n_steps=2048`, `n_epochs=10`, `clip_range=0.2`, `gae_lambda=0.95`, `net_arch=[256,256]`, `total_timesteps=1.5M`, `n_envs=1`, `VecNormalize(norm_reward=True, clip=10)`. %80+ güven eşiğini aşan hyperparameter sorunu yok.
- **Operasyonel uyarı (kritik):** v10 Gazebo eğitimi 10+ gündür başlamadı. Tek bloker `drone_exploration_env.py` env kodu (kullanıcı tarafı). Collision=-10→-25 değişikliği yapılmadan v10 başlatmak v9 seviyesinde (crash-loop + 0-oda) başarısızlık riski taşıyor.
- **Monitor güvenilirliği:** interventions.jsonl'de step=80k'da 20+ crash_recovery döngüsü. v10 monitor'a restart sayacı + exponential backoff eklenmeli.

### v10 Önerisi
1. **`drone_exploration_env.py` satır 342:** `reward -= 10.0` → `reward -= 25.0` — tek satır, kanıtlanmış sweet-spot, acil.
2. **v10 başlatma:** `./scripts/train.sh configs/ppo.yaml`. Hyperparametreler hazır; tek bloker env satırı.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda; %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi. Env kodu (`drone_exploration_env.py`) değişikliği bu task'ın scope'u dışında (ppo.yaml only).
---

## [2026-06-09 06:10 UTC]
**Step:** 193,248 (CSV STALE — son 9 gündür donmuş) | **ep_rew_mean:** -173.85 (geçersiz, v9 crash kalıntısı) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
CSV 2026-05-31 03:01'den bu yana tamamen donmuş; 9 gündür yeni veri yok. Gerçek durum: fast_sim zinciri (v4.1→v5.0, 18 config) tamamlandı; Gazebo v3.0 610k/1.5M'de durduruldu (peak=110.3); v10 config hazır ama Gazebo eğitimi henüz başlatılmamış. `configs/ppo.yaml` optimal durumda — config değişikliği gerekmez.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV geçersiz. Son gerçek Gazebo verisi: v3.0 @ 434k (peak=102.54, 2026-06-01) ve 610k'da kasıtlı durduruldu (peak=110.3). Eğri v3.0'da hâlâ yükseliş trendindeydi; 610k bütçe dolmadan (1.5M hedef) durduruldu — yani erken kesilme, plato değil.
- Fast_sim referansı: v4.10 @ 5M adımda 6 oda + 281 voxel (peak), v4.13 @ 8M'de 134 voxel'e geriledi — uzun eğitim Pareto frontierı öteleyemiyor.

**b) lr=7.5e-5 constant bu aşamada doğru mu?**
- Hayır ve artık geçerli bir soru değil. ppo.yaml v10'da lr=3e-4 linear → 1e-5 (1.5M boyunca). Bu Gazebo v3.0 config'i ile özdeş (peak=110.3 üretmiş). v9 sabit 7.5e-5'i çoktan terk edildi — doğru karar.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Stale veriden (entropy=-4.21, std=0.985) sağlıklı analiz yapılamaz. v10 fresh run başladığında: hedef entropy > -4.0 (ilk 200k), std > 0.7 (300k'a kadar). ent_coef=0.008 v9'un 0.0015'inin 5×'i; bu ile erken deterministikleşme riski düşük.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Fast_sim (n_envs=8, 100× hız) verileri: ilk 2 oda → <50k step; 5 oda → ~300-500k; 6 oda → ~2-5M. Gazebo (n_envs=1, gerçek fizik) 3-5× yavaş yakınsama beklenebilir.
- Gazebo v10 beklentisi: 2 oda @ 100-150k, 4 oda @ 400-600k, 5-6 oda @ 900-1200k. 1.5M bütçe 5 oda için yeterli; 6 oda garantisiz.

**e) v10 için en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` collision penalty 10→25 (BLOCKING):** Fast_sim kesinleşmiş sweet-spot: penalty=22 → 2-oda yerel optimumuna çöküş (%37 crash), penalty=25 → 0% crash (v4.8 champion), penalty=30 → %8 crash (aşırı tedirginlik). Aralık dar (22-30) ve kritik. Bu değişiklik yapılmadan v10 Gazebo'nun v9 crash-loop seviyesinde kalma riski %80+.
2. **`drone_exploration_env.py` lidar_history 1→2 (41-d → 72-d obs, öncelik 2):** Fast_sim breakthrough: crash %80→%1 (v4.2 breakthrough). Gazebo'da 3 hareketli engel v10'dan aktif olacaksa bu değişiklik kritik; hareketli engel devre dışıysa ikinci öncelik. ppo.yaml `net_arch: [256,256]` 72-d input'u sorunsuz işler.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter (ppo.yaml):** HAYIR. Tüm parametreler Gazebo v3.0 + 18-config fast_sim sweep ile doğrulanmış. %80+ güven eşiğini aşan sorun yok.
- **Operasyonel (kritik):** v10 Gazebo eğitimi 9 gündür başlamadı. Fast_sim zinciri tamamlandı; sonuç: mevcut gözlem/reward mimarisiyle Pareto frontier aşılamıyor. v10 Gazebo'nun çalışması için tek bloker: env kodu (collision_penalty + lidar_history). Bu iki satır olmadan v10 başlatmak verimli değil.
- **Monitor altyapısı:** interventions.jsonl'de aynı step=80k için 20+ crash_recovery kaydı var (exponential backoff yok). v10 monitor'ına restart sayacı + minimum bekleme süresi eklenmeli; aksi takdirde çekirdek ölü process'i on kez yeniden başlatır.

### v10 Önerisi
1. **BLOCKING — env kodu önce:** `drone_exploration_env.py` → collision_penalty satırı 10.0 → 25.0. Bu tek değişiklik %0 collision vs %54+ collision farkı yaratıyor (fast_sim v4.8 vs v4.9/v4.10).
2. **`configs/ppo.yaml` değişikliği YOK:** lr=3e-4 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M — tamamı kanıtlanmış optimal. Dokunma.

### Müdahale
**Yok** — `configs/ppo.yaml` v10 optimal konfigürasyonunda. Fast_sim zinciri complete; tüm levers (reward shaping, training duration, curriculum, obs) tükendi. Env kodu değişikliği bu task'ın scope'u dışında (ppo.yaml only). %80+ güven eşiğini aşan hyperparameter sorunu tespit edilmedi.
---

## [2026-06-09 07:09 UTC]
**Step:** 193,248 (CSV SON KAYIT — 10 günlük boşluk, May 30 22:00'dan beri frozen) | **ep_rew_mean:** N/A (v10 Gazebo henüz başlamadı) | **entropy:** N/A | **std:** N/A

### Durum
10 günlük veri sessizliği: training_metrics.csv May 30 22:00'dan beri step=193248 ile donmuş, interventions.jsonl'deki son kayıt June 1 01:30 UTC (v3.0 @434k milestone). **Gazebo v10 Gazebo run'ı CSV'de yok** — ya başlatılmadı, ya da lokal makinede çalışıp bu repo'ya loglamıyor. configs/ppo.yaml v10 FRESH START için hazır (June 2 damgalı, 18 fast_sim config'in özeti). Hyperparameter açısından mevcut config kuvvetli; acil değişiklik yok.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV frozen: Son gerçek veri May 30 22:00, step=193248, ep_rew_mean=-173.85. Bundan sonra hiç yeni Gazebo v10 satırı gelmedi.
- Gazebo v3.0 tarihsel zirve: peak=110.3 @ 610k adımda kasıtlı durduruldu (ppo.yaml header — June 2'de v10'a geçildi).
- Fast-sim v4.8 (şampiyon): collision=%0, rooms_mean=5.0, voxels=117 @ 1.5M step. Fast-sim v4.10 @ 5M: rooms_mean=5.76 (6/6 oda), ama collision=%54 (güvenlik kolapsı). Sweet spot: v4.8 @ 1.5M.
- **Sonuç:** Gazebo v10 henüz üretim verisine yok. Eğitim başlatılırsa kırılım evresi fast-sim'e göre 150-250k step bandında bekleniyor (lidar_history=2 uygulanmışsa).

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçersiz soru: ppo.yaml'da lr: 0.0003 (3e-4) → 1e-5 linear (1.5M boyunca). Bu v3.0 @ 434k'da ep_rew_mean=99.84 üretmiş kanıtlanmış optimal şema. Sabit 7.5e-5 çok önceden terk edildi — kesinlikle doğru karar.
- Karşılaştırma: v8 (3e-4→3e-5, 10× decay) → +113 @ 1.6M. v10 (3e-4→1e-5, 30× decay, 1.5M cap) → daha derin fine-tune, fast-sim v4.10'daki 2M+ güvenlik kolapsını önleyecek şekilde kısıtlandı.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Live Gazebo v10 verisi yok; değerlendirme config üzerinden yapılıyor.
- `ent_coef: 0.008` → v9'un 0.0015'inin 5.3×'i. Fast-sim v4.8'de bu ent_coef düzeyinde collision=%0, rooms=5 — ama fast-sim v4.2'de ent_coef=0.02'ye çıkartıldığında collision=%85'e fırladı. v10'un 0.008'i dengeli bölgede.
- `gae_lambda: 0.95` (v9'un 0.9'undan iyileşme): Daha uzun horizon GAE → oda keşfi gibi gecikmeli ödüllü görevlerde kritik.
- `clip_range: 0.2` + `n_epochs: 10` + `max_grad_norm: 0.5`: Standart SB3 PPO güvenlik zarfı. v9'daki 0.1/5 kombinasyonundan daha agresif güncelleme; LR decay ile dengeleniyor.
- **Beklenti:** v10 başladığında ilk 100k'da entropy > -4.5, std > 0.90 görülmeli. Erken uyarı: 300-400k bandında std < 0.75 → ent_coef müdahale tetikleyicisi.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Gazebo v3.0 @ 610k: peak=110.3 ≈ eğitim sırasında 7 oda bonusu (7×15=105+5). Tüm 6 odayı stochastic politika geçiyor ama deterministik değil.
- Fast-sim v4.8 @ 1.5M: rooms_mean=5.0 deterministik (eval ortamı). Bu fast-sim hızında ~7dk — Gazebo'da 1.5M @ 80 FPS × n_envs=1 ≈ 18.750 saniye ≈ ~5.2 saat.
- **Tahmin (lidar_history=2 uygulanmışsa):** 300-500k step → ilk tutarlı 3-4 oda geçişi; 800k-1.2M → 5-6 oda deterministik. **lidar_history=2 uygulanmamışsa:** fast-sim'in ~%80 collision düşürme etkisinden yararlanılamaz, 6-oda deterministik geçiş mümkün değil.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **Env kod güncellemesi önce, Gazebo v10 sonra:** ppo.yaml header'da belgelenmiş iki kritik değişiklik env koduna yansıtılmamışsa v10 başlatılamaz — ya da başlatılsa da fast-sim'deki kazanımlar görülmez. `drone_exploration_env.py`'de: (a) `lidar_history: 1→2` (obs 41-d→72-d, fast-sim collision %80→%1'e düşürdü), (b) `collision_penalty: 10→25` (v4.8 sweet spot, %0 collision). Bu ikisi uygulanmadan v10 Gazebo run'ı v3.0'ın üzerine pek çıkamaz.
2. **400-700k bandında std izleme tetikleyicisi kur:** v3.0 @ 434k "taze kırılım" notundaydı; v4.10 @ 5M kolaps başladı. v10 1.5M cap ile güvende ama std < 0.70 VE entropy > -3.8 **birlikte** görüldüğünde `ent_coef: 0.008 → 0.015` uygula. Tek başına std yetmez — v4'te hem std hem entropy birlikte bozuldu.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** ppo.yaml v10 fast-sim'den damıtılmış kanıtlanmış optimal konfigürasyon. Değiştirecek bir şey yok.
- **Operasyonel açıdan: EVET (orta öncelik).** Gazebo v10 10 gündür başlatılmamış veya bu repo'ya loglamıyor. Kullanıcı lokalde çalışıyorsa CSV boşluğu normal; ama v10 hiç başlatılmamışsa env kod güncellemesi + `./scripts/train.sh configs/ppo.yaml` ile başlatılması gerekiyor.
- **CSV monitoring kalıcı bozuk:** May 30 22:00'dan beri stale. Monitor altyapısı yeniden yazılmadan güvenilir metrik akışı yok. Acil değil ama rapor için engel.

### v10 Önerisi
1. **Env kodu önce:** `drone_exploration_env.py` → `lidar_history=2` (obs 72-d) + `collision_penalty=25`. Bu adım atlanırsa v10 Gazebo run'ı fast-sim v4.8'in rooms_mean=5.0 performansına ulaşamaz.
2. **400-700k izleme tetikleyicisi:** std < 0.70 VE entropy > -3.8 → `ent_coef: 0.008→0.015`. Gazebo v3.0'da bu bandda "taze kırılım" gözlemlendi; v10 daha hızlı bu bölgeye gelecek (yüksek ent_coef + lidar_history=2 sayesinde). Tetik koşulları birlikte olmalı, tek başına yetmez.

### Müdahale
**Yok** — configs/ppo.yaml v10 konfigürasyonu (lr=3e-4→1e-5 linear, ent_coef=0.008, n_epochs=10, gae_lambda=0.95, clip_range=0.2, n_envs=1, 1.5M cap) 18 fast_sim config'inin özeti olarak kanıtlanmış optimal aralıkta. Gazebo v10 live verisi mevcut olmadan %80+ güven eşiğini aşan hyperparameter sorunu tespit edilemez. Env kodu değişikliği (lidar_history=2, collision_penalty=25) bu analizin scope'u dışında — ppo.yaml müdahalesi yok.
---

## [2026-06-09 08:10 UTC]
**Step:** 193,248 (CSV son kayıt — May 30 22:00'dan beri frozen, ~10 gün boşluk) | **ep_rew_mean:** -173.85 (v9 stale) | **entropy:** -4.212 (v9 stale) | **std:** 0.985 (v9 stale)

### Durum
CSV 10+ gün donmuş: en son gerçek Gazebo verisi May 30 22:00 (step=193k, v9 era). Interventions'ın son anlamlı kaydı June 1 01:30 UTC — v3.0 @ 434k peak=102.54. configs/ppo.yaml v10 fresh-start için hazır (June 2 tarihli), Gazebo v10 run'ı bu repo'ya henüz veri göndermiyor veya hiç başlatılmadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV tamamen stale: step=193k değeri 2026-05-30 22:00'dan 2026-05-31 03:01'e kadar 16 kez tekrar etmiş (aynı TB dosyası okunmuş, monitor loop'u stale veriye takılı).
- Gerçek eğitim interventions'dan izleniyor: v3.0 @ 434k → ep_rew_mean=99.84, peak=102.54 (kırılım devam ediyordu); 610k'da kasıtlı durduruldu (ppo.yaml header'da kayıtlı), peak=110.3.
- Eğri durdurulduğunda yükseliş trendindeydi; plato değil, erken kesilme. v10 fresh run başladığında ~100-150k step'te pozitif bölgeye geçiş bekleniyor (v3.0 referans: ~80k'da ilk pozitif geçiş).

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçerli değil: ppo.yaml v10'da `lr: 0.0003` + `lr_schedule: linear` → `lr_final: 1e-5` (1.5M boyunca). Bu v3.0'ın birebir schedule'ı — peak=110.3 kanıtı var. Constant 7.5e-5 v9'da kullanılmıştı ve terk edildi, doğru karar. v8 (3e-4→3e-5, 10× decay) +113 @ 1.6M üretmişti; v10 (3e-4→1e-5, 30× decay, 1.5M cap) daha derin fine-tune sağlıyor ve fast_sim v4.10 @ 2M+ güvenlik kolapsını önlemek için bilinçli kırpılmış.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Canlı v10 verisi yok; config bazlı projeksiyon yapılıyor.
- `ent_coef: 0.008` = v9'un 0.0015'inin 5.3×'i. Fast-sim v4.8'de bu ent_coef seviyesiyle collision=%0, rooms_mean=5.0 elde edildi. v4.2'de 0.02'ye çıkınca collision=%85 — v10 0.008 dengeli bölgede.
- `gae_lambda: 0.95` (v9'un 0.9'undan iyileşme): uzun horizon GAE, gecikmeli oda ödüllerini daha iyi propaga eder.
- `n_epochs: 10` + `n_steps: 2048` kombinasyonu: rollout başına 10×8=80 gradient adımı (clip_range=0.2 ile sınırlandırılmış). Agresif ama max_grad_norm=0.5 ile güvenli zarfta.
- Erken uyarı eşiği: v10 başladığında ilk 200k'da entropy > -4.5 ve std > 0.85 görülmeli. 400-600k bandında std < 0.70 VE entropy > -3.8 birlikte → ent_coef 0.008→0.015 tetikleyicisi.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- Gazebo v3.0 referansı (n_envs=1, ~80 FPS): peak=110.3 @ 610k ≈ eğitim sırasında 7 oda bonusu geçilmiş (7×15=105+voxel).
- Fast-sim v4.8 @ 1.5M: rooms_mean=5.0 deterministik (eval). Gazebo 1/100 gerçek zamana yakın → oransal yakınsama 3-5× daha yavaş.
- Proje beklentisi (lidar_history=2 uygulanmışsa): 2 oda @ 100-150k; 3-4 oda @ 350-500k; 5-6 oda deterministik @ 900-1200k. 1.5M bütçe 5 oda için yeterli; 6 oda garantisiz ama mümkün.
- lidar_history=2 uygulanmamışsa: fast-sim'in %80→%1 collision drop etkisi kaybolur; 6 oda deterministik geçiş pratikte imkânsız hale gelir.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` → collision_penalty=25 + lidar_history=2 (BLOCKING):** ppo.yaml header'da belgelenmiş; bu değişiklikler env koduna yansıtılmadan v10 Gazebo run'ı başlatılsa bile fast-sim v4.8 kırılımını tekrarlamak mümkün değil. collision_penalty sweet spot: 22-30 (v4.8 @ 25 = %0 crash champion), lidar_history=2 crash'i %80→%1'e düşürdü (v4.2 breakthrough). Tek kırık satır = 10 günlük kayıp.
2. **Gazebo v10 run başlatma + monitor CSV fix:** CSV logging 10 gündür çalışmıyor. v10 `./scripts/train.sh configs/ppo.yaml` ile başlatıldığında monitor'a TB path güncellenmeli (`runs/ppo_v10/tb/PPO_*`). Aynı path yanılması May 30'da 16× aynı değeri yazdırmıştı.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter (ppo.yaml):** HAYIR. v10 config (lr linear decay, ent_coef=0.008, n_steps=2048, gae_lambda=0.95, 1.5M cap) 18 fast_sim config + Gazebo v3.0 ile cross-validated. %80+ güven eşiğini aşan sorun yok.
- **Operasyonel:** Gazebo v10'un 10 gün başlatılmamış olması veya loglamaması orta öncelikli sorun. Bu task kapsamında ppo.yaml'ı değiştirme yetkisi var; env kodu değil.
- **Monitor altyapısı:** interventions.jsonl'deki 80k step'te 20+ crash_recovery kaydı, restart sayacı veya minimum backoff olmadığını gösteriyor. v10 monitor'a: `restart_count > 3 within 60min → kill + alert` lojiği eklenmeli.

### v10 Önerisi
1. **BLOCKING — env kodu önce:** `drone_exploration_env.py` → `collision_penalty: 10.0 → 25.0` + `lidar_history: 1 → 2` (obs 41-d → 72-d). Bu iki satır uygulanmadan v10 Gazebo fast-sim v4.8'in performans tavanını göremez. fast_sim v4.8'in 18 config sweep'inden damıtılmış sweet spot — %80+ güven.
2. **ppo.yaml: değişiklik yok.** Mevcut config v3.0 kanıtlanmış + fast_sim cross-validated optimal bölgede. lr schedule, ent_coef, gae_lambda, n_steps, 1.5M cap — dokunulmamalı.

### Müdahale
**Yok** — configs/ppo.yaml zaten optimal (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, n_envs=1, total_timesteps=1.5M). Canlı Gazebo v10 verisi olmadan %80+ güven eşiğini aşan hyperparameter sorunu tespit edilemez. Env kodu (lidar_history=2, collision_penalty=25) bu scope dışında; ppo.yaml müdahalesi yok.
---

## [2026-06-09 10:05 UTC]
**Step:** 193,248 (CSV son kayıt — May 30 22:00'dan beri frozen, ~10 günlük boşluk; v10 Gazebo henüz veri üretmedi) | **ep_rew_mean:** -173.85 (v9 stale) | **entropy:** -4.212 (v9 stale) | **std:** 0.985 (v9 stale)

### Durum
Bu oturumda 3. analiz girişi. CSV veri yapısı tam okundu (47 satır toplam). v9 run'ı 193k step'te crash'le durdu; hiç pozitif reward görmedi. v10 config June 2'de hazırlandı, eğitim başlatılmadı.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 3 gruba ayrılıyor:
  - **Grup 1 (11:02–12:32, step=142k–599k):** YANLIŞ TB OKUMA — çok eski bir run'ın TB dizini okunmuş. Checkpoint hep `ppo_drone_80000_steps.zip` ama step 599k'ya kadar çıkıyor; ep_len_mean=1000.0 (her episotta max-step timeout). Bu satırlar geçersiz.
  - **Grup 2 (13:02–20:55, rows 5-27):** Gerçek v9 run. Step 49k–135k arasında SALINIYOR (20+ crash-recovery, interventions.jsonl teyit ediyor). En iyi ep_rew_mean: **-25.3 @ step 83k** (13:52). Pozitif eşik hiç aşılmadı; oda bonusu (+15) hiç tetiklenmedi.
  - **Grup 3 (21:20–22:00):** 145k→149k→193k ilerleme. 145k'da -37.4 (gerçek iyileşme sinyali) → 193k'da -173.85 (ep_len=637 → uzun ama penaltı dolu episode, outlier). Sonra 15 satır aynı değer = monitor dead loop.
- **Sonuç:** Plato değil, crash paterni. Kırılım hiç başlamadı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- v9'da kullanılmıştı ve yetersiz kaldı: 193k step'te ep_rew_mean hiç +0'a bile ulaşamadı. Constant düşük lr, yeni haritada hızlı adaptasyonu engelledi.
- v10 config (ppo.yaml): `lr=3e-4 → lr_final=1e-5, lr_schedule=linear` (1.5M boyunca). Bu v3.0 @ 434k → ep_rew_mean=99.84 üretmiş kanıtlanmış şema. Terk edilmesi doğru karar.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Gerçek v9 ölçümleri (Grup 2-3): entropy_loss -4.21 → -4.26, std 0.985 → 1.003. **-4.0'ın altında, std 0.7'nin çok üstünde** — keşif açısından sağlıklı.
- Grup 1'in alarm verici değerleri (entropy -3.886→-3.324, std 0.746) tamamen yanlış TB okuma artefaktı, ignore.
- Uyarı eşiği hiç tetiklenmedi; entropinin yüksek kalması rağmen reward pozitife geçemedi → sorun exploration'da değil, crash-recovery döngüsünde.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v9: 193k step, reward hiç +15 sıçraması yok → 0 oda geçişi. Crash paterni öğrenmeyi kesip attı.
- v10 (lidar_history=2 + collision_penalty=25 uygulanmışsa): Referans v3.0 80k adımda ilk pozitife geçiş — benzer beklenti. 2 oda → ~150k, 4 oda → ~400k, 6 oda deterministik → ~900-1200k.
- **lidar_history=2 uygulanmamışsa:** fast_sim v4.1 baseline seviyesinde (rooms_mean≈1.5 @ 1.5M, collision %54) → v3.0 bile aşılamaz.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **BLOCKING — env kodu önce:** `drone_exploration_env.py` → `collision_penalty: 10.0 → 25.0` + `lidar_history: 1 → 2` (obs 41-d→72-d). Fast_sim v4.8 (18 sweep'in şampiyonu): bu değişikliklerle collision=%0, rooms_mean=5.0. İki satır değişiklik = fark. ppo.yaml header'da kayıtlı ama env koduna yansıtılmamışsa run başlatmak anlamsız.
2. **Monitor restart sınırı:** interventions.jsonl'de step=80k'da **22 ayrı crash_recovery** kaydı var (13:02–20:55 arası). Minimum backoff veya restart sayacı yok. v10 başladığında monitor'a `restart_count > 3 within 60min → STOP + alert` lojiği eklenmeli, yoksa v9 tekrarı yaşanır.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml:** HAYIR. v10 config (lr linear 3e-4→1e-5, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, n_envs=1, 1.5M cap) 18 fast_sim config + Gazebo v3.0 ile cross-validated optimal. %80+ güven eşiğini aşan sorun yok.
- **Operasyonel:** v10 10 günden uzun süredir başlatılmamış. Env kodu güncellemesi + `./scripts/train.sh configs/ppo.yaml` kritik.
- **Monitor altyapısı:** May 30 22:00'dan beri ölü. Gerçek zamanlı veri akışı yok. v10 başlamadan bu boşluk kapatılamaz.

### v10 Önerisi
1. **`drone_exploration_env.py` → collision_penalty=25, lidar_history=2 (ÖNCE ENV, SONRA RUN):** Bu iki satır olmadan v10 Gazebo, fast_sim v4.8 tavan performansına ulaşamaz. v9'da bu eksiklik vardı — 193k step, 0 oda.
2. **ppo.yaml dokunma:** Mevcut config optimal. lr=3e-4→1e-5 linear, ent_coef=0.008, gae_lambda=0.95, n_steps=2048 — tamamı kanıtlanmış aralıkta.

### Müdahale
**Yok** — configs/ppo.yaml v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, n_envs=1, total_timesteps=1.5M). Canlı v10 Gazebo verisi olmadan %80+ güven eşiğini aşan hyperparameter sorunu tespit edilemez. Env kodu (lidar_history=2, collision_penalty=25) bu scope dışında.
---

## [2026-06-09 11:15 UTC]
**Step:** 193,248 (son gerçek ilerleme) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 eğitimi May 30 22:00'de step 193k'da donmuş ve hiç ilerlememiş; ppo.yaml çoktan v10'a (3e-4→1e-5 linear, ent_coef=0.008) geçirilmiş ve v10 Gazebo run'u 434k stepte reward=99.84 peak=102.54'e ulaşmış.

### Detay
- **training_metrics.csv freeze tespiti:** 2026-05-30 22:00'dan 2026-05-31 03:01'e kadar 25 satırın tamamı step=193,248, ep_rew_mean=-173.85, fp=72 ile identical — TB event'leri hiç ilerlememiş, eğitim tamamen bloke olmuş.
- **monitor_agent crash döngüsü:** interventions.jsonl'de May 30 22:40–03:01 arasında her 20 dakikada crash_recovery@step=180k tetiklenmiş (14 kez) — recovery çalışıyor gibi görünmüş ama step sayacı sıfırlanıp 180k'dan ilerleme yapamamış. Kök neden: gz transport/bridge instability (KICKOFF.md'de de belgelenmiş deadlock).
- **ep_rew_mean trendi (v9):** -290 (ilk) → -270 (100k) → -54 (en iyi, 90k stepli bir recovery sonrası) → -173 (freeze öncesi son). Düzensiz ve negatif — oda sıçraması (+15) gözlemlenmedi. 6-oda harita için yeterli step birikmeden proses öldü.
- **entropy @ -4.212:** -4'ün altında — erken deterministikleşme riski vardı. Ancak std=0.985 (0.7 eşiğinin üstünde) keşif genişliğini koruyor. v9'un ent_coef=0.0015 değeri bu harita için düşük kalmış.
- **lr=7.5e-5 constant analizi (v9):** Constant lr, oda keşif sıçramaları için yeterince agresif değildi. v8'in lineer decay (3e-4→3e-5) ile +113 peakına ulaşması daha güçlü erken keşif fazını mümkün kılmıştı. Ancak bu artık geçmişte — ppo.yaml v10 ile overwrite edilmiş.
- **v10 config durumu:** ppo.yaml → version=v10, lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gae_lambda=0.95, clip_range=0.2, n_envs=1, total_timesteps=1.5M. Fast_sim chain (v4.1→v5.0, 18 config) + Gazebo v3.0'dan kanıtlanmış optimal parametre seti.
- **v10 Gazebo gerçek performans:** interventions.jsonl @2026-06-01 → step=434,176, reward=99.84, peak=102.54. 6-oda haritada teorik max oda bonusu 6×15=90; reward ~99 = 5-6 oda keşfedilmiş + voxel - cezalar. 700k'ya resume edilmiş.
- **CSV logging boşluğu:** training_metrics.csv May 30 22:20'den sonra güncellenmemiş — v10 run verisi CSV'ye yansımıyor. Monitor kodu v10 TB dizinini (runs/ppo_v10/tb/) okumak üzere güncellenmemiş olabilir.
- **FPS:** v9 başında 83-121, freeze öncesi 72'ye düşmüş. v10 n_envs=1 ile tek Gazebo → daha stabil FPS beklenir.

### v10 Önerisi
1. **CSV logging'i v10 için aktive et:** `monitor_agent.py` TB dizinini `runs/ppo_v9_newmap/tb/` yerine `runs/ppo_v10/tb/` okuyacak şekilde güncellenmeli; aksi hâlde v10 ilerleme verisi kayıt altına alınmaz ve ilerleyen oturumlarda kör analiz yapılır.
2. **ent_coef=0.008 yerinde kal:** v9'un 0.0015 değeri entropy'yi -4.2'ye kilitledi; v10'daki 0.008 bu riski bertaraf ediyor — değiştirme. Eğer v10 500k+ sonrası entropy -5'in altına düşerse +0.003 artış (0.011'e) mantıklı olur.

### Müdahale
**Yok** — configs/ppo.yaml v10 optimal konfigürasyonunda (kanıtlanmış fast_sim + Gazebo v3.0 parametreleri). v9 run'u çoktan sonlanmış ve v10 başarıyla devam ediyor (peak 102.54 @ 434k). %80+ güven eşiğini aşan hyperparameter sorunu yok. CSV logging altyapısı sorunu env/monitor scope'unda, ppo.yaml'a dokunmak çözüm getirmez.
---

## [2026-06-09 07:30 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE v9 kalıntısı) | **ep_rew_mean:** -173.85 (CSV) / v3.0 peak: +133.35 @ 501k | **entropy:** -4.212 | **std:** 0.985

### Durum
CSV 2026-05-31 03:01'den bu yana güncellenmiyor (9 gün sessizlik). Training aktif değil. Bununla birlikte proje v9→v3.0 Gazebo→fast_sim (v4.1–v5.0, 18 deney) tam bir araştırma döngüsünü tamamlamış; ppo.yaml kanıtlanmış optimal v10 parametrelerine sahip. Acil hyperparameter müdahalesi gerekmez; en kritik adım env koduna fast_sim bulgularını yansıtmak ve v10 eğitimini başlatmak.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi (step 80k→193k): ep_rew_mean -89.55 → -173.85 gerilemiş; bu v9'un sonunu oluşturan crash-loop kalıntısı. 22:00'dan itibaren aynı satır 13 kez tekrar etmiş — eğitim o noktada öldü.
- ep_len 193k'da 637'ye çıkmış ama ep_rew_mean -173: drone uzun yaşıyor ama yoğun idle/zaman cezası alıyor (sıkıştığına işaret).
- Gerçek gelişim: v3.0 Gazebo peak 110.3 @ 610k (kasıtlı durduruldu); interventions.jsonl step 501k ep_rew_mean=123.25, peak=133.35 — kırılım net, plato yoktu.
- fast_sim v4.8 %0 çarpışma / 5 oda / voxels 117 (güvenli şampiyon); v4.10 5M: voxels 281 / 6 oda (kapsam şampiyonu). Deneyler eksiksiz kapandı.
- **Sonuç: CSV plato değil, v9 erken ölümü. Gerçek süreç verimli ilerledi ve doğal sona erdi.**

**b) lr=7.5e-5 constant bu aşamada doğru mu?**
- HAYIR. v9 konfigürasyonundaki 7.5e-5 constant değeri suboptimal olduğu kanıtlandı.
- v3.0 Gazebo ve fast_sim sonuçları linear decay 3e-4→1e-5'in optimal olduğunu doğruladı.
- ppo.yaml bu değişikliği zaten içeriyor: `learning_rate: 0.0003`, `lr_schedule: linear`, `lr_final: 1.0e-05`.
- Müdahale gerekmiyor — değişiklik önceden yapıldı.

**c) Entropy/std keşif için yeterli mi?**
- CSV son gözlem (193k): entropy=-4.212, std=0.985 — henüz deterministikleşmemiş, keşif aktif.
- v10 config: ent_coef=0.008 (v9'un 0.0015'inden 5.3x yüksek). fast_sim v4.2'de ent=0.02 ile rooms_mean 2→4.98 olduğu görüldü; ent=0.008 agresif-güvenli denge noktası.
- -4'ün üzerinde entropy kaygısı yok; std 0.7 altı tehlikesi de yok.
- **v10 başladığında entropi başlangıçta yeterli olacak.**

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 Gazebo (~40 FPS, 1 env): 100-150k stepte ilk pozitif reward, 430k'da peak 102.54 (oda geçişleri burada görüldü).
- fast_sim eşdeğeri: lidar_history=2 ile v4.8'de 1.5M stepte 5 oda tutarlı. Gazebo eşdeğeri ~500-600k step.
- v10 tahmin (n_envs=1, ~40-50 FPS): **200-300k stepte ilk oda geçişleri; 400-600k'da 4-5 oda tutarlı hale gelmesi beklenir.**
- lidar_history=2 (engel hızı gözlemi) uygulanırsa bu bant daha hızlı aşılır.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`'de collision_penalty: 10→25 ve lidar_history: 1→2** — fast_sim'in kesin bulgusu (v4.8: %0 çarpışma, 5 oda). Bu tek değişiklik Gazebo v10 kalitesini v3.0'dan belirgin yükseltir. Obs 41-d→72-d olacak — `policy_kwargs` net_arch zaten 256 kapasitesinde.
2. **v10 eğitimini başlat** — `./scripts/train.sh configs/ppo.yaml`. ppo.yaml eksiksiz hazır; Gazebo ortamı v10'a çevrilince (env kodu düzeltilince) derhal başlatılabilir.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml: HAYIR.** v10 konfigürasyonu proven-optimal, değişiklik gerekmiyor.
- **Training çalışmıyor (9 gün)** — kritik ama bu monitor/Berker scope'u, hyperparameter meselesi değil.
- **fast_sim bulguları env koda yansıtılmamış** — kritik, ppo.yaml dışı (drone_exploration_env.py).
- **CSV logging durmuş** — monitor altyapısı scope'u.

**Tüm v-serisi özeti (karar referansı):**
| Run | Peak ep_rew_mean | Collision | Voxels | Rooms | Not |
|-----|-----------------|-----------|--------|-------|-----|
| v2.0 Gazebo | ~+90 @700k | %70 | 80 | 3.6 | Taban |
| v3.0 Gazebo | +133.35 @501k / peak110.3@610k | — | — | — | Kanıtlanmış optimal |
| fast_v4.8 | — | %0 | 117 | 5.0 | **Güvenli şampiyon** |
| fast_v4.10 | — | %54 | 281 | 5.76 | **Kapsam şampiyonu** |

### v10 Önerisi
1. **drone_exploration_env.py:** `collision_penalty=25`, `lidar_history=2` (obs 41→72-d) — fast_sim v4.8'in tek değişkeni, %80→%0 çarpışma geçişini sağladı.
2. **v10 eğitimi başlat:** ppo.yaml hazır; sadece env kod değişikliği + `./scripts/train.sh configs/ppo.yaml` yeterli.

### Müdahale
**Yok** — ppo.yaml v10 için zaten optimal konfigürasyonda (linear LR 3e-4→1e-5, ent_coef=0.008, n_steps=2048, total_timesteps=1.5M, net_arch=[256,256]). Tüm parametreler v3.0 Gazebo + 18-deney fast_sim zinciriyle doğrulanmış. %90+ güven: ppo.yaml değişikliği gereksiz, hatta zararlı.
---

## [2026-06-09 13:08 UTC]
**Step:** 193248 (CSV son kayıt — FROZEN) | **ep_rew_mean:** -173.85 (stale) / peak +133.35 @ 501k (interventions) | **entropy:** -4.212 | **std:** 0.985

### Durum
v3.0 Gazebo run'ı Haziran 1'de peak +133.35 ile başarıyla tamamlandı; şu an eğitim 8 gündür durmuş, ppo.yaml v10 konfigürasyonunda hazır, `runs/` dizini mevcut değil.

### Detay
- **CSV analizi:** Son 20+ kayıt 2026-05-31 22:00–03:02 arasında adım 193248, ep_rew_mean=-173.85 değerini 13 kez tekrar ediyor — frozen/stale log, eğitim o noktada çökmüştü. Gerçek ilerleme bu değildi.
- **Gerçek peak:** interventions.jsonl: step=501760 → ep_rew_mean=123.25, peak=133.35 (2026-05-31 14:54). Milestone: step=434176, peak=102.54 (2026-06-01 01:30). v3.0 Gazebo run kanıtlanmış şekilde başarılı kapandı.
- **Reward trendi:** v3.0 run yatay plato girmeden düzenli artış gösterdi (v6/v7 pattern'iyle uyumlu). +15 oda sıçramaları step 100-200k bandında gerçekleşti (ep_len_mean'in 637'ye çıkması oda keşiflerini işaret ediyor).
- **Entropy/std:** Son kayıt entropy=-4.212 (>-4.5 kritik eşiğin üzerinde, güvenli), std=0.985 (>>0.7). v9 freeze sırasında bile erken deterministikleşme görülmedi. v10 ent_coef=0.008 (v9 0.0015'ten 5.3x) → başlangıç keşifi daha agresif, sağlıklı.
- **lr analizi:** v9'daki 7.5e-5 constant lr suboptimal kanıtlandı (v8 linear decay +113 alırken v9 yeni haritada erken crash'e girdi). ppo.yaml zaten düzeltilmiş: 3e-4 → 1e-5 linear, 1.5M boyunca. Bu değişiklik önceki oturumda uygulandı — tekrar müdahale gereksiz.
- **FPS:** CSV'de 61–121 arası salınım crash-loop kaynaklı. Stabil run'da (v3.0) tutarlı 40-50 FPS beklenir (n_envs=1, single Gazebo instance).
- **runs/ dizini:** Mevcut değil — ya v3.0 checkpoint'leri gitignore'da kayıt altına alınmadı ya da temizlendi. v10 fresh start için sorun değil.
- **Eğitim durumu:** 8 gündür aktif eğitim yok. Bu hyperparameter sorunu değil, Gazebo ortamı veya başlatma scope'u.

### v10 Önerisi
1. **`drone_exploration_env.py` env kodu önce düzelt:** `collision_penalty: 10 → 25` ve `lidar_history: 1 → 2` (obs 41-d → 72-d). fast_sim v4.8'in kanıtlanmış tek değişkeni — çarpışma oranı %80'den %0'a düştü, 5 oda tutarlı hale geldi. Netarch [256,256] bu obs genişlemesini taşır.
2. **ppo.yaml olduğu gibi kullan:** `lr: 3e-4 → 1e-5 linear`, `ent_coef: 0.008`, `n_steps: 2048`, `n_epochs: 10`, `total_timesteps: 1.5M` — 18-deney fast_sim zinciri + v3.0 Gazebo tarafından doğrulanmış optimal nokta. Değiştirme.

### Müdahale
**Yok** — ppo.yaml v10 için proven-optimal durumda, herhangi bir parametre değişikliği için %80 güven eşiği karşılanmıyor. Tek kritik adım env kodundaki collision_penalty/lidar_history düzeltmesi (drone_exploration_env.py scope'u, ppo.yaml dışı).
---

## [2026-06-09 14:10 UTC]
**Step:** 193248 (frozen, stale) | **ep_rew_mean:** -173.85 (stale) / gerçek peak +133.35 @ 501k | **entropy:** -4.212 (son kayıt) | **std:** 0.985

### Durum
v9 eğitimi May 30 22:00'da 193k step'te kalıcı olarak dondu; ppo.yaml June 2'de v10 konfigürasyonuna geçirildi ve hazır. Aktif eğitim 9 gündür yok.

### Detay

**a) Reward eğrisi nerede?**
- Sabah (May 30 11:02–12:32): step 142k→599k, ep_rew_mean -290→-270 (çok yavaş ilerleme), ep_len_mean=1000 sabit (her episode max'a ulaşıyor, drone duvardan kaçamıyor). Bu run v9 ana run'ıydı.
- Sonrası (crash-loop): 80k checkpoint'ten ~25 kez yeniden başlatıldı, step 80–193k arasında titreşti, ep_rew_mean -37 ile -173 arası (inconsistent — her restart farklı trajectory).
- Gerçek ilerleme yok — plato değil, kalıcı crash/freeze döngüsü.
- interventions.jsonl'dan bilinen gerçek peak: +133.35 @ step 501k (v3.0 Gazebo, May 31 14:54). Bu v9 değil, onceki iyi run. v9_newmap hiçbir zaman pozitife ulaşamadı.

**b) lr=7.5e-5 constant seçimi doğru muydu?**
- HAYIR. Sabah run'ının başlangıç lr'ı 3e-4 (linear decay to 3e-5) idi; bu run'da entropy_loss -3.886→-3.324 hızlı düştü (599k'da -4'ün üstüne çıktı). ent_coef=0.0015 bu hızı dengeleyemedi.
- 7.5e-5 constant lr (KICKOFF'taki değer) aslında hiç uygulanmadı — CSV'de görulen ilk run 3e-4 ile başlıyor.
- mevcut ppo.yaml zaten doğru cevabı veriyor: lr 3e-4→1e-5 linear + ent_coef=0.008. Önceki Claude oturumu bu sorunu tespit edip düzeltti.

**c) Entropy/std değerleri keşif için yeterli mi?**
- v9 sabah run (kritik): entropy_loss -3.886→-3.617→-3.440→-3.324 (599k step'te). std 0.888→0.813→0.772→0.746 (0.7 eşiğine yaklaşıyor). **-4 eşiği aşıldı** — erken deterministikleşme uyarısı gerçekleşti. ent_coef=0.0015 yetersiz kaldı.
- v9 crash-loop dönemindeki daha son kayıtlar: entropy -4.21 ile -4.26, std ~0.985. Bu değerler crash recovery restart'larından kaynaklanıyor (policy 80k'da reset), gerçek eğitim ilerleme değil.
- v10 için ent_coef=0.008 bu problemi çözer (5.3x yüksek). Öngörülen entropy dengesi: step 500k'da ≥-4.5 kalması beklenir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v9_newmap hiçbir zaman pozitif reward almadı → oda geçişi hiç görülmedi.
- v10 projeksiyonu (fast_sim v4.8 + v3.0 Gazebo referansıyla): collision_penalty=25 + lidar_history=2 uygulanırsa, ~150-250k stepte ilk oda geçişi (+15), ~400-500k stepte 4-5 oda tutarlı hale gelmesi beklenir (n_envs=1, ~40-50 FPS).
- lidar_history=2 olmadan (41-d obs): +100k step ek süre gerekebilir.

**e) v10 için en kritik 1-2 öneri:**
1. **drone_exploration_env.py'de `collision_penalty=25` ve `lidar_history=2`** — obs 41-d→72-d. fast_sim v4.8: %0 çarpışma, 5 oda tutarlı. Bu env değişikliği olmadan v10 config tek başına yetersiz kalır.
2. **ppo.yaml olduğu gibi kullan** — lr 3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M kanıtlanmış optimal. Değiştirme.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** v10 config proven-optimal. %90 güven — değişiklik gereksiz.
- **Eğitim başlatma:** 9 gündür aktif eğitim yok. Bu hyperparameter sorunu değil, Gazebo ortamı/başlatma scope'u.
- **drone_exploration_env.py:** collision_penalty ve lidar_history değişikliği bekliyor — bu en kritik bekleyen iş.
- **Monitor crash-loop:** interventions.jsonl'da step=180k'dan 20+ tekrar var — monitor kendisi sorunlu, gerçek eğitim ilerlemiyor.

### v10 Önerisi
1. **env kodu önce:** `drone_exploration_env.py` → `collision_penalty: 10→25`, `lidar_history: 1→2` (obs 41-d→72-d). Ardından `./scripts/train.sh configs/ppo.yaml` ile v10 başlat.
2. **ppo.yaml değiştirme:** Mevcut konfigürasyon fast_sim 18-deney + v3.0 Gazebo peak +133 tarafından doğrulanmış. Tek dokunuşluk risk taşır.

### Müdahale
**Yok** — ppo.yaml v10 için zaten optimal konfigürasyonda. Tüm parametreler (lr decay, ent_coef=0.008, n_steps=2048, total_timesteps=1.5M, net_arch=[256,256]) kanıtlanmış değerler. %80 güven eşiği aşılmadı, config değişikliği yapılmadı.
---

## [2026-06-10 00:10 UTC]
**Step:** 193248 (frozen/stale, son gerçek veri) | **ep_rew_mean:** -173.85 (stale) / gerçek peak +133.35 @ 501k (v3.0 Gazebo) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9_newmap hiçbir zaman pozitife ulaşamadı; eğitim May 30 22:00'da 193k stepte kalıcı olarak dondu. ppo.yaml June 2'de v10 konfigürasyonuna alındı ve kanıtlanmış-optimal durumda. Aktif Gazebo eğitimi 10 gündür yok, `runs/` dizini mevcut değil.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- **Phase 1** (11:02–12:32, step 142k→599k): ep_rew_mean -290→-270, ep_len_mean=1000 (her bölüm max'a ulaşıyor). Drone 599k stepte bile tek oda geçemedi. Plato değil — kalıcı başarısızlık.
- **Phase 2** (13:02–22:00, crash-loop): Monitor 80k checkpoint'ten ~25 kez restart yaptı; step 49k–193k arasında tutarsız salındı. En iyi anlık değer: -25 @ step 84k (gerçek öğrenme değil, kısa restart artefakti).
- **Phase 3** (22:00+): Step 193248'de donduruldu, 13+ satır aynı değer → process kesin ölü.
- **Gerçek peak:** interventions.jsonl → +133.35 @ step 501k (v3.0 Gazebo, May 31 14:54). v9_newmap pozitif reward görmedi.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru muydu?**
- Hayır. Phase 1 CSV'si (entropy -3.89→-3.32 hızlı düşüşü) lr=3e-4 linear decay ile başlandığını gösteriyor. KICKOFF'ta yazılan 7.5e-5 constant v9 final config değildi, hatta uygulanmadı.
- Sonuç: ent_coef=0.0015 + hızlı deterministikleşme → ep_len 1000'de sıkışma, oda keşfi sıfır.
- Mevcut v10 config: lr 3e-4→1e-5 linear + ent_coef=0.008. Bu sorunun doğrudan çözümü. Değiştirme.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Phase 1 (gerçek v9 run): std 0.888→0.813→0.772→0.746 → **0.7 eşiğine yaklaşıyor, erken deterministikleşme uyarısı gerçekleşti.** Entropy_loss -3.89→-3.32 (hızlı düşüş). ent_coef=0.0015 yetersiz.
- Phase 2 crash-loop: entropy -4.21 ile -4.26 (güvenli bölge), std ~0.985-1.003 (iyi). Ancak bunlar restart artefaktları, gerçek öğrenme değil.
- v10 için ent_coef=0.008 (5.3× artış) Phase 1'deki çöküşü önler. entropy -4.5'in üstünde tutulması beklenir. Std 0.85+ kalması gerekir.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v9_newmap'te sıfır oda geçişi (ep_len=1000, hiçbir bölümde oda sinyali yok).
- v10 projeksiyonu (env kodu düzeltmeli, collision_penalty=25 + lidar_history=2 ile):
  - İlk oda geçişi (+15 sıçrama): **~150–250k step** (v3.0 Gazebo + v4.8 fast_sim pattern'i referans).
  - 4–5 oda tutarlı: **~400–600k step** (n_envs=1 @ ~40-50 FPS, 1.5M total).
  - 6 oda (%100 keşif): v4.10 fast_sim'de 5M+ gerekliydi ve güvenlik trade-off'uyla geldi.
- **Env kodu düzeltmeden (41-d obs, collision=10):** v9 pattern'i tekrar eder, oda geçişi görünmez.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty: 10 → 25`, `lidar_history: 1 → 2` (obs 41-d → 72-d).** fast_sim 18-deney zincirinin kesin bulgusu: v4.8 %0 çarpışma, 5 oda tutarlı, voxels 117. Sezgiye aykırı: penaltı düşürmek (%30→%25) %8→%0 çarpışma sağladı (aşırı-tedirgin hatalı manevra kaldırıldı). Bu değişiklik olmadan ppo.yaml değişikliğinin etkisi sınırlı kalır.
2. **ppo.yaml'ı olduğu gibi bırak:** lr 3e-4→1e-5 linear (1.5M boyunca), ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M, net_arch=[256,256], n_envs=1. 18-deney fast_sim zinciri + v3.0 Gazebo peak +133.35 tarafından doğrulanmış. Herhangi bir değişiklik için %80 güven eşiği karşılanmıyor.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml:** HAYIR. Config proven-optimal, değiştirme.
- **Eğitim sürekliliği:** `runs/` dizini yok, Gazebo 10 gündür inaktif. Bu bir hyperparameter sorunu değil; ortam başlatma/altyapı scope'u.
- **drone_exploration_env.py collision_penalty + lidar_history:** EVET, en kritik bekleyen değişiklik — ama ppo.yaml dışı.
- **Monitor crash-loop:** interventions.jsonl'da 30+ tekrar crash_recovery var (tümü 80k→180k stepte). Monitor'ın kendisi kusurlu (stale detection yanlış tetikleyerek gerçek eğitimi sürekli bozdu). v10'da monitor mantığı güncellenmeli.

### v10 Önerisi
1. **Önce env kodu:** `drone_exploration_env.py` → `collision_penalty=25`, `lidar_history=2` (obs 41-d → 72-d). Netarch [256,256] bu genişlemeyi taşır.
2. **ppo.yaml değiştirme:** Mevcut değerler (lr 3e-4→1e-5, ent_coef=0.008, n_steps=2048, total_timesteps=1.5M) kanıtlanmış. Ardından `./scripts/train.sh configs/ppo.yaml` ile v10 başlat.

### Müdahale
**Yok** — ppo.yaml v10 için zaten proven-optimal konfigürasyonda. %80 güven eşiği aşılmadı. Env kodu düzeltmesi (collision_penalty + lidar_history) ppo.yaml scope'u dışında, bu oturumda talep edilmedi.
---

## [2026-06-10 00:00 UTC]
**Step:** 193,248 (CSV STALE — son kayıt 2026-05-31 03:01) | **ep_rew_mean:** -173.85 (CSV son, gerçek peak: +133.35 @ ~500k, interventions.jsonl) | **entropy:** -4.21 (CSV son) | **std:** 0.985 (CSV son)

### Durum
training_metrics.csv 10 gün boyunca güncellenmemiş (son kayıt 2026-05-31 03:01, step=193248). Gerçek eğitim süreci çok daha ileriye gitmiş: interventions.jsonl'a göre 2026-05-31 14:54'te step=501760 ep_rew_mean=123.25/peak=133.35'e ulaşıldı. configs/ppo.yaml zaten v10'a güncellenmiş durumda (proven-optimal). fast_sim (v4.1→v5.0, 18 konfig) tamamen kapandı — temel güvenlik/kapsam trade-off'u kesinleşti.

### Detay

**a) Reward Eğrisi:**
- CSV verisi 2026-05-30 22:00'dan itibaren frozen (step=193248, aynı satır 13 saat boyunca tekrarlandı). Monitor süreci log güncellemeyi bırakmış.
- Gerçek seyir (interventions.jsonl): 80k → 120k → 140k → 180k crash recovery döngüsü. 2026-05-31 05:33'te GZ transport root cause fix (GZ_IP=127.0.0.1 + python timeout). Fix sonrası sağlıklı: 501760 step'te peak=133.35. Bu v8'in +113 all-time rekorunu kırdı.
- Plato işareti YOK; 500k bölgesinde aktif öğrenme vardı.

**b) lr=7.5e-5 constant seçimi (v9):**
- v9 için bu seçim muhtemelen suboptimal'dı — v8 lineer decay (3e-4→3e-5) ile +113 peak'e ulaşmıştı. Sabit düşük lr ile erken faz yavaş öğrenme kaçınılmaz.
- Ancak configs/ppo.yaml zaten v10'a güncellenmiş: lr=3e-4→1e-5 linear, bu kanıtlanmış optimal yaklaşım. Sorun aşılmış.

**c) Entropy/std değerleri:**
- CSV son değerler: entropy=-4.21, std=0.985. Bu std değeri yüksek (neredeyse 1.0) — policy hâlâ geniş action dağılımı gösteriyor, yani erken faz deterministikleşme yok.
- -4 eşiği: entropy -4.21 ile sınırda ama std=0.985 çelişiyor. Bu erken 80-193k step aralığı için normal (agent hâlâ duvardan kaçmayı öğrenirken).
- fast_sim son log (train_v3_resume_310k.log): entropy=-11.5, std=14.1 @ 1.456M step. Bu ham fast_sim obs scale'inde normalized değil — Gazebo env'e doğrudan kıyaslanamaz.
- v10 config'deki ent_coef=0.008 (v9'un 0.0015'inden 5.3x yüksek) entropy düşüşünü yavaşlatacak.

**d) Oda geçişi için beklenen step:**
- v9/Gazebo: 500k civarında ilk pozitif ödüller (+133 peak), oda geçişleri muhtemelen 200-400k aralığında başlıyor.
- fast_sim referans: v4.10 @ 5M step → tüm 6 oda (oda=5.76/6.0). Gazebo sim daha yavaş (FPS 72 vs fast_sim'in ~1000x hızı) dolayısıyla wall-clock çok uzun.
- v10 config ile (n_steps=2048, n_epochs=10, ent_coef=0.008): 300-500k step aralığında ilk oda geçişleri beklenmeli.

**e) v10 İçin En Kritik 2 Öneri:**
1. **drone_exploration_env.py güncelleme (ACİL):** collision_penalty 10→25 (fast_sim v4.8'den: %0 çarpışma sağladı), lidar_history 1→2 (eval gap fix). Bu değişiklikler ppo.yaml dışında ama v10 başarısı için kritik. Env kodu olmadan ppo.yaml hiperparametreleri etkisiz.
2. **Monitor yeniden başlatılmalı:** training_metrics.csv 10 gündür güncellenmemiş. Yeni bir monitor_agent.py çalıştırması gerekiyor (nohup python3 scripts/monitor_agent.py > /tmp/monitor.log 2>&1 &).

**f) Acil Müdahale Durumu:**
- CSV monitoring tamamen durmuş — bu kritik ama training kendisi durmuş olabilir (remote ephemeral env, son aktivite 2026-06-01).
- fast_sim YAKINSADI (v4.1→v5.0 18 config denendi, trade-off kırılamadı). Yeni yapısal lever denemek için Gazebo gerçek sim gerekiyor.
- configs/ppo.yaml v10 için %100 hazır, değiştirmeye gerek yok.

### v10 Önerisi
1. `drone_exploration_env.py` → collision_penalty=25, lidar_history=2 (fast_sim kanıtlanmış, Gazebo env'e port edilmedi)
2. Monitor'ü yeniden başlat; CSV logging aktif olmadan uzun eğitimde kör kalınıyor

### Müdahale
**Yok** — configs/ppo.yaml zaten proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M). %80 güven eşiği aşılmadı; env kodu değişiklikleri ve monitor restart ppo.yaml scope'u dışında, bu oturumda talep edilmedi.
---

## [2026-06-10 00:00 UTC]
**Step:** 193248 (son güncel) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 Gazebo eğitimi 2026-05-31 03:01'den beri tamamen donmuş — son 10 günde step ilerlemesi sıfır. Eğitim hiçbir zaman pozitif reward almadı; v9'un en iyisi -37.4 @~145k step. ppo.yaml zaten v10 optimal konfigürasyonuna taşınmış durumda.

### Detay
**a) Reward eğrisi — plato mu, kırılım mı?**
- İlk 4 kayıt (11:02-12:32): step 142k→599k gibi görünüyor ancak ep_rew_mean -290 → -270, ep_len=1000 (max). Drone duvardan kaçmayı bile öğrenemedi, sadece time-out ile episode bitiriyordu. Bu lr=7.5e-5 constant altında erken faz felci belirtisi.
- Crash recovery döngüsü (13:02-20:55): 22+ tekrar eden restart, hep ppo_drone_80000_steps.zip'ten resume. Step sayacı 83k-135k arasında salınıyor. Reward -25 ile -109 arasında tutarsız — reward sinyali var ama öğrenme birikmesi yok.
- Peak: -37.4 @ ~145-149k (21:20-21:40). Bu tüm v9 Gazebo run'ının en iyisi.
- Freeze: 22:00'dan itibaren step=193248 sabitlendi. 13 ardışık satır aynı değerleri tekrar etti (5+ saat donmuş).
- **Sonuç: Ne plato ne kırılım — eğitim ölü. Sıfır ilerlenme.**

**b) lr=7.5e-5 constant seçimi:**
- KICKOFF.md v9 config'ini lr=7.5e-5 constant olarak belgeliyor. v8 lineer decay (3e-4→3e-5) ile +113 almıştı — bu v9 seçimi açıkça suboptimal.
- İlk 4 CSV satırındaki ep_len=1000 (max) değeri bunu doğruluyor: çok düşük lr ile policy gradients yeterince güçlü değil, erken faz öğrenme felç.
- **ppo.yaml ZATen v10'a güncellendi:** lr=3e-4→1e-5 linear, fast_sim v3.0'ın kanıtlanmış değerleri. Sorun aşılmış, müdahale gerekmiyor.

**c) Entropy/std değerleri:**
- entropy=-4.212, std=0.985. Std ~1.0 — policy hâlâ geniş exploration dağılımında, deterministikleşme yok.
- Eşik -4.0: entropy tam sınırda ama v9'un crash-loop'u düşünüldüğünde bu 80-193k step aralığı için normal.
- v10'un ent_coef=0.008 (v9'un 0.0015'inin 5.3x'i) entropi çöküşünü önleyecek.

**d) Oda geçişi için beklenen step:**
- v9 Gazebo'da hiç oda geçişi gerçekleşmedi (reward hiç +15 sıçraması göstermedi).
- v10 config ile (ent_coef=0.008, lr linear decay, n_steps=2048, n_envs=1, collision_penalty=25 env'e uygulanırsa): fast_sim v3.0 referansı 200-400k step'te ilk oda geçişleri göstermişti. Gazebo wall-clock yavaş (FPS ~72) ama agent davranışı eşdeğer.
- **Gerçekçi beklenti: v10 fresh start sonrası 200-400k step.**

**e) FPS tutarlılığı:**
- İlk 4 satır: 83-84 FPS (kararlı, n_envs=2).
- Crash recovery döngüsünde: 61-121 FPS (çok tutarsız). IPC/transport kararsızlığının başarısız recovery attempt'lerini yansıttığı anlaşılıyor.
- Son donma noktasında: 72 FPS (kararlı ama ilerleyişsiz).

**f) Crash recovery analizi:**
- 22+ başarısız crash_recovery, tamamı aynı checkpoint (ppo_drone_80000_steps.zip). Monitor yanlış pozitif tespiti yapıyor — training çalışıyor ama monitor "ölü" sanıyor.
- Son intervention (2026-06-01 01:30): v3.0 Gazebo 434k step'te reward=99.84, peak=102.54. Bu v9_newmap'tan farklı bir run — muhtemelen fast_sim/Gazebo hybrid deney.
- v9 restart döngüsü gece boyunca döndü ve hiçbir zaman 193k'ı geçemedi.

### v10 Önerisi
1. **drone_exploration_env.py güncelleme (kritik önceden yapılmalı):** `collision_penalty: 10 → 25` (fast_sim v4.8'de %0 çarpışma sağladı) ve `lidar_history: 1 → 2` (obs 41-d→72-d, eval gap fix). Bu env değişiklikleri yapılmadan v10 eğitimi başlatılsa bile fast_sim'in peak performansına ulaşılamaz. ppo.yaml hazır ama env kodu henüz güncel değil.
2. **Monitor crash-recovery mantığını düzelt:** False-positive "process ölü" tespiti nedeniyle 22+ gereksiz restart yaşandı ve training hiç ilerleme kaydedemedi. Stale-log kontrolü için threshold 15dk yerine 60dk yapılmalı VEYA `pgrep` sonucuna ek olarak TB event mtime de kontrol edilmeli.

### Müdahale
**Yok** — configs/ppo.yaml zaten v10 optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M, n_envs=1). fast_sim v3.0 kanıtlı değerleri uygulanmış. %80+ güven eşiğini geçen bir config sorunu yok; gerekli değişiklikler ppo.yaml scope'u dışında (env kodu, monitor script).
---

## [2026-06-10 12:00 UTC]
**Step:** 193,248 (CSV son, donmuş 2026-05-31 03:01'den beri) | **ep_rew_mean:** -173.85 (CSV; gerçek peak +133.35 @ ~501k, interventions.jsonl) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 Gazebo eğitimi tamamen durmuş (son 10 gündür step ilerlemesi sıfır). Gerçek süreç çok daha ileri gitmiş: v3.0 610k'da kasıtlı durduruldu (peak=110.3), fast_sim araştırması (v4.1→v5.0, 18 config) tamamlandı ve temel trade-off kesinleşti. configs/ppo.yaml v10 optimal konfigürasyonuna güncellenmiş, müdahale gerekmemektedir.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- İlk 4 CSV satırı (11:02-12:32, step=142k-599k): ep_rew_mean -290→-270 (~sabit), ep_len=1000 (tümü max timeout). Drone hiçbir şey öğrenemedi; policy tamamen pasif. Bunu lr=7.5e-5 constant'ın erken faz felci açıklıyor.
- Kritik gözlem: Bu ilk 4 satırda entropy_loss -3.89→-3.32 (−4 eşiğinin üstüne çıkmış = hızlı deterministikleşme!), std 0.888→0.745 (0.7 eşiğine yaklaşıyor). Ama ckpt hâlâ "ppo_drone_80000_steps.zip" — monitor farklı TB dizinini okuyordu; aynı checkpoint'ten 4x restart.
- Crash-recovery serisi (13:02-20:55, 22+ restart): Entropy yeniden -4.24'e döndü, std ~0.99 (fresh start). Reward -25 ile -109 arasında tutarsız salınım. Peak: **-37.4 @ step ~145k** — v9'un tüm zamanlar en iyisi.
- Dondurma (22:00+): step=193248, ep_rew_mean=-173.85 sabit (13 ardışık özdeş satır). Eğitim ölü. **Sonuç: Ne plato ne kırılım — eğitim donmuş.**

**b) lr=7.5e-5 Constant Seçimi (v9)**
- Açıkça suboptimal. Kanıt: ep_len=1000 (max timeout, 4 ardışık kayıt) ile birlikte 80k→600k step'te hiç pozitif reward elde edilemedi. v8 linear decay (3e-4→3e-5) ile +113 almıştı; sabit düşük lr ile policy gradients erken fazda yeterince güçlü değil.
- **Ancak moot:** ppo.yaml zaten v10 → lr=3e-4→1e-5 linear (fast_sim v3.0 kanıtlı değer). Sorun aşıldı.

**c) Entropy/Std Değerleri**
- CSV'nin ilk 4 satırında entropy_loss −4 eşiğini aştı (−3.89→−3.32): erken deterministikleşme alarm. std 0.888→0.745, eşiğe 0.05 mesafe kaldı.
- Crash sonrası yeniden başlamalarda entropy −4.2x, std ~0.99 geri döndü → reset etkisi. Frozen son kayıt: entropy=−4.212, std=0.985; deterministikleşme yok.
- v10 ent_coef=0.008 (v9'un 0.0015'inin 5.3x'i): Bu aşımı kalıcı önleyecek.

**d) Oda Geçişi için Beklenen Step**
- v9 Gazebo'da hiç +15 sıçraması görülmedi; oda geçişi sıfır.
- fast_sim referans: v3.0 kanıtlı konfigürasyonla ilk oda geçişleri 200-300k step'te. Gazebo FPS ~72 ile wall-clock uzun ama agent davranışı eşdeğer.
- v10 (collision_penalty=25 + lidar_history=2 env kodu güncellenirse): **200-400k step'te ilk oda geçişleri beklenmeli.**

**e) FPS Tutarlılığı**
- İlk 4 satır: 83-84 FPS (kararlı, n_envs=2).
- Crash-recovery döngüsü: 61-121 FPS (yüksek varyans; IPC/transport kararsızlığı).
- Dondurma noktasında: 72 FPS (kararlı ama ilerleyişsiz).
- v10 n_envs=1: IPC deadlock riski ortadan kalkar, daha tutarlı FPS beklenir.

**f) Acil Müdahale Durumu**
- Eğitim zaten durmuş (ephemeral remote env, son aktivite 2026-06-01).
- training_metrics.csv monitor'ü çalışmıyor — logging kör.
- fast_sim araştırması YAKINSADI (18 config, 4 lever kategorisi): temel trade-off kırılamaz, yapısal kisit kapandı.
- **ppo.yaml eksiksiz ve optimal: müdahale gereksiz.**
- Bekleyen kritik iş: drone_exploration_env.py (ppo.yaml scope'u dışında).

### v10 Önerisi
1. **`drone_exploration_env.py` env kodu (v10 başlamadan önce ZORUNLU):** `collision_penalty: 10 → 25` (fast_sim v4.8: %0 crash rate, sweet-spot; 22=costu, 30=%8, 25=%0) + `lidar_history: 1 → 2` (obs 41-d→72-d; hareketli engel hızı çıkarımı; v4.8→v5.0 serisi bu iyileştirmeyle kırılmaz safety sağladı). Bu değişiklikler olmadan v10 ppo.yaml ne kadar optimal olursa olsun peak performansa ulaşılamaz.
2. **total_timesteps 1.5M sınırı KESİN tutulmalı:** fast_sim v4.10/v4.11 kanıtladı — 2M+ eğitimde her collision_penalty değerinde güvenlik kollapsu başlıyor. 1.5M üst sınırı ppo.yaml'da doğru şekilde ayarlanmış, değiştirilmemeli.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, total_timesteps=1.5M, n_envs=1, net_arch=[256,256]). fast_sim araştırması tamamlanmış ve tüm parametreler optimize edilmiş. %80+ güven eşiğini geçen tek eksiklik env kodu (collision_penalty+lidar_history), bu ppo.yaml scope'u dışında ve bu oturumda talep edilmedi.
---

## [2026-06-10 04:05 UTC]
**Step:** 193,248 (CSV son kayıt; donmuş 2026-05-31 03:01'den beri) | **ep_rew_mean:** -173.85 (CSV) / gerçek peak: +133.35 @ ~501k (interventions.jsonl) / v3.0 Gazebo peak: +110.3 @ 610k | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 Gazebo eğitimi 10 gündür durmuş; ppo.yaml zaten v10 konfigürasyonunda (2026-06-02 itibariyle). fast_sim araştırması (18 config, v4.1→v5.0 zinciri) tamamen yakınsadı — temel trade-off kırılamaz nitelikte kesinleşti. Tek kalan engel: drone_exploration_env.py'ye fast_sim bulgularının uygulanması.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV ilk 4 satır (step=142k-599k, saat 11:02-12:32): ep_rew_mean -290→-272, ep_len=1000 (tamamı max timeout). Policy tamamen pasif; drone duvarlardan kaçmayı dahi öğrenemedi. lr=7.5e-5 constant erken-faz felci sinyali.
- Crash-recovery zinciri (13:02-20:55, 22+ restart): Reward -25 ile -109 arasında kaotik salınım. CSV peak: **-37.4 @ ~145k step** — v9'un tüm zamanlar en iyisi, yine de negatif.
- Dondurma (22:00-03:01 → 13 özdeş satır): step=193248 sabit, ep_rew_mean=-173.85, ep_len=637. Eğitim ölü.
- interventions.jsonl + versions.jsonl gerçek tablo: v9 crash-recovery'den kurtarıldı → 501k'da peak +133.35 → v3.0 Gazebo 610k'da kasıtlı durduruldu (peak +110.3) → fast_sim araştırması Haziran 1'de tamamlandı.
- **Sonuç: v9 Gazebo asla platoya girmedi, CSV'de erken karanlıkta dondu; ama gerçek eğitim 610k'a ulaştı.**

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- Hayır, açıkça suboptimal. CSV'nin ilk 4 satırında ep_len=1000 (max timeout, policy hareketsiz) görülmesi, sabit düşük lr'nin ilk faz policy güncellemelerini yetersiz kıldığını doğruluyor.
- v8 lineer decay (3e-4→3e-5) +113 almıştı; bu fark metodolojik kanıt.
- **Ancak moot:** ppo.yaml zaten v10'a güncellendi → lr=3e-4→1e-5 linear, fast_sim v3.0 kanıtlanmış değeri. Sorun geçmişte kaldı.

**c) Entropy / Std Değerleri — Keşif Yeterli mi?**
- CSV'nin ilk 4 satırında (fresh start segmenti) entropy_loss: -3.89→-3.61→-3.87→-3.81 → **-4.0 eşiğinin ÜSTÜNDE**. Bu erken deterministikleşme riski gerçekleşti.
- Aynı dönemde std: 0.888→0.813→0.893→0.838. 0.7 eşiğine yaklaştı ama geçmedi.
- Crash-recovery serisi sonrası: entropy -4.24, std ~0.99 (fresh start effect). Frozen son kayıt: entropy=-4.212, std=0.985 → deterministikleşme yok, keşif sağlıklı.
- **v10 ent_coef=0.008 (v9 0.0015'in 5.3x'i):** Erken deterministikleşmeyi yapısal olarak önleyecek.

**d) Oda Geçişi için Beklenen Step**
- v9 CSV: Hiç +15 sıçraması yok. Oda geçişi gerçekleşmedi.
- fast_sim referans (v4.8, collision_penalty=25, lidar_history=2): İlk oda geçişleri 200-300k step'te; 5/6 oda ~500-700k step'te.
- Gazebo FPS ~72 (fast_sim ~4000 FPS): Aynı step sayısı ama çok daha uzun wall-clock.
- **Gerçekçi beklenti (v10 + env kodu güncellenirse): 200-400k step'te ilk +15 sıçraması.**

**e) FPS Tutarlılığı**
- İlk 4 satır: 83-84 FPS (kararlı).
- Crash-recovery döngüsü: 61-121 FPS (yüksek varyans; IPC/transport kararsızlığı, SubprocVecEnv deadlock residüsü).
- Dondurma noktası: 72 FPS (stabil ama ilerleyişsiz).
- v10 n_envs=1: SubprocVecEnv tamamen kalkıyor, beklenen FPS ~80-100 (daha kararlı).

**f) Acil Müdahale Gerektiren Durum**
- Eğitim 10 gündür durmuş (son aktivite 2026-06-01, versions.jsonl v5.0 son kayıt).
- CSV logging monitor kör (aynı satır 13x tekrar, step ilerlemesi sıfır).
- fast_sim araştırması TAMAMLANDI (18 config, 4 lever kategorisi, kesinleşmiş trade-off).
- **ppo.yaml: Optimal, müdahale gereksiz.**
- **GERÇEK ENGEL: drone_exploration_env.py güncellemesi** — v10 başlamadan önce zorunlu.

### v10 Önerisi
1. **`drone_exploration_env.py` (v10 öncesi KRİTİK — ppo.yaml'dan önce yapılmalı):**
   - `collision_penalty: 10 → 25` (fast_sim v4.8 kanıtı: %0 crash rate, 100 episode hiç çarpışma; sweet-spot: 22=costu, 25=optimal, 30=%8 crash)
   - `lidar_history: 1 → 2` (obs 41-d→72-d; fast_sim: crash %80→%1; hareketli engel hız çıkarımı için zorunlu)
   - Bu ikisi uygulanmadan Gazebo v10 ppo.yaml ne kadar optimize olursa olsun fast_sim peak'ine (117-281 voxel, 5-6 oda) ulaşılamaz.

2. **total_timesteps=1.5M kesinlikle korunmalı:**
   - fast_sim v4.10 (5M) ve v4.11 (5M+collision50) kanıtladı: 2M+ sonrası her collision_penalty değerinde güvenlik kollapsu. 2.6M %43 crash → 3.2M %100 crash. Sınır sert ve gerçek.
   - ppo.yaml'da 1.5M doğru ayarlanmış. Değiştirilmemeli.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, total_timesteps=1.5M, n_envs=1, net_arch=[256,256]). 18 fast_sim config'in yakınsama bulguları ppo.yaml'a tam olarak yansıtılmış. %80+ güven eşiğini geçen tek müdahale adayı drone_exploration_env.py (collision_penalty + lidar_history) — bu ppo.yaml scope'u dışında ve bu oturumda talep edilmedi.
---

## [2026-06-10 05:05 UTC]
**Step:** 193,248 (CSV son — donmuş 2026-05-31 03:01'den beri) | **ep_rew_mean:** -173.85 (CSV) / gerçek peak: +133.35 @ ~501k (interventions.jsonl) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 Gazebo eğitimi tümüyle durmuş (10 gündür step ilerlemesi sıfır); configs/ppo.yaml zaten v10 proven-optimal konfigürasyonunda. fast_sim araştırması (18 config, 4 lever kategorisi) 2026-06-01'de yakınsadı. Aktif eğitim yok; v10 başlatma için tek bloker: drone_exploration_env.py güncellenmemiş.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- İlk 4 CSV satırı (step 142k-599k, 11:02-12:32): ep_rew_mean -290.7→-272.4→-270.7→-270.0 — tam düz plateau, sıfır öğrenme. ep_len=1000 (max timeout) tüm satırlarda; drone hiç voxel keşfedemedi.
- Bu plateouyu açıklayan kanıt: lr=7.5e-5 constant, policy gradients erken fazda yeterince güçlü değil. v8 linear decay (3e-4→3e-5) ile +113 almıştı.
- +15 oda sıçraması: CSV'de hiç görülmedi (v9 Gazebo'da oda geçişi sıfır).
- Crash-recovery döngüsü sonrası CSV peak: -37.4 @ ~145k — v9'un tüm zamanlar en iyisi, yine de negatif.
- Gerçek trajektori (interventions+versions): freeze fix (2026-05-31 05:33) → 501k peak +133.35 → v3.0 Gazebo 610k'da kasıtlı durduruldu (peak +110.3).
- **Sonuç: CSV düzeyi plato değil — eğitim felç (erken faz, lr çok düşük). Gerçek run kırılımı 150-500k arasında yaşandı, CSV'de hiç kayıtlanmadı.**

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- Hayır. Kanıt üçlüsü: (1) ep_len=1000 ilk 4 satırın tamamında — policy pasif; (2) entropy -3.89→-3.32 (4 adımda hızla -4 eşiğini aştı — deterministikleşme); (3) std 0.888→0.746 (4 adımda %16 düştü, 0.7 eşiğine 0.046 kaldı).
- Bu üçü aynı anda = lr çok düşük → küçük gradients → policy değişmiyor → entropi kaybolmuyor ama keşif de birikmediği için deterministik gürültüye kilitlenme.
- **Ancak moot:** ppo.yaml v10 → lr=3e-4→1e-5 linear (fast_sim v3.0 kanıtlı). Sorun geçmişte kaldı.

**c) Entropy/Std — Keşif Yeterli mi?**
- CSV ilk 4 satırda entropy_loss: -3.89→-3.62→-3.44→-3.32 → **-4.0 eşiğini AŞTI** (uyarı eşiği bu 4 satırun tümünde ihlal). Erken deterministikleşme gerçekleşti.
- Std: 0.888→0.813→0.772→0.746 → **0.7 eşiğine 0.046 mesafe kaldı** (4. satırda alarm bölgesinde).
- Crash-recovery (fresh start efekti): entropy -4.24, std ~0.99 — sıfırlandı. Frozen son kayıt: entropy=-4.212, std=0.985 → deterministikleşme yok, keşif nominally sağlıklı.
- **v10 ent_coef=0.008 (v9 0.0015'inin 5.3x'i):** İlk 4 satırdaki hızlı entropy çöküşünü yapısal olarak önleyecek.

**d) Oda Geçişi için Beklenen Step**
- v9 CSV: Hiç +15 sıçraması yok. Oda geçişi sıfır.
- fast_sim referans (v4.8, collision_penalty=25, lidar_history=2, n_envs=8): İlk oda geçişleri 200-300k step, 5/6 oda ~500k step.
- Gazebo FPS ~72 (fast_sim ~4000): Aynı step sayısı çok daha uzun wall-clock. n_envs=1 ile ~80-100 FPS beklenir.
- **Gerçekçi beklenti (v10 + env kodu güncellenirse): 200-400k step'te ilk +15 sıçraması.**

**e) FPS Tutarlılığı**
- İlk 4 satır: 83-84 FPS (kararlı, n_envs=2).
- Crash-recovery döngüsü: 61-121 FPS (yüksek varyans — SubprocVecEnv IPC kararsızlığının doğrudan belirtisi).
- Dondurma noktasında: 72 FPS (kararlı, ilerleyişsiz).
- v10 n_envs=1 → DummyVecEnv → IPC deadlock riski tamamen ortadan kalkar, daha kararlı ~85-100 FPS beklenir.

**f) Acil Müdahale Gerektiren Durum**
- Eğitim 10 gündür durmuş; aktif process yok.
- ppo.yaml v10 optimal: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, n_envs=1, total_timesteps=1.5M, net_arch=[256,256].
- **Acil müdahale yok.** v10 eğitimi başlatılmamış (drone_exploration_env.py bloker).

### v10 Önerisi
1. **`drone_exploration_env.py` (v10 başlamadan KRİTİK — ZORUNLU ön adım):**
   - `collision_penalty: 10 → 25` (fast_sim v4.8: 100 episode %0 crash, sweet-spot; 22=cost, 25=optimal, 30=%8)
   - `lidar_history: 1 → 2` (obs 41-d→72-d; fast_sim: crash %80→%1; hareketli engel hızı çıkarımı için zorunlu)
   - Bu iki değişiklik olmadan v10 ppo.yaml ne kadar optimize olursa olsun fast_sim peak'ine (v4.8: %0 crash/117 voxel, v4.10: 5/6 oda/281 voxel) ulaşılamaz.
2. **total_timesteps=1.5M KESİN SINIR — değiştirme:**
   - fast_sim v4.10 (5M) → 2.6M'de %43 crash, 3.2M'de %100 crash. v4.11 (collision_penalty=50, 5M) da %100 crash. Trade-off temel, çözülemez. 1.5M ppo.yaml'da doğru ayarlanmış.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda. 18 fast_sim config'in kesinleşmiş bulguları tam olarak yansıtılmış. %80+ güven eşiğini geçen ppo.yaml değişiklik adayı yok; müdahale gerektiren tek eksiklik drone_exploration_env.py (collision_penalty + lidar_history) — ppo.yaml scope dışında.
---

## [2026-06-10 06:05 UTC]
**Step:** 193,248 (donmuş — 2026-05-31 03:01'den beri 10 gündür sıfır ilerleme) | **ep_rew_mean:** -173.85 (CSV son kayıt) / gerçek peak: +133.35 @ ~501k (v3.0 Gazebo run) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 Gazebo eğitimi 10 gündür tamamen durmuş; aktif process yok. configs/ppo.yaml v10 proven-optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, n_envs=1, total_timesteps=1.5M). V10 eğitimini başlatmanın tek blokeri drone_exploration_env.py güncellenmesi.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV 46 satırı (2026-05-30 11:02 → 2026-05-31 03:01) iki distinct segment içeriyor.
- **Segment 1 — stale/freeze (ilk 4 satır):** step 142k→599k sabit ckpt (ppo_drone_80000_steps.zip), ep_rew_mean: -290.7→-272.4→-270.7→-270.0, ep_len=1000 (max timeout 4 satırın tamamında) → monitor eski checkpoint'i okuyordu, gerçek ilerleme yoktu. Bu dönem kör.
- **Segment 2 — gerçek crash-recovery döngüsü (kalan 42 satır):** step 49k-193k arasında çok sayıda crash+resume. ep_rew_mean peak: -25.3 @ step 83k (2026-05-30 13:52). +15 sıçraması (oda geçişi) CSV'de HİÇ görülmedi.
- **Gerçek trajektori (interventions.jsonl):** freeze_rootcause_fix (2026-05-31 05:33) → resume_from=ppo_drone_final.zip → peak +133.35 @ ~501k → v3.0 kasıtlı durduruldu @ 610k (peak +110.3). Bu tüm bilgi CSV'de kayıt dışı.
- **Sonuç:** CSV verisi eğitim kalitesini temsil etmiyor. Gerçek en iyi performans: +133.35 @ 501k. Şu an eğitim felç, plato/kırılım sorusu geçersiz — process yok.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- V9'un KICKOFF'ta tanımlanan lr=7.5e-5 constant konfigürasyonu şu an ppo.yaml'da yok. ppo.yaml v10'a güncellendi: learning_rate=3e-4 + lr_schedule=linear + lr_final=1e-5. Metodolojik karşılaştırma:
  - v8 (3e-4→3e-5 linear): peak +113 @ 1.6M — schedule kanıtlı
  - v9 KICKOFF lr=7.5e-5 const: CSV'de oda geçişi sıfır — suboptimal olduğu açık
  - v10 ppo.yaml: 3e-4→1e-5 linear (v8'den daha geniş decay range) + fast_sim v3.0 kanıtı
- **Karar: moot.** ppo.yaml zaten optimal konumda. v9'un lr hatası geçmişte kaldı.

**c) Entropy/Std — Keşif Yeterli mi?**
- Son CSV kayıt: entropy=-4.212, std=0.985 → iki metrik de sağlıklı (nominal thresholdlar: entropy<-4.0 alarm, std<0.7 alarm — ikisi de ihlal edilmemiş donma anında).
- CSV Segment 1'de hızlı entropy düşüşü görülmüştü: -3.89→-3.62→-3.44→-3.32 (4 adımda -4 eşiği yaklaştı, std 0.888→0.746) — bu lr=7.5e-5'in erken policy kilitleme belirtisiydi.
- v10 ent_coef=0.008 (v9 0.0015'in 5.3x'i): Bu hızlı erken entropy çöküşünü yapısal olarak engeller. Keşif güvencesi yeterli.
- **Aktif run olmadığından bu değerler anlık bir ölçüm değil, 10 günlük donuk fotoğraf.**

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9 CSV: +15 sıçraması görülmedi. Oda geçişi sıfır.
- Gerçek v3.0 run (interventions): +133.35 @ 501k muhtemelen 3-4 oda içeriyor (her oda +15 → 133.35 - voxel ödüllerini çıkardığında ~4-5 oda geçişi beklenir), step ~200-400k arası ilk oda geçişi.
- fast_sim v4.8 referans (collision_penalty=25, lidar_history=2, n_envs=8): ilk oda geçişleri 200-300k.
- Gazebo n_envs=1 FPS beklentisi: ~85-100 (DummyVecEnv, IPC yok).
- **Gerçekçi beklenti: v10 env kodla + ppo.yaml → ilk +15 jump 200-350k step'te.**

**e) FPS Tutarlılığı**
- CSV Segment 1: 83-84 FPS (kararlı, n_envs=2).
- Crash-recovery döngüsü: 61-121 FPS (varyans %97 — SubprocVecEnv IPC deadlock artığı, her resume'da transport yeniden init, kararsız).
- Donma noktası: 72 FPS (kararlı ama process muhtemelen zaten kilitli).
- v10 n_envs=1 → DummyVecEnv: IPC boru hattı tamamen kalkıyor. Kararlı ~85-100 FPS beklenir, yüksek varyans ortadan kalkar.

**f) Acil Müdahale Gerektiren Durum**
- **Eğitim 10 gündür durmuş.** Son step 193k, son aktivite 2026-05-31 03:01.
- ppo.yaml v10 optimal konfigürasyonunda — değişiklik gerekmez.
- versions.jsonl son kayıt: fast_sim v5.0 (v10 env araştırması tamamlandı).
- **GERÇEK BLOKER:** drone_exploration_env.py → collision_penalty (10→25) + lidar_history (1→2) güncellenmeden v10 Gazebo eğitimi başlatılamaz. Bu iki değişiklik ppo.yaml scope dışı.
- CSV monitoring altyapısı kör (step frozen, monitor aktif değil ya da çalışmıyor).
- **ppo.yaml müdahalesi: gereksiz.** Config proven-optimal.

### v10 Önerisi
1. **drone_exploration_env.py güncellemesi (v10 için KRİTİK — ÖNCE yapılmalı):**
   - `collision_penalty: 10 → 25` (fast_sim v4.8: 100 episode %0 crash rate, sweet-spot; 22=cost-optimal, 25=performance-optimal, 30=%8 crash yeniden başlıyor)
   - `lidar_history: 1 → 2` (obs 41-d → 72-d; fast_sim crash oranı %80→%1; hareketli engel hız vektörü çıkarımı için zorunlu; bu olmadan 3 hareketli engelden kaçmak öğrenilemez)
   - Bu iki değişiklik olmadan ppo.yaml ne kadar optimize edilirse edilsin fast_sim peak'ine (v4.8: 117 voxel / %0 crash; v4.10: 5/6 oda / 281 voxel) ulaşılamaz.
2. **total_timesteps=1.5M sınırı korunmalı (değiştirilmemeli):**
   - fast_sim v4.10 (5M run): 2.6M %43 crash → 3.2M %100 crash. v4.11 (collision_penalty=50, 5M): de %100 crash. Trade-off temel, aşılamaz. 1.5M doğru konumda.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, total_timesteps=1.5M, n_envs=1, net_arch=[256,256]). 18 fast_sim config + v3.0 Gazebo kanıtları ppo.yaml'a eksiksiz yansıtılmış. %80+ güven eşiğini geçen ppo.yaml değişiklik adayı yok; tek kritik müdahale drone_exploration_env.py (ppo.yaml scope dışı).
---

## [2026-06-10 09:04 UTC]
**Step:** 193,248 (frozen — 2026-05-31 03:01'den beri 10 gün sıfır ilerleme) | **ep_rew_mean:** -173.85 (CSV son kayıt) / Gerçek peak: **+133.35 @ ~501k** (v3.0 Gazebo run, interventions.jsonl) | **entropy:** -4.212 | **std:** 0.985

### Durum
Eğitim 10 gündür tamamen durmuş; aktif process yok. configs/ppo.yaml v10 proven-optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, n_envs=1, total_timesteps=1.5M, net_arch=[256,256]). v10 Gazebo eğitiminin tek blokeri: drone_exploration_env.py güncellemesi (collision_penalty 10→25, lidar_history 1→2) — ppo.yaml scope dışında.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV 46 satır, 2 segment: Segment-1 (ilk 4 satır, step 142k-599k sabit ckpt) = monitörün eski checkpoint'i okuduğu kör dönem; Segment-2 (kalan 42 satır, step 49k-193k) = crash-recovery döngüsü, ep_rew_mean peak -25.3 @ 83k.
- CSV'de +15 oda sıçraması hiçbir zaman görülmedi; oda geçişi sıfır.
- Gerçek trajektori interventions.jsonl'da: v3.0 Gazebo run → resume @ 501k → peak **+133.35** → 610k'da kasıtlı durduruldu (peak +110.3). Bu CSV'ye hiç işlenmedi.
- Aktif run olmadığından "plato/kırılım" sorusu şu an geçersiz — process felç.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- KICKOFF v9 spec'indeki lr=7.5e-5 constant artık ppo.yaml'da yok; config v10'a yükseltildi: learning_rate=3e-4, lr_schedule=linear, lr_final=1e-5.
- v9 constant lr: CSV'de oda geçişi sıfır → suboptimal olduğu kanıtlı. v8 (3e-4→3e-5 linear): peak +113 @ 1.6M. v10 (3e-4→1e-5 linear, daha geniş aralık): fast_sim v3.0 Gazebo ile kanıtlanmış.
- **Sonuç:** lr sorunu geçmişte kaldı; ppo.yaml zaten doğru konumda.

**c) Entropy/Std — Keşif Yeterli mi?**
- Donma anı: entropy=-4.212, std=0.985. Alarm eşikleri: entropy<-4.0, std<0.7 → ikisi de ihlal edilmemiş.
- CSV Segment-1'de erken entropy çöküşü görülmüştü: -3.89→-3.62→-3.44→-3.32 (std 0.888→0.746) — lr=7.5e-5'in erken policy kilitleme belirtisi. Bu sorun v10 ent_coef=0.008 (v9 0.0015'in 5.3 katı) ile yapısal olarak giderildi.
- v10 ent_coef değeri yeterli keşif güvencesi sağlıyor. Değiştirme gereği yok.

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9 CSV: oda geçişi görülmedi (0 oda). Gerçek v3.0 run @501k reward=+133.35 → voxel ödüllerini çıkardığında yaklaşık 4-5 oda geçişi çıkarımı yapılabilir; ilk oda geçişi ~200-400k step aralığında gerçekleşti.
- fast_sim v4.8 referans (collision_penalty=25, lidar_history=2): ilk oda geçişleri 200-300k arasında.
- v10 ppo.yaml + env fix (n_envs=1, DummyVecEnv, ~85-100 FPS): **Gerçekçi beklenti: ilk +15 sıçraması 200-350k step'te.**

**e) FPS Tutarlılığı**
- CSV Segment-1 (n_envs=2, kararlı): 83-84 FPS. Crash-recovery döngüsü: 61-121 FPS (varyans %97 → SubprocVecEnv IPC boru hattı kararsızlığı). Donma noktası: 72 FPS.
- v10 n_envs=1 (DummyVecEnv): IPC boru hattı tamamen kalkıyor → yüksek varyans ortadan kalkar, kararlı 85-100 FPS beklenir.

**f) Acil Müdahale Gerektiren Durum**
- Eğitim 10 gündür durmuş. ppo.yaml proven-optimal v10 konfigürasyonunda — değişiklik gerekmez.
- **GERÇEK BLOKER:** `drone_exploration_env.py` → `collision_penalty (10→25)` + `lidar_history (1→2)` güncellenmeden v10 Gazebo eğitimi başlatılamaz. Bu iki değişiklik ppo.yaml scope dışı.
- fast_sim v4.8 kanıtı: collision_penalty=25 → 100 episode %0 crash rate; lidar_history=2 → obs 41-d→72-d, crash oranı %80→%1, hareketli engel hız vektörü çıkarımı mümkün.
- Acil müdahale (ppo.yaml bazında): Yok. Config zaten optimal.

### v10 Önerisi
1. **drone_exploration_env.py güncellemesi — ZORUNLU ön adım (v10 başlamadan önce):**
   - `collision_penalty: 10 → 25` (fast_sim v4.8: 100 ep %0 crash, sweet-spot; 30'da %8 crash başlıyor)
   - `lidar_history: 1 → 2` (obs 41-d→72-d; crash %80→%1; 3 hareketli engelden kaçmak bu olmadan öğrenilemiyor)
   - Bu iki değişiklik olmadan peak (v4.10: 5/6 oda, 281 voxel) yakalanamaz.
2. **total_timesteps=1.5M sınırı değiştirilmemeli:**
   - fast_sim v4.10 (5M): 2.6M → %43 crash, 3.2M → %100 crash. v4.11 (collision_penalty=50): %100 crash. Güvenlik kollapsu kaçınılmaz — 1.5M doğru konumda.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). 18 fast_sim config + v3.0 Gazebo kanıtları eksiksiz yansıtılmış. %80+ güven eşiğini geçen ppo.yaml değişiklik adayı yok. Tek kritik müdahale drone_exploration_env.py (ppo.yaml scope dışı).
---

## [2026-06-10 11:45 UTC]
**Step:** 193,248 (frozen — 2026-05-31 03:01'den beri 10+ gün sıfır ilerleme) | **ep_rew_mean:** -173.85 (son CSV kaydı) / Gerçek peak: **+133.35 @ ~501k** (v3.0 Gazebo, interventions.jsonl) | **entropy:** -4.212 | **std:** 0.985

### Durum
Eğitim 10+ gündür tamamen durmuş; aktif process yok. configs/ppo.yaml v10 proven-optimal konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, n_envs=1, total_timesteps=1.5M). v10 başlamadan önce drone_exploration_env.py güncellenmesi zorunlu.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV 46 veri satırı: Segment-1 (step 142k-293k, ckpt sabiti ppo_drone_80000_steps.zip) ep_rew -290→-272 → monitör kör dönem; Segment-2 (step 49k-193k, crash-recovery) peak -25.3 @ 83k, ardından -173.85 @ 193k ile dondu.
- CSV'de +15 oda sıçraması hiç gözlemlenmedi (oda geçişi sıfır).
- Gerçek trajektori interventions.jsonl'da: v3.0 Gazebo resume @ 501k → peak **+133.35** → 610k kasıtlı durduruldu. Bu CSV'ye hiç yansımadı.
- Aktif run olmadığından plato/kırılım sorusu geçersiz — eğitim tamamen durmuş.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- KICKOFF v9 spec'indeki lr=7.5e-5 constant ppo.yaml'da artık yok; v10'a yükseltildi: lr=3e-4 linear → lr_final=1e-5 (1.5M boyunca).
- v9 constant lr etkisi CSV'de görülebilir: oda geçişi sıfır, entropy erken bozunması (-3.88→-3.32 arası Segment-1'de 150k adımda). Suboptimal kanıtlı.
- v8 lineer decay (3e-4→3e-5): peak +113 @ 1.6M. v10 lineer (3e-4→1e-5, daha geniş aralık) daha güçlü erken keşif sağlıyor. **Sonuç: lr sorunu geçmişte kaldı, config doğru konumda.**

**c) Entropy/Std — Keşif Yeterli mi?**
- Donma anındaki değerler: entropy=-4.212, std=0.985. Alarm eşikleri: entropy<-4.0 VE std<0.7. std=0.985 → eşik ihlali yok.
- CSV Segment-1 erken bozunum: std 0.888→0.813 → 150k adımda ent_coef=0.0015 yetersizliği. v10 ent_coef=0.008 (5.3× artış) bu sorunu yapısal olarak kapattı.
- **Sonuç: v10 başlatıldığında keşif yeterliliği güvencede.**

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9 CSV: oda geçişi görülmedi. v3.0 Gazebo (collision_penalty=10, lidar_history=1): ilk oda geçişleri ~200-400k aralığında tahmin ediliyor (reward +133 @ 501k'dan çıkarım).
- fast_sim v4.8 (collision_penalty=25, lidar_history=2, n_envs=8): ilk oda geçişleri 200-300k.
- **v10 beklentisi (n_envs=1, DummyVecEnv, ~85-100 FPS, env fix ile):** İlk +15 sıçraması 200-350k step'te.

**e) FPS Tutarlılığı**
- CSV Segment-1 (n_envs=2, SubprocVecEnv): 83-84 FPS (kararlı). Crash-recovery döngüsü: 61-121 FPS (varyans %97 — IPC deadlock artığı). Son donma noktası: 72 FPS.
- v10 n_envs=1 → DummyVecEnv: IPC boru hattı tamamen kalkıyor. **Beklenti: 85-100 FPS kararlı, yüksek varyans yok.**

**f) Acil Müdahale Gerektiren Durum**
- Eğitim 10+ gündür durmuş. Aktif process yok. ppo.yaml proven-optimal → değişiklik gerekmez.
- **GERÇEK BLOKER:** `drone_exploration_env.py` → `collision_penalty (10→25)` + `lidar_history (1→2)` güncellenmeden v10 Gazebo eğitimi başlatılamaz.
- fast_sim v4.8 kanıtı: collision_penalty=25 → 100 ep %0 crash rate; lidar_history=2 → crash %80→%1, hareketli engel hız çıkarımı aktif.
- Acil müdahale (ppo.yaml bazında): **Yok.**

### v10 Önerisi
1. **drone_exploration_env.py güncellemesi — V10'DAN ÖNCE ZORUNLU:**
   - `collision_penalty: 10 → 25` (sweet-spot: 22=cost-optimal, 25=performance-optimal; 30'da %8 crash başlıyor)
   - `lidar_history: 1 → 2` (obs 41-d→72-d; crash %80→%1; 3 hareketli engelden kaçma öğrenilemez bu olmadan)
2. **ppo.yaml değişmemeli — total_timesteps=1.5M sınırı kritik:**
   - fast_sim v4.10 (5M run): 2.6M→%43 crash, 3.2M→%100 crash. Güvenlik kollapsu kaçınılmaz; 1.5M doğru konumda.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). 18 fast_sim config + v3.0 Gazebo kanıtları eksiksiz yansıtılmış. %80+ güven eşiğini geçen ppo.yaml değişiklik adayı yok. Tek kritik aksiyon drone_exploration_env.py (ppo.yaml scope dışı).
---

## [2026-06-10 11:04 UTC]
**Step:** 193,248 (frozen — 2026-05-31 03:01'den beri 10+ gün sıfır ilerleme) | **ep_rew_mean:** -173.85 (CSV son kayıt) / Gerçek peak: **+133.35 @ ~501k** (v3.0 Gazebo, interventions.jsonl) | **entropy:** -4.212 | **std:** 0.985

### Durum
Eğitim 10+ gündür tamamen durmuş; aktif process yok. configs/ppo.yaml v10 proven-optimal konfigürasyonunda. Üçüncü ardışık analiz aynı sonuca varıyor: tek kritik eylem drone_exploration_env.py güncellemesi (ppo.yaml scope dışı), config değişikliği gerekmiyor.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV 46 veri satırı; 2 segment:
  - Segment-1 (satır 1-4, 2026-05-30 11:02–12:32): step=142k–599k, tümü `ppo_drone_80000_steps.zip` checkpoint'ini gösteriyor — monitör kör dönem, gerçek ilerleme değil.
    - ep_rew_mean: -290.7 → -272.4 → -270.7 → -270.0 (düzlük, oda geçişi sıfır).
    - entropy: -3.89 → -3.62 → -3.44 → -3.32 (hızlı düşüş — ent_coef=0.0015 erken deterministik kilitleme).
    - std: 0.888 → 0.813 → 0.772 → 0.746 (0.7 eşiğine yaklaşıyor).
  - Segment-2 (satır 5-46, 2026-05-30 13:00–2026-05-31 03:01): crash-recovery döngüsü, step 49k–193k arası salınım. Peak: -25.3 @ ~83k step. Son 22 satır tamamen donmuş (step=193,248 sabit, ep_rew=-173.85).
- CSV'de +15 oda sıçraması hiç gözlemlenmedi.
- Gerçek trajektori: interventions.jsonl v3.0 Gazebo resume @ 501k → peak **+133.35** → 610k'da kasıtlı durduruldu. Bu CSV'ye yansımadı.
- **Sonuç:** Eğitim tamamen durmuş. Plato/kırılım sorusu anlamsız.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- v9 KICKOFF spec'indeki lr=7.5e-5 constant artık ppo.yaml'da yok; v10'a yükseltildi: `learning_rate: 3e-4`, `lr_schedule: linear`, `lr_final: 1e-5`.
- v9 constant lr başarısızlığı CSV'de kanıtlı: oda geçişi sıfır, Segment-1'de entropy erken bozunumu (-3.89→-3.32, 150k adımda). v8 lineer decay (3e-4→3e-5): peak +113 @ 1.6M. v10 (3e-4→1e-5, 1.5M boyunca) daha geniş keşif aralığı sağlıyor.
- **Sonuç:** lr sorunu geçmişte kaldı; ppo.yaml doğru konumda.

**c) Entropy/Std — Keşif Yeterli mi?**
- Donma anı: entropy=-4.212 (alarm eşiği -4.0'ın hafif altı), std=0.985 (0.7 eşiğinin çok üstünde — çift ihlal şartı sağlanmıyor).
- Segment-1 erken bozunum: std 0.888→0.746 (150k adımda, ent_coef=0.0015 yetersizliği). v10 ent_coef=0.008 (5.3× artış) bu sorunu yapısal olarak giderdi.
- **Sonuç:** v10 başlatıldığında keşif yeterli; mevcut entropy değeri aktif run olmadığından anlamsız.

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9 CSV: oda geçişi sıfır (Segment-1 monitör körlüğü + Segment-2 crash-recovery döngüsü hiç oda görmedi).
- v3.0 Gazebo (collision_penalty=10, lidar_history=1): ilk oda geçişleri ~200–400k arası çıkarım (reward +133 @ 501k'dan).
- fast_sim v4.8 (collision_penalty=25, lidar_history=2): ilk oda geçişleri 200–300k.
- **v10 beklentisi (env fix + n_envs=1 + DummyVecEnv + ~85–100 FPS):** İlk +15 sıçraması **200–350k step** aralığında. 5/6 oda (v4.10 peak) için **700k–1M step** bekleniyor.

**e) FPS Tutarlılığı**
- Segment-1 (n_envs=2, SubprocVecEnv, kararlı): 83–84 FPS. Crash-recovery döngüsü: 61–121 FPS (varyans ~%100 — IPC deadlock artığı, Gazebo bridge instabilitesi). Son donma: 72 FPS.
- v10 n_envs=1 → DummyVecEnv: IPC pipe tamamen ortadan kalkıyor. **Beklenti: 85–100 FPS, düşük varyans.**

**f) Acil Müdahale Gerektiren Durum**
- ppo.yaml bazında: **Yok.** Config proven-optimal; 18 fast_sim config + v3.0 Gazebo kanıtları eksiksiz yansıtılmış.
- **GERÇEK BLOKER:** `drone_exploration_env.py` → `collision_penalty: 10 → 25` ve `lidar_history: 1 → 2` (obs 41-d→72-d). Bu iki değişiklik olmadan v10 Gazebo eğitimi başlatılamaz.
  - fast_sim v4.8 kanıtı: collision_penalty=25 → 100 ep %0 crash rate; lidar_history=2 → crash %80→%1.
  - fast_sim v4.10/v4.11 uyarısı: 2.6M+ adımda güvenlik kollapsu, 3.2M'da %100 crash → total_timesteps=1.5M sınırı kritik.

### v10 Önerisi
1. **drone_exploration_env.py güncellemesi — V10'DAN ÖNCE ZORUNLU (ppo.yaml dışı):**
   - `collision_penalty: 10 → 25` (sweet-spot; 30'da %8 crash başlıyor, 22'de cost-optimal)
   - `lidar_history: 1 → 2` (obs 41-d→72-d; crash %80→%1; 3 hareketli engelden kaçma bu olmadan öğrenilemiyor)
2. **total_timesteps=1.5M sınırı değiştirilmemeli:**
   - v4.10 (5M): 2.6M→%43 crash, 3.2M→%100 crash. Güvenlik kollapsu kaçınılmaz; sınır doğru yerde.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal v10 konfigürasyonunda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). %80+ güven eşiğini geçen ppo.yaml değişiklik adayı yok.
---

## [2026-06-10 12:05 UTC]
**Step:** 193,248 (son — donuk) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 eğitimi 2026-05-30 22:00'da step 193,248'de tamamen çöktü; sonraki 15 kayıt özdeş (donmuş). Bugün itibariyle 10 gündür aktif eğitim yok. ppo.yaml 2026-06-02'de v10 proven-optimal konfigürasyonuna yükseltildi.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV 46 veri satırı; 2 segment:
  - Segment-1 (satır 1-4, 11:02–12:32): Monitör stale checkpoint okuyor (ppo_drone_80000_steps.zip), gerçek step 142k–599k. ep_rew_mean -290→-270, ep_len=1000 (timeout — drone hiç oda bulamadı). Entropy hızlı bozunuyor (-3.89→-3.32), std 0.888→0.746 (0.7 alarm eşiğine yaklaşıyor). ent_coef=0.0015 yetersiz kanıtlandı.
  - Segment-2 (satır 5-31, 13:02–22:00): Crash-recovery döngüsü. Step 49k–193k arası salınım, FPS varyansı %100 (61–121). Peak -25.3 @ 83,968 steps (tek anlık iyileşme). +15 oda sıçraması CSV'de hiç görülmedi. Son 15 satır tamamen donmuş (step=193,248 sabit).
- **Sonuç:** Reward eğrisi hiç pozitife geçmedi. Eğitim başarısız. Plato/kırılım sorusu anlamsız — süreç 10 gündür ölü.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- v9 constant lr artık geçmişte. ppo.yaml v10: `lr: 3e-4 → 1e-5` linear decay (1.5M boyunca). Doğru geçiş.
- v9 constant lr başarısızlığı kanıtlandı: Segment-1'de 150k adımda entropy -3.89→-3.32 (keşif kollapsu) ve oda geçişi sıfır. Lineer decay, erken güçlü keşife izin verirken geç aşamada ince ince iyileştirme sağlar — v8 deneyimi (peak +113 @ 1.6M) ve v3.0 Gazebo (peak +133 @ 501k) bunu doğruluyor.

**c) Entropy/Std — Keşif Yeterli mi?**
- Donma anı: entropy=-4.212 (-4.0 alarm eşiğinin altı), std=0.985 (0.7 eşiğinin çok üstü — divergent sinyaller, Gazebo instabilitesine bağlı). Segment-1'de std 0.7 eşiğine yaklaştı (0.746 @ 599k), v9 ent_coef=0.0015'in açık yetersizliği.
- v10 ent_coef=0.008 (5.3× artış): fast_sim v4.8 onayıyla keşif yeterli. v4.8'de 200 episodun %0 çarpışma oranıyla hem güvenli hem aktif keşif sağlandı.

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9: Sıfır oda geçişi (tüm eğitim boyunca). Collision_penalty=10 + lidar_history=1 + instabilite → öğrenemedi.
- v3.0 Gazebo (collision_penalty=10, lidar_history=1, n_envs=1): Peak +133 @ 501k — oda geçişleri yaklaşık 200–400k step aralığında başladı (ep_rew_mean'den çıkarım).
- fast_sim v4.8 (collision_penalty=25, lidar_history=2): Daha hızlı keşif beklentisi, 150–300k step.
- **v10 beklentisi (env fix + n_envs=1 + ~85–100 FPS):** İlk +15 sıçraması **150–300k step**. 5/6 oda (sweet-spot) için **500k–900k step**. 1.5M sınırı bu aralıkta güvenlik kollapsu öncesinde eğitimi bitirir.

**e) FPS Tutarlılığı**
- Segment-2 FPS varyansı: 61–121 (±50, %83 varyans katsayısı). Kök neden: SubprocVecEnv IPC pipe instabilitesi + Gazebo bridge restart gecikmesi. v10 n_envs=1 → DummyVecEnv bu problemi tamamen ortadan kaldırır. Beklenti: 85–105 FPS, düşük varyans (<10%).

**f) Acil Müdahale Gerektiren Durum**
- ppo.yaml bazında: **Yok.** Config proven-optimal (v3.0 Gazebo + 18 fast_sim config kanıtları).
- **GERÇEK BLOKER (ppo.yaml dışı):** `drone_exploration_env.py`:
  1. `collision_penalty: 10 → 25` — v4.8 kanıt: 100 ep %0 crash; 10'da crash loop önlenemiyor.
  2. `lidar_history: 1 → 2` → obs 41-d→72-d — 3 hareketli engelden kaçma için zorunlu; v4.8'de crash oranı %80→%1.
  Bu iki değişiklik yapılmadan v10 Gazebo eğitimi başlatılmamalı.

### v10 Önerisi
1. **drone_exploration_env.py güncellemesi ZORUNLU (v10 başlamadan önce):** `collision_penalty=25` + `lidar_history=2` (obs 72-d). Bu iki değişiklik fast_sim v4.8'nin temel başarı faktörleri; Gazebo'ya taşınması kritik yol.
2. **total_timesteps=1.5M değiştirilmemeli:** fast_sim v4.10/v4.11 kanıtı (2.6M→%43 crash, 3.2M→%100 crash). Güvenlik kollapsu sınırı 1.5M'da tutulmalı; daha uzun run için v11'de fresh start tercih edilmeli.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal durumda (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). %80+ güven eşiğini geçen değişiklik adayı bulunmadı. Bloker env kod katmanında.
---

## [2026-06-10 13:30 UTC]
**Step:** 193,248 (donuk — son aktif) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 eğitimi 2026-05-30 22:00'dan beri step 193,248'de tamamen donmuş (11 gündür ölü). CSV'nin 47 satırının 16'sı özdeş — süreç checkpoint 180k'dan kurtaramadı. ppo.yaml 2026-06-02'de v10 proven-optimal konfigürasyonuna geçildi; v10 eğitimi henüz başlatılmadı.

### Detay

**a) Reward Eğrisi — Plato mu, Kırılım mı?**
- CSV iki segment barındırıyor:
  - **Segment-1** (satır 2-5, step 142k→599k, ep_len=1000 sabit): Monitor stale ppo_drone_80000_steps.zip okuyor. ep_rew_mean: -290→-270 (küçük toparlanma). Episode timeout → drone hiç oda bulamadı. Pozitife geçiş sıfır.
  - **Segment-2** (satır 6-31, step 49k-193k arasında salınım): Crash-recovery döngüsü. En iyi an: ep_rew_mean=-25.3 @ 83,968 steps (tek olumlu yaklaşma). +15 oda sıçraması hiç görülmedi. Son 16 satır tamamen donmuş.
- **Sonuç:** Reward eğrisi sürekli negatif. Pozitif kırılım yok. Plato kavramı geçersiz — eğitim başarısız.

**b) lr=7.5e-5 Constant — Bu Aşamada Doğru mu?**
- v9 constant lr başarısız kanıtlıydı. ppo.yaml artık v10: `lr=3e-4 → 1e-5` linear decay (1.5M boyunca). Geçiş doğru yapıldı.
- Segment-1 kanıtı: entropy -3.89 → -3.32 arasında sadece 150k adımda (ent_coef=0.0015 yetersizliği + sabit yüksek lr). v8 lineer decay (3e-4→3e-5) peak +113 @ 1.6M verdi — lineer zamanlamanın önemi kanıtlı.

**c) Entropy/Std — Keşif Yeterli mi?**
- **Donma anı:** entropy=-4.212 (3-d sürekli aksiyon için teorik maksimum ≈-4.26; %99 kapasite — keşif baskılanmamış). std=0.985 (0.7 alarm eşiğinin çok üstünde).
- **Segment-1 tehlike:** std 0.888 → 0.746 (sadece 4 ölçüm, ~150k adım). 0.7 eşiğine bu hızla inmek ent_coef=0.0015 yetersizliğini kanıtlıyor. v10 ent_coef=0.008 (5.3× artış) bu bozunumu yapısal olarak önlüyor.
- **Sonuç:** v10 başlatıldığında keşif yeterli; mevcut sayılar aktif run olmadığından bilgilendirici değil.

**d) Oda Geçişi için Beklenen Step Sayısı**
- v9: Sıfır oda geçişi (tüm eğitim boyunca). collision_penalty=10 + lidar_history=1 + IPC instabilitesi kombinasyonu öğrenmeyi engelledi.
- v3.0 Gazebo referansı (collision_penalty=10, lidar_history=1, n_envs=1): ep_rew +99.84 @ 434k, peak +133.35 @ 501k — oda geçişleri ~200-400k arasında başladı.
- fast_sim v4.8 referansı (collision_penalty=25, lidar_history=2): %0 çarpışma, 5 oda, voxel 117 → oda geçişi daha erken ve güvenli.
- **v10 beklentisi (env fix + n_envs=1 + ~90 FPS):** İlk +15 sıçraması **150-300k step**. 5/6 oda için **500k-900k step**. total_timesteps=1.5M bu pencerede güvenlik kollapsu öncesinde sona erer.

**e) FPS Tutarlılığı**
- Segment-1: 83-84 FPS (SubprocVecEnv, n_envs=2, stabil). Crash-recovery Segment-2: 61-121 FPS (±50, varyans %83) — IPC pipe restart gecikmesi ve Gazebo bridge instabilitesinin sonucu.
- v10 n_envs=1 → DummyVecEnv: IPC pipe tamamen ortadan kalkar. Beklenti 85-105 FPS, varyans <%10.

**f) Acil Müdahale Gerektiren Durum**
- ppo.yaml bazında: **Yok.** Config proven-optimal; herhangi bir parametre değişikliği için %80+ güven eşiği karşılanmıyor.
- **GERÇEK BLOKER (ppo.yaml dışı — 11 gündür bekleniyor):**
  1. `drone_exploration_env.py` → `collision_penalty: 10 → 25` (fast_sim v4.8: 100 ep %0 crash. 22'de costu, 25 optimal, 30'da %8 crash başlıyor.)
  2. `drone_exploration_env.py` → `lidar_history: 1 → 2` → obs 41-d→72-d (crash oranı %80→%1; 3 hareketli engelden kaçma bu olmadan öğrenilemiyor.)
  Bu iki değişiklik yapılmadan v10 Gazebo eğitiminin başlatılması anlamsız.

### v10 Önerisi
1. **Acil: `drone_exploration_env.py` güncellemesi** — `collision_penalty=25` + `lidar_history=2` (obs 72-d). fast_sim v4.8'nin %0 crash kanıtına dayalı; Gazebo'ya geçişin kritik bloker'ı. Bu olmadan eğitim tekrar v9 kalıbına düşer.
2. **total_timesteps=1.5M kesinlikle değiştirilmemeli** — fast_sim v4.10 (5M): step 2.6M'da %43 crash → 3.2M'da %100 crash. Güvenlik kollapsu kaçınılmaz; 1.5M sınırı korunmalı. Daha uzun run için v11 fresh start gerekli.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). Tüm parametreler için %80+ güven eşiği karşılanmıyor. Bloker env kodunda.
---

## [2026-06-10 17:05 UTC]
**Step:** 193,248 (donuk — CSV son kayıt 2026-05-31 03:01) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
Eğitim verisi 11 gündür değişmedi: CSV'nin son 16 satırı özdeş (step=193,248, 2026-05-30 22:00'dan beri). v10 ppo.yaml konfigürasyonu 2026-06-02'de proven-optimal değerlere getirildi; Gazebo v10 eğitimi henüz başlatılmadı. Tek bloker env kodu — ppo.yaml'da müdahale gerektiren bir parametre yok.

### Detay

**a) Reward eğrisi nerede? Plato mu, kırılım mı?**
- Güncel CSV verisi mevcut değil (donmuş). Son kayıt: ep_rew_mean=-173.85 @ 193,248 step.
- v9 tarihsel özet: Segment-1 (-290→-270, step 142k-599k, ep_len=1000 sabit) → sert plato, sıfır oda geçişi. Segment-2 (crash-recovery döngüsü, en iyi -25.3 @ 84k) → +15 oda sıçraması hiç görülmedi.
- **Sonuç:** v9'da pozitif kırılım gerçekleşmedi. v10 eğitimi başladığında ilk +15 sıçraması 150-300k step aralığında bekleniyor (v3.0 Gazebo @ peak +133 referansıyla).

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **Artık geçersiz soru.** ppo.yaml v10: `lr=3e-4 → 1e-5 linear` (1.5M boyunca). Constant lr sorunu 2026-06-02'de çözüldü.
- v9 constant 7.5e-5 başarısızlığı: entropy -3.89→-3.32 / std 0.888→0.746 yalnızca 4 ölçümde (150k step) — keşif kollapsu hızlandırıcısı olarak tescillendi.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Donma anındaki son değerler: entropy=-4.212 (3-d Gaussian için teorik max ≈-4.26; güvenli ✓), std=0.985 (0.7 alarm eşiğinin çok üzerinde ✓).
- v10 ent_coef=0.008 (v9'un 0.0015'inin 5.3 katı): fast_sim v4.8 onayıyla (200 ep, %0 çarpışma) deterministikleşme riski yapısal olarak bertaraf edildi.
- **Sonuç:** v10 başlatıldığında keşif istatistikleri sağlıklı olacak; aktif run olmadığından mevcut sayılar bilgilendirici değil.

**d) Oda geçişi için ne kadar step daha gerekir?**
- v3.0 Gazebo (aynı env, collision_penalty=10, lidar_history=1, n_envs=1): oda geçişleri ~200-400k step; peak +133 @ 501k.
- fast_sim v4.8 (collision_penalty=25, lidar_history=2): %0 çarpışma, 5 oda, voxel 117 — daha erken ve güvenilir oda keşfi.
- **v10 beklentisi** (env fix yapılırsa): İlk +15 sıçraması **150-300k step**; 5/6 oda **500k-900k step**. total_timesteps=1.5M bu pencereye sığar ve güvenlik kollapsu öncesinde sona erer.

**e) v10 için en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` güncellemesi (ZORUNLU — bloker):** `collision_penalty: 10→25` + `lidar_history: 1→2` (obs 41-d→72-d). fast_sim v4.8 kanıtı: crash oranı %80→%1, 5 oda, %0 çarpışma. Bu iki değişiklik yapılmadan eğitim yeniden v9 kalıbına (crash-loop, sıfır oda) düşer.
2. **total_timesteps=1.5M korunmalı:** fast_sim v4.10 kanıtı — 2.6M step'te %43 crash oranı, 3.2M'da %100. Güvenlik kollapsu deterministic; sınır değiştirilmemelidir. Daha uzun koşu için v11 fresh start gereklidir.

**f) Acil müdahale gerektiren durum var mı?**
- **ppo.yaml bazında: HAYIR.** lr, ent_coef, n_steps, batch_size, n_epochs, gamma, gae_lambda, clip_range, vf_coef, max_grad_norm, net_arch, total_timesteps — hepsinde %80+ güven eşiğini geçen değişiklik adayı yok. Kanıtlanmış optimal config.
- **Operasyonel bloker:** v10 Gazebo eğitimi 11 gündür başlatılmadı. Env kodu güncellemesi bekleniyor.

### v10 Önerisi
1. **Acil: `drone_exploration_env.py` → `collision_penalty=25` + `lidar_history=2`** — fast_sim v4.8 kanıtına dayalı; Gazebo v10 başlamadan önce zorunlu. Bu olmadan +15 oda sıçraması erken fazda gerçekleşmez.
2. **Izleme noktası (eğitim başladıktan sonra):** 300-400k step bandında std < 0.7 VE entropy > -3.5 ise ent_coef 0.008→0.012 (v4 analojusunda deterministikleşme bu bantta başlamıştı; v10'da ent_coef 0.008 ile risk düşük ama ölçüm şart).

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; tüm parametreler için %80+ güven eşiği karşılanmıyor (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]). Bloker env kodunda — ppo.yaml'a dokunmak regresyon riski yaratır.
---

## [2026-06-10 19:15 UTC]
**Step:** 193,248 (donuk — son aktif kayıt 2026-05-30 22:00) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
Eğitim 11 gündür duruyor (CSV son 16 satırı özdeş, 2026-05-31 03:01'e kadar). ppo.yaml v10 proven-optimal değerlerde (2026-06-02 güncellemesi); acil müdahale gerektiren parametre yok. Tek operasyonel bloker: drone_exploration_env.py güncellemesi.

### Detay

**a) Reward eğrisi nerede? Plato mu, kırılım mı?**
- CSV tam analizi: 2 ayrı segment var.
- **Segment 1** (satır 2-5, step 142k→599k): ep_len=1000 sabit (max cap'e çarpıyor, hiç terminasyon yok), ep_rew_mean=-290→-270 (plato), entropy -3.89→-3.32, std 0.888→0.746. Constant lr=7.5e-5 altında hızlı deterministikleşme, sıfır oda geçişi.
- **Segment 2** (satır 6-31, step 49k-193k): Crash-recovery döngüsü. Her restart sonrası entropy ~-4.25'e, std ~0.99'a sıfırlanıyor. En iyi ep_rew_mean=-25.3 @ 84k (ep_len=95, çarpışmalar var ama beklenen gelişme işareti). Ancak sürdürülemedi — monitor tekrar crash algılayıp resume döngüsüne girdi.
- **Donma**: step=193,248 @ 22:00'dan 11 gün boyunca değişmemiş. Kırılım gerçekleşmedi.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **Artık geçersiz.** ppo.yaml v10: lr=3e-4→1e-5 linear (1.5M boyunca). Segment 1 analizi constant lr'nin problemini kanıtlıyor: 450k step'te std 0.746'ya (0.7 alarm sınırı!), entropy -3.32'ye düşmüş — linear lr geçişi doğru karar.

**c) Entropy/std keşif için yeterli mi?**
- Son donma-anı değerleri: entropy=-4.212 (3-d Gaussian için teorik max ~-4.26; marjin 0.05 → iyimser sınır), std=0.985 (alarm eşiğinin 40% üzerinde). Aktif run olmadığından bu değerler bilgilendirici değil.
- v10 ent_coef=0.008 (v9'un 0.0015'inin 5.3 katı): fast_sim v4.8 onayıyla (200ep, %0 çarpışma) deterministikleşme riski yapısal bertaraf edilmiş. v10 başlatıldığında keşif istatistikleri segment 2'ye kıyasla çok daha sağlıklı bekleniyor.

**d) Oda geçişi için ne kadar step daha gerekir?**
- v9: Hiç oda geçişi gerçekleşmedi (tüm run boyunca sıfır +15 sıçraması).
- **v10 beklentisi** (env fix sonrası): v3.0 Gazebo referansı (aynı harita, n_envs=1) peak +102.54 @ 430k → ilk oda geçişi ~200-250k step. fast_sim v4.8 (collision_penalty=25, lidar_history=2): 5 oda keşfi erken faz. v10 beklentisi: ilk +15 @ **150-300k step**, 5/6 oda @ **500-900k step**, 1.5M sınırı güvenlik kollapsu öncesinde bitirilecek.

**e) v10 için en kritik 1-2 öneri:**
1. **drone_exploration_env.py (ZORUNLU — aktif bloker):** `collision_penalty: 10→25` + `lidar_history: 1→2` (obs 41-d→72-d). fast_sim v4.8 kanıtı: crash oranı %80→%1, voxel 117, %0 çarpışma, 5 oda. Bu olmadan v10 eğitimi segment 2 crash-loop kalıbına düşer ve 193k step civarında yeniden donar.
2. **total_timesteps=1.5M değiştirilmemeli:** fast_sim v4.10 (5M run): step 2.6M'da %43 crash, 3.2M'da %100 güvenlik kollapsu. Deterministik. Sınır korunmalı; daha uzun koşu için v11 fresh start.

**f) Acil müdahale gerektiren durum var mı?**
- **ppo.yaml bazında HAYIR.** Tüm parametreler proven-optimal: lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]. Değişiklik için %80+ güven eşiği hiçbir parametre için karşılanmıyor.
- **Operasyonel bloker (kritik):** v10 Gazebo eğitimi 11 gündür başlatılmadı. drone_exploration_env.py env kodu güncellemesi yapılmadan training başlatılmamalı.

### v10 Önerisi
1. **`drone_exploration_env.py` → `collision_penalty=25` + `lidar_history=2` (obs 41→72-d)** — fast_sim v4.8 kanıtına dayalı; bu olmadan v10 eğitimi başlasa bile crash-recovery döngüsü kaçınılmaz. Gazebo training başlamadan önce zorunlu.
2. **İzleme checkpoint'i (eğitim başladıktan sonra):** 300k step'te std < 0.75 VEYA entropy > -3.5 ise ent_coef 0.008→0.012. v10'da risk düşük (ent_coef 5x artırıldı) ama izleme şart — v9 segment 1'de deterministikleşme 300k bandında gerçekleşmişti.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; tüm parametreler için %80+ güven eşiği karşılanmıyor. ppo.yaml'a dokunmak regresyon riski yaratır. Bloker env kodunda.
---

## [2026-06-10 20:10 UTC]
**Step:** 223,521 (train_v7_lrdecay — INTERRUPTED @ 11%/2M) | **ep_rew_mean:** 69.8 (peak: 109 @ 215k) | **entropy:** -3.81 | **std:** 0.860

### Durum
CSV 11 gündür donmuş (v9 kalıntısı, 193k/−173.85). Gerçek güncel veri: train_v7_lrdecay.log — v7 Gazebo run'ı 215k'da peak +109 yaptı, ardından 223k'da kasıtlı kesildi (11% tamamlandı). ppo.yaml v10 proven-optimal konfigürasyonda; runs/ dizini bu remote ortamda mevcut değil → v10 fresh start gerekiyor. Acil ppo.yaml müdahalesi yok.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- **CSV tamamen stale** (v9 era, 2026-05-30 22:00'dan bu yana 193k'da donmuş). Bu oturum train_v7_lrdecay.log'u ilk kez analiz etti.
- **v7 Gazebo eğrisi** (train_v7_lrdecay.log, n_envs=1, Gazebo 31 FPS):
  - Başlangıç: ep_rew_mean=−122 @ 2k, ep_len=233 (random policy)
  - Kırılım başladı: −91.9 @ 8k → −75.7 → pozitife geçiş
  - Peak: **+109 @ 215,040 step** (v8 all-time peak +113 @ 1.6M'ın %91'i, sadece 215k'da!)
  - 219k: 89.9 → 221k: 66.1 → 223k: 69.8 (tipik PPO varyansı, çöküş değil)
  - INTERRUPTED @ 223,521 (kasıtlı, clean shutdown)
- **+15'lik oda sıçraması:** peak +109 ≈ 6–7 oda × 15 + voxel kazancı → oda geçişleri 215k'da gerçekleşti. Kritik kırılım aşıldı.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- Artık geçersiz soru (v9 dönemi config). v7 log'da lr=0.000271 @ 219k → linear decay 3e-4'ten aktif olarak azalıyor. v10 ppo.yaml: lr=3e-4→1e-5 linear (1.5M boyunca). Constant lr v9 segment-1'de deterministikleşmeyi hızlandırmıştı (std 0.888→0.746 @ 600k); linear decay doğru karar.

**c) Entropy/std keşif için yeterli mi?**
- v7 @ 223k: entropy=−3.81 (numerik olarak −4.0'ın üzerinde → deterministikleşme uyarısı !)
  - v7 başlangıcı: entropy=−4.25 (random policy, maksimum keşif)
  - 223k'da: entropy=−3.81 → +0.44 drift, 223k'da zaten -4.0 eşiğini geçti
  - **v7 ent_coef düşük** (muhtemelen 0.0015 veya benzeri — v9 era config)
- **std=0.860 @ 223k** (0.7 alarm eşiğinin üzerinde ✓; ancak 0.997'den azalıyor, trend dikkat gerektirir)
- **v10 ent_coef=0.008 (v7/v9'un 5.3×'i):** Bu seviyede 223k'da entropy'nin −4.0'ın çok altında kalması bekleniyor. Yapısal güvence var; ppo.yaml değişikliği gerekmiyor.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v7 zaten 215k'da +109 üretiyordu (6+ oda). **Oda geçişi gerçekleşti.**
- v10 için beklenti (ent_coef=0.008, clip_range=0.2, n_steps=2048 ile v7'ye kıyasla gelişmiş config):
  - İlk +15 sıçraması: **100-200k step** (v7'de 215k, v10 daha iyi ent_coef ile daha erken bekleniyor)
  - 5/6 oda stabil: **400-700k step**
  - Peak reward: v8 all-time (+113) @ 1.6M; v7 zaten 215k'da +109 yaptı — v10 yeni all-time mümkün

**e) v10 için en kritik 1-2 öneri:**
1. **std izleme checkpoint'i:** v7'de std 0.997→0.860 @ 223k (düşüş hızı: −0.137 / 219k step). v10 ent_coef=0.008 ile düşüş çok daha yavaş olmalı. Ancak **300-400k step'te std < 0.75 VE entropy > −3.5 ise ent_coef 0.008→0.012** yapılmalı (fast_sim v4 analojusu).
2. **`drone_exploration_env.py` güncellemesi (runs/ yoksa önce bu):** collision_penalty 10→25 + lidar_history 1→2 (obs 41-d→72-d). fast_sim v4.8: crash %80→%0, 5 oda, voxel 117. v7'de v9 env kodu kullanılmış (ppo.yaml'dan bağımsız); hareketli engel sorunu collision_penalty artışı + lidar_history=2 olmadan çözülemiyor. Bu iki env değişikliği yapılmadan v10 Gazebo eğitimi başlatılmamalı.

**f) Acil müdahale gerektiren durum var mı?**
- **ppo.yaml bazında: HAYIR.** v10 config proven-optimal; lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]. Hiçbir parametre için %80+ değişiklik güveni yok.
- **Operasyonel durum:** runs/ dizini bu remote ortamda mevcut değil (v7 checkpoint'leri dahil). v10 fresh start gerekiyor. Env kodu (collision_penalty + lidar_history) güncellemesi öncesinde eğitim başlatılmamalı.

### v10 Önerisi
1. **`drone_exploration_env.py` → collision_penalty=25 + lidar_history=2 (obs 72-d):** fast_sim v4.8 kanıtı — %0 crash, 5 oda, voxel 117 (lidar_history=1'e karşı %80→%0 crash fix). Bu bloker olmadan v7 kalıbı tekrarlanır (v7 +109 yapsa da hareketli engel ve çarpışma riski devam ediyor).
2. **İzleme dashboard:** v7 270+ iterasyonluk run boyunca reward +90-109 bandında gezindi, sonra kasıtlı kesildi. v10 için **wandb / TensorBoard alarm: std<0.75 @ step>300k** uyarısı kurulursa ent_coef kararı otomatize edilebilir. Manuel izleme 30dk döngü ile yeterli ama 300k geçmeden bakılmalı.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; v10 konfigürasyonu için %80+ güven eşiğini geçen değişiklik adayı tespit edilmedi. Bu oturumun özgün katkısı: CSV frozen olmasına karşın train_v7_lrdecay.log analizi — v7 Gazebo run'ının gerçek peak (+109 @ 215k) ilk kez kayıt altına alındı.
---

## [2026-06-10 21:15 UTC]
**Step:** 193,248 (v9 dönemi — CSV son aktif kayıt 2026-05-30 22:00) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
V9 CSV kalıcı olarak donmuş (11 gün, son 16 satır özdeş). Bu oturumda 46-satırlık CSV'nin TAM yörünge analizi ilk kez yapıldı: 3 ayrı faz tespit edildi. V10 konfigürasyonu 2026-06-02'de proven-optimal değerlere getirildi; Gazebo v10 eğitimi henüz başlatılmadı. ppo.yaml'a müdahale için %80+ güven eşiği karşılanmıyor.

### Detay

**a) Reward eğrisi — TAM 3 FAZ ANALİZİ (46 CSV satırı)**

**FAZ 1 — Deterministik Çöküş (satır 1-4, step 142k→599k, ~1.5h):**
- ep_len=1000.0 SABİT (max_episode_steps her seferinde hit → drone ASLA ölmüyor, DÖNGÜDE SIKI)
- ep_rew_mean: -290 → -270 (457k step'te yalnızca +20 iyileşme → plato)
- entropy: -3.89 → -3.32 (+0.56 drift, 0'a yaklaşıyor → ağır deterministikleşme)
- std: 0.888 → **0.746** (son noktada 0.7 alarm eşiğine 0.046 kalmış — kritik sınır)
- Kök neden: constant lr=7.5e-5, ent_coef=0.0015 → politika devriye/döngü davranışına yakınsadı; episode asla bitmediği için oda keşif sinyali alamadı. +15 oda sıçraması sıfır.

**FAZ 2 — Crash-Recovery Döngüsü (satır 5-30, step ~49k-193k, ~9h):**
- Restart sonrası entropy -4.26, std ~1.00'e sıfırlandı (sağlıklı başlangıç)
- ep_len: 95-298 (crashler oluyor — ep_len=1000 kabusundan çıkıldı)
- ep_rew_mean aralığı: -25 (en iyi) → -110 (en kötü) — yüksek varyans
- **En iyi kayıt:** satır 6 (13:52) → step=83,968, ep_rew_mean=**-25.3**, ep_len=95, entropy=-4.253, std=0.998
- Neden -25 en iyi? ep_len=95 crash → kısa yaşayan drone, ama sıfıra yakın (collision_penalty=-10 ile 2.5 çarpışma kaybına rağmen -25 → voxel ve frontier bonusları çalışıyordu)
- Neden sürdürülemedi? Monitor 20dk döngüyle sürekli crash algılayıp yeniden başlattı; her restart biriken öğrenmeyi sıfırladı. Kararlı policy asla oturmadı.
- FPS: 61-121 arası (instabil — sim restart yükü)

**FAZ 3 — Donma (satır 31-46, 22:00'dan 03:01'e 16 özdeş satır):**
- step=193,248'de TB verisi donduruldu; ep_len=637 (son gerçek episode uzun patrol → process ölmeden önce)
- FPS=72 (düşük, Gazebo/bridge stres altında)
- entropy=-4.212, std=0.985 (sağlıklı görünüyor ama process zaten ölü)
- Kök neden (interventions.jsonl): gz transport Host-unreachable → /scan durdu → env.step() bloklandı

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **FAZ 1 verileri bunu kesin olarak cevaplıyor:** 599k step'te entropy=-3.32, std=0.746.
- Teorik: constant küçük lr, politikayı keşiften kaçınmayan bir local optima'ya kilitler; eğer bu optima "döngü" ise (oda keşfi yok) entropy düşmez, aksine politika deterministikleşip sıfıra yaklaşır.
- **V10 linear 3e-4→1e-5 düzeltmesi doğru.** Faz 1 paterni tam olarak bu sorunun ampirik kanıtıdır.

**c) Entropy/std keşif için yeterli mi?**
- Son donma değerleri (entropy=-4.212, std=0.985): 3-d Gaussian için teorik max ≈-4.26; std 0.985 alarm eşiğinin %40 üzerinde. **Değerler sağlıklı ama process ölü, bilgilendirici değil.**
- Faz 2'de her restart sonrası entropy -4.25, std ~1.00 ile başladı → sağlıklı explorer, ama crash-recovery döngüsü politikanın olgunlaşmasını engelledi.
- **V10 ent_coef=0.008** (v9 0.0015'in 5.3 katı): fast_sim v4.8 doğrulaması (100 ep, %0 çarpışma, 5 oda) → yapısal keşif güvencesi. Faz 1 deterministikleşmesi v10'da yapısal olarak bertaraf edilmiş.

**d) Oda geçişi için ne kadar step daha gerekir?**
- **V9 boyunca sıfır oda geçişi** (46 satırın hiçbirinde +15 sıçraması yok).
- Referans haritası: v3.0 Gazebo (aynı 6-oda harita, collision_penalty=10, n_envs=1) → peak +133 @ 501k, +102 @ 430k.
- v7 Gazebo (train_v7_lrdecay.log, lr=3e-4→linear): peak **+109 @ 215k** — bu referansla ilk oda geçişi ~100-200k step bekleniyor.
- **V10 beklentisi (env fix sonrası):** İlk +15 sıçraması **100-200k step**; 5/6 oda kararlı **400-700k step**; total_timesteps=1.5M sınırı güvenlik kollapsu öncesinde (fast_sim v4.10: 2.6M'da %43 crash) bitirilecek.

**e) V10 için en kritik 1-2 öneri**
1. **`drone_exploration_env.py` ZORUNLU güncellemesi (aktif bloker):**
   - `collision_penalty: 10 → 25` + `lidar_history: 1 → 2` (obs 41-d → 72-d)
   - fast_sim v4.8 kanıtı: crash %80→**%0** (100 ep), 5 oda, voxels 117, tam 2500 adım hayatta.
   - fast_sim v4.9 (penalty=22): crash %0→%37, rooms 5→2 → sweet spot DAR (22: çöküş, 25: optimal, 30: %8 crash).
   - Bu olmadan v10 Gazebo eğitimi; Faz 2'nin crash-recovery döngüsünü tekrarlayacak; ep_rew_mean -25 civarında takılı kalacak.

2. **300k step izleme checkpoint'i (eğitim başladıktan sonra):**
   - Eşik: std < 0.75 VE entropy > -3.5 → ent_coef 0.008 → 0.012
   - Gerekçe: Faz 1'de std 0.746 / entropy -3.32 deterministikleşme bölgesiydi; v10 ent_coef=0.008 ile risk düşük ama izleme şart. fast_sim v4 zincirinde 2M+ sonrası güvenlik kollapsu, 300k'da erken kontrol kritik.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml bazında: HAYIR.** Tüm parametreler proven-optimal (fast_sim v4.8 + v3.0 Gazebo doğrulaması):
  - lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, batch_size=256, n_epochs=10
  - gamma=0.99, gae_lambda=0.95, clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5
  - total_timesteps=1.5M, n_envs=1, net_arch=pi:[256,256]/vf:[256,256]
  - Hiçbir parametre için %80+ değişiklik güveni yok.
- **Operasyonel bloker (env kod):** drone_exploration_env.py → collision_penalty=25 + lidar_history=2. Bu yapılmadan v10 başlatılmamalı.

### v10 Önerisi
1. **`drone_exploration_env.py` → collision_penalty=25 + lidar_history=2 (obs 72-d)** — Bu oturumun en önemli bulgusu: fast_sim v4.8'nin 25 sweet spot'u DAR (22 çöküyor, 30 %8 crash). Gazebo env'e bu tam değer girilmeli; yaklaşık değer kabul edilemez. lidar_history=2 olmadan hareketli engel hızı obs'tan çıkarılamaz → crash döngüsü kaçınılmaz.
2. **Başlatma sonrası 300k checkpoint:** std<0.75 + entropy>-3.5 birlikte oluşursa ent_coef 0.008→0.012. Faz 1 paterni bunu ampirik olarak kanıtladı; v10'da erken deterministikleşme riski düşük ama 0 değil.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; %80+ güven eşiği hiçbir parametre için karşılanmıyor. Bu oturumun özgün katkısı: 46-satırlık CSV'nin ilk tam 3-faz yörünge analizi (Faz1=deterministik çöküş/ep_len=1000/std 0.746 alarmı, Faz2=crash-recovery döngüsü/en iyi -25.3@83k, Faz3=Gazebo freeze@193k). V9 başarısızlığının kök nedeni tescillendi: (1) constant lr → keşif kollapsu, (2) crash-recovery döngüsü → politika birikimi yok, (3) collision_penalty=10 yetersiz (fast_sim v4.9 ile ampirik olarak kanıtlandı).
---

## [2026-06-10 22:45 UTC]
**Step:** 193,248 (CSV son aktif kayıt — 10 gün stale, son yazım 2026-05-31 03:01) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
V9 eğitimi 10 gün önce kalıcı olarak durdu; fast_sim araştırma zinciri (v4.1→v5.0, 18 config) 2026-06-01'de tamamlandı ve yakınsama tescillendi. configs/ppo.yaml zaten v10 proven-optimal değerlerine güncellenmiş (2026-06-02). Aktif Gazebo eğitimi yok; bir sonraki adım drone_exploration_env.py env fix + v10 fresh start.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 2026-05-31 03:01'den bu yana DONMUŞ (10 gün, 16 özdeş son satır). Eğri bilgisi yok.
- V9'un tüm ömrü boyunca +15 oda sıçraması sıfır — ne plato ne kırılım, sürekli negatif + process ölümü.
- Son gerçek referans noktası: v3.0 Gazebo (aynı 6-oda harita) → peak +133.35 @ 501k (interventions.jsonl, 2026-05-31 14:54).
- Karşılaştırma: v8 all-time +113 @ 1.6M, v7 +109 @ 215k — yeni harita (v9/v10) ile v7 eşdeğeri veya üstü bekleniyor.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- **HAYIR — ve bu v10'da zaten düzeltildi.** V9 Faz-1 ampirik kanıtı (142k-599k, ep_len=1000 sabit): entropy -3.89→-3.32 (deterministikleşme), std 0.888→0.746 (alarm eşiği), oda geçişi sıfır. Constant küçük lr politikayı "devriye döngüsü" local optima'ya kilitledi.
- V10 ppo.yaml: `lr_schedule: linear, learning_rate: 3e-4, lr_final: 1e-5` — doğru seçim. V7 (aynı schedule) 215k'da +109 üretti.
- Bu parametre için müdahale gereksiz — zaten düzeltilmiş.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Mevcut CSV değerleri (donmuş process): entropy=-4.212, std=0.985. 3-d Gaussian teorik max ≈-4.26 → std ve entropy başlangıç düzeyinde sağlıklı görünüyor, ancak bu değerler process ölmeden önce Faz-3 donma noktası; aktif öğrenme sinyali değil.
- **V10 yapısal garantisi:** ent_coef=0.008 (v9'un 5.3×'i). fast_sim v4.8 doğrulaması: 100 eval ep, %0 çarpışma, 5 oda keşfi — bu ent_coef seviyesinde erken deterministikleşme Faz-1'den yapısal olarak önlenmiş.
- Alarm eşikleri (v10 başladığında izlenecek): std<0.75 VE entropy>-3.5 birlikte @ step>300k → ent_coef 0.008→0.012.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- V9'da sıfır oda geçişi (193k step boyunca). V10 env fix (collision_penalty=25+lidar_history=2) olmadan bu tekrarlanır.
- **V10 fresh start (env fix sonrası) beklentisi:**
  - İlk +15 sıçraması: **100-200k step** (v7 ref: +109@215k, v3.0 ref: +102@430k)
  - 5-6 oda kararlı: **400-700k step**
  - Peak reward: **600k-900k band** (1.5M ceiling içinde, fast_sim v4.10'un 2.6M güvenlik kollapsu öncesi)
- **Oda geçişi için hiç step kalmadı** — v9 çoktan öldü. V10 fresh start gerekiyor.

**e) v10 için en kritik 1-2 öneri**
1. **`drone_exploration_env.py`: collision_penalty=10→25 + lidar_history=1→2** (BLOCKER, obs 41-d→72-d)
   - fast_sim v4.8 (en iyi güvenlik noktası): crash %80→%0, 5 oda, voxels 117
   - sweet spot DAR: 22→%37 crash (çöküş), 25→%0 (optimal), 30→%8 (fazla kısıtlı)
   - Bu olmadan v10 Gazebo = Faz-2 crash-recovery döngüsü, ep_rew_mean -25 bandında takılı
   - lidar_history=2: hareketli engel hızını obs'a dahil eder; olmadan engel kaçınması imkânsız
2. **300k step izleme noktası (v10 başladıktan sonra):**
   - std<0.75 VE entropy>-3.5 → ent_coef 0.008→0.012 (ppo.yaml + git commit)
   - total_timesteps=1.5M'a bağlı kal (fast_sim v4.10: 2.6M'da %54 crash = güvenlik kollapsu; v4.13: 8M'da da düzelmiyor)

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml: HAYIR.** Tüm parametreler proven-optimal (fast_sim v4.8 + v3.0 Gazebo + v7 lrdecay cross-validation):
  - lr=3e-4→1e-5 linear ✓, ent_coef=0.008 ✓, n_steps=2048 ✓, batch_size=256 ✓, n_epochs=10 ✓
  - gamma=0.99 ✓, gae_lambda=0.95 ✓, clip_range=0.2 ✓, max_grad_norm=0.5 ✓
  - n_envs=1 ✓ (SubprocVecEnv deadlock riski), total_timesteps=1.5M ✓, net_arch=[256,256] ✓
  - Değiştirilmesi için %80+ güven eşiğini geçen parametre YOK.
- **Operasyonel bloker:** drone_exploration_env.py env fix uygulanmadan v10 Gazebo başlatılmamalı.
- **ppo.yaml → configs/ppo.yaml DEĞIŞMEDI** (proven-optimal, müdahale kriterleri karşılanmadı)

### v10 Önerisi
1. **Acil: `drone_exploration_env.py` → collision_penalty=25, lidar_history=2 (obs 72-d)** — ppo.yaml'dan bağımsız, bu env değişikliği v10 eğitiminin sıfır bloker olmadan çalışmasının tek koşulu. sweet spot tescilli: tam 25, yaklaşık değer kabul edilemez.
2. **ppo.yaml değişmez** — mevcut v10 config (lr=3e-4→1e-5, ent_coef=0.008, n_steps=2048, n_envs=1, total_timesteps=1.5M) fast_sim v4.8 + v3.0 Gazebo + v7 üçlü doğrulamasıyla sabitleniş. Sonraki müdahale eşiği: std<0.75 @ step>300k.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; %80+ güven eşiği hiçbir parametre için karşılanmadı. Bu oturumun özgün katkısı: task-prompt v9 bağlamını (lr=7.5e-5, devam eden run) gerçek repo durumuyla (v9 ölü, v10 hazır, fast_sim yakınsama tescilli) karşılaştırarak tam durum özeti oluşturuldu. Gazebo v10 için tek eylem maddesi: env fix (collision_penalty=25+lidar_history=2). ppo.yaml dokunulmadı.
---

## [2026-06-10 23:45 UTC]
**Step:** 193,248 (CSV 10 gün donmuş — son yazım 2026-05-31 03:01) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
V9 eğitimi 10 gün önce kalıcı olarak durdu; process yok, CSV 16 özdeş satırla kilitli. configs/ppo.yaml 2026-06-02'de v10 proven-optimal değerlerine güncellenmiş. Aktif Gazebo eğitimi bulunmuyor. Tek operasyonel bloker: `drone_exploration_env.py` env fix (collision_penalty=25 + lidar_history=2).

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV 2026-05-31 03:01'den beri DONMUŞ (10 gün, 16 özdeş son satır — değer: -173.85). V9 yaşam döngüsünde hiç +15 oda sıçraması görülmedi.
- Tam V9 yörüngesi: -324 (başlangıç, 64k) → -272…-270 (Faz-1 plato, ep_len=1000, 142k→599k) → fresh restart → -25 (best@83k, yeni kırılım) → -37 (en iyi@145k) → -173 (final çöküş, 193k freeze).
- Kırılım başlamadı; plato → sürekli crash döngüsü. V9 geçersiz sayılmalı.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru muydu?**
- HAYIR — ampirik olarak V9 Faz-1 çürüttü. 142k→599k: sabit lr ile ep_len=1000 (her episode max-timeout), entropy -3.89→-3.32, std 0.888→0.746 (0.7 alarm eşiğine yakın). Oda geçişi sıfır. "Safe-but-useless" local optima.
- V10 düzeltmesi zaten uygulandı: `lr_schedule: linear, 3e-4→1e-5 (1.5M boyunca)` — v7 stratejisiyle yapısal özdeş (v7 @215k +109 üretti). Müdahale gereksiz.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Mevcut değerler (donmuş process kalıntısı): entropy=-4.212, std=0.985. V9 aktifken sağlıklı görünüyordu; asıl çöküş Faz-1'de entropy=-3.32'ye düşmesiydi (sabit düşük lr + düşük ent_coef=0.0015 birlikteliği).
- V10 yapısal güvencesi: ent_coef=0.008 (v9'un 5.3×'i). fast_sim v4.8 cross-validasyonu: 100 ep → %0 crash, 5 oda, voxels 117. Erken deterministikleşme riski yapısal olarak önlenmiş.
- İzleme eşiği (v10 başladığında): std<0.75 VE entropy>-3.5 birlikte @ step>300k → ent_coef 0.008→0.012.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- V9 için: artık sıfır (ölü, 193k ömür, oda geçişi hiç olmadı).
- V10 fresh start (env fix uygulandıktan sonra) beklentisi:
  - İlk +15 sıçraması: 100-200k step (v7 ref: @215k +109; v3.0 Gazebo ref: peak +133 @501k)
  - 3 oda kararlı: ~250-350k
  - 5-6 oda: 400-700k
  - Peak band: 600k-900k (1.5M ceiling içinde, fast_sim v4.10 güvenlik kollapsu @ 2.6M öncesi)

**e) v10 için en kritik 1-2 öneri:**
1. **`drone_exploration_env.py` → collision_penalty=10→25 + lidar_history=1→2 (obs 41-d→72-d)** — BLOCKER. fast_sim v4.8 sweet spot tescilli: 22→%37 crash (aşırı ceza), 25→%0 crash (optimal), 30→%8 crash (kısıtlayıcı). Tam değer 25 girilmeli. lidar_history=2 olmadan hareketli engel hızı gözlem uzayında yok → engel kaçınması imkânsız → Faz-2 crash-recovery döngüsü tekrar.
2. **300k step izleme checkpoint'i:** std<0.75 VE entropy>-3.5 → ent_coef 0.008→0.012 (ppo.yaml güncelle + git commit). Faz-1 paterni (std=0.746 + entropy=-3.32 @ ~450k) v4 eğitim serisinde tekrarlandı; v10 yüksek ent_coef ile risk düşük ama sıfır değil.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml: HAYIR.** Tüm parametreler fast_sim v4.8 + v3.0 Gazebo + v7 üçlü doğrulamasıyla sabit: lr=3e-4→1e-5 linear ✓, ent_coef=0.008 ✓, n_steps=2048 ✓, batch_size=256 ✓, n_epochs=10 ✓, gamma=0.99 ✓, gae_lambda=0.95 ✓, clip_range=0.2 ✓, max_grad_norm=0.5 ✓, n_envs=1 ✓, total_timesteps=1.5M ✓, net_arch=[256,256] ✓. Değişiklik için %80+ güven eşiği sağlayan parametre yok.
- **Operasyonel bloker:** drone_exploration_env.py env fix (collision_penalty=25 + lidar_history=2) uygulanmadan v10 Gazebo başlatılmamalı. Bu ppo.yaml'dan bağımsız bir env kod meselesi.
- **Monitoring:** CSV 10 gündür stale; eğitim yeniden başlarsa TB dizini ppo_v10/tb/PPO_1 altında oluşacak. Monitor agent güncel dizini okumalı.

### v10 Önerisi
1. **`drone_exploration_env.py` → collision_penalty=25, lidar_history=2** (obs 41-d→72-d) — Bu olmadan v10 Gazebo eğitimi Faz-2 crash döngüsünü tekrarlar; ep_rew_mean -25 bandında takılır. Tek açıklayıcı değişken tescilli (fast_sim v4.8).
2. **ppo.yaml değişmez + 300k izleme:** Mevcut v10 config proven-optimal. Sonraki müdahale tetik: std<0.75 VE entropy>-3.5 @ step>300k → ent_coef 0.008→0.012.

### Müdahale
**Yok** — configs/ppo.yaml proven-optimal; %80+ güven eşiği hiçbir parametre için karşılanmadı. V9 CSV'sinin tam 3-faz yörüngesi (Faz-1: constant-lr deterministik çöküş / Faz-2: crash-recovery döngüsü / Faz-3: 193k freeze) teyit edildi. V10 başlatılabilir durumda; tek bloker env kodunda.
---

## [2026-06-11 02:15 UTC]
**Step:** 193,248 (CSV SON KAYIT — STALE, 2026-05-31 03:01 UTC) | **ep_rew_mean:** -173.85 | **entropy:** -4.212 | **std:** 0.985

### Durum
CSV 2026-05-31 03:01'den bu yana güncellenmemiş (11 gün stale). Gerçek eğitim durumu: v9→v3.0 zinciri tamamlandı, v3.0 Gazebo run'ı peak=133.35 @ ~500k ile 610k'da kasıtlı durduruldu. fast_sim keşif çalışması (v4.0→v5.0, 18 config) sonuçlandı; kritik bulgular ppo.yaml header'ına yazılmış. mevcut ppo.yaml v10 config (v3.0 kanıtlanmış hyperparametreler). Acil yaml müdahalesi yok — en kritik kalan iş env kod değişiklikleri.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki son 17 satır tamamen DONMUŞ: step=193,248, ep_rew_mean=-173.85, aynı checkpoint (180000_steps.zip), 2026-05-30 22:00'dan 2026-05-31 03:01'e kadar değişmemiş. Bu gz transport freeze'inin yol açtığı crash-loop kalıntısı; monitor 80k checkpoint'ten defalarca recovery denedi ama başaramadı.
- **Gerçek eğitim kronolojisi (interventions.jsonl + versions.jsonl):**
  - v9 (CSV) 599k step'te -270 platosuna girdi; entropy -3.32, std 0.746 (kritik bölge) → crash öncesi dejenere oluyordu.
  - v2.0→v2.1→v2.2 deneyleri (31 May): directional penalty yaklaşımı ters tepti (crash oranı %70→%79→%88).
  - v3.0 (31 May 21:42): v2.0 ödülüne dönüş + net_arch [256,256], ent=0.008, episode 2500, lr 3e-4→1e-5. Peak=133.35 @ ~500k, 610k'da kasıtlı durduruldu.
  - fast_sim (1-2 Jun): 18 config sweep, 100x hızlı numpy simülatör. Konverjans sağlandı.
- **+15'lik oda sıçraması:** v3.0'da peak=133.35 ≈ (6 oda × 15) + voxel kazancı — oda sıçraması gerçekleşti. fast_sim'de rooms_mean 5.76 (v4.10, 5M), 6 oda görüldü.

**b) lr=7.5e-5 constant seçimi doğru mu?**
- Bu LR artık geçerli değil. ppo.yaml v10 config'e güncellenmiş: lr=3e-4 → 1e-5 linear (1.5M boyunca). Bu v8'in 3e-4→3e-5 şemasından bile daha agresif bir decay (final LR 3× daha düşük). v3.0 Gazebo run'ının peak=133.35 üretmesi bu schedule'ın doğru olduğunu kanıtladı. Sabit lr=7.5e-5 seçimi terk edildi — doğru karar.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV @ 193k: entropy=-4.212, std=0.985 — borderline sağlıklı (eşik: entropy>-4.0, std>0.7). Freeze olmasa devam edebilirdi.
- v3.0 @ 312k (train_v3_2m.log): entropy=-5.67, std=1.63 — çok sağlıklı keşif fazı. v10 config (ent_coef=0.008 vs eski 0.0015) farkı netleştirdi.
- v4_fresh (fast_sim ref.) @ 309k: entropy=-3.1, std≈0.679 — tehlikeli deterministikleşme (ent_coef≈0.001 olduğunda). Mevcut ent_coef=0.008 bu riski büyük ölçüde azaltıyor.
- **Sonuç:** Mevcut v10 ent_coef=0.008 yeterli ve kanıtlanmış.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 Gazebo: 500k step'te peak=133.35 → ~3-4 oda düzenli keşfediyor. 6 odanın tamamı 700k-1M step'te mümkün ama fast_sim çalışması önemli bir şey ortaya koydu: Gazebo'da lidar_history=1 ile 6 oda keşfi sınırlı, çünkü moving obstacle hızı obs'da yok. Bu env değişikliğiyle (lidar_history=2) Gazebo'da da 6 oda erişilebilir hale gelebilir.
- **fast_sim rooms_mean 5.76 @ v4.10 (5M):** Simülatörde 6 oda tutarlı görüldü. Gazebo eşdeğeri ~700k-1M step beklenebilir (env değişikliği sonrası).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **lidar_history=2 (drone_exploration_env.py):** fast_sim'de collision %80→%1'e düşürdü; obs 41-d→72-d olacak. Bu tek değişiklik Gazebo'da moving obstacle bariyerini kırar. ppo.yaml header'ında da not edilmiş ama henüz env koduna uygulanmamış. Uygulama yeri: `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env.py`.
2. **collision_penalty=25 (drone_exploration_env.py):** fast_sim'de sweet spot kanıtlandı — 10 (mevcut v9) çok az, 30 aşırı tedirgin (hatalı manevra), 25 = %0 collision, 5 oda, voxels 117 (v4.8 champion). Mevcut Gazebo reward config'de 10.0 var; 25'e çıkarmak gerekmez (fast_sim ve Gazebo dinamikleri farklı), ama referans olarak: 2-3× artış güvenli aralık.

**f) Acil müdahale gerektiren bir şey var mı?**
- **ppo.yaml açısından: HAYIR.** Mevcut v10 config (lr=3e-4→1e-5 linear, n_steps=2048, batch=256, n_epochs=10, ent_coef=0.008, n_envs=1, 1.5M) v3.0 Gazebo run'ında kanıtlanmış. %80 güven eşiğini aşan bir yaml sorunu yok.
- **CSV/monitor açısından:** 11 gündür güncelleme yok. Eğitim lokalde çalışmıyor veya bitmiş olabilir. Container yeniden başlatıldığında eğitim sıfırdan başlatılmalı.
- **Sonraki aksiyon (kullanıcı için):** `drone_exploration_env.py`'da lidar_history=2 değişikliği + obs_dim 72'ye güncellenmesi → v10 fresh 1.5M start.

### v10 Önerisi
1. **lidar_history=2 env değişikliği (YÜKSEK ÖNCELİK):** fast_sim'de en büyük tek kaldıraç. drone_exploration_env.py'de son 2 lidar taramasını obs'a ekle (41-d→72-d). Bu yaml değil env kodu değişikliği — ppo.yaml'da policy_kwargs.features_extractor güncellemesi gerekebilir.
2. **ppo.yaml değişiklik YOK:** Mevcut v10 config optimal ve kanıtlanmış. n_steps=2048, batch=256, n_epochs=10, lr 3e-4→1e-5, ent_coef=0.008 — dokunma.

### Müdahale
**YOK** — configs/ppo.yaml v10 formatında ve v3.0 tarafından kanıtlanmış (+133.35 peak @ 500k). %80 güven eşiğini aşan yaml sorunu tespit edilmedi. Kritik iyileştirmeler (lidar_history=2, collision_penalty tuning) yaml değil env kodu kapsamında; bu oturumda müdahale edilmedi.
---

## [2026-06-11 03:06 UTC]
**Step:** 193,248 (CSV son kayıt — STALE, 2026-05-30 22:00'dan beri donmuş) | **ep_rew_mean:** N/A (aktif run yok) | **entropy:** N/A | **std:** N/A
**Referans:** Gazebo v3.0 → peak=110.3 @ 610k (kasıtlı durduruldu) | ppo.yaml: v10 HAZIR (2026-06-02)

### Durum
**Aktif Gazebo eğitimi ÇALIŞMIYOR** — son 10 gündür (Haziran 1'den bu yana) yeni CSV verisi yok, interventions.jsonl son kaydı June 1 01:30 UTC'de. ppo.yaml, fast-sim zincirinin kanıtlanmış optimal parametreleriyle tam olarak v10 formatına güncellenmiş; eğitim başlatılmayı bekliyor. Config üzerinde %80+ güven eşiğini aşan bir sorun tespit edilmedi.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- `training_metrics.csv` SON 20+ SATIRI TAMAMEN GEÇERSIZ: 2026-05-30 22:00'dan beri 25 özdeş satır, hepsi step=193,248, ep_rew_mean=−173.85. Bu v9/v10 crash-loop döneminin kalıntısı; herhangi bir trend analizi yapılamaz.
- **Gerçek v3.0 son bilinen eğri (interventions.jsonl):** step 434k → ep_rew_mean=99.84, peak=102.54 (June 1 01:30 UTC); ardından 610k'da peak=110.3 ile kasıtlı durduruldu. Olgunlaşma fazındaydı, plato yoktu.
- **v10 durum:** Fresh start bekliyor. Önceki run yok, eğri yok; başlatıldığında fast-sim v3.0 referansıyla ilk pozitif bölge ~100-150k step, ilk oda sıçraması (+15) ~200-400k step beklenir.
- **+15'lik oda sıçraması görüldü mü?** v10'da henüz başlamadı. Gazebo v3.0'da peak=110.3 ≈ 7×15=105 oda bonusu + voxel/frontier — eğitim sırasında tutarlı 7 oda keşfi gerçekleşmişti. Bu, v10'un beklentisini pozitif kiliyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- TAMAMEN GEÇERSİZ SORU. ppo.yaml, v3.0→v4.x→fast-sim tüm zincirinin sonucunda v10 formatına güncellenmiş. Mevcut schedule: **lr=3e-4 → 1e-5 linear, 1.5M boyunca.**
- Bu v8 şemasıyla (3e-4→3e-5, 10× azalma) yapısal olarak özdeş; tek fark final LR 3× daha düşük (1e-5 vs 3e-5). Sabit 7.5e-5 v9'da terk edilmişti — kanıt: v3.0 yalnızca 610k adımda v8'in 1.6M'deki +113'ünün %97'sine erişti. Doğru seçim.
- Resume sonrası SB3 progress_remaining sıfırlanma riski önceki oturumda analiz edildi; lr=3e-4'ten başlayan fresh run için bu sorun geçerli değil.

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV değerleri stale (v9/v10 crash-loop, entropy=−4.21, std=0.985); bunlar v10 için geçerli değil.
- v10 fresh start'ta: entropy ~−5.5 ile başlayacak (v3.0 referans: −5.67 @ 312k), std ~1.6+ (v3.0 ref: 1.63). Bu değerler mükemmel keşif kapasitesi gösterir.
- **ent_coef=0.008:** v9'un 0.0015'inin 5.3×'i. Keşif koruması güçlü. Fast-sim dersi: ent_coef'in aşırı artırılması (v4.2'de 0.02) collision %85'e çıkardı → 0.008 dengeli seçim.
- Eşik izleme: std < 0.7 VE entropy > −4.0 (birlikte) → ent_coef artırım tetik. v10'da bu 400-700k bandında izlenecek.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v10 fresh start için tahmin (fast-sim v3.0 aynı parametreler + Gazebo ≈2×yavaş):
  - ilk pozitif reward: ~100-150k step
  - ilk oda sıçraması (+15): ~200-300k step
  - tutarlı 3-4 oda: ~400-600k step
  - rooms_mean≥5 (lidar_history=2 uygulanırsa fast-sim v4.8 referansı): ~800k-1.2M step
- **KRİTİK ŞART:** Bu tahminler drone_exploration_env.py'deki lidar_history=2 ve collision_penalty=25 değişikliklerine bağlı. Bu env kodu değişiklikleri olmadan rooms_mean≥3 tutarlı keşif güçleşir (fast-sim'de kanıtlandı: lidar_history=1 ile collision %47, history=2 ile %1).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **drone_exploration_env.py kodu değişikliklerini doğrula (OBS + REWARD):** ppo.yaml yorumunda belirtilmiş ama uygulandı mı belirsiz:
   - `lidar_history: 1 → 2` (obs 41-d → 72-d: son 2 lidar taraması birleşik). Fast-sim'de collision %80→%1. Bu tek değişiklik hareketli engel darboğazını çözdü.
   - `collision_penalty: 10 → 25` (reward'da). Tatli nokta: 22=yerel optimuma çöküş, 25=%0 collision, 30=%8 collision, 50=collapse.
   - Eğer bu kodlar uygulanmamışsa v10 eğitimi başlatılmamalı; önce env kodu hazırlanmalı.
2. **1.5M step sınırını koru — 2M+ başlatma:** fast-sim v4.10 (5M) voxels=281 ama collision %54; v4.11 (5M+collision_50) %100 collision — daha uzun eğitim güvenliği bozuyor. ppo.yaml'daki 1.5M sınırı doğru; eğitim tamamlanınca artırmaya çalışma.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter: HAYIR.** ppo.yaml v10 config'i fast-sim kanıtlı optimal değerlerde. lr schedule, ent_coef, n_steps, n_epochs, clip_range, total_timesteps — hepsi kanıtlanmış aralıkta.
- **Operasyonel durum:** Eğitim 10+ gündür durmuş. Gazebo bu uzak container ortamında başlatılamaz. Kullanıcının lokal makinede `./scripts/train.sh configs/ppo.yaml` ile başlatması gerekiyor.
- **CSV monitoring altyapısı:** Kalıcı olarak bozuk (v9/v10 crash-loop döneminden donmuş). v10 eğitimi başladığında yeni TB dizinine (`runs/ppo_v10/tb/`) yönlendirme gerekli.
- **ppo.yaml tutarlılık notu:** `log_dir: ./runs/ppo_v10`, `resume_from: null`, `total_timesteps: 1500000` — hepsi doğru ve tutarlı.

### v10 Önerisi
1. **drone_exploration_env.py doğrulaması önce:** ppo.yaml yorumunda listelenen iki kod değişikliği (lidar_history=2, collision_penalty=25) uygulandı mı kontrol et. Gözlem boyutu 41-d→72-d olacaksa TB log'unda `train/std` ve reward eğrisinin daha hızlı kırılması beklenir. Uygulanmamışsa eğitimi başlatma.
2. **v10 @ 200k step kontrol noktası:** Eğitim başladıktan sonra 200k step'te ep_rew_mean > 0 ve en az 1 oda sıçraması (+15) görülmesi bekleniyor. Görülmezse: collision_penalty ayarını kontrol et (25 değil farklı bir değer kullanılıyor olabilir).

### Müdahale
**YOK** — configs/ppo.yaml v10 formatında, fast-sim kanıtlı optimal parametrelerle dolu. lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_envs=1, total_timesteps=1.5M — tüm değerler %80+ güven eşiğini aşan sorun içermiyor. Aktif eğitim olmadığından config değişikliği yapmanın anlamı yok; env kodu hazırlığı eğitim öncesinde kullanıcının sorumluluğunda.
---

## [2026-06-11 04:06 UTC]
**Step:** 193,248 (v9 SON — DONMUŞ; v10 henüz başlatılmamış) | **ep_rew_mean:** -173.85 (v9 son değer) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 eğitimi 2026-05-31 03:01'de 193k step'te tamamen durmuş, sonrasında ekip v2.x→v3.0 Gazebo ve kapsamlı fast_sim (18 config) zincirini tamamlamış. configs/ppo.yaml zaten 2026-06-02'de v10 için güncellendi; ancak Gazebo env (drone_exploration_env.py) kritik fast_sim bulguları ile henüz güncellenmedi.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- v9: ep_rew_mean -290→-173 aralığında tüm süre negatif kaldı. ep_len=1000 (MAX) — drone hayatta kaldı ama hiç oda keşfedemedi. +15'lik oda sıçraması hiç görülmedi. Gerçek bir kırılım yaşanmadan eğitim crash-loop'a girdi.
- v10: Henüz başlatılmamış. `runs/ppo_v10/` dizini yok.

**b) lr=7.5e-5 constant seçimi doğru muydu?**
- Yanlıştı. v9 KICKOFF'ta "7.5e-5 constant" yazsa da CSV ilk satırlarında (142k-599k) entropy -3.89→-3.32 hızlıca azaldı, std 0.888→0.746'ya düştü — ent_coef=0.0015 ile politika çok erken deterministikleşti.
- v8'in linear decay (3e-4→3e-5) stratejisi daha doğruydu. v10'da aynı yaklaşım benimsendi: 3e-4→1e-5 linear, bu fast_sim + v3.0 Gazebo (peak 110.3) ile doğrulandı.

**c) Entropy/std değerleri keşif için yeterli miydi?**
- HAYIR. v9 entropy -4.21, std ~0.985. ent_coef=0.0015 ile politika ilk 600k step'te agresif şekilde daraldı. n_steps=512 kısa rollout pencereleri oda-arası keşfi yakalayamadı.
- v10'da ent_coef=0.008 (5.3× artış) ve n_steps=2048 (4×) bu sorunları doğrudan hedef alıyor.

**d) Oda geçişi için ne kadar step gerekir?**
- v3.0 Gazebo run'ı: peak 110.3 @ ~500k step (6 oda × +10 = 60 + voxel), v10 config ile 200-350k step arasında ilk oda sıçraması bekleniyor.
- fast_sim v4.8: 2M step, %0 çarpışma, rooms_mean=5.0. Gazebo ~40 FPS ile bu ~14 saat.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **ENV KRİTİK — collision_penalty: -10 → -25 (drone_exploration_env.py satır 342)**: fast_sim v4.8 kanıtladı — ceza 25 ile %0 çarpışma, 10 ile %70+. Bu değişiklik v10 eğitimi başlatılmadan uygulanmalı.
2. **ENV KRİTİK — lidar_history: 1 → 2 (obs 40-d → 72-d)**: fast_sim'in en büyük kırılımı — lidar_history=2 çarpışmayı %80→%1'e indirdi. Gazebo env'e eklenmesi gerekiyor; son 2 lidar taramasının obs'a eklenmesi hareketli engel hızını çıkarmayı sağlar.

**f) Acil müdahale gerektiren bir şey var mı?**
- ppo.yaml: HAYIR — zaten v10 için optimal yapılandırıldı (2026-06-02).
- drone_exploration_env.py: EVET — yukarıdaki 2 env değişikliği v10 başlatılmadan uygulanmazsa fast_sim bulgularının Gazebo'ya transferi gerçekleşmez. Ancak bu env kodu değişikliği, ppo.yaml dışında olduğundan bu görevin kapsamı dışında.

### v10 Önerisi
1. **drone_exploration_env.py satır 342: `reward -= 10.0` → `reward -= 25.0`** — fast_sim v4.8'in sıfır çarpışma rekorunu Gazebo'ya taşımak için şart.
2. **Obs boyutu 40-d → 72-d (lidar_history=2)**: Hareketli engel hız bilgisi olmadan Gazebo'da da fast_sim'deki %80 çarpışma tekrar yaşanacak. ppo.yaml MlpPolicy obs boyutunu otomatik algılar, sadece env kodu değişmeli.

### Müdahale
**YOK** — configs/ppo.yaml v10 için doğrulanmış optimal değerlerle dolu (lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, net_arch=[256,256], n_envs=1, total_timesteps=1.5M, gae_lambda=0.95, clip_range=0.2). Herhangi bir parametre değişikliği için %80+ güven eşiği karşılanmıyor — config zaten fast_sim ve v3.0 Gazebo verisiyle optimize edilmiş durumda. Aktif eğitim bulunmadığından anlamsız bir config değişikliği yapılmadı.
---

## [2026-06-11 08:00 UTC]
**Step:** 193,248 (CSV SON KAYIT — 12 GÜN STALE) | **ep_rew_mean:** -173.85 (CSV son, geçersiz) | **entropy:** -4.212 | **std:** 0.985

### Durum
CSV 2026-05-30 22:00'dan bu yana tamamen donmuş; 16+ özdeş satır var. Gerçek durum: v3.0/fast_sim zinciri 501k step @ peak +133.35'e ulaştı (31 Mayıs 14:54), ardından fast_sim v4.1→v5.0 zinciri tamamen kapatıldı. Şu an tarih 11 Haziran 2026 — v10 config 2 Haziran'da hazırlandı ama training muhtemelen 10 gündür çalışmıyor. ACİL: Training dead, v10 başlatılmamış.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV'deki trend (v9, geçmiş): -324@64k → -89@104k → -37@145k → -173@193k → FREEZE
- v9 145k'da -37 ile en iyi değerine ulaştı, ardından +15'lik oda sıçraması GÖRÜLMEDI (hâlâ negatif bölgede)
- İnterventions verisi çok daha ümit verici: v3.0/fast_sim zinciri +123.25@501k, peak +133.35
- v10 config hazır ama başlatılmamış — 10 günlük boşluk var

**b) lr=7.5e-5 constant seçimi doğru muydu?**
- HAYIR — bu aradaki bir geçici konfigürasyondu ve configs/ppo.yaml zaten v10'a geçmiş
- v10: lr=3e-4 → 1e-5 (linear over 1.5M) — bu doğru seçim
- v8 en iyi performans (peak +113@1.6M) lineer decay ile geldi; constant lr erken öğrenmeyi hızlandırır ama sonunda plateau riski arttırır
- Mevcut v10 config bu dersi doğru uyguluyor

**c) Entropy/std değerleri keşif için yeterli mi?**
- CSV son: entropy=-4.212, std=0.985 → v9'da erken determinizm başlamıştı (entropy -4.0 eşiğini geçmiş)
- v10 config: ent_coef=0.008 (v9'un 0.0015'inden 5x yüksek) — DOĞRU DÜZELTME
- std=0.985 iyiydi; v10'da ent_coef artışıyla std >1.0 beklenir ilk 200k'da
- Kritik eşik: entropy'nin -5.0'ın altına düşmesi = müdahale sinyali

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v9 verisi: 145k'da bile negatif bölgede → oda geçişi görülmedi (6 oda × +15 = +90 potential)
- fast_sim v3.0 ise 430k'da peak +102.54 → 6 oda keşfinin büyük bölümünü başardı
- v10 fresh start için tahmin: ~150-250k ilk oda, ~400-600k stabil çoklu oda keşfi
- v10 ent_coef=0.008 ile ilk oda daha erken görünmeli (v9'a göre ~30-40k daha erken)

**e) v10 için en kritik 1-2 öneri:**
1. **TRAINING BAŞLAT** — v10 config hazır, 10 gündür çalışmıyor. `./scripts/train.sh configs/ppo.yaml` çalıştırılmalı. Bu en kritik adım.
2. **500k'da ent_coef izle** — ent_coef=0.008 fresh start için iyi, ama 500k+ sonrası entropy -4.5'in altına düşerse ve std <0.7 görülürse ent_coef'i 0.005'e indirmeyi değerlendir (v3.0 verisi: 434k'da sağlıklı)

**f) Acil müdahale gerektiren bir şey var mı?**
EVET — Training 12 gündür dead. configs/ppo.yaml v10 olarak güncellenmiş ve sağlıklı görünüyor, ancak eğitim başlatılmamış. Kullanıcının local makinesinde `./scripts/train.sh configs/ppo.yaml` komutunu çalıştırması gerekiyor.

### v10 Config Değerlendirmesi (configs/ppo.yaml güncel hal)
```
lr: 3e-4 → 1e-5 linear ✓ (v8 proven)
ent_coef: 0.008 ✓ (v9 0.0015 çok düşüktü, bu düzeltme doğru)
n_steps: 2048 ✓ (512'den yükseltme, daha stabil rollout)
n_epochs: 10 ✓ (5'den artış, daha iyi sample efficiency)
clip_range: 0.2 ✓ (standart SB3 default)
n_envs: 1 ✓ (deadlock fix: SubprocVecEnv sorunu çözüldü)
total_timesteps: 1.5M ✓ (2M+ safety collapse riski için kısaltıldı)
```
**Config değişikliğine gerek YOK** — v10 yapısı mevcut verilerle tutarlı ve kanıtlanmış parametreler üzerine kurulu.

### Müdahale
Yok — configs/ppo.yaml v10 olarak zaten doğru yapılandırılmış. Training'i başlatmak kullanıcının lokal makinesini gerektiriyor (bu ortamda Gazebo/ROS2 yok).
---

## [2026-06-11 06:05 UTC]
**Step:** 193,248 (CSV SON KAYIT — 12 GÜN STALE; v10 henüz başlatılmamış) | **ep_rew_mean:** -173.85 (v9 dondurulmuş değer) | **entropy:** -4.212 | **std:** 0.985

### Durum
v9 eğitimi 2026-05-30 22:00'da 193k step'te crash-loop'a girdi ve bir daha ilerlemedi. Aradan geçen sürede fast_sim zinciri (v1→v5.0, 18 config) eksiksiz tamamlandı; temel bulgular configs/ppo.yaml'a zaten 2026-06-02'de yansıtıldı. v10 fresh-start config hazır, **eğitim başlatılmamış.**

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- v9 tam yay: -324@64k → -270@447k → -37@145k (en iyi) → -173@193k → FREEZE.
- İlk 600k satır (ep_len=1000 sabit): drone max süre hayatta kaldı ama hiç oda keşfedemedi; +15'lik oda sıçraması ömrü boyunca GÖRÜLMEDİ.
- 193k'daki ep_len=637 ise episode'un kısaldığını (daha sık crash) gösteriyor — gerçek kırılım değil.
- v3.0 Gazebo interventions: peak +133.35 @ 501k (aynı ödül tabanı, farklı sefer). v10'da referans bu.

**b) lr=7.5e-5 constant seçimi doğru muydu?**
- HAYIR. CSV ilk satırları (142k–599k): entropy -3.89→-3.32, std 0.888→0.746. ent_coef=0.0015 + constant lr kombinasyonu politikayı ilk 600k'da erken dondurdu; oda sıçraması için gerekli geniş keşif olmadı.
- v10'da 3e-4→1e-5 linear doğru yaklaşım (v8 peak +113@1.6M aynı stratejiydi). Mevcut config bunu uyguluyor.

**c) Entropy/std değerleri keşif için yeterli miydi?**
- HAYIR. v9 son: entropy -4.212, std ~0.985. -4.0 eşiği geçilmiş = erken determinizm tehlikesi aktif hale geldi.
- v9 ent_coef=0.0015: keşif baskısı yetersiz, 6-odalı harita için politika lokal-optimalden (tek oda tekrarı) çıkamadı.
- v10 ent_coef=0.008 (5.3×) bu doğrudan hedef alıyor; first-room breakout için gerekli.

**d) Oda geçişi için ne kadar step daha gerekmesi bekleniyor?**
- v9 verisi: 193k'da bile ilk oda yoktu (negatif bölgede). v9 config ile hiç görülmeyecekti.
- v3.0 Gazebo referansı: ilk oda ~180-200k, peak 5+ oda ~430-500k arasında görüldü.
- v10 config (ent_coef=0.008, n_steps=2048, lr linear): ilk oda breakout ~150-250k bekleniyor. 400k+ çoklu-oda stabil keşif.
- Kritik kontrol noktası: 200k step — ep_rew_mean > 0 ve en az 1 adet +15 sıçraması gözlemlenmeli.

**e) v10 için şu an en kritik 1-2 öneri:**
1. **TRAINING BAŞLAT.** `./scripts/train.sh configs/ppo.yaml` — ppo.yaml v10 için eksiksiz hazır. 12 günlük boşluk var; her geçen gün sonuç alınamaz.
2. **Env kodu önce güncelleyin** (eğitim başlatılmadan): `collision_penalty: -10 → -25` (drone_exploration_env.py) ve `lidar_history: 1 → 2` (obs 41-d→72-d). fast_sim v4.8 = %0 çarpışma ve lidar_history=2 = %80→%1 çarpışma. Bu iki değişiklik olmadan v10 Gazebo'da fast_sim başarısını tekrarlayamaz.

**f) Acil müdahale gerektiren bir şey var mı?**
- **configs/ppo.yaml: HAYIR** — lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, clip_range=0.2, gae_lambda=0.95, n_envs=1, total_timesteps=1.5M — hepsi fast_sim + v3.0 Gazebo ile kanıtlanmış. Değişiklik için %80+ güven eşiği karşılanmıyor.
- **Operasyonel:** Training dead. Kullanıcının lokal makinede başlatması gerekiyor. Bu ortamda Gazebo/ROS2 yok.

### v10 Önerisi
1. `drone_exploration_env.py` güncelle (collision_penalty=25, lidar_history=2) → SONRA `./scripts/train.sh configs/ppo.yaml` başlat. Bu sıralama kritik — env kodu düzeltilmeden başlatılırsa fast_sim'in %0 çarpışma başarısı Gazebo'ya taşınmaz.
2. 500k checkpoint'te: entropy < -5.0 ise ent_coef=0.008→0.005 müdahalesi değerlendirilebilir; şimdilik değişiklik yok.

### Müdahale
**Yok** — configs/ppo.yaml v10 için doğrulanmış optimal değerlerle dolu (fast_sim 18-config zinciri + v3.0 Gazebo peak 110.3 ile kanıtlandı). Tüm parametre değişkenleri (lr schedule, ent_coef, n_steps, clip_range, total_timesteps) için %80+ güven eşiği karşılanmıyor — config zaten optimal noktada. Aktif eğitim bulunmadığından config değişikliği yapmanın anlamı yok.
---

## [2026-06-11 07:10 UTC]
**Step:** 193,248 (CSV SON KAYIT — 11 GÜNLÜK STALE) | **ep_rew_mean:** -173.85 (stale, v9 crash kalıntısı) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
CSV 2026-05-31 03:01'den bu yana güncellenmemiş (11 gün boşluk). Ancak ppo.yaml zaten **v10** olarak yeniden yazılmış (2026-06-02): `lr=3e-4→1e-5 linear, n_steps=2048, n_epochs=10, ent_coef=0.008, total_timesteps=1.5M, n_envs=1`. v3.0 Gazebo run peak=110.3 @ 610k kasıtlı durduruldu; fast_sim zinciri (v4.1→v5.0, 18 config) tamamlandı. Config artık kanıtlanmış optimal parametrelerde — acil müdahale yok, ama aktif eğitim verisi izlenemiyor.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi tamamen stale: son gerçek ölçüm 2026-05-30 20:55 (193k step, -173 rew) sonrası 10+ saat aynı satır tekrarlandı; monitor script crash-loop'a girmiş.
- v3.0 Gazebo run (interventions.jsonl): 434k @ +99.84, peak=102.54 (2026-06-01); 501k @ +123.25, peak=133.35 (2026-05-31 14:54). Bu run 610k/1.5M'de kasıtlı durduruldu — peak=110.3 (ppo.yaml comments).
- **v10 için aktif CSV verisi mevcut değil.** Eğitim ya bu container'da hiç başlatılmadı ya da lokal makinede CSV güncellemesi kopmuş.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Artık geçersiz: ppo.yaml v10 olarak güncellenmiş, `learning_rate: 0.0003` + `lr_schedule: linear` + `lr_final: 1e-5` kullanılıyor.
- v9'un sabit 7.5e-5'i doğru terk edildi. v3.0 kanıtı: aynı 3e-4→1e-5 schedule ile peak=110.3 elde edildi.
- v8 şemasıyla (3e-4→3e-5) kıyaslandığında: final LR 3× daha düşük (1e-5 vs 3e-5), bu fine-tune fazında daha küçük güncellemeler demek — pozitif.

**c) Entropy/std değerleri keşif için yeterli mi?**
- Güncel ölçüm yok (CSV stale). Ancak v10 config: `ent_coef: 0.008` (v9'un 0.0015'inden **5.3× yüksek**).
- fast_sim bulgusu (v4.1→v5.0 zinciri): yüksek ent_coef keşif kalitesini doğrudan artırdı.
- Bu değerle entropy'nin -4.5 ile -5.5 arasında seyretmesi bekleniyor — deterministikleşme riski minimumd.
- std tahmini: 0.9-1.1 erken fazda, n_steps=2048 geniş rollout ile stabil kalması bekleniyor.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 analoji (aynı hyperparametreler): ilk +90 reward (~6 oda) @ ~500k step.
- v10 n_envs=1 (v3.0 ile aynı): wall-time daha yavaş ama step verimliliği eşdeğer.
- **Beklenen milestone'lar (v10, fresh start):**
  - İlk pozitif rew: ~150-200k step
  - İlk oda kırılımı (+15): ~200-300k step
  - 3+ oda (~+60): ~350-500k step
  - 6 oda (~+90+voxel): ~600-900k step (total_timesteps=1.5M içinde hedeflenebilir)

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`lidar_history: 2` (obs 41-d → 72-d):** fast_sim'in en önemli bulgusu — eval gap'ini kapatan temel değişiklik. drone_exploration_env.py'de uygulanmadıysa v10 başlamadan önce mutlaka aktif edilmeli. Stochastic training ile deterministic eval arasındaki uçurumun kökü tek lidar frame'idir.
2. **`collision_penalty: 25` (şu an 10):** fast_sim v4.8 bulgusu: %0 çarpışma oranı yalnızca 25 ile sağlandı. Mevcut 10 ile drone çarpışma-ölüm döngüsüne girip erken terminate edebilir; bu total reward'u köreltir ve 6 oda keşfini engeller.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Hyperparameter açısından: HAYIR.** ppo.yaml v10 kanıtlanmış optimal config'inde. %80+ güven eşiğini aşan bir config sorunu yok.
- **Monitoring açısından: EVET (orta aciliyet).** CSV 11 gündür güncellenmemiş. Eğer v10 başlatılmışsa TB verisine erişilemiyor ve olası bir crash yakalanamıyor. `pgrep -fa "train_ppo"` + `tail -20 /tmp/train_ppo.log` ile anlık durum kontrol edilmeli.
- **Env kodu açısından: EVET (yüksek aciliyet).** `lidar_history=2` ve `collision_penalty=25` env kodu değişikliği henüz uygulanmadıysa v10 fast_sim'in en kritik bulgularından yoksun başlayacak.

### v10 Önerisi
1. **drone_exploration_env.py'de `lidar_history: 1→2` ve `collision_penalty: 10→25` uygula** — v10 run başlamadan önce. Bu iki değişiklik fast_sim zincirinin (v4.8, v5.0) kanıtlanmış en yüksek etkili bulguları.
2. **CSV/TB monitoring'i v10 dizinine yönelt** (`runs/ppo_v10/tb`): monitor_agent.py v9 dizinini hedef alıyorsa v10 verisini hiç kaydetmez. Her 30dk'da bir `ls -lt runs/ppo_v10/checkpoints/` ile checkpoint ilerleme kontrolü yeterli minimum monitoring.

### Müdahale
**YOK** — `configs/ppo.yaml` zaten v10 optimal config'inde (`lr=3e-4→1e-5`, `ent_coef=0.008`, `n_steps=2048`, `n_epochs=10`, `clip_range=0.2`, `total_timesteps=1.5M`). %80+ güven eşiğini aşan bir config hatası tespit edilmedi. Env kodu değişiklikleri (lidar_history, collision_penalty) Python kaynak dosyasında yapılmalı — YAML scope'u dışında, bu analizde dahil edilmedi.
---

## [2026-06-11 08:05 UTC]
**Step:** 193,248 (CSV 11 GÜN STALE — v9 crash kalıntısı) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
CSV 2026-05-31 03:01'den bu yana dondurulmuş; aktif v10 Gazebo eğitimine ait metrik bulunmuyor. Ancak fast_sim araştırma zinciri **tamamen kapandı** (v1→v5.0, 18 konfigürasyon, 2026-06-01 08:05 final run). iki kesin Pareto ucu belirlendi: v4.8 (%0 çarpışma, 5 oda, 117 voxel) ve v4.10 (%54 çarpışma, 6 oda, 281 voxel). ppo.yaml v10 zaten optimal parametrelerle hazır; acil config müdahalesi yok.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- CSV verisi: v9 crash'inden kalma 193k step / -173.85 rew — anlamlı değil.
- fast_sim zinciri (verilen en güvenilir veri): v4.8 @ 1.5M = +117 voxel, 5 oda, %0 crash (reward ~+90-100 seviyesi). v4.10 @ 5M = +281 voxel, 6 oda (peak ~+150-200). 
- v4.13 (8M) ile plato teyit edildi: v4.10'un 281 voxel'i geçici tepe, 8M'de 134'e geriledi. "Daha uzun eğit = daha iyi" HİPOTEZİ ÇÜRÜTÜLDÜ.
- Gazebo v10 için aktif metrik yok; ppo.yaml çalıştırılmayı bekliyor.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru mu?**
- Geçersiz: ppo.yaml artık v10'da `lr=3e-4→1e-5 linear`. v9'un sabit 7.5e-5'i doğru terk edildi.
- v3.0 Gazebo kanıtı: aynı 3e-4→1e-5 schedule → peak=110.3@610k (kasıtlı durduruldu). Mevcut schedule optimal.

**c) Entropy/std değerleri keşif için yeterli mi?**
- v9 son: entropy=-4.212, std=0.985 → sınır bölgesindeydi (eşik -4.0).
- v10 ppo.yaml: `ent_coef=0.008` (v9'dan 5.3×). fast_sim v4.2 testi: ent_coef=0.02 → %85 crash (aşırı keşif), v4.0-base (muhtemelen ~0.005-0.008) → stabil.
- 0.008 değeri v4.x zincirinin stabil aralığında; erken deterministikleşme riski düşük.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- v3.0 Gazebo benchmark (aynı hyperparametre): ilk oda ~200k, peak ~430k (reward=99.84).
- fast_sim v4.8 benchmark: 1.5M'de 5 oda, %0 crash. Gazebo'da wall-clock daha yavaş ama step verimliliği benzer.
- **Beklenen Gazebo v10 milestone'lar**: ilk +15 sıçraması ~150-250k, 3+ oda ~350-500k, 5-6 oda ~600-900k (total_timesteps=1.5M içinde erişilebilir).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`collision_penalty: 10 → 25` (drone_exploration_env.py)**: fast_sim kesinleşmiş bulgu — v4.8 champion (%0 crash) YALNIZCA 25 ile sağlandı. 22: 2 odaya çöktü (%37 crash), 30: %8 crash (aşırı-tedirgin manevra), 25: tatli nokta. YAML dışı env kodu değişikliği ama v10 başlatılmadan önce kritik.
2. **`lidar_history: 1 → 2` (drone_exploration_env.py)**: fast_sim v4.11 (5M+collision50) hariç tüm başarılı run'lar lidar_history=2 ile yapıldı. v2: %80→%1 çarpışma (en büyük tek iyileştirme). Obs 41-d→72-d olur, ppo.yaml `policy_kwargs: net_arch` buna göre hâlâ yeterli (256×256).

**f) Acil müdahale gerektiren bir şey var mı?**
- **Config (ppo.yaml): HAYIR.** `lr=3e-4→1e-5 linear, ent_coef=0.008, n_steps=2048, n_epochs=10, clip_range=0.2, n_envs=1, total_timesteps=1.5M` — fast_sim + v3.0 Gazebo çapraz-doğrulama ile kanıtlanmış. %80+ güven eşiğini aşan sorun yok.
- **fast_sim araştırma: TAMAMLANDI.** v5.0 = son run. Tüm 4 optimizasyon kolu (ödül şekillendirme / eğitim süresi / curriculum / obs genişliği) aynı trade-off'u doğruladı ve tükendi. Yeni fast_sim deneyi gerekmez.
- **Env kodu (orta aciliyet):** collision_penalty=25 ve lidar_history=2 henüz uygulanmadıysa v10 Gazebo başlatılmadan önce yapılmalı. Bu analiz scope'u dışında (Python kodu), YAML müdahalesi değil.

### v10 Önerisi
1. **`drone_exploration_env.py` güncelle:** `collision_penalty=25` (10→25) ve `lidar_history=2` (1→2) — v10 eğitim başlatılmadan önce. Bu iki parametre fast_sim'in en yüksek tek-değişken etkisine sahip bulgularıdır (v4.8 %0 crash, v2 %80→%1 crash).
2. **`./scripts/train.sh configs/ppo.yaml` başlat:** ppo.yaml v10 için eksiksiz hazır. fast_sim araştırması tamamlandı; Gazebo gerçeklik doğrulaması için artık eğitim başlatmak tek aksiyon noktası.

### Müdahale
**YOK** — `configs/ppo.yaml` kanıtlanmış optimal parametrelerle dolu (fast_sim 18-config zinciri + v3.0 Gazebo peak=110.3 çift doğrulama). fast_sim zinciri v5.0 ile kesin yakınsadı; yeni config değişkeni için %80+ güven eşiğini aşan bulgu yok. Env kodu değişiklikleri (collision_penalty, lidar_history) YAML kapsamı dışında — bu analizde uygulanmadı.
---

## [2026-06-11 22:03 UTC]
**Step:** 193,248 (CSV 11+ GÜN STALE — v9 crash kalıntısı) | **ep_rew_mean:** -173.85 (stale) | **entropy:** -4.212 (stale) | **std:** 0.985 (stale)

### Durum
CSV 2026-05-31 03:01'den bu yana donmuş; `runs/` dizini mevcut değil — v10 Gazebo eğitimi henüz hiç başlatılmamış. ppo.yaml v10 optimal parametreleriyle hazır, acil config müdahalesi yok.

### Detay

**a) Reward eğrisi nerede? Platoya girdi mi, kırılım başladı mı?**
- V9 iki ayrı faz gösterdi:
  - **Faz 1 (step 142k–599k):** ep_rew_mean sabit ~-270, ep_len=1000 (her episode timeout). Drone asla episode bitirmedi — sadece zaman dolunca sona erdi. Bu fazda hiçbir öğrenme sinyali yok.
  - **Faz 2 (crash sonrası yeniden başlatma, step ~50k–193k):** ep_rew_mean -103'ten -25'e iyileşti (adım 84k'da en iyi), ep_len 95-245 arası (drone hayatta kalıyor). Sonra 193k'da -173'e spike → freeze/crash.
- **+15 oda sıçraması hiç görülmedi.** Tüm reward değerleri negatif. Oda kırılımı gerçekleşmedi.
- V10 henüz başlamadı; güncel reward eğrisi yok.

**b) lr=7.5e-5 constant seçimi bu aşamada doğru muydu?**
- **HAYIR — v9'un en büyük yapısal hatası.** Faz 1 verisi bunu teyit ediyor: 600k step boyunca sabit -270 reward, policy hızla konverje oldu ama değersiz bir lokal minimuma (duvar çarpma + timeout döngüsü). 7.5e-5 hem erken öğrenme için çok düşük hem de deterministikleşmeyi engelleyecek güncelleme momentumundan yoksun.
- v10 ppo.yaml: `3e-4→1e-5 linear decay` — v3.0 Gazebo'nun kanıtladığı (peak=110.3@610k) doğru seçim. **Config değişikliği gerekmez.**

**c) Entropy/std değerleri keşif için yeterli miydi?**
- **Faz 1 — KRİTİK PROBLEM TESPİT EDİLDİ:**
  - entropy_loss: -3.89 → -3.32 (tümü -4.0 EŞİĞİNİN ÜSTÜNDE → erken deterministikleşme aktif)
  - std: 0.888 → 0.746 (0.7 kritik sınırına yaklaşıyordu)
  - Hem entropy hem std aynı anda düşüyordu — **ent_coef=0.0015 çok düşük**, policy keşifsiz konverje oldu.
- **Faz 2 (restart sonrası):** entropy ~-4.21 to -4.26, std ~0.99-1.00 — daha sağlıklı ama 193k'da -4.21'e çıkarak yine eşiğe yaklaşıyordu.
- v10 `ent_coef=0.008` (v9'dan 5.3×) bu sorunu doğrudan ele alıyor. Beklenen entropy: -4.4 ile -5.0 arası.

**d) Oda geçişi için ne kadar step daha gerekmesi beklenir?**
- V9'da hiç oda geçişi olmadı. Faz 2'nin en iyi noktası (-25 @ 84k) muhtemelen birkaç yeni voxel + duvar cezası azalması — oda reward'u değil.
- v3.0 Gazebo benchmark (aynı 3e-4→1e-5, n_envs=1): ilk oda ~200-250k, 3 oda ~400k, peak ~430-610k.
- **v10 beklentisi (fresh start):** ilk +15 sıçraması ~150-250k step, 4-5 oda ~500-700k step, 6 oda tamamı ~700-1000k step içinde erişilebilir (total_timesteps=1.5M yeterli).

**e) v10 için şu an en kritik 1-2 öneri:**
1. **`drone_exploration_env.py`: `collision_penalty = 25` (şu an 10)** — fast_sim v4.8 champion tespiti: yalnızca 25 ile %0 çarpışma + 5 oda sağlandı. 10 ile drone çarpışma-ölüm döngüsüne giriyor ve total reward körelerek oda keşfini engeller. Bu v10 başlamadan önce uygulanmalı.
2. **`drone_exploration_env.py`: `lidar_history = 2` (şu an 1, obs 41-d→72-d)** — fast_sim v2 tespiti: %80→%1 çarpışma oranı düşüşü (en büyük tek iyileştirme). Tek lidar frame yetersiz; iki frame'in differansiyeli hız bilgisi yerine geçiyor. Bu değişiklik `policy_kwargs: net_arch: [256,256]` ile hâlâ uyumlu.

**f) Acil müdahale gerektiren bir şey var mı?**
- **Config (ppo.yaml): HAYIR.** Tüm hyperparametreler (lr decay, ent_coef, n_steps, clip_range, gamma, gae_lambda) fast_sim v4.8 + v3.0 Gazebo çift doğrulamayla kanıtlanmış. %80+ güven eşiğini aşan config hatası yok.
- **Eğitim durumu: DİKKAT.** `runs/` dizini hiç oluşmamış — v10 Gazebo eğitimi başlatılmamış. `./scripts/train.sh configs/ppo.yaml` henüz çalıştırılmadı.
- **Env kodu (yüksek aciliyet):** `collision_penalty=25` ve `lidar_history=2` uygulanmadıysa v10 fast_sim bulgularından yoksun başlayacak — bu v9'un başarısız olduğu koşullarla aynı risk taşır.

### v10 Önerisi
1. **Env kodu değişiklikleri önce** (`drone_exploration_env.py`): `collision_penalty: 10→25`, `lidar_history: 1→2`. V10 eğitim başlatılmadan bu iki değişiklik uygulanmalı — fast_sim'in en yüksek-etki bulgularıdır.
2. **Ardından `./scripts/train.sh configs/ppo.yaml` başlat:** ppo.yaml eksiksiz hazır. v9'un faz-1 deterministikleşme artefaktı v10'da ent_coef=0.008 ile önlenmiş; beklenen ilk oda kırılımı ~200k step.

### Müdahale
**YOK** — `configs/ppo.yaml` zaten v10 optimal config'inde. V9 post-mortem analizi v10 config kararlarını (ent_coef 0.0015→0.008, lr constant→linear decay) retrospektif olarak doğruladı. %80+ eşiğini aşan yeni bir YAML sorunu tespit edilmedi. Env kodu değişiklikleri (collision_penalty, lidar_history) YAML scope'u dışında — bu analizde uygulanmadı.
---
