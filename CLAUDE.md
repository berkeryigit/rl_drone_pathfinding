# CLAUDE.md — A3C Branch (Claude bunu OTOMATİK okur)

Merhaba Claude. Bu repo bir KOU pekiştirmeli öğrenme dönem projesi. Sen **A3C (discrete)**
ile çalışan ekip üyesine yardım ediyorsun. Aşağısı senin tam bağlamın + yapılacaklar listesi.

## 0. EN ÖNEMLİ KURAL — BRANCH
- Bu iş **`algo/a3c`** branch'inde yapılır. **`main`'e ve `algo/ppo`'ya ASLA push etme.**
- İlk iş: `git fetch origin && git checkout algo/a3c && git pull origin algo/a3c`.
- Tüm commit/push **sadece `origin algo/a3c`**.

## 1. Proje 1 paragraf
Tek katlı 6 odalı **sabit** binada lidar+odometri ile keşif yapan drone. Amaç: **çarpışmadan
maksimum zemin voxel'i gezmek.** Ekip aynı ortamda farklı RL algoritması koşup karşılaştırıyor
(PPO/TD3 continuous, A3C/DQN discrete). Senin algoritman **A3C** → **discrete** aksiyon.
Ortam, Berker'in PPO'su (`algo/ppo`) ile **birebir aynı**; tek fark aksiyon uzayı.

## 2. Donanım/ortam (bu ekip: MacBook → Ubuntu 24.04 VM)
- **NVIDIA GPU YOK** → torch **CPU**, Gazebo **yazılım render** (mesa/llvmpipe). fps düşük (~5–15), normal.
- Apple Silicon ise VM **arm64**; base image'ler (`osrf/ros:jazzy-desktop`) çok-mimarili.
- Kurulum 2 yol (detay: `docker/README.md`):
  - **NATIVE (önerilen):** VM'de ROS Jazzy + gz Harmonic + venv. Bkz `a3c_talimatlar.md` §1.
  - **Docker (CPU):** `docker/docker-compose.cpu.yml` (NVIDIA'lı `docker-compose.yml`'i KULLANMA).
- GPU'suzken her terminalde: `export LIBGL_ALWAYS_SOFTWARE=1 GZ_IP=127.0.0.1 SIM_HEADLESS=1`

## 3. Berker'in PPO'da ACI ÇEKEREK öğrendiği DERSLER (bunlara uy)
1. **TEK sim / TEK env (`n_envs=1`).** Çoklu Gazebo süreci BOZUYOR (transport çakışması,
   step ~2048'de donma). A3C aslında async-multi-worker'dır → bu ders A3C ile çelişir;
   bu yüzden **A2C'yi n_envs=1 ile** koşuyoruz (= senkron/tek-worker A3C). Bkz `train_a2c.py` başı.
2. **`GZ_IP=127.0.0.1` ŞART.** Çoklu ağ arayüzünde gz transport "Host unreachable" verip
   `reset()`'i asıyor, eğitim **step ~2048'de donuyordu.** `train_a2c.sh` bunu ayarlıyor.
3. **"core dumped / python3.12 çöktü" ZARARSIZ** — process çıkarken rclpy/gz teardown segfault'u;
   model önce kaydedilir, kayıp yok. Latest checkpoint'ten resume et.
4. **Checkpoint+resume:** her 20k step checkpoint. Crash olursa `resume_from: <latest>` + restart.
5. **Harita/başlangıç SABİT:** `multi_room.sdf`, drone modeli, **R0 (-5,-5) spawn** değişmez. 3 hareketli engel kalır.

## 4. Discrete aksiyon (PPO'dan tek fark)
Env `discrete=True` → **Discrete(4)**: 0=ileri, 1=sol, 2=sağ, 3=dur. Gözlem 40-d, ödül v2.1
(yön-duyarlı lidar cezası) — PPO ile aynı. `train_a2c.py` bunu otomatik kullanır.

## 5. Çalıştır / izle / değerlendir
```bash
# kurulum sonrası tek komut (sim açar, GZ_IP+headless ayarlar, A2C başlatır):
./scripts/train_a2c.sh configs/a2c.yaml
# izleme:
source .venv/bin/activate
python3 scripts/tb_metrics.py --config configs/a2c.yaml   # step/reward/voxels/ep_len JSON
tensorboard --logdir runs/a2c_v1/tb
# eğitim sonu kıyas (100-ep kapsama + çarpışma %):
python3 scripts/eval_coverage.py --model runs/a2c_v1/checkpoints/a2c_drone_final.zip --episodes 100 --version a2c_v1
```

## 6. ✅ YAPILACAKLAR LİSTESİ (sırayla işle, her adımı doğrula)
- [ ] **T1.** `git checkout algo/a3c` (doğru branch — kontrol et: `git branch --show-current`).
- [ ] **T2.** Ortam: VM'de ROS Jazzy + gz Harmonic var mı? Yoksa `docker/README.md` Yol 1/2.
- [ ] **T3.** `cd ros2_ws && colcon build --symlink-install && cd ..` — hatasız derlensin.
- [ ] **T4.** `python3 -m venv .venv --system-site-packages && source .venv/bin/activate && pip install -r requirements.txt` (CPU torch; arm64'te torch wheel sorun olursa `pip install torch`).
- [ ] **T5.** Smoke testi (`a3c_talimatlar.md` §1): `Discrete(4)`, voxel artıyor, çarpışma yok.
- [ ] **T6.** `export LIBGL_ALWAYS_SOFTWARE=1` + `./scripts/train_a2c.sh configs/a2c.yaml` → sim açılıyor, **step 2048'i geçiyor** (donmuyor!), reward zamanla yükseliyor.
- [ ] **T7.** İzle: ep_len_mean artıyor mu (çarpışma azalıyor mu), voxels_max yükseliyor mu.
- [ ] **T8.** Plato/sorun olursa: `fixes.txt` + Berker'in `algo/ppo` `docs/PROGRESS.md`'sine bak; lr↓ veya ent ayarı.
- [ ] **T9.** Hedef step'e (config 700k; GPU'suz yavaşsa önce 300k) ulaşınca `eval_coverage.py` ile 100-ep değerlendir + figürler.
- [ ] **T10.** Loglar/figürler/`docs/REPORT.md` ile A3C sonucunu PPO ile karşılaştır (rapor için).
- [ ] **T11.** `git add -A && git commit && git push origin algo/a3c` (SADECE bu branch).

## 7. Loglama (rapor için — şart)
Her şey otomatik loglanıyor: `runs/a2c_v1/progress.csv`, TB, `scripts/report.py` → `docs/figures/`,
`docs/REPORT.md`. Hata+çözüm → `fixes.txt`, ilerleme → `docs/PROGRESS.md`. Bunları güncel tut.

## 8. (Opsiyonel) Otonom operatör
`.claude/agents/rl-train-operator.md` — Berker'in kurduğu otonom izleme/kurtarma/versiyon-atlama
playbook'u. İstersen periyodik kontrol için kullan (config'i `configs/a2c.yaml` ver).

## 9. Daha fazla detay
- Adım adım kurulum/çalıştırma: **`a3c_talimatlar.md`**
- Docker/VM/GPU'suz: **`docker/README.md`**
- PPO'nun tüm hata/çözüm geçmişi: `algo/ppo` branch'inde `fixes.txt` + `docs/PROGRESS.md`

Takıldığın her noktada önce `fixes.txt`'e bak — muhtemelen Berker o tuzağa çoktan düşüp çözmüştür. 🚁
