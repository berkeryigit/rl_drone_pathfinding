# 🎬 Videoda Gösterilecek Kod + Ne Anlatmalı

> Az ama vurucu göster. 3 ZORUNLU snippet (çarpışma çözümü, ödül, config-farkı) + 2 opsiyonel.
> Dosya yolları repo köküne göre (`rl_drone_pathfinding/`).

---

## ⭐ 1. ÇARPIŞMA ÇÖZÜMÜ — `lidar_history` (EN ÖNEMLİ)
**Dosya:** `fast_sim/fast_drone_env.py` · satır **188, 206–207, 166**

```python
# reset() — gözlem geçmişini ilk kareyle doldur (satır 188)
self._lidar_hist = [lidar_obs.copy() for _ in range(self.lidar_history)]

# step() — her adım yeni lidar karesini ekle, son K kareyi tut (206–207)
self._lidar_hist.append(lidar_obs)
self._lidar_hist = self._lidar_hist[-self.lidar_history:]

# _make_obs() — K kareyi gözleme koy (166)
np.concatenate(self._lidar_hist),   # 32 * lidar_history
```
**Ne anlat:** "Projenin en kritik bulgusu bu üç satır. Drone'a tek lidar karesi yerine **son 2 kareyi**
veriyorum. Tek kareyle 'engel şu an şurada' bilgisini görür; iki kareyle **engelin hangi yöne ne hızla
gittiğini** çıkarsayıp önünden çekilir. Bu değişiklik çarpışmayı **%80'den %1'e** indirdi — aylarca
ödül ayarıyla çözemediğimi, doğru **gözlem tasarımı** çözdü."

---

## ⭐ 2. ÖDÜL FONKSİYONU — "dönüş ≈ voxel"
**Dosya:** `fast_sim/fast_drone_env.py` · satır **215–235** (`step()` içi)

```python
reward = -0.01                                    # her adım: zaman cezası
if new_voxel:
    far = min(1.0, hypot(x-SPAWN_X, y-SPAWN_Y)/16) # uzaklık 0..1
    reward += 1.0 + self.far_voxel_bonus * far     # yeni hücre (+uzaksa ekstra)
else:
    self._idle += 1
    if self._idle > self.idle_grace:
        reward -= self.idle_penalty                # oyalanma cezası
if new_room:
    reward += self.room_bonus                      # yeni oda kilometre taşı
if scan_min < 1.0:
    reward -= 0.5 * (1.0 - scan_min)               # duvara yaklaşma cezası
reward += 0.05 * forward_open * forward_act        # ileri-açık bonusu
if scan_min < 0.30:                                # ÇARPIŞMA -> terminal
    reward -= self.collision_penalty
```
**Ne anlat:** "Ödül felsefem net: **toplam ödül ≈ gezilen voxel sayısı.** Her yeni hücre +1, yeni oda
büyük bonus, çarpışma büyük ceza, oyalanma ufak ceza. `room_bonus`, `collision_penalty`, `far_voxel_bonus`
gibi katsayıları versiyondan versiyona değiştirip davranışı şekillendirdim — işte tüm deneyler bu
katsayıları aramaktı."

---

## ⭐ 3. VERSİYONLAR ARASI FARK — Config (tek satır = farklı sonuç)
**Dosya:** `configs/fast_v4_8.yaml` vs `configs/fast_v4_10.yaml`

```yaml
# v4.8 (GÜVENLİ, %0 çarpışma)        # v4.10 (KAPSAM, 281 voxel/6 oda, %54)
collision_penalty: 25.0              collision_penalty: 25.0   # AYNI
far_voxel_bonus:   1.0               far_voxel_bonus:   1.0    # AYNI
total_timesteps:   2000000           total_timesteps:   5000000  # ← TEK FARK
```
**Ne anlat:** "Burası çok çarpıcı: v4.8 ile v4.10'un **ödül/ceza ayarları BİREBİR AYNI** — tek fark
eğitim süresi, 2 milyon vs 5 milyon adım. Yani v4.10'un çok daha fazla keşfedip ama çarpması *farklı
ödülden değil*, sadece **daha uzun eğitimden** geldi. Bu, eğitim süresinin de bir denge kaldıracı
olduğunu gösteriyor." *(v4.1'i de aç: `collision_penalty: 10` + `far_voxel_bonus: 0` → 2 odaya hapsoldu.)*

---

## (Opsiyonel) 4. HIZLI SİM'İN KALBİ — numpy ray-cast lidar
**Dosya:** `fast_sim/fast_drone_env.py` · satır **123–154** (`_lidar()`)

**Ne anlat:** "Gazebo saniyede ~40 adım. Ben aynı 2B ortamı numpy ile **ışın-tarama (ray-cast)** olarak
yazdım: 360 ışını duvar segmentleri ve engel daireleriyle vektörize kesiştiriyorum. Sonuç ~4000 fps —
**100 kat hızlı**, bir gecede 14 deney." (Kodu satır satır okuma; 'vektörize ışın-duvar kesişimi' de yeter.)

---

## (Opsiyonel) 5. EĞİTİM KURULUMU — PPO + paralel env
**Dosya:** `fast_sim/train_fast.py` · satır **107, 130**

```python
venv = SubprocVecEnv(facs)            # 8 paralel env (numpy'de serbest)
model = PPO(policy, venv, learning_rate=..., n_steps=1024, ...)
```
**Ne anlat:** "Stable-Baselines3 PPO, 8 paralel ortam, VecNormalize ile ödül normalize. Gazebo'da çoklu
env sorun çıkarıyordu; numpy'de serbestçe 8 paralel koşturup eğitimi hızlandırdım."

---

## Gösterim sırası önerisi (videoda)
1. **Ödül fonksiyonu** (#2) → "hedefi koda nasıl döktüm"
2. **lidar_history** (#1) → "asıl atılım, çarpışma çözümü" *(en çok zaman buna ayır)*
3. **Config farkı** (#3) → "versiyonlar nasıl ayrışıyor, v4.8 vs v4.10 tek satır"
4. (vakit varsa) ray-cast (#4) ve PPO (#5) → "altyapı/hız"

> İpucu: kodu satır satır okuma; **ne yaptığını ve NEDEN işe yaradığını** anlat. Asıl mesaj:
> "çarpışmayı ödül değil **gözlem** çözdü" ve "v4.8↔v4.10 farkı sadece **eğitim süresi**".
