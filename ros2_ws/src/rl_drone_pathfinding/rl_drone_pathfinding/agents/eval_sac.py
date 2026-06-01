"""
Egitilmis SAC modelini degerlendir:
  - N episode calistir, metrikleri CSV'e kaydet
  - Her episode icin top-down trajectory GIF olustur
  - Ozet bar chart PNG kaydet

Kullanim:
  python3 -m rl_drone_pathfinding.agents.eval_sac \
      --model runs/sac_fast_rooms/checkpoints/best/best_model.zip \
      --episodes 10
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
    WORLD_HALF, GRID_CELL_XY, GRID_NXY, N_ROOMS,
)

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"


def load_model(path: str, device: str) -> SAC:
    """torch.compile ile kaydedilen modellerde _orig_mod. prefixini temizler."""
    try:
        return SAC.load(path, device=device)
    except RuntimeError as e:
        if "_orig_mod" not in str(e):
            raise
        # torch.load'u gecici olarak patch'le, _orig_mod. prefixini strip et
        _orig_load = torch.load
        def _patched(f, *args, **kwargs):
            data = _orig_load(f, *args, **kwargs)
            if isinstance(data, dict):
                return {k.replace("._orig_mod.", "."): v for k, v in data.items()}
            return data
        torch.load = _patched
        try:
            model = SAC.load(path, device=device)
        finally:
            torch.load = _orig_load
        print("[eval_sac] torch.compile prefix temizlendi, model yuklendi")
        return model

GIF_STEP = 10
GIF_FPS  = 10


def run_episode(model: SAC, env: DroneExplorationEnv, deterministic: bool = False,
                reset_options: dict | None = None) -> dict:
    obs, _ = env.reset(options=reset_options)
    done = False
    total_reward = 0.0
    positions: list[tuple[float, float]] = []
    explored_cells: set[tuple[int, int]] = set()
    step = 0
    info_final: dict = {}
    snapshots: list[frozenset] = []

    while not done:
        action, _ = model.predict(obs, deterministic=deterministic)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        total_reward += reward
        step += 1
        info_final = info

        x, y = info.get("x", 0.0), info.get("y", 0.0)
        positions.append((x, y))

        gx = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((y + WORLD_HALF) / GRID_CELL_XY)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY:
            explored_cells.add((gx, gy))

        if step % GIF_STEP == 0:
            snapshots.append(frozenset(explored_cells))

    if not snapshots or snapshots[-1] != frozenset(explored_cells):
        snapshots.append(frozenset(explored_cells))

    return {
        "total_reward":    total_reward,
        "steps":           step,
        "explored_voxels": info_final.get("explored_voxels", len(explored_cells)),
        "visited_rooms":   info_final.get("visited_rooms", 0),
        "collision_count": info_final.get("collision_count", 0),
        "positions":       positions,
        "snapshots":       snapshots,
    }


def create_gif(data: dict, ep: int, out_dir: Path):
    snapshots = data["snapshots"]
    positions = data["positions"]
    n_frames  = len(snapshots)
    if n_frames == 0:
        return

    traj_idx = np.linspace(0, len(positions) - 1, n_frames, dtype=int)

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#2a2a3e")
    ax.set_xlim(0, GRID_NXY)
    ax.set_ylim(0, GRID_NXY)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color("#81c784"); sp.set_linewidth(1.5)

    title = fig.suptitle("", color="white", fontsize=10)

    rgba_base = np.full((GRID_NXY, GRID_NXY, 4), [0.16, 0.16, 0.24, 1.0], dtype=np.float32)
    img = ax.imshow(rgba_base.copy(), origin="lower",
                    extent=[0, GRID_NXY, 0, GRID_NXY],
                    interpolation="nearest")
    dot, = ax.plot([], [], "o", color="#ff5252", markersize=8, zorder=5)

    explore_color = np.array([0.506, 0.780, 0.518, 0.85], dtype=np.float32)

    def update(frame):
        snap = snapshots[frame]
        cx, cy = positions[traj_idx[frame]]

        rgba = rgba_base.copy()
        for (gx, gy) in snap:
            if 0 <= gy < GRID_NXY and 0 <= gx < GRID_NXY:
                rgba[gy, gx] = explore_color
        img.set_data(rgba)

        dgx = (cx + WORLD_HALF) / GRID_CELL_XY
        dgy = (cy + WORLD_HALF) / GRID_CELL_XY
        dot.set_data([dgx], [dgy])

        pct = len(snap) / (GRID_NXY * GRID_NXY) * 100
        title.set_text(
            f"Ep {ep+1}  |  Ödül: {data['total_reward']:.1f}  |  "
            f"Keşif: %{pct:.1f}  |  Oda: {data['visited_rooms']}/{N_ROOMS}  |  "
            f"Çarpışma: {data['collision_count']}"
        )
        return [img, dot, title]

    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 // GIF_FPS, blit=True)
    gif_path = out_dir / f"episode_{ep+1:02d}.gif"
    anim.save(str(gif_path), writer=PillowWriter(fps=GIF_FPS))
    plt.close(fig)
    print(f"[eval_sac] GIF: {gif_path}")


def save_csv(metrics: list[dict], path: Path):
    fields = ["episode", "total_reward", "steps",
              "explored_voxels", "visited_rooms", "collision_count"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, m in enumerate(metrics):
            w.writerow({k: round(m[k], 2) if isinstance(m[k], float) else m[k]
                        for k in fields if k != "episode"} | {"episode": i + 1})
    print(f"[eval_sac] CSV: {path}")


def save_summary(metrics: list[dict], path: Path):
    labels  = [f"Ep {i+1}" for i in range(len(metrics))]
    rewards = [m["total_reward"]    for m in metrics]
    voxels  = [m["explored_voxels"] for m in metrics]
    rooms   = [m["visited_rooms"]   for m in metrics]
    colls   = [m["collision_count"] for m in metrics]

    fig, axes = plt.subplots(1, 4, figsize=(18, 4))
    fig.suptitle("SAC Eval Özeti", fontsize=13)

    axes[0].bar(labels, rewards, color="#4fc3f7")
    axes[0].set_title("Toplam Ödül"); axes[0].set_ylabel("Reward")

    max_voxels = GRID_NXY * GRID_NXY
    axes[1].bar(labels, voxels, color="#81c784")
    axes[1].set_title("Keşfedilen Voxel"); axes[1].set_ylabel("Adet")
    axes[1].axhline(max_voxels, color="red", linestyle="--", label=f"Max ({max_voxels})")
    axes[1].legend()

    axes[2].bar(labels, rooms, color="#ffb74d")
    axes[2].set_title("Ziyaret Edilen Oda"); axes[2].set_ylabel("Oda")
    axes[2].set_ylim(0, N_ROOMS + 1)
    axes[2].axhline(N_ROOMS, color="red", linestyle="--", label=f"Max ({N_ROOMS})")
    axes[2].legend()

    axes[3].bar(labels, colls, color="#ef9a9a")
    axes[3].set_title("Çarpışma Sayısı"); axes[3].set_ylabel("Adet")

    plt.tight_layout()
    plt.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[eval_sac] Özet: {path}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",    required=True,
                        help="Model .zip (örn: runs/sac/checkpoints/best/best_model.zip)")
    parser.add_argument("--episodes",  type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=500,
                        help="Episode basina max step (default: 500)")
    parser.add_argument("--out-dir",   default="runs/sac_fast_rooms/eval_results")
    parser.add_argument("--no-gif",       action="store_true", help="GIF olusturma")
    parser.add_argument("--deterministic", action="store_true",
                        help="Deterministik aksiyonlar (default: stochastic)")
    parser.add_argument("--fixed-spawn", action="store_true",
                        help="Her episode'u sirayla sabit spawn'dan baslat (tekrarlanabilir eval)")
    args, _ = parser.parse_known_args(argv)

    import shutil
    out_dir = Path(args.out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
        print(f"[eval_sac] Eski sonuclar silindi: {out_dir}")
    gif_dir = out_dir / "gifs"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_gif:
        gif_dir.mkdir(parents=True, exist_ok=True)

    det_str = "deterministik" if args.deterministic else "stochastic"
    print(f"[eval_sac] Model: {args.model}  |  Device: {DEVICE}  |  MaxSteps: {args.max_steps}  |  {det_str}")
    model = load_model(args.model, device=DEVICE)
    env   = DroneExplorationEnv(max_episode_steps=args.max_steps, eval_mode=True)

    # Sim ilk basladiginda fizik tam oturmuyor — bir warmup reset yap
    print("[eval_sac] Sim warmup...")
    env.reset()
    import time; time.sleep(2.0)

    all_metrics = []
    for ep in range(args.episodes):
        reset_options = None
        if args.fixed_spawn:
            spawn_idx = ep % N_ROOMS          # her odadan sirayla (R0..R5, sonra tekrar)
            reset_options = {"spawn_index": spawn_idx}
            print(f"\n[eval_sac] Episode {ep+1}/{args.episodes}  (sabit spawn R{spawn_idx})")
        else:
            print(f"\n[eval_sac] Episode {ep+1}/{args.episodes}")
        data = run_episode(model, env, deterministic=args.deterministic,
                           reset_options=reset_options)
        m = {k: v for k, v in data.items() if k not in ("positions", "snapshots")}
        all_metrics.append(m)
        print(f"  Ödül={m['total_reward']:.1f}  Voxel={m['explored_voxels']}  "
              f"Oda={m['visited_rooms']}/{N_ROOMS}  Çarpışma={m['collision_count']}")
        if not args.no_gif:
            create_gif(data, ep, gif_dir)

    env.close()

    save_csv(all_metrics, out_dir / "metrics.csv")
    save_summary(all_metrics, out_dir / "summary.png")

    print("\n=== EVAL ÖZET ===")
    print(f"Ort. Ödül:      {np.mean([m['total_reward']    for m in all_metrics]):.1f}")
    print(f"Ort. Voxel:     {np.mean([m['explored_voxels'] for m in all_metrics]):.0f} / {GRID_NXY*GRID_NXY}")
    print(f"Ort. Oda:       {np.mean([m['visited_rooms']   for m in all_metrics]):.1f} / {N_ROOMS}")
    print(f"Ort. Çarpışma:  {np.mean([m['collision_count'] for m in all_metrics]):.1f}")
    print(f"\nTüm sonuçlar:   {out_dir}/")


if __name__ == "__main__":
    main()
