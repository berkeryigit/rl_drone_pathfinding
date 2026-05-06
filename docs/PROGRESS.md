# PROGRESS — rl_drone_pathfinding

Adım adım yapılan işler. Her bloğun başında tarih + kim + neyi neden yaptı.

---

## 2026-05-05 — Berker — Pipeline iskeleti (Day 0)

Yarın eğitim koşulabilsin diye sadece **pipeline + Docker + GitHub repo** kuruldu;
training koşulmadı.

### Dosyalar

* `ros2_ws/src/rl_drone_pathfinding/package.xml`, `setup.py`, `setup.cfg`,
  `resource/rl_drone_pathfinding`
  → ament_python ROS 2 paket iskeleti. Entry-points: `train_ppo`, `eval_ppo`,
  `env_smoke_test`.

* `ros2_ws/src/rl_drone_pathfinding/worlds/multi_room.sdf`
  → 16x16 m kapalı bina, 4 oda (NE/NW/SW/SE), iç duvarlarda 2 m'lik kapı
  boşlukları, 3 statik engel (silindir + kutu).
  Pluginler: physics, user-commands, scene-broadcaster, sensors (ogre2),
  imu, contact.

* `ros2_ws/src/rl_drone_pathfinding/models/rl_drone/{model.config, model.sdf}`
  → Hover-drone (gravity link-level off). 0.30×0.30×0.10 chassis + nose marker.
  Sensorler: 360 ışınlı planar gpu_lidar (10 m, gauss σ=0.02), IMU.
  Pluginler: `gz-sim-velocity-control-system` (cmd_vel, body frame),
  `gz-sim-odometry-publisher-system`, `gz-sim-pose-publisher-system`.

* `ros2_ws/src/rl_drone_pathfinding/config/ros_gz_bridge.yaml`
  → `clock`, `scan`, `imu`, `odom` (GZ→ROS) ve `cmd_vel` (ROS→GZ) köprüleri.

