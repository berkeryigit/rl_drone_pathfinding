# DQN Drone Keşif Projesi — Teslim Kodu

## Özet

Bu klasör, `Fast2DDroneExplorationEnv` ortamında **DQN (Deep Q-Network)** algoritmasıyla eğitilmiş drone keşif ajanının tam kodunu içerir.

## Ortam

- **Fast2DDroneExplorationEnv**: Gazebo gerektirmeyen, saf Python Gymnasium ortamı
- 16×16 m, 6 odalı 2D harita
- 64-bin LIDAR, ±gürültü (stokastik gözlem → POMDP)
- 3 hareketli engel (stokastik geçiş)
- Sürekli aksiyon uzayı: `[vx, vy, wz]` → 9 discrete aksiyona sarılmış

## Aksiyon Uzayı

| ID | Açıklama |
|----|----------|
| 0 | İleri |
| 1 | Geri |
| 2 | Sola |
| 3 | Sağa |
| 4 | Sola dön |
| 5 | Sağa dön |
| 6 | İleri + sola dön |
| 7 | İleri + sağa dön |
| 8 | Dur |

## Ödül Fonksiyonu

```
r_t = -0.01                          # zaman cezası (her adım)
    + 3.0  * [yeni voxel keşfedildi] # keşif ödülü
    + 20.0 * [yeni oda keşfedildi]   # oda keşif bonusu
    - 0.10 * [50 adımdır yeni voxel yok]  # aylaklik cezası
    - (0.7 - d_min)/0.7 * 0.3       # duvar yakınlık cezası (d<0.7 m)
    + (-40.0) * [çarpışma]           # çarpışma cezası
    + 60.0  * [tüm 6 oda keşfedildi] # tamamlama bonusu
    - 0.10 * [aynı hücreye tekrar gidildi]  # döngü cezası
```

## Dosyalar

```
kod/
├── env/
│   ├── __init__.py
│   └── fast_2d_drone_env.py   ← simülasyon ortamı
├── train.py                   ← DQN eğitimi
├── evaluate.py                ← model değerlendirme
├── config.yaml                ← hiperparametreler
├── requirements.txt           ← bağımlılıklar (== ile sabitlenmiş)
├── seeds.txt                  ← 5 seed
├── run_all.sh                 ← tüm seedleri çalıştır
└── README.md                  ← bu dosya
```

## Kurulum ve Çalıştırma

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. Tüm seed'leri eğit
chmod +x run_all.sh
./run_all.sh

# 3. Tek seed eğit
python train.py --seed 42

# 4. Modeli değerlendir
python evaluate.py --model runs/seed_42/checkpoints/dqn_drone_final.zip --episodes 10

# 5. Ortamı görsel olarak izle
python evaluate.py --model runs/seed_42/checkpoints/dqn_drone_final.zip --render
```

