import gymnasium as gym
import numpy as np
from .drone_exploration_env import DroneExplorationEnv, V_MAX, VZ_MAX, W_MAX

# 7 aksiyon: hover / forward / back / yaw_left / yaw_right / up / down
ACTION_TABLE = np.array([
    [   0.0,    0.0,    0.0],   # 0: hover
    [ V_MAX,    0.0,    0.0],   # 1: forward
    [-V_MAX,    0.0,    0.0],   # 2: back
    [   0.0,    0.0,  W_MAX],   # 3: yaw left
    [   0.0,    0.0, -W_MAX],   # 4: yaw right
    [   0.0,  VZ_MAX,    0.0],  # 5: up
    [   0.0, -VZ_MAX,    0.0],  # 6: down
], dtype=np.float32)


class DroneExplorationEnvDiscrete(DroneExplorationEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_space = gym.spaces.Discrete(len(ACTION_TABLE))

    def step(self, action: int):
        return super().step(ACTION_TABLE[int(action)])
