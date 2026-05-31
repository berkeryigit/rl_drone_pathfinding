# Docker / Ortam Rehberi (MacBook + Ubuntu 24.04 VM)

Bu projeyi 3 şekilde koşabilirsin. **Önerilen: VM içinde NATIVE** (Docker en zoru).

## Hangi Mac?
- **Apple Silicon (M1/M2/M3 — `arm64`)**: VM'in (UTM/Parallels) Ubuntu **arm64** olur.
  NVIDIA GPU **YOK** → torch **CPU**, Gazebo **yazılım render** (mesa/llvmpipe). Yavaş ama çalışır.
- **Intel Mac (`x86_64`)**: yine NVIDIA GPU yok (Mac'lerde) → aynı CPU/yazılım-render durumu.
- Her iki durumda da **GPU hızlandırma yok** → eğitim fps'i düşük (~5–15) olur. Bunu bekle.

## Yol 1 — VM içinde NATIVE (önerilen)
Ubuntu 24.04 VM'inde, `a3c_talimatlar.md` §1'i izle (ROS Jazzy + gz Harmonic + venv).
Sadece **GPU'suz** olduğun için şu env'leri ekle (yazılım render):
```bash
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe GZ_IP=127.0.0.1 SIM_HEADLESS=1
```
`scripts/train_a2c.sh` zaten `GZ_IP` ve headless ayarlıyor; üstüne `LIBGL_ALWAYS_SOFTWARE=1` yeterli.

## Yol 2 — Docker (GPU'suz / CPU)
NVIDIA'lı `docker-compose.yml`'i KULLANMA (o x86+NVIDIA için). Bunun yerine:
```bash
cd <repo>            # algo/a3c checkout'lu
UID=$(id -u) GID=$(id -g) docker compose -f docker/docker-compose.cpu.yml up -d --build
docker exec -it rl_drone_cpu bash
# Konteyner içinde:
cd /workspace/ros2_ws && colcon build --symlink-install && cd ..
python3 -m venv .venv --system-site-packages && source .venv/bin/activate && pip install -r requirements.txt
./scripts/train_a2c.sh configs/a2c.yaml
```
- `Dockerfile.cpu`: CUDA yok (CPU torch), mesa+xvfb (yazılım GL), çok-mimarili base.
- GUI yok (headless). gz `gpu_lidar` yazılım GL ile çalışır; sorun çıkarsa eğitimi
  `xvfb-run -a ./scripts/train_a2c.sh ...` ile sar.

## Yol 3 — macOS'ta Docker Desktop (VM olmadan)
Docker Desktop bir Linux VM'i zaten içerir; yukarıdaki `docker-compose.cpu.yml` çalışır
ama yine GPU yok + dosya I/O daha yavaş. VM-native ile fark az.

## GPU'suz performans ipuçları
- fps düşükse (~5–10): `configs/a2c.yaml`'de `total_timesteps`'i 700k→300k düşürerek
  önce hızlı bir baseline al; çalıştığını görünce uzat.
- Çekirdek sayısı önemli: VM'e mümkün olduğunca çok CPU çekirdeği ver.
- Eğitim sırasında GUI açma (zaten headless); rendering yükünü artırır.

## Sorun giderme
| Sorun | Çözüm |
|---|---|
| `colcon build` torch/CUDA hatası | CPU Dockerfile kullan; CUDA wheel'i arch'ında yok |
| Gazebo açılmıyor / GL hatası | `LIBGL_ALWAYS_SOFTWARE=1`; `xvfb-run -a` ile sar |
| `/scan` gelmiyor, step 2048 donma | `GZ_IP=127.0.0.1` ayarlı mı? (freeze fix) |
| torch arm64 wheel yok | `pip install torch --break-system-packages` (PyPI arm64 CPU) |
| Çok yavaş | total_timesteps↓, VM'e daha çok çekirdek, headless kal |
