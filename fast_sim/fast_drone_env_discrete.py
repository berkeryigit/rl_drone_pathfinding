"""A3C (discrete) için ayrık-aksiyonlu drone keşif ortamı.

================================================================================
Berker'in PPO tarafı CONTINUOUS aksiyon [v, w] kullanır. A3C klasik olarak
DISCRETE aksiyonla çalışır. Bu dosya, paylaşılan FastDroneEnv'i (BİREBİR aynı
harita/ödül/gözlem) miras alıp SADECE aksiyon uzayını Discrete(7) yapar.
Böylece "continuous (PPO/TD3) vs discrete (A3C/DQN)" karşılaştırması adil olur.
================================================================================

7 ayrık aksiyon, [-1,1] normalize (v, w) uzayına eşlenir (FastDroneEnv.step
bunları V_MAX / W_MAX ile ölçekler):
    0 ileri tam       1 ileri-sol       2 ileri-sağ
    3 keskin sol      4 keskin sağ      5 orta ileri      6 dur/bekle
"""
from __future__ import annotations

import numpy as np
from gymnasium import spaces

from fast_drone_env import FastDroneEnv

# (v_norm, w_norm) — [-1,1]; FastDroneEnv.step V_MAX=0.6, W_MAX=1.5 ile ölçekler
DISCRETE_ACTIONS = np.array([
    [1.0,  0.0],   # 0 ileri tam (hızlı keşif)
    [0.7,  0.5],   # 1 ileri-sol  (yumuşak sola tara)
    [0.7, -0.5],   # 2 ileri-sağ  (yumuşak sağa tara)
    [0.3,  1.0],   # 3 keskin sol (yerinde dön, köşe/kapı)
    [0.3, -1.0],   # 4 keskin sağ
    [0.5,  0.0],   # 5 orta ileri (temkinli ilerle)
    [0.0,  0.0],   # 6 dur/bekle  (hareketli engel geçsin)
], dtype=np.float32)


class FastDroneEnvDiscrete(FastDroneEnv):
    """FastDroneEnv'in ayrık-aksiyonlu (A3C) sürümü. Ortam/ödül/gözlem AYNI."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # gözlem uzayı + tüm ödül parametreleri miras (DEĞİŞMEZ); yalnız aksiyon ayrık
        self.action_space = spaces.Discrete(len(DISCRETE_ACTIONS))

    def step(self, action):
        # ayrık indeks -> sürekli [v, w] -> paylaşılan fizik/ödül
        cont = DISCRETE_ACTIONS[int(action)]
        return super().step(cont)


if __name__ == "__main__":
    import time
    e = FastDroneEnvDiscrete(max_episode_steps=2500, lidar_history=2)
    o, _ = e.reset()
    print("obs shape:", o.shape, " action_space:", e.action_space)
    t0 = time.time(); n = 20000; info = {}
    for _ in range(n):
        o, r, term, trunc, info = e.step(e.action_space.sample())
        if term or trunc:
            o, _ = e.reset()
    print(f"{n} adim {time.time()-t0:.2f}s -> {n/(time.time()-t0):.0f} fps")
    print(f"son: vox={info['explored_voxels']} rooms={info['visited_rooms']}")
