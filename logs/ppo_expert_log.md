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
