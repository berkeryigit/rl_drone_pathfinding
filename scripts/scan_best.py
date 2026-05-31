"""
N episode çalıştırır. Filtre: rooms >= MIN_ROOMS.
Sıralama: reward DESC, voxels DESC.
Parallel tarama için --env-id ve --out argümanları alır.

Kullanım (tekli):
    python3 scripts/scan_best.py [N_EPS]

Kullanım (parallel - scan_parallel.sh tarafından çağrılır):
    ENV_ID=2 python3 scripts/scan_best.py 5000 --out /tmp/scan_2.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_env_id = int(os.environ.get("ENV_ID", "0"))
os.environ["ROS_DOMAIN_ID"] = str(_env_id)
os.environ["GZ_PARTITION"]  = f"sim{_env_id}"

import numpy as np
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

from rl_drone_pathfinding.envs.drone_exploration_env import (
    DroneExplorationEnv,
    SPAWN_CANDIDATES,
)

MIN_ROOMS = 3
TOP_N     = 200
DEFAULT_OUT = Path("runs/ppo_v8_frontier/best_runs.json")


def _spawn_label(idx: int) -> str:
    x, y, z, _ = SPAWN_CANDIDATES[idx]
    return f"s{idx}({x:+.0f},{y:+.0f},z={z:.1f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n_eps", type=int, nargs="?", default=20_000)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    n_eps    = args.n_eps
    out_path = Path(args.out)

    cfg = yaml.safe_load(open("configs/ppo.yaml"))
    ec  = cfg["env"]

    def _factory():
        return DroneExplorationEnv(
            world_name=ec["world_name"],
            drone_name=ec["drone_name"],
            max_episode_steps=ec["max_episode_steps"],
            env_id=_env_id,
        )

    vec_env = DummyVecEnv([_factory])
    vn_path = Path("runs/ppo_v8_frontier/checkpoints/vec_normalize.pkl")
    vec_env = VecNormalize.load(str(vn_path), vec_env)
    vec_env.training  = False
    vec_env.norm_reward = False

    model = PPO.load(
        "runs/ppo_v8_frontier/checkpoints/ppo_drone_final.zip", env=vec_env
    )

    raw_env: DroneExplorationEnv = vec_env.venv.envs[0]
    rng = np.random.default_rng()

    # best list: rooms>=MIN_ROOMS, reward DESC, voxels DESC
    best: list[dict] = []
    found3  = 0
    t_start = time.time()

    tag = f"[env{_env_id}]"
    print(f"{tag} Basladi: {n_eps} ep, filtre rooms>={MIN_ROOMS}, "
          f"siralama: reward↓ voxels↓, top {TOP_N}", flush=True)

    for ep in range(n_eps):
        spawn_idx = int(rng.integers(len(SPAWN_CANDIDATES)))
        raw_env._forced_spawn_idx = spawn_idx

        obs   = vec_env.reset()
        done  = False
        ep_ret = 0.0
        steps  = 0
        last_info: dict = {}

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, r, dones, infos = vec_env.step(action)
            ep_ret    += float(r[0])
            last_info  = infos[0]
            done       = bool(dones[0])
            steps     += 1

        rooms  = int(last_info.get("visited_rooms",  0))
        floors = int(last_info.get("visited_floors", 0))
        voxels = int(last_info.get("explored_voxels", 0))
        end    = "trunc" if steps >= ec["max_episode_steps"] else "crash"

        rec = {
            "ep":        ep,
            "env_id":    _env_id,
            "spawn_idx": spawn_idx,
            "spawn_pos": list(SPAWN_CANDIDATES[spawn_idx]),
            "return":    round(ep_ret, 2),
            "rooms":     rooms,
            "floors":    floors,
            "voxels":    voxels,
            "steps":     steps,
            "end":       end,
        }

        if rooms >= MIN_ROOMS:
            found3 += 1
            best.append(rec)
            # reward DESC, voxels DESC
            best.sort(key=lambda x: (-x["return"], -x["voxels"]))
            if len(best) > TOP_N:
                best.pop()

        if rooms >= MIN_ROOMS or ep < 5 or (ep + 1) % 200 == 0:
            el = time.time() - t_start
            rate = (ep + 1) / el if el > 0 else 1
            eta  = (n_eps - ep - 1) / rate / 3600
            print(
                f"{tag} ep{ep:5d}/{n_eps}"
                f"  {_spawn_label(spawn_idx):<18}"
                f"  ret={ep_ret:+7.1f}"
                f"  r={rooms} f={floors} v={voxels:4d}"
                f"  {steps:4d}s/{end}"
                f"  found3={found3}"
                f"  ETA≈{eta:.1f}h",
                flush=True,
            )

        if (ep + 1) % 500 == 0:
            _save(best, out_path, ep + 1, n_eps, found3)

    _save(best, out_path, n_eps, n_eps, found3)

    el = time.time() - t_start
    print(f"{tag} Bitti: {n_eps} ep, {el/3600:.2f}h, rooms>={MIN_ROOMS}: {found3}, "
          f"top {len(best)} kaydedildi → {out_path}", flush=True)

    import os as _os
    _os._exit(0)


def _save(best, out_path, done_eps, total_eps, found3):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(
        {"done_eps": done_eps, "total_eps": total_eps,
         "rooms3_found": found3, "top200": best},
        indent=2))
    tmp.replace(out_path)


if __name__ == "__main__":
    main()
