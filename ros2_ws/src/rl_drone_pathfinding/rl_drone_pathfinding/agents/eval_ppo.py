"""Roll out a trained PPO policy on DroneExplorationEnv and print episode stats."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from rl_drone_pathfinding.envs import DroneExplorationEnv


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ppo.yaml")
    parser.add_argument("--model", required=True,
                        help="Path to a trained PPO .zip")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--spawn-idx", type=int, default=None,
                        help="Force a fixed spawn candidate index (0-7) for all episodes.")
    args = parser.parse_args(argv)

    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)
    env_cfg = cfg["env"]

    def _factory():
        env = DroneExplorationEnv(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
        )
        if args.spawn_idx is not None:
            env._forced_spawn_idx = args.spawn_idx
        return env

    vec_env = DummyVecEnv([_factory])

    # Load VecNormalize stats if available (policy expects normalized obs).
    vn_path = Path(args.model).parent / "vec_normalize.pkl"
    use_vn = vn_path.exists()
    if use_vn:
        print(f"[eval_ppo] Loading VecNormalize stats from {vn_path}")
        vec_env = VecNormalize.load(str(vn_path), vec_env)
        vec_env.training = False   # freeze running stats
        vec_env.norm_reward = False  # show raw episode returns

    model = PPO.load(args.model, env=vec_env)

    returns, rooms_list, floors_list = [], [], []
    for ep in range(args.episodes):
        obs = vec_env.reset()
        done = False
        ep_ret = 0.0
        last_info = {}
        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, r, dones, infos = vec_env.step(action)
            # r is VecEnv array; since norm_reward=False it's raw
            ep_ret += float(r[0])
            last_info = infos[0]
            done = bool(dones[0])
        returns.append(ep_ret)
        rooms = last_info.get('visited_rooms', '?')
        floors = last_info.get('visited_floors', '?')
        voxels = last_info.get('explored_voxels', '?')
        rooms_list.append(rooms if isinstance(rooms, int) else 0)
        floors_list.append(floors if isinstance(floors, int) else 0)
        print(f"ep {ep:02d}  return={ep_ret:+.2f}  "
              f"voxels={voxels}  rooms={rooms}  floors={floors}")

    print(f"\nmean return : {np.mean(returns):+.2f}  (std {np.std(returns):.2f})")
    print(f"mean rooms  : {np.mean(rooms_list):.1f} / 12")
    print(f"mean floors : {np.mean(floors_list):.1f} / 3")

    # rclpy cleanup can crash; use os._exit to skip teardown safely.
    import os as _os
    _os._exit(0)


if __name__ == "__main__":
    main()
