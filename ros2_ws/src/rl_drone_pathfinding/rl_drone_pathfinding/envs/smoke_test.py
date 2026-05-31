"""Quick sanity check for DroneExplorationEnv (v2, 2D action). Not a unit test."""
import time

import numpy as np

from rl_drone_pathfinding.envs import DroneExplorationEnv


def main():
    env = DroneExplorationEnv(max_episode_steps=200)
    obs, info = env.reset()
    print("obs shape:", obs.shape, "(beklenen 40)  obs sample:", obs[:6])
    total = 0.0
    for i in range(80):
        # Sabit aksiyon: ileri + hafif sola donus — env'i hareket ettir.
        a = np.array([0.8, 0.15], dtype=np.float32)
        obs, r, term, trunc, info = env.step(a)
        total += r
        if i % 10 == 0:
            print(f"step {i:3d}  r={r:+.3f}  vox={info['explored_voxels']:3d}"
                  f"  rooms={info['visited_rooms']}  min_l={info['min_lidar']:.2f}"
                  f"  x={info['x']:+.2f} y={info['y']:+.2f}")
        if term or trunc:
            print("episode bitti:", "carpisma/term" if term else "trunc")
            break
    print("toplam odul:", total)
    env.close()
    time.sleep(0.2)


if __name__ == "__main__":
    main()
