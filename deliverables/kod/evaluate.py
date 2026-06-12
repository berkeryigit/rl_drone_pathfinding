"""Egitilmis PPO politikalarinin DETERMINISTIK (greedy) degerlendirmesi.

Egitim egrisi tek basina kanit degildir; bu script egitilmis modeli
deterministic=True ile calistirip episode getirisi + kesif metriklerini uretir.
Her seed icin runs/seed_<N>/best/best_model.zip (yoksa final_model.zip) yuklenir.

algo/td3 (SAC) teslimindeki evaluate.py ile AYNI protokol; tek fark model sinifi
(SAC -> PPO). Ortam, seed sapmalari (+20000), episode sayisi birebir ayni.

Kullanim:
    python evaluate.py --runs-root runs --seeds-file seeds.txt --episodes 20 \
        --out ../sonuclar/eval_per_episode.csv

Cikti:
    eval_per_episode.csv  -> seed x episode bazinda ham deterministik sonuc
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env.fast_2d_drone_env import (  # noqa: E402
    Fast2DConfig, Fast2DDroneExplorationEnv, N_ROOMS, GRID_NXY, LIDAR_MAX,
)
from train import load_config  # noqa: E402

_TOTAL_CELLS = GRID_NXY * GRID_NXY
_DEVICE = "cpu"


def _resolve_model(run_dir: Path) -> Path | None:
    for candidate in (run_dir / "best" / "best_model.zip", run_dir / "final_model.zip"):
        if candidate.exists():
            return candidate
    return None


def run_episode(model: PPO, env: Fast2DDroneExplorationEnv, ep_seed: int) -> dict:
    obs, info = env.reset(seed=ep_seed)
    done = False
    ep_return = 0.0
    steps = 0
    while not done:
        action, _ = model.predict(obs, deterministic=True)  # greedy
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
        "min_lidar": round(float(info.get("min_lidar", LIDAR_MAX)), 3),
    }


def read_seeds(path: Path) -> list[int]:
    seeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seeds.append(int(line))
    return seeds


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Deterministik PPO politika degerlendirmesi")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--seeds-file", type=Path, default=Path(__file__).resolve().parent / "seeds.txt")
    parser.add_argument("--episodes", type=int, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    episodes = int(args.episodes if args.episodes is not None else cfg["eval"]["episodes"])
    env_cfg = cfg["env"]
    seeds = read_seeds(args.seeds_file)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for seed in seeds:
        run_dir = args.runs_root / f"seed_{seed}"
        model_path = _resolve_model(run_dir)
        if model_path is None:
            print(f"[evaluate] seed={seed}: model bulunamadi ({run_dir}), atlaniyor")
            continue
        model = PPO.load(str(model_path), device=_DEVICE)
        env = Fast2DDroneExplorationEnv(
            config=Fast2DConfig(
                max_episode_steps=int(env_cfg["max_episode_steps"]),
                random_start=bool(env_cfg["random_start"]),
                lidar_noise_std=float(env_cfg["lidar_noise_std"]),
                odom_noise_std=float(env_cfg["odom_noise_std"]),
                wind_std=float(env_cfg["wind_std"]),
            ),
            seed=seed + 20_000,
        )
        rets = []
        for ep in range(episodes):
            m = run_episode(model, env, ep_seed=seed * 1000 + ep)
            m.update({"seed": seed, "episode": ep + 1})
            rows.append(m)
            rets.append(m["ep_return"])
        env.close()
        print(f"[evaluate] seed={seed}: {episodes} ep, ort getiri={np.mean(rets):.1f} (+/-{np.std(rets):.1f})")

    if not rows:
        print("[evaluate] Hic sonuc uretilmedi (egitilmis model yok). Once train.py calistirin.")
        return

    fields = ["seed", "episode", "ep_return", "steps", "explored_voxels",
              "coverage_pct", "visited_rooms", "success", "crashed", "min_lidar"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})
    print(f"[evaluate] {len(rows)} satir -> {args.out}")


if __name__ == "__main__":
    main()
