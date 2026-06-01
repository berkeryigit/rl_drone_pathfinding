import gymnasium as gym
import numpy as np
from .drone_exploration_env import DroneExplorationEnv, V_MAX, VZ_MAX, W_MAX

# 5 aksiyon: Sürekli ileri hareket ağırlıklı (Tembelliği önler)
ACTION_TABLE = np.array([
    [   1.0,    0.0,    0.0],   # 0: Sadece Ileri (Tam gaz)
    [   0.8,    0.0,    1.0],   # 1: Ileri + Hafif Sola Donus
    [   0.8,    0.0,   -1.0],   # 2: Ileri + Hafif Saga Donus
    [   0.4,    0.0,    1.0],   # 3: Yari Ileri + Keskin Sola Donus (Spin atamaz, daire cizer)
    [   0.4,    0.0,   -1.0],   # 4: Yari Ileri + Keskin Saga Donus (Spin atamaz, daire cizer)
], dtype=np.float32)


class DroneExplorationEnvDiscrete(DroneExplorationEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_space = gym.spaces.Discrete(len(ACTION_TABLE))

    def step(self, action: int):
        return super().step(ACTION_TABLE[int(action)])
