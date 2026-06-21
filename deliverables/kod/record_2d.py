"""En iyi modeli 2D ortamda calistirip GIF + ozet PNG kaydeder.

Cikti:
  ../sonuclar/kayitlar/episode_N.gif   — drone turu animasyonu
  ../sonuclar/kayitlar/episode_N_son.png — son kare (tam kesif haritasi)

Kullanim:
    python3 record_2d.py                          # runs/seed_123/best/best_model.zip
    python3 record_2d.py --model runs/seed_42/best/best_model.zip
    python3 record_2d.py --episodes 3 --seed 123
    python3 record_2d.py --fps 20 --skip 2        # daha akici GIF
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from stable_baselines3 import SAC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env.fast_2d_drone_env import (
    Fast2DConfig, Fast2DDroneExplorationEnv,
    GRID_NXY, GRID_CELL_XY, WORLD_HALF, N_ROOMS, LIDAR_MAX,
)

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"

_TOTAL_CELLS = GRID_NXY * GRID_NXY
HERE = Path(__file__).resolve().parent


def _overlay_explored(base_img: np.ndarray, explored_raw: np.ndarray, scale: int) -> np.ndarray:
    """Kesfedilen voxelleri acik yesil ile renklendir.

    render() zaten np.flipud(img) donduruyor: satirlar = y-ters-cevrilmis.
    explored_raw[gx, gy] → gx = yatay (x), gy = dikey (y).
    Flipud sonrasi piksel satiri: size - (gy+1)*cell_px ... size - gy*cell_px
    """
    img = base_img.copy()
    size = img.shape[0]
    cell_px = max(1, int(GRID_CELL_XY * scale))
    gxs, gys = np.where(explored_raw[:, :, 0])
    for gx, gy in zip(gxs, gys):
        px0 = int(gx * GRID_CELL_XY * scale)
        px1 = min(size, px0 + cell_px)
        py0 = max(0, size - int((gy + 1) * GRID_CELL_XY * scale))
        py1 = min(size, size - int(gy * GRID_CELL_XY * scale))
        if py1 <= py0 or px1 <= px0:
            continue
        patch = img[py0:py1, px0:px1]
        # Sadece saf arkaplan pikselleri (245,245,245) yesile boya.
        # Duvar≈45, drone≈92, engel≈123 — hepsi <200, korunur.
        mask = patch.mean(axis=2) > 200
        img[py0:py1, px0:px1][mask] = [180, 230, 180]
    return img


def _add_text(img_pil: Image.Image, text: str) -> Image.Image:
    draw = ImageDraw.Draw(img_pil)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([0, 0, img_pil.width, 22], fill=(30, 30, 30))
    draw.text((4, 4), text, fill=(255, 255, 255), font=font)
    return img_pil


def record_episode(
    model: SAC,
    env: Fast2DDroneExplorationEnv,
    ep_idx: int,
    out_dir: Path,
    fps: int = 15,
    skip: int = 2,
    first_seed: int | None = None,
) -> dict:
    scale = 48
    # Sadece ilk episode'da seed ver; sonrakilerde None bırak ki RNG devam etsin.
    obs, _ = env.reset(seed=first_seed)
    frames: list[Image.Image] = []
    ep_return = 0.0
    step = 0
    done = False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        ep_return += float(reward)
        step += 1
        done = terminated or truncated

        if step % (skip + 1) == 0 or done:
            raw = env.render()                  # render() zaten flipud uygular
            frame = _overlay_explored(raw, env._explored, scale)

            voxels = int(info.get("explored_voxels", 0))
            rooms  = int(info.get("visited_rooms", 0))
            cover  = voxels / _TOTAL_CELLS * 100.0
            txt = (f"Ep{ep_idx+1} | Adim:{step:>4} | "
                   f"Getiri:{ep_return:>7.1f} | "
                   f"Oda:{rooms}/{N_ROOMS} | "
                   f"Kapsam:{cover:>4.1f}%")
            pil = Image.fromarray(frame)
            pil = _add_text(pil, txt)
            frames.append(pil)

    # GIF kaydet
    gif_path = out_dir / f"episode_{ep_idx+1:02d}.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=True,
    )
    # Son kare PNG
    png_path = out_dir / f"episode_{ep_idx+1:02d}_son.png"
    frames[-1].save(png_path)

    metrics = {
        "ep_return": round(ep_return, 2),
        "steps": step,
        "visited_rooms": int(info.get("visited_rooms", 0)),
        "coverage_pct": round(int(info.get("explored_voxels", 0)) / _TOTAL_CELLS * 100, 1),
        "success": int(info.get("visited_rooms", 0) >= N_ROOMS),
        "crashed": int(bool(info.get("collision", False))),
    }
    print(f"  [Ep{ep_idx+1}] getiri={metrics['ep_return']:.1f}  "
          f"oda={metrics['visited_rooms']}/{N_ROOMS}  "
          f"kapsam={metrics['coverage_pct']:.1f}%  "
          f"basari={'EVET' if metrics['success'] else 'HAYIR'}  "
          f"→ {gif_path.name}")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description="2D ortamda model kaydi (GIF)")
    parser.add_argument("--model", type=Path,
                        default=HERE / "runs/seed_123/best/best_model.zip")
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--fps", type=int, default=15, help="GIF kare hizi")
    parser.add_argument("--skip", type=int, default=2,
                        help="Her N+1 adimda 1 kare (dosya boyutu icin)")
    parser.add_argument("--out", type=Path,
                        default=HERE / "../sonuclar/kayitlar")
    args = parser.parse_args(argv)

    if not args.model.exists():
        print(f"HATA: model bulunamadi: {args.model}")
        sys.exit(1)

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Model  : {args.model}")
    print(f"Cikti  : {args.out}")
    print(f"Device : {DEVICE}")
    print()

    model = SAC.load(str(args.model), device=DEVICE)
    env = Fast2DDroneExplorationEnv(
        config=Fast2DConfig(max_episode_steps=600, random_start=True),
        render_mode="rgb_array",
        seed=args.seed,
    )

    all_metrics = []
    for ep in range(args.episodes):
        m = record_episode(model, env, ep, args.out,
                           fps=args.fps, skip=args.skip,
                           first_seed=args.seed if ep == 0 else None)
        all_metrics.append(m)

    env.close()

    print()
    print("─" * 50)
    rets   = [m["ep_return"]    for m in all_metrics]
    rooms  = [m["visited_rooms"] for m in all_metrics]
    covers = [m["coverage_pct"] for m in all_metrics]
    succs  = [m["success"]      for m in all_metrics]
    print(f"Ortalama getiri  : {np.mean(rets):.1f} ± {np.std(rets):.1f}")
    print(f"Ortalama oda     : {np.mean(rooms):.2f}")
    print(f"Ortalama kapsam  : {np.mean(covers):.1f}%")
    print(f"Basari orani     : %{np.mean(succs)*100:.0f}")
    print(f"GIF kayitlari    : {args.out}/")


if __name__ == "__main__":
    main()