* `ros2_ws/src/rl_drone_pathfinding/launch/sim_launch.py`
  → `gz sim`'i dünya ile başlat → `ros_gz_sim::create` ile drone'u (4, -4, 0.6)
  pozisyonunda spawn et → `parameter_bridge` ile YAML'dan köprüleri kur.
  `GZ_SIM_RESOURCE_PATH` ayarlanıyor ki SDF include'ları çözülsün.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env.py`
  → `DroneExplorationEnv(gym.Env)`. Arka planda rclpy thread'i (`_RosBridge`
  node'u) lidar/odom dinler, ana thread cmd_vel publish eder.
  Reset: `gz service /world/multi_room/set_pose` ile drone'u 4 spawn'dan
  birine teleport eder.
  Obs 40-d, action 2-d (v, ω). Reward: yeni hücre +1, yeni oda +15,
  çarpışma -10 (terminate), yakın engel -0.5, idle -0.1, step -0.001.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_ppo.py`
  → SB3 PPO, YAML'dan hyperparameter okur, `CheckpointCallback`, TensorBoard.

* `ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/eval_ppo.py`
  → trained `.zip`'i yükle, N episode roll-out, return + cells + rooms istatistiği.

* `configs/ppo.yaml`
  → lr 3e-4, n_steps 2048, batch 64, ent_coef 0.005, MlpPolicy [128,128].
  total_timesteps 500k, save_freq 25k.

* `requirements.txt`
  → gymnasium 0.29.1, stable-baselines3[extra] 2.3.2, torch 2.4.0, pyyaml,
  tensorboard, tqdm.

* `docker/Dockerfile`
  → `osrf/ros:jazzy-desktop` üstüne `ros-jazzy-ros-gz*`, `gz-harmonic`,
  Cyclone DDS, python ML stack (CUDA 12.1 wheels). Non-root `dev` user host
  UID/GID ile eşleşiyor.

* `docker/docker-compose.yml`
  → `network_mode: host`, `ipc: host`, NVIDIA runtime, X11 socket mount,
  repo `/workspace`'e bind mount. ROS_DOMAIN_ID=42.

* `docker/{build.sh, run.sh}`
  → host UID/GID ile build + `xhost +local:docker` + container'a shell.

* `.gitignore`, `README.md`, `fixes.txt`

### Aynı gün — pip + venv + smoke test (eğitim öncesi son hazırlık)

Yarın eğitim koşulurken sürpriz çıkmasın diye Python tarafı da bugün doğrulandı.

* `python3 -m venv .venv --system-site-packages` (rclpy gibi ROS Python paketlerini
  görmesi için `--system-site-packages` şart) + `pip install -r requirements.txt`.
* `requirements.txt`: `stable-baselines3[extra]==2.3.2` Python 3.12 ile uyumsuz
  (ale-py 0.8 build edemiyor) → düz `stable-baselines3==2.3.2` + ayrı
  `tensorboard` / `rich` ile değiştirildi.
* Torch 2.4.0 + NVIDIA CUDA 12.1 wheel'leriyle kuruldu (~2GB).
* `python3 -m rl_drone_pathfinding.envs.smoke_test` — sim canlı iken: env
  reset OK, 50 step OK, lidar normalize doğru (0.10..0.40), reward fonksiyonu
  çalışıyor, exception yok. **Pipeline yarın eğitime hazır.**
* `scripts/setup.sh` (colcon + venv + pip), `scripts/train.sh` (sim auto-launch
  + train_ppo), `scripts/eval.sh` eklendi → README güncellendi.

### Aynı gün — host'ta sim doğrulama koşusu

Docker'a girmeye gerek kalmadan host'ta (Ubuntu 24.04 + ROS Jazzy + gz Harmonic
+ ros-jazzy-ros-gz*) doğrulama yapıldı, **eğitim koşulmadı**.

İlk denemede **2 bug** çıktı, ikisi de düzeltildi (detay `fixes.txt`'de):

1. `setup.py` data_files: `glob('models/*')` → setuptools dir kopyalayamayıp
   colcon build fail ediyor. Her model dir için ayrı entry yazıldı:
   `(share/.../models/rl_drone, glob('models/rl_drone/*'))`.
2. `launch/sim_launch.py`: `IncludeLaunchDescription` için `gz_args`'a `-r`
   eklenmemişti → gz paused başlıyor, sensör/clock publish etmiyordu.
   `'gz_args': f'-r -v 3 {world_file}'` olarak düzeltildi.

Doğrulama sonucu (host, `ros2 launch rl_drone_pathfinding sim_launch.py` +
elle `ros2 topic pub /cmd_vel`):

* /clock + /scan + /odom + /imu hepsi yayında, sim time akıyor.
* `cmd_vel.linear.x = 0.3` 3s → drone y: -4.0 → -3.04 (~0.95m, beklenen 0.9m).
  Yaw=π/2 spawn olduğundan body-x → world +y, doğru.
* `cmd_vel.angular.z = 0.5` 2s → yaw 1.57 → 2.65 rad (Δ≈1.08, beklenen 1.0).
* Z sabit 0.6 → link-level gravity-off doğru çalışıyor.

### Yarın (2026-05-06) eğitim — tek satır

```bash
cd ~/Desktop/RLProje/rl_drone_pathfinding
./scripts/train.sh                              # configs/ppo.yaml, 500k step
# ayrı terminal: source .venv/bin/activate && tensorboard --logdir runs/ppo/tb
```

500k step için RTX-class GPU'da ~süreyi ölç ve buraya not düş. Eğer 8 saat+ olursa
configs/ppo_quick.yaml diye `total_timesteps: 100000` olan bir varyant aç,
önce onunla baseline al.

### İleride (eğitimden sonra)

1. (opsiyonel, sadece ekip teslimatı için) `./docker/build.sh` → image build.
2. Reward eğrisi + ep_len + custom metrik (cells, rooms) TensorBoard'da grafik.
3. Dinamik kapı + hareketli engel + lidar gürültüsü senaryoları (PDF §2 + §3).
4. PPO vs (TD3 / DQN / A3C) karşılaştırma — ekip arkadaşlarının kendi paketleri
   (ya ayrı klasör ya ayrı branch) hazır olunca aynı env üstünde koşturup
   reward/cells/rooms karşılaştır.

---

## 2026-05-06 — Berker — Eğitim run 2 (resume) → run 3 (exploration boost)

### Run 2: 140k → 290k step (sabah)

* `configs/ppo.yaml`: `total_timesteps: 500000`,
  `resume_from: ppo_drone_140000_steps.zip`. `train_ppo.py`'a
  `reset_num_timesteps=False` eklendi → checkpoint sayacı korunarak resume.
* Saat 10:24'te checkpoint 288544'e ulaştı, eval için durduruldu.
* Eval gözlemi (saat 10:30, GUI'li): drone spawn odasından çıkamıyor, hover +
  duvardan kaçma loop'una sıkışmış. Local optimum.
  - `ep_len_mean` 299 → 381 (yaşıyor)
  - `ep_rew_mean` -12.7 → -19 (sadece -0.001 step + -0.1 idle topluyor)
  - `entropy_loss` -3.62 (hâlâ keşif var ama yetmemiş)
  - Sebep: door-crossing +15 ödülü gamma=0.99'la bu kadar uzaktayken value
    fn göremiyor. Discovery sinyali zayıf.

### Run 3: 290k → 2M step (saat 10:35'te başladı, ~10-12 saat)

Yapılan müdahaleler:

* `envs/drone_exploration_env.py` — discovery rewards 3x:
  - yeni voxel: `+1.0 → +3.0`
  - yeni oda:   `+15  → +50`
  - yeni kat:   `+25  → +100`
  Çarpışma/idle/step penaltyleri AYNI bırakıldı (keşif bonusunu artırmak amaç,
  güvenlik sinyalini bozmamak için).
* `configs/ppo.yaml` — `ent_coef: 0.005 → 0.02` (4x policy entropy bonusu).
  Toplam: discovery × 3 + entropy × 4 = "bir tık daha cesur ol, bulduğunda da
  daha çok kazan."
* `agents/train_ppo.py`:
  - **Bug fix**: SB3'te `reset_num_timesteps=False` iken `total_timesteps`
    DELTA olarak yorumlanıyor (SB3 internally num_timesteps ekliyor). YAML
    yorumu "absolute" diyordu ama davranış öyle değildi. Resume'de
    target - current hesaplanıp delta olarak learn()'e geçildi → yaml
    gerçekten absolute oldu.
  - **Override eklendi**: `PPO.load()` kaydedilmiş hyperparametreleri geri
    yüklediği için, resume'den sonra `model.ent_coef = yaml.ent_coef`
    set ediliyor. Yoksa yaml'daki 0.02 etkisiz kalırdı.
* Resume kaynağı: `ppo_drone_290k_pre_eval.zip` (interrupted.zip'in yedeği,
  step=292337). Yeni interrupt'lar interrupted.zip'i overwrite etse de bu
  yedek korunur.

Beklenen: ilk 50-100k step'te reward DÜŞÜŞÜ olabilir (entropy yüksek + value
fn yeni reward ölçeğine adapte olurken). Sonra ep_rew_mean'in net pozitife
çıkması beklenir, çünkü bir tek door-crossing artık +50 (eskiden -19'luk bir
episode'u tek başına +30'a çevirir).

### Run 3 ↻ pivot: sıfırdan başlat + SDF deliklerini büyüt (saat 11:00)

Run 3'ü ~5 dk sonra durdurduk. Sebep: yeni reward fonksiyonu eski value
function'ı geçersiz kılıyor; over-converged 290k policy'den kurtulmak yerine
**baştan başlamak daha temiz** (öğrenme zaten 290k harcandı, FAKAT o policy
"hover" ezberlemişti — tablanın silinmesi 1.7M step'in büyük kısmını
zaten yeniden yatırım sayılır, üstelik temiz bir öğrenme eğrisi raporlama
için ÇOK daha güzel).

#### Çıkarılan/Yeniden yapılan kararlar

1. **FAST-LIO 2 fikri reddedildi.** Berker önerdi: arka planda lidar SLAM
   koşturup map çıkaralım, observation'a ekleyelim. Reddedildim çünkü:
   (a) sim'de zaten ground-truth pozisyon var (`/odom`), env de kendi
   voxel grid'ini tutuyor; (b) SLAM pipeline sim FPS'i 39→~10'a düşürür;
   (c) map'i observation yapmak için MLP yerine CNN gerek → mimari değişir,
   1 günlük iş; (d) rapor için süslü ama task'a katkı yok.

2. **SDF: Floor delikleri 2x2 → 3x3 büyütüldü.**
   - Berker GUI'de floor 1→2 deliğini bulamadığını söyledi. Matematiksel
     olarak vardı (SW quadrant, x∈[-6,-4], y∈[-6,-4]) ama 2x2 bir delik
     16x16 binada drone'un random keşifle bulması zor.
   - Yeni:
     * Floor 0→1 hole: NE quadrant, x∈[3.5,6.5], y∈[3.5,6.5] (3x3)
     * Floor 1→2 hole: SW quadrant, x∈[-6.5,-3.5], y∈[-6.5,-3.5] (3x3)
   - Alan 2.25x büyüdü, tesadüfen üstünden geçme şansı ~2x.
   - SDF link'ler yeniden boyutlandırıldı: floor*_left/right/mid_s/mid_n
     panelleri tam delik etrafını saracak şekilde.
   - Env docstring güncellendi.

3. **Eski runs/ppo/ koruma kararı.** v1 (eski reward + 2x2 delik + ent_coef
   0.005) sonuçları silinmedi:
   * `runs/ppo/checkpoints/` → 140k, 248k, 268-288k step'ler hâlâ orada
   * `runs/ppo/tb/` → TensorBoard logları
   * Yeni v2 run yeni klasöre yazıyor: `runs/ppo_v2_explore/`
   - Hocaya rapor gösterirken: "v1'i denedik, drone spawn'da takıldı (eval
     videosu + TB grafiği). Reward fonksiyonunu rölelendirip + entropy
     bumpladık + SDF delikleri büyüttük → v2'de şu sonuca ulaştık."
     Bu iterasyonlu deney narratif raporda artı.

4. **Yaml: `resume_from: null`**, output paths'ı `runs/ppo_v2_explore/`'a
   çevirdik. `total_timesteps: 2000000` aynı (artık absolute target,
   train_ppo.py fix'i sayesinde).

#### v2 run plan'ı

Saat 11:05 başladı: sıfırdan 2M step, ~12-14 saat (sıfırdan başlamak
+~%20 yavaş çünkü ilk 50k random eylemlerle çok episode terminate ediyor).
Berker eve giderken çalışıyor olacak; checkpoint her 10k step'te,
overwrite-safe.

### v2 → v3 pivot: multi-floor spawn (saat 11:50)

#### Gözlem (140k step eval)

v2 başarılı kısmı: ep_rew_mean -33 (10k) → +3 (65k) → **+40 (140k)**.
Discovery rewards + ent_coef bumpı tutmuş, drone artık spawn odasında
takılı değil — çoklu oda dolaşıyor, kapıları geçiyor.

v2'nin hâlâ eksik kısmı: drone **sadece floor 0'da** dolaşıyor. Berker
eval'i 11:48-11:50 arasında izledi, drone hep aynı katta. Üst katlara
hiç çıkmıyor.

#### Sebep teşhisi

1. **Spawn hep floor 0'da.** SPAWN_CANDIDATES'in 5 noktası da z=0.6'da
   (zemin). PPO on-policy → drone training rollout'larında üst katları
   asla deneyimlemiyor → value function "yukarı çıkma" eylemine değer
   atfedemiyor.
2. **Vertical hareket pahalı.** vz_max=0.4 m/s, 2.5m yüksekliğe çıkmak
   ~6 saniye = forward exploration zaman kaybı. Anlık discovery reward
   kaybı gamma=0.99 ile değerlendirildiğinde +100'lük gecikmiş floor
   bonusundan değerli görünüyor.
3. (4,4,0.6) NE spawn'ı tam delik altı ama yine de yukarı çıkmıyor —
   çünkü hiç yukarı çıkmış trayektory tatmamış, value function
   up-direction action'a 0 yakın değer veriyor.

#### v3 müdahaleleri

* `envs/drone_exploration_env.py` — SPAWN_CANDIDATES diversifiye edildi:
  - 5 spawn floor 0 (eskisi gibi)
  - 2 spawn floor 1 (z=3.1, NE delik üstü ve NW)
  - 1 spawn floor 2 (z=5.6, SW delik üstü)
  - **Cheat değil** çünkü `_visited_floors` reset'te spawn floor ile
    prefill ediliyor, +200 ancak başka floor'a geçince veriliyor.
  - Beklenen etki: %37 ihtimalle drone üst katta uyanır, oradan keşfe
    başlar, value fn üst katları da öğrenir, ileri rollout'larda "yukarı
    çıkmak yararlı" gradient'i belirir.

* `envs/drone_exploration_env.py` — `new_floor` bonusu **+100 → +200**.
  Floor geçişi en nadir event, oda (+50) ile arasındaki oran 4x'e
  çıkarıldı.

* `configs/ppo.yaml` — output dizini `runs/ppo_v3_floors/`'a alındı,
  v2 sonuçları `runs/ppo_v2_explore/` altında dokunulmadan kalıyor.
  `resume_from: ppo_drone_140000_steps.zip` (v2'nin 140k checkpoint'i —
  floor 0 navigation öğrenilmiş, oradan üst katları eklemek hızlı olur).

#### v3 run plan'ı

Saat 11:55 başladı: 140k → 2M (1.86M step delta), ~12-14 saat. Eğer
~250-300k civarı eval'de drone üst kata çıkmaya başlamamışsa, daha
agresif tweak'ler gerekecek (örn. voxel multiplier üst katlarda,
intrinsic curiosity bonus). Şu an minimal-değişiklik prensibi.

### v3 → v4 pivot: entropy explosion fix (saat 22:15)

#### Veri (1.45M step'te durduruldu, plot scriptiyle teşhis)

`scripts/plot_training.py` koşturup TB event'lerinden v1/v2/v3 6-panel
grafiği + entropy zoom + reward zoom çıkarıldı (`docs/figures/`).

**Bulgular:**

1. `docs/figures/v3_plateau_zoom.png` — ep_rew_mean **plateau değil,
   regression**: 440k civarı PEAK ~+95, sonra +40-50'ye geri düştü.
   1.0M-1.45M ortalaması ~+45.

2. `docs/figures/entropy_zoom.png` — KRİTİK BULGU: action distribution
   `std` **1 → 14**'e patladı (action space [-1,1] iken!). `entropy_loss`
   -4 → -12 (daha negatif = yüksek entropi). Yani policy çökmedi —
   tam tersi, **explode etti.**

3. v3/310k eval'de "rooms=1 in 10/11 episodes" gözleminin sebebi şu:
   `--deterministic` eval mean action kullanır. Mean action zayıf çünkü
   policy std'sini büyüterek (rastgele aksiyon → bazen kazanç) reward
   topluyor; mean action'ı optimize etmiyor.

#### Sebep teşhisi

`ent_coef × entropy_loss` PPO loss'una eklenir. Reward magnitude büyük
olduğunda (oda +50, kat +200), advantage büyük → policy gradient büyük.
ent_coef=0.02 entropi'yi maximize etmek için **policy std'sini büyütme**
gradient'i veriyor (Gaussian entropy = 0.5·log(2πeσ²) → std artırmak
entropi artırır, ücretsiz bonus). Reward gradient bunu durduramamış.

#### v4 müdahaleleri

A. **`ent_coef`: 0.02 → 0.001** (20x düşürüldü). Entropi bonusu hâlâ
   var ama std'yi büyütme cezbeden değil. Policy doğal olarak std'yi
   küçültür, mean action gradient'i hâkim olur.

B. **Idle penalty time-decay** (`envs/drone_exploration_env.py`):
   ```python
   if self._steps_since_new_voxel < 30:
       reward += -0.1     # arama, yön bulma — normal
   else:
       reward += -0.5     # oda biten, ÇIK
   ```
   v3'te drone spawn odasında 850 step idle olup -85 birikiyordu ama
   yine de net pozitif kalıyordu (+150 voxel). Yeni decay ile aynı
   strateji -425 (5x ceza) → net negatif → drone başka odaya gitmek
   zorunda kalır.

C. **Resume from peak (440k)** — fresh start değil. v3'ün öğrenmiş
   olduğu floor 0 navigation + biraz da floor 1/2 farkındalığını
   koruyalım. ent_coef düşük olunca policy std'si bu peak'ten itibaren
   düşmeye başlayacak.

D. Output `runs/ppo_v4_low_ent/`, v3 sonuçları korundu.

#### v4 run plan'ı

Saat 22:15 başladı: 440k → 2M (1.56M step delta), ~12 saat (yarın
~10:00 civarı biter). Beklenti:

- ilk 50-100k step'te reward düşebilir (idle decay sert, drone uyum
  sağlamaya çalışır)
- 600k civarı: std küçülmeye başlar (eski 14 → ~3-5)
- 1M+ : mean action policy iyileşir, deterministic eval'de rooms>1
- 2M sonu: hedef rooms 3-4 ortalama, ara sıra üst kata çıkış

Tüm grafikler `docs/figures/`:
- `training_curves_all.png` (6-panel v1-v2-v3)
- `reward_curve_summary.png` (tek panel reward özet)
- `v3_plateau_zoom.png` (regression görünür)
- `entropy_zoom.png` (KRİTİK: std explosion)

### v4 → v5 pivot: PPO update stabilization (saat 02:00)

#### Veri (v4 fresh, 310k step'te durduruldu)

`scripts/plot_training.py` v4 dahil yeniden koşturuldu. Bulgular:

1. **Entropy fix tutmuş** ✓ — v4'te std 1 → 0.7'ye **düşüyor** (v3'te
   1 → 14 explode etmişti). entropy_loss -4.3 → -3.0 (yukarı = az
   entropi). ent_coef 0.001 doğru çağrı.

2. **Reward hâlâ peak-then-regress paterni** ⚠ — v4 60-100k civarı peak
   ~+85'e ulaşıyor, sonra 200-310k arası **+30 ile +85 arası yüksek
   varyans osilasyon** ortalama ~+50. Yani v4 daha da **kötü** (yüksek
   varyans), reward summary grafiğinden net görünüyor.

3. v3 ile karşılaştırma:
   - v3: smooth ama yavaş peak (440k +95) sonra düşüş +45
   - v4: hızlı peak (80k +85) sonra osilasyon +30/+85 mean +50

#### Sebep teşhisi

Entropy düzelmesine rağmen reward osilasyonu sürüyor → sorun **PPO update
mechanics**, exploration değil. Yüksek magnitudeli reward (oda +50, kat
+200, idle decay -0.5, çarpışma -10) → yüksek varyans advantage → büyük
policy gradient güncellemeleri → her n_steps=2048 rollout'tan sonra
policy fazla değişiyor → sonraki rollout'ta data distribution kayıyor
→ önceki öğrenmeyi unutuyor.

PPO'nun bunu önlemek için clip_range=0.2 mekanizması var ama bizim
reward scale'imizde 0.2 hâlâ büyük. Ek olarak n_epochs=10 ile her
rollout'a 10 kez gradient gönderilmesi overfit'i derinleştiriyor.

#### v5 müdahaleleri (env'e dokunma yok, sadece PPO yaml)

| Param | v4 | v5 | Neden |
|---|---|---|---|
| `clip_range` | 0.2 | **0.1** | Per-step policy shift'i sınırla, overshoot durdur |
| `n_epochs` | 10 | **5** | Her rollout'tan daha az gradient pass, daha az overfit |
| `batch_size` | 64 | **256** | Minibatch gradient'i daha düşük varyanslı |
| `gae_lambda` | 0.95 | **0.9** | Advantage estimate biraz daha bias / az varyans |
| `ent_coef` | 0.001 | 0.001 | v4'te tuttu, koru |

Idle decay env değişikliği aynen v4'tekiyle korundu. Multi-floor spawn
+ bumped rewards aynı.

#### v5 run plan'ı

Saat 02:05 başladı: sıfırdan 350k watcher (v3/v4'te ne olduğunu anlamış
olduğumuz step sayısı), sonra durup eval + plot + (gerekirse) v6.
Beklenti: peak biraz daha geç gelir ama daha smooth, düşüşsüz / az
varyanslı plateau. Eğer hâlâ osilasyon varsa, v6'da reward
normalization (VecNormalize) veya lr schedule eklemek gerekecek.
