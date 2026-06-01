"""Roll out a trained DQN policy on DroneExplorationEnvDiscrete and print episode stats."""
from __future__ import annotations

import argparse

import numpy as np
import yaml
from stable_baselines3 import DQN
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack

from rl_drone_pathfinding.envs import DroneExplorationEnvDiscrete


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dqn.yaml")
    parser.add_argument("--model", required=True,
                        help="Path to a trained DQN .zip")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--deterministic", action="store_true")
    args = parser.parse_args(argv)

    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)
    env_cfg = cfg["env"]

    env = DroneExplorationEnvDiscrete(
        world_name=env_cfg["world_name"],
        drone_name=env_cfg["drone_name"],
        max_episode_steps=env_cfg["max_episode_steps"],
    )
    vec_env = DummyVecEnv([lambda: env])
    vec_env = VecFrameStack(vec_env, n_stack=4)
    model = DQN.load(args.model)

    returns = []
    for ep in range(args.episodes):
        obs = vec_env.reset()
        done = False
        ep_ret = 0.0
        last_info = {}
        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, r, dones, infos = vec_env.step(action)
            ep_ret += r[0]
            last_info = infos[0]
            done = dones[0]
        returns.append(ep_ret)
        print(f"ep {ep:02d}  return={ep_ret:+.2f}  "
              f"cells={last_info.get('explored_voxels')}  "
              f"rooms={last_info.get('visited_rooms')}")

    print(f"\nmean return over {args.episodes} eps: "
          f"{np.mean(returns):+.2f}  (std {np.std(returns):.2f})")
    vec_env.close()


if __name__ == "__main__":
    main()
