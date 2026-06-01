"""HIZLI sim policy'sini 100 episode degerlendir + kapsama/yorunge/carpisma figurleri.
Gazebo eval_coverage.py ile AYNI cikti formati (kiyas icin).
    python3 fast_sim/eval_fast.py --model runs/fast_v1/checkpoints/fast_drone_final.zip --episodes 100
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fast_drone_env import (FastDroneEnv, WALLS, SPAWN_X, SPAWN_Y, WORLD_HALF,  # noqa: E402
                            GRID_NXY, N_ROOMS)

REPO = Path(__file__).resolve().parents[1]
TOTAL = GRID_NXY * GRID_NXY


def draw_walls(ax):
    for (x0, y0, x1, y1) in WALLS:
        ax.plot([x0, x1], [y0, y1], color="black", linewidth=2.5, zorder=5)
    for name, (lx, ly) in {"R3": (-5, 4), "R4": (1, 4), "R5": (6, 4),
                           "R0": (-5, -4), "R1": (1, -4), "R2": (6, -4)}.items():
        ax.text(lx, ly, name, fontsize=9, color="gray", ha="center", alpha=0.6, zorder=4)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--episodes", type=int, default=100)
    ap.add_argument("--version", default="fast_v1")
    ap.add_argument("--max-steps", type=int, default=2500)
    ap.add_argument("--lidar-history", type=int, default=1)
    a = ap.parse_args(argv)

    env = FastDroneEnv(max_episode_steps=a.max_steps, lidar_history=a.lidar_history)
    model = PPO.load(a.model)   # norm_obs=False -> ham obs, vecnormalize gerekmez
    print(f"[eval_fast] {a.model} | {a.episodes} ep")

    coverage = np.zeros((GRID_NXY, GRID_NXY), np.float64)
    rets, vox, rooms, eplen = [], [], [], []
    collisions, col_pts, trajs = 0, [], []
    for ep in range(a.episodes):
        obs, _ = env.reset(); done = False; ret = 0.0; traj = [(SPAWN_X, SPAWN_Y)]; info = {}; n = 0
        while not done:
            act, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, info = env.step(act)
            ret += r; n += 1; traj.append((info["x"], info["y"])); done = term or trunc
        coverage += env._explored
        rets.append(ret); vox.append(info["explored_voxels"]); rooms.append(info["visited_rooms"]); eplen.append(n)
        if info.get("collision"):
            collisions += 1; col_pts.append((info["x"], info["y"]))
        if ep < 12:
            trajs.append((traj, bool(info.get("collision"))))
        if (ep + 1) % 20 == 0:
            print(f"  {ep+1}/{a.episodes} ret~{np.mean(rets):.1f} vox~{np.mean(vox):.0f} "
                  f"rooms~{np.mean(rooms):.2f} col%={100*collisions/(ep+1):.0f}", flush=True)

    rets, vox, rooms, eplen = map(np.array, (rets, vox, rooms, eplen))
    cov_cells = int((coverage > 0).sum())
    fig_dir = REPO / "docs" / "figures"; fig_dir.mkdir(parents=True, exist_ok=True)

    # kapsama isi haritasi
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(coverage.T / a.episodes, origin="lower",
                   extent=[-WORLD_HALF, WORLD_HALF, -WORLD_HALF, WORLD_HALF],
                   cmap="viridis", vmin=0, vmax=1, aspect="equal")
    draw_walls(ax)
    ax.plot(SPAWN_X, SPAWN_Y, "*", color="red", markersize=20, markeredgecolor="white", zorder=6, label="Baslangic")
    fig.colorbar(im, ax=ax, label="episode orani")
    ax.set_title(f"{a.version} (numpy sim) KAPSAMA — {a.episodes} ep | birlesik {cov_cells}/{TOTAL}")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.legend(loc="upper right")
    fig.tight_layout(); p1 = fig_dir / f"eval_{a.version}_coverage.png"; fig.savefig(p1, dpi=120); plt.close(fig)

    # yorungeler + carpisma
    fig, ax = plt.subplots(figsize=(9, 8)); draw_walls(ax)
    for i, (tr, col) in enumerate(trajs):
        ax.plot([p[0] for p in tr], [p[1] for p in tr], color=plt.cm.tab10(i % 10), linewidth=1.0, alpha=0.7, zorder=3)
    if col_pts:
        ax.scatter([p[0] for p in col_pts], [p[1] for p in col_pts], marker="x", color="red", s=60, linewidths=2, zorder=7, label=f"carpisma ({len(col_pts)})")
    ax.plot(SPAWN_X, SPAWN_Y, "*", color="lime", markersize=20, markeredgecolor="black", zorder=8, label="Baslangic")
    ax.set_xlim(-WORLD_HALF, WORLD_HALF); ax.set_ylim(-WORLD_HALF, WORLD_HALF); ax.set_aspect("equal")
    ax.set_title(f"{a.version} (numpy sim) YORUNGELER + carpisma"); ax.legend(loc="upper right")
    fig.tight_layout(); p2 = fig_dir / f"eval_{a.version}_trajectories.png"; fig.savefig(p2, dpi=120); plt.close(fig)

    def st(x):
        return f"{x.mean():.1f} ± {x.std():.1f} (min {x.min():.0f}, max {x.max():.0f})"
    md = [f"# {a.version} (numpy/Gymnasium sim) — {a.episodes} episode", "",
          f"Model: `{Path(a.model).name}` | deterministic | hareketli engeller aktif | ~100x hizli sim", "",
          "| Metrik | Deger |", "|---|---|",
          f"| Return | {st(rets)} |",
          f"| Voxel / {TOTAL} | {st(vox)} |",
          f"| Oda / {N_ROOMS} | {st(rooms)} |",
          f"| Episode / {a.max_steps} | {st(eplen)} |",
          f"| Carpisma orani | {100*collisions/a.episodes:.0f}% ({collisions}/{a.episodes}) |",
          f"| Birlesik kapsama | {cov_cells}/{TOTAL} ({100*cov_cells/TOTAL:.0f}%) |", "",
          f"![coverage](figures/eval_{a.version}_coverage.png)", "",
          f"![traj](figures/eval_{a.version}_trajectories.png)", ""]
    (REPO / "docs" / f"EVAL_{a.version}.md").write_text("\n".join(md))
    print(f"saved {p1}, {p2}, EVAL_{a.version}.md")
    print("EVAL_SUMMARY " + json.dumps({
        "episodes": a.episodes, "return_mean": float(rets.mean()),
        "voxels_mean": float(vox.mean()), "voxels_max": int(vox.max()),
        "rooms_mean": float(rooms.mean()), "rooms_max": int(rooms.max()),
        "eplen_mean": float(eplen.mean()), "collision_rate": collisions / a.episodes,
        "union_coverage_cells": cov_cells, "union_coverage_pct": 100 * cov_cells / TOTAL}))


if __name__ == "__main__":
    main()
