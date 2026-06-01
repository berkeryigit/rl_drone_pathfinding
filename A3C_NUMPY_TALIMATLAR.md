# A3C — NUMPY HIZLI SİM TALİMATLARI (Gazebo/ROS İPTAL)

> **Bu dosya, A3C ile çalışacak arkadaşın Claude'una hitaben yazılmıştır.**
> Berker (PPO tarafı) tüm zorlu dersleri çıkardı; aşağıdaki recete bunları içeriyor.

---

## ⚠️ 0. EN ÖNEMLİ DEĞİŞİKLİK — GAZEBO/ROS İPTAL

Arkadaşın **çok az vakti var.** Gazebo + ROS 2 kurulumu (Ubuntu VM, Docker, software render)
saatler alır ve yavaştır. **ARTIK GAZEBO/ROS KULLANMIYORUZ.**

Bunun yerine: **numpy/Gymnasium hızlı sim** (`fast_sim/`). Aynı ortamın 2D ray-cast klonu —
~100× hızlı (≈3000 fps), **MacBook'ta doğrudan çalışır** (sadece Python + pip, ROS YOK, GPU şart değil).

> Eski Gazebo dosyaları (`ros2_ws/`, `docker/`, `a3c_talimatlar.md`) repoda **arşiv** olarak duruyor
> ama **KULLANILMAYACAK**. Tüm iş `fast_sim/` + `configs/a3c_v*.yaml` üzerinden.

---

## 1. GÖREV

Tek katlı **6 odalı sabit** binada, lidar + odometri ile keşif yapan drone. Hareketli 3 engel var.
Amaç: **çarpışmadan maksimum voxel (zemin hücresi) gezmek.**

Ekip aynı ortamda farklı algoritmalar koşuyor (continuous vs discrete kıyası):
- Berker → **PPO (continuous)** `algo/ppo`  ← referans
- **Sen → A3C (discrete)** `algo/a3c`  ← BU BRANCH
- Diğerleri → TD3, DQN

**A3C notu:** SB3'te birebir "A3C" sınıfı yok. Senkron eşdeğeri **A2C** kullanıyoruz (aynı
actor-critic + advantage; "asenkron işçiler" yerine `n_envs=8` paralel env = senkron çoklu-işçi).
Literatürde A2C, A3C'nin pratik biçimidir — **raporunda böyle belirt.** Aksiyon **DISCRETE (7 aksiyon)**.

---

## 2. KURULUM (MacBook, ~5 dk)

```bash
cd <repo>/                       # rl_drone_pathfinding klasörü
git checkout algo/a3c
git pull origin algo/a3c
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_numpy.txt
```
ROS, Gazebo, Docker **GEREKMİYOR.** Hızlı test:
```bash
python3 fast_sim/fast_drone_env_discrete.py     # ~3000 fps + "obs (72,) Discrete(7)" yazmalı
```

---

## 3. NE YAPACAKSIN — 8 VERSİYON, HER BİRİ 1.5M, PROGRESİF İYİLEŞTİRME

