"""
Egitilmis SAC modelini degerlendir:
  - N episode calistir, metrikleri CSV'e kaydet
  - Her episode icin top-down trajectory GIF olustur
  - Ozet bar chart PNG kaydet

Kullanim (container icinde):
  python3 -m rl_drone_pathfinding.agents.eval_sac \
      --model runs/sac/checkpoints/best/best_model.zip \
      --episodes 5
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from stable_baselines3 import SAC

from rl_drone_pathfinding.envs import DroneExplorationEnv
from rl_drone_pathfinding.envs.drone_exploration_env import (
    WORLD_HALF, GRID_CELL_XY, GRID_NXY, GRID_NZ, N_FLOORS, FLOOR_HEIGHT,
)

FLOOR_LABELS = ["Zemin Kat", "1. Kat", "2. Kat"]
FLOOR_COLORS = ["#81c784", "#4fc3f7", "#ffb74d"]
GIF_STEP = 10       # her kac step'te bir frame
GIF_FPS  = 10


def _floor_id(z: float) -> int:
    return max(0, min(N_FLOORS - 1, int(z // FLOOR_HEIGHT)))


def run_episode(model: SAC, env: DroneExplorationEnv) -> dict:
    obs, _ = env.reset()
    done = False
    total_reward = 0.0
    positions: list[tuple] = []
    explored_snapshots: list[frozenset] = []
    explored_now: set[tuple] = set()
    step = 0
    info_final: dict = {}

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        total_reward += reward
        step += 1
        info_final = info

        x, y, z = info.get("x", 0.0), info.get("y", 0.0), info.get("z", 0.0)
        positions.append((x, y, z))

        gx = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((y + WORLD_HALF) / GRID_CELL_XY)
        gz = _floor_id(z)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY:
            explored_now.add((gx, gy, gz))

        if step % GIF_STEP == 0:
            explored_snapshots.append(frozenset(explored_now))

    if not explored_snapshots or explored_snapshots[-1] != frozenset(explored_now):
        explored_snapshots.append(frozenset(explored_now))

    return {
        "total_reward": total_reward,
        "steps": step,
        "explored_voxels": info_final.get("explored_voxels", len(explored_now)),
        "visited_rooms":   info_final.get("visited_rooms", 0),
        "visited_floors":  info_final.get("visited_floors", 0),
        "positions":       positions,
        "explored_snapshots": explored_snapshots,
    }


def create_gif(data: dict, ep: int, out_dir: Path):
    snapshots = data["explored_snapshots"]
    positions = data["positions"]
    n_frames  = len(snapshots)
    if n_frames == 0:
        return

    traj_idx = np.linspace(0, len(positions) - 1, n_frames, dtype=int)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor("#1e1e2e")
    fig.suptitle(
        f"Episode {ep+1}  |  "
        f"Odül: {data['total_reward']:.1f}  |  "
        f"Voxel: {data['explored_voxels']}  |  "
        f"Oda: {data['visited_rooms']}/12  |  "
        f"Kat: {data['visited_floors']}/3",
        color="white", fontsize=11,
    )

    imgs, dots = [], []
    for fid, (ax, label, color) in enumerate(zip(axes, FLOOR_LABELS, FLOOR_COLORS)):
        ax.set_facecolor("#2a2a3e")
        ax.set_title(label, color=color, fontsize=10)
        ax.set_xlim(0, GRID_NXY)
        ax.set_ylim(0, GRID_NXY)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(color); sp.set_linewidth(1.5)

        rgba = np.zeros((GRID_NXY, GRID_NXY, 4), dtype=np.float32)
        rgba[:, :] = [0.16, 0.16, 0.24, 1.0]
        img = ax.imshow(rgba, origin="lower",
                        extent=[0, GRID_NXY, 0, GRID_NXY],
                        interpolation="nearest", vmin=0, vmax=1)
        imgs.append((img, fid, color))

        dot, = ax.plot([], [], "o", color="#ff5252", markersize=7, zorder=5)
        dots.append((dot, fid))

    plt.tight_layout()

    def _hex_to_rgba(hex_color: str, alpha: float = 0.85) -> list:
        r, g, b = matplotlib.colors.to_rgb(hex_color)
        return [r, g, b, alpha]

    def update(frame):
        snap = snapshots[frame]
        cx, cy, cz = positions[traj_idx[frame]]
        cur_floor = _floor_id(cz)

        for (img, fid, color), (dot, _) in zip(imgs, dots):
            rgba = np.zeros((GRID_NXY, GRID_NXY, 4), dtype=np.float32)
            rgba[:, :] = [0.16, 0.16, 0.24, 1.0]
            fc = _hex_to_rgba(color)
            for (gx, gy, gz) in snap:
                if gz == fid and 0 <= gy < GRID_NXY and 0 <= gx < GRID_NXY:
                    rgba[gy, gx] = fc
            img.set_data(rgba)

            if cur_floor == fid:
                dgx = (cx + WORLD_HALF) / GRID_CELL_XY
                dgy = (cy + WORLD_HALF) / GRID_CELL_XY
                dot.set_data([dgx], [dgy])
            else:
                dot.set_data([], [])

        return [img for (img, _, _) in imgs] + [dot for (dot, _) in dots]

    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 // GIF_FPS, blit=True)
    gif_path = out_dir / f"episode_{ep+1:02d}.gif"
    anim.save(str(gif_path), writer=PillowWriter(fps=GIF_FPS))
    plt.close(fig)
    print(f"[eval_sac] GIF: {gif_path}")


def save_csv(metrics: list[dict], path: Path):
    fields = ["episode", "total_reward", "steps",
              "explored_voxels", "visited_rooms", "visited_floors"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, m in enumerate(metrics):
            w.writerow({
                "episode":         i + 1,
                "total_reward":    round(m["total_reward"], 2),
                "steps":           m["steps"],
                "explored_voxels": m["explored_voxels"],
                "visited_rooms":   m["visited_rooms"],
                "visited_floors":  m["visited_floors"],
            })
    print(f"[eval_sac] CSV: {path}")


def save_summary(metrics: list[dict], path: Path):
    labels  = [f"Ep {i+1}" for i in range(len(metrics))]
    rewards = [m["total_reward"]   for m in metrics]
    voxels  = [m["explored_voxels"] for m in metrics]
    rooms   = [m["visited_rooms"]   for m in metrics]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle("SAC Eval Özeti", fontsize=13)

    axes[0].bar(labels, rewards, color="#4fc3f7")
    axes[0].set_title("Toplam Ödül"); axes[0].set_ylabel("Reward")

    axes[1].bar(labels, voxels, color="#81c784")
    axes[1].set_title("Keşfedilen Voxel"); axes[1].set_ylabel("Adet")
    axes[1].axhline(GRID_NXY * GRID_NXY * GRID_NZ,
                    color="red", linestyle="--",
                    label=f"Max ({GRID_NXY*GRID_NXY*GRID_NZ})")
    axes[1].legend()

    axes[2].bar(labels, rooms, color="#ffb74d")
    axes[2].set_title("Ziyaret Edilen Oda"); axes[2].set_ylabel("Oda")
    axes[2].set_ylim(0, 13)
    axes[2].axhline(12, color="red", linestyle="--", label="Max (12)")
    axes[2].legend()

    plt.tight_layout()
    plt.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[eval_sac] Özet: {path}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",    required=True,
                        help="Model .zip (örn: runs/sac/checkpoints/best/best_model.zip)")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--out-dir",  default="runs/sac/eval_results")
    args, _ = parser.parse_known_args(argv)

    out_dir = Path(args.out_dir)
    gif_dir = out_dir / "gifs"
    out_dir.mkdir(parents=True, exist_ok=True)
    gif_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eval_sac] Model yükleniyor: {args.model}")
    model = SAC.load(args.model)
    env   = DroneExplorationEnv()

    all_metrics = []
    for ep in range(args.episodes):
        print(f"\n[eval_sac] Episode {ep+1}/{args.episodes}")
        data = run_episode(model, env)
        m = {k: v for k, v in data.items()
             if k not in ("positions", "explored_snapshots")}
        all_metrics.append(m)
        print(f"  Ödül={m['total_reward']:.1f} | Voxel={m['explored_voxels']} | "
              f"Oda={m['visited_rooms']}/12 | Kat={m['visited_floors']}/3")
        create_gif(data, ep, gif_dir)

    env.close()

    save_csv(all_metrics, out_dir / "metrics.csv")
    save_summary(all_metrics, out_dir / "summary.png")

    print("\n=== EVAL ÖZET ===")
    print(f"Ort. Ödül:   {np.mean([m['total_reward']   for m in all_metrics]):.1f}")
    print(f"Ort. Voxel:  {np.mean([m['explored_voxels'] for m in all_metrics]):.0f}")
    print(f"Ort. Oda:    {np.mean([m['visited_rooms']   for m in all_metrics]):.1f}/12")
    print(f"Ort. Kat:    {np.mean([m['visited_floors']  for m in all_metrics]):.1f}/3")
    print(f"\nTüm sonuçlar: {out_dir}/")


if __name__ == "__main__":
    main()
