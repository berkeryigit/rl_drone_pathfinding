"""Quick sanity check for DroneExplorationEnv. Not a unit test."""
import time

import numpy as np

from rl_drone_pathfinding.envs import DroneExplorationEnv


def main():
    env = DroneExplorationEnv(max_episode_steps=200)
    obs, info = env.reset()
    print("obs shape:", obs.shape, "obs sample:", obs[:6])
    total = 0.0
    for i in range(60):
        # Constant action: forward + slight upward + no yaw, just to exercise 3D.
        a = np.array([0.5, 0.2, 0.0], dtype=np.float32)
        obs, r, term, trunc, info = env.step(a)
        total += r
        if i % 10 == 0:
            print(f"step {i:3d}  r={r:+.3f}  vox={info['explored_voxels']:3d}"
                  f"  rooms={info['visited_rooms']}  fl={info['visited_floors']}"
                  f"  z={info['z']:.2f}  min_l={info['min_lidar']:.2f}"
                  f"  up={info['scan_up']:.2f}  dn={info['scan_down']:.2f}")
        if term or trunc:
            print("episode ended:", "term" if term else "trunc")
            break
    print("total reward:", total)
    env.close()
    time.sleep(0.2)


if __name__ == "__main__":
    main()
