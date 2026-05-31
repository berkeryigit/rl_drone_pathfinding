#!/usr/bin/env python3
"""v2.x policy'sini N episode degerlendirir ve haritayi NASIL gezdigini gorsellestirir.

Cikti:
  docs/figures/eval_<ver>_coverage.png     - kapsama isi haritasi (hangi hucre kac kez gezildi) + duvarlar
  docs/figures/eval_<ver>_trajectories.png  - ornek yorungeler + baslangic + carpisma noktalari
  docs/EVAL_<ver>.md                         - istatistik ozeti

Sim AYRI bir process'te ayakta olmali (runner script halleder). norm_obs=false
oldugu icin policy ham obs bekler -> VecNormalize gerekmez, ham env kullanilir.
Engeller train_ppo'daki updater thread ile hareket ettirilir (gercekci kosul).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from stable_baselines3 import PPO

from rl_drone_pathfinding.envs import DroneExplorationEnv
from rl_drone_pathfinding.envs.drone_exploration_env import (
    SPAWN_X, SPAWN_Y, WORLD_HALF, GRID_NXY, GRID_CELL_XY, N_ROOMS,
)
from rl_drone_pathfinding.agents.train_ppo import _start_obstacle_updaters

REPO = Path(__file__).resolve().parents[1]
TOTAL = GRID_NXY * GRID_NXY

# multi_room.sdf duvar segmentleri (gorsel icin) — [(x0,y0,x1,y1), ...]
WALLS = [
    # dis sinir
    (-8, -8, 8, -8), (-8, 8, 8, 8), (-8, -8, -8, 8), (8, -8, 8, 8),
    # ic dikey x=-2 (kapi y[-4,-2])
    (-2, -8, -2, -4), (-2, -2, -2, 8),
    # ic dikey x=4 (kapi y[3,5])
    (4, -8, 4, 3), (4, 5, 4, 8),
    # ic yatay y=0 (kapilar x[-7,-5],[0,2],[5,7])
    (-8, 0, -7, 0), (-5, 0, 0, 0), (2, 0, 5, 0), (7, 0, 8, 0),
]


def draw_walls(ax):
    for (x0, y0, x1, y1) in WALLS:
        ax.plot([x0, x1], [y0, y1], color="black", linewidth=2.5, zorder=5)
    # oda etiketleri
    labels = {"R3": (-5, 4), "R4": (1, 4), "R5": (6, 4),
              "R0": (-5, -4), "R1": (1, -4), "R2": (6, -4)}
    for name, (lx, ly) in labels.items():
        ax.text(lx, ly, name, fontsize=9, color="gray", ha="center", alpha=0.6, zorder=4)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--episodes", type=int, default=100)
    ap.add_argument("--config", default=str(REPO / "configs/ppo.yaml"))
    ap.add_argument("--deterministic", action="store_true", default=True)
    ap.add_argument("--stochastic", dest="deterministic", action="store_false")
    ap.add_argument("--version", default="v2_0")
    args = ap.parse_args(argv)

    import yaml
    cfg = yaml.safe_load(open(args.config))
    env_cfg = cfg["env"]

    env = DroneExplorationEnv(
        world_name=env_cfg["world_name"],
        drone_name=env_cfg["drone_name"],
        max_episode_steps=env_cfg["max_episode_steps"],
    )
    # Engelleri hareket ettir (egitimdeki gercekci kosul)
    obs_threads, obs_stop = _start_obstacle_updaters(env_cfg["world_name"], 1)

    model = PPO.load(args.model)
    print(f"[eval] model={args.model} episodes={args.episodes} deterministic={args.deterministic}")

    coverage = np.zeros((GRID_NXY, GRID_NXY), dtype=np.float64)
    returns, voxels_l, rooms_l, eplen_l = [], [], [], []
    collisions = 0
    collision_pts = []
    trajectories = []  # ornek yorungeler (ilk ~12)

    for ep in range(args.episodes):
        obs, _ = env.reset()
        done = False
        ret = 0.0
        traj = [(SPAWN_X, SPAWN_Y)]
        info = {}
        steps = 0
        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, r, term, trunc, info = env.step(action)
            ret += r
            steps += 1
            traj.append((info["x"], info["y"]))
            done = term or trunc
        coverage += env._explored
        returns.append(ret)
        voxels_l.append(info.get("explored_voxels", 0))
        rooms_l.append(info.get("visited_rooms", 0))
        eplen_l.append(steps)
        if info.get("collision"):
            collisions += 1
            collision_pts.append((info["x"], info["y"]))
        if ep < 12:
            trajectories.append((traj, bool(info.get("collision"))))
        if (ep + 1) % 10 == 0:
            print(f"[eval] {ep+1}/{args.episodes}  ret~{np.mean(returns):.1f}  "
                  f"vox~{np.mean(voxels_l):.0f}  rooms~{np.mean(rooms_l):.2f}  "
                  f"col%={100*collisions/(ep+1):.0f}", flush=True)

    obs_stop.set()

    returns = np.array(returns); voxels_l = np.array(voxels_l)
    rooms_l = np.array(rooms_l); eplen_l = np.array(eplen_l)
    cov_cells = int((coverage > 0).sum())  # en az 1 kez gezilen hucre sayisi

    fig_dir = REPO / "docs" / "figures"; fig_dir.mkdir(parents=True, exist_ok=True)

    # ---- Figur 1: kapsama isi haritasi ----
    fig, ax = plt.subplots(figsize=(9, 8))
    frac = coverage.T / args.episodes  # T: x yatay, y dikey
    im = ax.imshow(frac, origin="lower", extent=[-WORLD_HALF, WORLD_HALF, -WORLD_HALF, WORLD_HALF],
                   cmap="viridis", vmin=0, vmax=1, aspect="equal")
    draw_walls(ax)
    ax.plot(SPAWN_X, SPAWN_Y, marker="*", color="red", markersize=20,
            markeredgecolor="white", zorder=6, label="Baslangic (R0)")
    fig.colorbar(im, ax=ax, label="episode orani (1.0 = her episode gezildi)")
    ax.set_title(f"v2.0 KAPSAMA ISI HARITASI — {args.episodes} episode\n"
                 f"birlesik benzersiz hucre: {cov_cells}/{TOTAL}")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.legend(loc="upper right")
    fig.tight_layout()
    p1 = fig_dir / f"eval_{args.version}_coverage.png"; fig.savefig(p1, dpi=120); plt.close(fig)
    print(f"saved {p1}")

    # ---- Figur 2: ornek yorungeler + carpisma noktalari ----
    fig, ax = plt.subplots(figsize=(9, 8))
    draw_walls(ax)
    cmap = plt.cm.tab10
    for i, (traj, col) in enumerate(trajectories):
        xs = [p[0] for p in traj]; ys = [p[1] for p in traj]
        ax.plot(xs, ys, color=cmap(i % 10), linewidth=1.0, alpha=0.7, zorder=3)
    # tum carpisma noktalari
    if collision_pts:
        cx = [p[0] for p in collision_pts]; cy = [p[1] for p in collision_pts]
        ax.scatter(cx, cy, marker="x", color="red", s=60, linewidths=2,
                   zorder=7, label=f"carpisma ({len(collision_pts)})")
    ax.plot(SPAWN_X, SPAWN_Y, marker="*", color="lime", markersize=20,
            markeredgecolor="black", zorder=8, label="Baslangic (R0)")
    ax.set_xlim(-WORLD_HALF, WORLD_HALF); ax.set_ylim(-WORLD_HALF, WORLD_HALF)
    ax.set_aspect("equal")
    ax.set_title(f"v2.0 ORNEK YORUNGELER (ilk {len(trajectories)} ep) + TUM carpisma noktalari")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.legend(loc="upper right")
    fig.tight_layout()
    p2 = fig_dir / f"eval_{args.version}_trajectories.png"; fig.savefig(p2, dpi=120); plt.close(fig)
    print(f"saved {p2}")

    # ---- Markdown ozet ----
    def stat(a):
        return f"{a.mean():.1f} ± {a.std():.1f}  (min {a.min():.0f}, max {a.max():.0f})"
    md = [
        f"# v2.0 Performans Degerlendirmesi — {args.episodes} episode", "",
        f"Model: `{Path(args.model).name}` | deterministic={args.deterministic} | hareketli engeller: aktif", "",
        "## Istatistikler", "",
        "| Metrik | Deger |", "|---|---|",
        f"| Return (odul) | {stat(returns)} |",
        f"| Kesfedilen voxel / {TOTAL} | {stat(voxels_l)} |",
        f"| Ziyaret edilen oda / {N_ROOMS} | {stat(rooms_l)} |",
        f"| Episode uzunlugu / {env_cfg['max_episode_steps']} | {stat(eplen_l)} |",
        f"| Carpisma orani | {100*collisions/args.episodes:.0f}% ({collisions}/{args.episodes}) |",
        f"| Birlesik benzersiz hucre kapsama | {cov_cells}/{TOTAL} ({100*cov_cells/TOTAL:.0f}%) |",
        "",
        "## Yorum",
        f"- Episode'larin %{100*collisions/args.episodes:.0f}'i CARPISMA ile bitti "
        f"(ort. {eplen_l.mean():.0f}/{env_cfg['max_episode_steps']} adim). Carpismasa daha cok gezecek.",
        f"- {N_ROOMS} odanin ortalama {rooms_l.mean():.1f}'ine ulasiliyor (max {rooms_l.max():.0f}).",
        f"- 100 episode birlesince haritanin %{100*cov_cells/TOTAL:.0f}'i en az bir kez geziliyor.",
        "",
        "![coverage](figures/eval_%s_coverage.png)" % args.version, "",
        "![trajectories](figures/eval_%s_trajectories.png)" % args.version, "",
    ]
    (REPO / "docs" / f"EVAL_{args.version}.md").write_text("\n".join(md))
    print(f"saved {REPO / 'docs' / f'EVAL_{args.version}.md'}")

    # JSON ozet (stdout) — runner/operator parse edebilir
    print("EVAL_SUMMARY " + json.dumps({
        "episodes": args.episodes,
        "return_mean": float(returns.mean()), "return_std": float(returns.std()),
        "voxels_mean": float(voxels_l.mean()), "voxels_max": int(voxels_l.max()),
        "rooms_mean": float(rooms_l.mean()), "rooms_max": int(rooms_l.max()),
        "eplen_mean": float(eplen_l.mean()),
        "collision_rate": collisions / args.episodes,
        "union_coverage_cells": cov_cells, "union_coverage_pct": 100 * cov_cells / TOTAL,
    }))

    import os as _os
    _os._exit(0)


if __name__ == "__main__":
    main()