Berker'in isteği: **8 model versiyonu eğit, her birinde parametreleri elinden geldiğince iyileştir.**
8 config hazır (`configs/a3c_v1.yaml` … `a3c_v8.yaml`), her biri bir öncekinin üzerine **kümülatif**
iyileştirme ekliyor (PPO'da kanıtlanmış derslere göre):

| Sürüm | Eklenen iyileştirme | Neden (PPO dersi) |
|---|---|---|
| **v1** | TABAN: lidar_history=1, sade ödül, collision 10 | Referans; çarpışma yüksek olacak |
| **v2** | **lidar_history 1→2** | 🔑 Çarpışmanın ASIL çözümü: 2 kare = engel hızı çıkarımı (PPO'da %80→%1) |
| **v3** | room_bonus 10→30 | Uzak odalara çekim (genişlik) |
| **v4** | far_voxel_bonus→1.0, idle_grace→30 | "Uza git" + yerel taramayı erken bitir → breadth |
| **v5** | **collision_penalty 10→25** | 🔑 "Gez SONRA hayatta kal" optimal olur (PPO'da %0 çarpışma verdi) |
| **v6** | ent_coef 0.01→0.02 | A2C/discrete keşfini artır (daha çok oda dene) |
| **v7** | n_steps 16→32, gae_lambda→0.98 | A2C kısa-rollout gürültüsünü azalt (kararlılık) |
| **v8** | FİNAL: entropi 0.015, en iyiler konsolide | Keşif/güvenlik dengesi — nihai teslim modeli |

### Çalıştırma — TEK KOMUT (önerilen)
```bash
bash scripts/run_a3c_all.sh
```
Bu, 8 versiyonu sırayla eğitir (her biri 1.5M) + 100-episode eval eder + figür/özet üretir.
Toplam ~1–2 saat (MacBook CPU). Çıktılar:
- `logs/a3c_results.txt` — 8 versiyonun EVAL_SUMMARY özeti
- `docs/EVAL_a3c_v*.md` — her versiyon detay tablosu
- `docs/figures/eval_a3c_v*_coverage.png` ve `_trajectories.png` — kapsama haritası + yörüngeler

### Ya da tek tek
```bash
python3 fast_sim/train_a3c.py --config configs/a3c_v2.yaml
python3 fast_sim/eval_a3c.py  --model runs/a3c_v2/checkpoints/a3c_drone_final.zip \
        --episodes 100 --version a3c_v2 --lidar-history 2   # <- config'teki lidar_history ile aynı olmalı!
```

> **DİKKAT:** eval'de `--lidar-history` değeri, o config'in `lidar_history`'si ile AYNI olmalı
> (v1 için 1, v2–v8 için 2). `run_a3c_all.sh` bunu otomatik yapar.

---

## 4. "İYİLEŞTİRME" NASIL OLMALI (Berker'in dersleri)

Recete sabit değil — **eval sonucuna bakıp ayarla.** PPO'da öğrenilenler:

1. **Çarpışmayı ödül DEĞİL gözlem çözer.** v2'deki `lidar_history=2` en büyük sıçramayı vermeli.
   Hâlâ yüksekse 3 dene (`configs`'te `lidar_history: 3`, eval'de `--lidar-history 3`).
2. **collision_penalty'nin tatlı noktası DAR.** PPO'da 25 optimaldi (%0), 22 çöktü, 30 %8, 50 %100.
   v5'te 25 ile başla; A3C'de farklı çıkarsa eval'e göre 20–30 arası tara.
3. **Aşırı ceza / aşırı entropi GERİ TEPER.** Çarpışma artarsa entropiyi (v6) düşür.
4. **Tek seferde tek şey değiştir.** Aynı anda çok parametre = kötü yakınsama (PPO v4.3'te %100 çarpışma).
5. **Eğitim süresi de kaldıraç:** 1.5M az gelirse en iyi versiyonu `total_timesteps: 3000000` yapıp uzat.

Her versiyon sonrası `logs/a3c_results.txt`'ye bak: **çarpışma oranı** ve **voxel/oda** nasıl değişti?
Bir değişiklik kötüleştirdiyse, sonraki versiyonda geri al ve not düş (rapor için değerli negatif sonuç).

---

## 5. macOS NOTU
`SubprocVecEnv` (paralel işçiler) macOS'ta `spawn` kullanır — `train_a3c.py` `if __name__` korumalı,
sorun olmamalı. Eğer takılırsa config'te `n_envs: 1` yap (yavaşlar ama çalışır). A3C için paralel
işçiler kavramsal olarak önemli; mümkünse 8'de bırak.

---

## 6. BRANCH KURALI (ÇOK ÖNEMLİ)
- Tüm commit/push **SADECE** `origin algo/a3c`'ye.
- `main`'e ve `algo/ppo`'ya **DOKUNMA.**
```bash
git add -A && git commit -m "a3c: vX egitim+eval sonuclari" && git push origin algo/a3c
```

## 7. RAPOR İÇİN
Bitince elinde şunlar olur: 8 versiyonun çarpışma/voxel/oda/kapsama tablosu (`logs/a3c_results.txt`),
her versiyon için kapsama+yörünge figürü, ve "v1→v8 nasıl iyileşti" anlatısı. Berker'in PPO sonuçlarıyla
**aynı formatta** olduğu için doğrudan kıyaslanır (continuous PPO vs discrete A3C).

**Bittiğinde Berker'e haber ver** — o kendi PPO branch'inde raporu yazıyor.
