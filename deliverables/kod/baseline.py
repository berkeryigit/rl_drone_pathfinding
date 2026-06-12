"""Baseline politikalar: rastgele + basit heuristik (engelden kacan).

Ajanin ogrenmesinin gercek bir kazanim oldugunu gostermek icin B5 baseline
karsilastirma grafigi (rapor sartı): rastgele politika ve/veya basit heuristik
vs egitilmis ajan. Bu script baseline'lari 2D ortamda uretip CSV'e yazar.

Tum rastgelelik numpy.random.default_rng ile uretilir (np.random.choice/seed YOK).

Kullanim:
    python baseline.py --seeds-file seeds.txt --episodes 20 \
        --out ../sonuclar/baseline_per_episode.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env.fast_2d_drone_env import (  # noqa: E402
    Fast2DConfig, Fast2DDroneExplorationEnv, N_ROOMS, GRID_NXY, LIDAR_BINS,
)
from train import load_config  # noqa: E402

_TOTAL_CELLS = GRID_NXY * GRID_NXY


def random_action(rng: np.random.Generator, obs: np.ndarray) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, size=3).astype(np.float32)


def heuristic_action(rng: np.random.Generator, obs: np.ndarray) -> np.ndarray:
    """En acik lidar yonune dogru ilerle, onu kapaliysa daha bos tarafa don.

    obs[:LIDAR_BINS] = normalize lidar (1.0 = en acik). Bin 0 = drone on yonu;
    binler yaw etrafinda saat yonunun tersine dizilir.
    """
    lidar = np.asarray(obs[:LIDAR_BINS], dtype=np.float32)
    front = float(np.min(np.concatenate([lidar[:3], lidar[-3:]])))  # on koni
    left = float(np.mean(lidar[1:LIDAR_BINS // 2]))                 # sol yari
    right = float(np.mean(lidar[LIDAR_BINS // 2:]))                # sag yari

    if front > 0.35:                       # on acik => ilerle, hafif yon ayari
        vx = 0.7
        wz = 0.4 * (left - right)
    else:                                  # on kapali => daha bos tarafa don
        vx = 0.05
        wz = 0.9 if left >= right else -0.9
    wz += float(rng.normal(0.0, 0.05))     # kucuk kasitli gurultu (takilmayi kirar)
    return np.array([vx, 0.0, float(np.clip(wz, -1.0, 1.0))], dtype=np.float32)


POLICIES = {"random": random_action, "heuristic": heuristic_action}


def run_episode(policy, rng, env, ep_seed: int) -> dict:
    obs, info = env.reset(seed=ep_seed)
    done = False
    ep_return = 0.0
    steps = 0
    while not done:
        action = policy(rng, obs)
        obs, reward, terminated, truncated, info = env.step(action)
        ep_return += float(reward)
        steps += 1
        done = terminated or truncated
    voxels = int(info.get("explored_voxels", 0))
    rooms = int(info.get("visited_rooms", 0))
    return {
        "ep_return": round(ep_return, 2),
        "steps": steps,
        "explored_voxels": voxels,
        "coverage_pct": round(voxels / _TOTAL_CELLS * 100.0, 2),
        "visited_rooms": rooms,
        "success": int(rooms >= N_ROOMS),
        "crashed": int(bool(info.get("collision", False))),
    }


def read_seeds(path: Path) -> list[int]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(int(line))
    return out


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Baseline (random + heuristic) degerlendirme")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--seeds-file", type=Path, default=Path(__file__).resolve().parent / "seeds.txt")
    parser.add_argument("--episodes", type=int, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    episodes = int(args.episodes if args.episodes is not None else cfg["baseline"]["episodes"])
    env_cfg = cfg["env"]
    seeds = read_seeds(args.seeds_file)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for name, policy in POLICIES.items():
        for seed in seeds:
            rng = np.random.default_rng(seed + 30_000)
            env = Fast2DDroneExplorationEnv(
                config=Fast2DConfig(
                    max_episode_steps=int(env_cfg["max_episode_steps"]),
                    random_start=bool(env_cfg["random_start"]),
                    lidar_noise_std=float(env_cfg["lidar_noise_std"]),
                    odom_noise_std=float(env_cfg["odom_noise_std"]),
                    wind_std=float(env_cfg["wind_std"]),
                ),
                seed=seed + 40_000,
            )
            rets = []
            for ep in range(episodes):
                m = run_episode(policy, rng, env, ep_seed=seed * 1000 + ep)
                m.update({"policy": name, "seed": seed, "episode": ep + 1})
                rows.append(m)
                rets.append(m["ep_return"])
            env.close()
            print(f"[baseline] {name} seed={seed}: ort getiri={np.mean(rets):.1f}")

    fields = ["policy", "seed", "episode", "ep_return", "steps", "explored_voxels",
              "coverage_pct", "visited_rooms", "success", "crashed"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})
    print(f"[baseline] {len(rows)} satir -> {args.out}")


if __name__ == "__main__":
    main()
