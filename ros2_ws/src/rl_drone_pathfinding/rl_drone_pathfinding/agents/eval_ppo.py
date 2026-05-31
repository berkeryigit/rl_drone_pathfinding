"""Roll out a trained PPO policy on DroneExplorationEnv and print episode stats."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from rl_drone_pathfinding.envs import DroneExplorationEnv
from rl_drone_pathfinding.envs.drone_exploration_env import N_ROOMS, GRID_NXY


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ppo.yaml")
    parser.add_argument("--model", required=True,
                        help="Path to a trained PPO .zip")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--deterministic", action="store_true")
    args = parser.parse_args(argv)

    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)
    env_cfg = cfg["env"]

    def _factory():
        return DroneExplorationEnv(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
        )

    vec_env = DummyVecEnv([_factory])

    # Load VecNormalize stats if available (policy expects normalized obs/reward).
    vn_path = Path(args.model).parent / "vec_normalize.pkl"
    if vn_path.exists():
        print(f"[eval_ppo] Loading VecNormalize stats from {vn_path}")
        vec_env = VecNormalize.load(str(vn_path), vec_env)
        vec_env.training = False       # freeze running stats
        vec_env.norm_reward = False    # show raw episode returns

    model = PPO.load(args.model, env=vec_env)

    total_cells = GRID_NXY * GRID_NXY
    returns, rooms_list, voxels_list = [], [], []
    for ep in range(args.episodes):
        obs = vec_env.reset()
        done = False
        ep_ret = 0.0
        last_info = {}
        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, r, dones, infos = vec_env.step(action)
            ep_ret += float(r[0])      # norm_reward=False -> raw
            last_info = infos[0]
            done = bool(dones[0])
        returns.append(ep_ret)
        rooms  = last_info.get('visited_rooms', 0)
        voxels = last_info.get('explored_voxels', 0)
        rooms_list.append(rooms if isinstance(rooms, int) else 0)
        voxels_list.append(voxels if isinstance(voxels, int) else 0)
        print(f"ep {ep:02d}  return={ep_ret:+.2f}  "
              f"voxels={voxels}/{total_cells}  rooms={rooms}/{N_ROOMS}")

    print(f"\nmean return : {np.mean(returns):+.2f}  (std {np.std(returns):.2f})")
    print(f"mean rooms  : {np.mean(rooms_list):.2f} / {N_ROOMS}")
    print(f"mean voxels : {np.mean(voxels_list):.1f} / {total_cells}")

    # rclpy cleanup can crash; use os._exit to skip teardown safely.
    import os as _os
    _os._exit(0)


if __name__ == "__main__":
    main()
