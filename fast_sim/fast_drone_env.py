"""HIZLI numpy/Gymnasium 2D drone keşif ortamı — Gazebo env'inin BİREBİR analoğu.

================================================================================
NEDEN: Gazebo+ROS ~40 fps. Aynı problem 2D düzlemsel -> numpy ray-cast ile
~1000-5000 fps (50-125x hızlı). 1.5M adım ~11 saat yerine dakikalar.
Berker'in kararı: Gazebo zorunlu değil; hızlı sürümle de eğit, ikisini kıyasla.
================================================================================

BİREBİR aynı (Gazebo env ile): harita (6 oda, kapılar, 3 hareketli engel),
sabit R0 spawn, 40-d gözlem, 2D action [v,w], v2.0 ödülü (üçlü eval'de EN İYİ).
TEK fark: simülatör (Gazebo yerine numpy ray-cast). ROS/rclpy YOK.
"""
from __future__ import annotations

import math
import gymnasium as gym
import numpy as np
from gymnasium import spaces

# ---------- Dünya / ızgara (multi_room.sdf ile birebir) ----------
WORLD_HALF   = 8.0
GRID_CELL_XY = 0.5
GRID_NXY     = int((2 * WORLD_HALF) / GRID_CELL_XY)   # 32 -> 1024 hücre

# ---------- Lidar / hareket (Gazebo env ile aynı) ----------
LIDAR_RAYS   = 360
LIDAR_BINS   = 32
LIDAR_MAX    = 10.0
LIDAR_MIN    = 0.15
LIDAR_NOISE  = 0.02
FORWARD_BIN  = 16
V_MAX        = 0.6
W_MAX        = 1.5
V_REVERSE    = -0.25
DT           = 0.15          # sim adımı/saniye (Gazebo'nun ~adım başına yer değiştirmesine denk)
COLLISION_DIST    = 0.30
OMNI_PENALTY_DIST = 1.0
IDLE_GRACE        = 40
DRONE_RADIUS = 0.15
WALL_HALF    = 0.10          # duvar yarı-kalınlığı (carpisma icin)

# ---------- Oda sınırları + sabit R0 spawn ----------
ROOM_X1, ROOM_X2, ROOM_Y0, N_ROOMS = -2.0, 4.0, 0.0, 6
SPAWN_X, SPAWN_Y, SPAWN_YAW = -5.0, -5.0, 0.0

# ---------- Duvar segmentleri (centerline) — multi_room.sdf ----------
# (x0,y0,x1,y1). Dış sınır + iç duvarlar (kapı boşlukları segmentler arasında).
WALLS = np.array([
    # dış sınır
    [-8, -8,  8, -8], [-8,  8,  8,  8], [-8, -8, -8,  8], [ 8, -8,  8,  8],
    # iç dikey x=-2, kapı y[-4,-2]
    [-2, -8, -2, -4], [-2, -2, -2,  8],
    # iç dikey x=4, kapı y[3,5]
    [ 4, -8,  4,  3], [ 4,  5,  4,  8],
    # iç yatay y=0, kapılar x[-7,-5],[0,2],[5,7]
    [-8,  0, -7,  0], [-5,  0,  0,  0], [ 2,  0,  5,  0], [ 7,  0,  8,  0],
], dtype=np.float64)
_WA = WALLS[:, :2]                 # segment baslangic (S,2)
_WE = WALLS[:, 2:] - WALLS[:, :2]  # segment vektoru (S,2)

# ---------- Hareketli engeller (Gazebo MOVING_OBS ile aynı) ----------
MOVING_OBS = [
    {"x0": -5.0, "y0": -3.0, "axis": "y", "amp": 2.0, "T": 7.0, "r": 0.35},
    {"x0":  1.0, "y0":  4.0, "axis": "x", "amp": 2.5, "T": 9.0, "r": 0.45},
    {"x0":  6.0, "y0": -4.0, "axis": "y", "amp": 2.5, "T": 5.0, "r": 0.35},
]


def _room_id(x, y):
    col = 0 if x < ROOM_X1 else (1 if x < ROOM_X2 else 2)
    row = 0 if y < ROOM_Y0 else 1
    return row * 3 + col


class FastDroneEnv(gym.Env):
    """Gazebo DroneExplorationEnv'in hızlı numpy analoğu (v2.0 ödülü)."""
    metadata = {"render_modes": []}

    def __init__(self, max_episode_steps=2500, seed=None, env_id=0):
        super().__init__()
        self.max_episode_steps = max_episode_steps
        self.action_space = spaces.Box(low=np.array([-1, -1], np.float32),
                                       high=np.array([1, 1], np.float32), dtype=np.float32)
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(40,), dtype=np.float32)
        # ışın açıları (gövde çerçevesi): -pi..pi, ray~180 = ileri (Gazebo ile aynı)
        self._ray_body = np.linspace(-math.pi, math.pi, LIDAR_RAYS, dtype=np.float64)
        self._np_random, _ = gym.utils.seeding.np_random(seed)
        self._reset_state()

    def _reset_state(self):
        self.x, self.y, self.yaw = SPAWN_X, SPAWN_Y, SPAWN_YAW
        self.v, self.w = 0.0, 0.0
        self._step = 0
        self._explored = np.zeros((GRID_NXY, GRID_NXY), bool)
        self._rooms = set()
        self._idle = 0

    # ----- engel konumları (zaman t'de) -----
    def _obstacles(self):
        t = self._step * DT
        cs, rs = [], []
        for o in MOVING_OBS:
            ph = 2.0 * math.pi * t / o["T"]
            ox = o["x0"] + (o["amp"] * math.sin(ph) if o["axis"] == "x" else 0.0)
            oy = o["y0"] + (o["amp"] * math.sin(ph) if o["axis"] == "y" else 0.0)
            cs.append((ox, oy)); rs.append(o["r"])
        return np.array(cs), np.array(rs)

    # ----- vektörize 360-ışın lidar (duvar segmentleri + engel daireleri) -----
    def _lidar(self, obs_c, obs_r):
        O = np.array([self.x, self.y])
        ang = self.yaw + self._ray_body                  # (R,)
        dx, dy = np.cos(ang), np.sin(ang)                # (R,)
        dist = np.full(LIDAR_RAYS, LIDAR_MAX)

        # ray-segment: O + t*d = A + u*E
        for i in range(WALLS.shape[0]):
            A = _WA[i]; E = _WE[i]
            denom = dx * E[1] - dy * E[0]                # (R,)
            nz = np.abs(denom) > 1e-9
            aox, aoy = A[0] - O[0], A[1] - O[1]
            t = (aox * E[1] - aoy * E[0]) / np.where(nz, denom, 1.0)
            u = (aox * dy - aoy * dx) / np.where(nz, denom, 1.0)
            hit = nz & (t > 0) & (u >= 0) & (u <= 1)
            dist = np.where(hit, np.minimum(dist, t), dist)

        # ray-circle
        for c, r in zip(obs_c, obs_r):
            fx, fy = O[0] - c[0], O[1] - c[1]
            b = dx * fx + dy * fy                        # d unit -> a=1
            cc = fx * fx + fy * fy - r * r
            disc = b * b - cc
            ok = disc >= 0
            sq = np.sqrt(np.where(ok, disc, 0.0))
            tc = -b - sq
            hit = ok & (tc > 0)
            dist = np.where(hit, np.minimum(dist, tc), dist)

        dist = np.clip(dist + self._np_random.normal(0, LIDAR_NOISE, LIDAR_RAYS),
                       LIDAR_MIN, LIDAR_MAX)
        return dist

    def _bin_lidar(self, ranges):
        bs = LIDAR_RAYS // LIDAR_BINS                     # 11
        out = ranges[:bs * LIDAR_BINS].reshape(LIDAR_BINS, bs).min(axis=1)
        return np.clip(out / LIDAR_MAX, 0.0, 1.0).astype(np.float32)

    def _make_obs(self, lidar_obs, scan_min):
        progress = self._explored.sum() / float(GRID_NXY * GRID_NXY)
        rooms_sc = (max(1, len(self._rooms)) - 1) / float(max(1, N_ROOMS - 1))
        idle_n = min(1.0, self._idle / float(self.max_episode_steps))
        return np.concatenate([
            lidar_obs,
            np.array([math.cos(self.yaw), math.sin(self.yaw)], np.float32),
            np.array([np.clip(self.v / V_MAX, -1, 1), np.clip(self.w / W_MAX, -1, 1)], np.float32),
            np.array([progress, rooms_sc], np.float32),
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1), idle_n], np.float32),
        ]).astype(np.float32)

    def _mark_voxel(self):
        gx = int((self.x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((self.y + WORLD_HALF) / GRID_CELL_XY)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY and not self._explored[gx, gy]:
            self._explored[gx, gy] = True
            return True
        return False

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)
        self._reset_state()
        oc, orad = self._obstacles()
        lidar = self._lidar(oc, orad)
        self._mark_voxel(); self._rooms.add(_room_id(self.x, self.y))
        return self._make_obs(self._bin_lidar(lidar), float(lidar.min())), {}

    def step(self, action):
        a = np.asarray(action, np.float32).reshape(-1)
        v = float(np.clip(a[0], -1.0, 1.0)); v = V_MAX * (v if v >= 0 else max(V_REVERSE, v))
        w = float(np.clip(a[1], -1.0, 1.0) * W_MAX)
        self.v, self.w = v, w
        self.yaw = (self.yaw + w * DT + math.pi) % (2 * math.pi) - math.pi
        self.x += v * math.cos(self.yaw) * DT
        self.y += v * math.sin(self.yaw) * DT
        self._step += 1

        oc, orad = self._obstacles()
        lidar = self._lidar(oc, orad)
        scan_min = float(lidar.min())
        lidar_obs = self._bin_lidar(lidar)

        new_voxel = self._mark_voxel()
        groom = _room_id(self.x, self.y)
        new_room = groom not in self._rooms
        if new_room:
            self._rooms.add(groom)

        # ----- ÖDÜL (v2.0 — üçlü eval'de en iyi) -----
        reward = -0.01
        if new_voxel:
            reward += 1.0; self._idle = 0
        else:
            self._idle += 1
            if self._idle > IDLE_GRACE:
                reward -= 0.05
        if new_room:
            reward += 10.0
        if scan_min < OMNI_PENALTY_DIST:
            reward -= 0.5 * (OMNI_PENALTY_DIST - scan_min) / OMNI_PENALTY_DIST
        forward_open = float(lidar_obs[FORWARD_BIN])
        forward_act = float(np.clip(a[0], 0.0, 1.0))
        reward += 0.05 * forward_open * forward_act

        terminated = scan_min < COLLISION_DIST
        if terminated:
            reward -= 10.0
        truncated = self._step >= self.max_episode_steps

        info = {"explored_voxels": int(self._explored.sum()),
                "visited_rooms": len(self._rooms),
                "min_lidar": scan_min, "x": self.x, "y": self.y,
                "collision": bool(terminated)}
        return self._make_obs(lidar_obs, scan_min), float(reward), terminated, truncated, info


if __name__ == "__main__":
    # hız + akil sagligi testi
    import time
    e = FastDroneEnv(max_episode_steps=2500)
    o, _ = e.reset()
    print("obs shape:", o.shape, "(beklenen 40)  action:", e.action_space)
    t0 = time.time(); n = 20000; tot = 0.0
    o, _ = e.reset()
    for i in range(n):
        o, r, term, trunc, info = e.step(e.action_space.sample())
        tot += r
        if term or trunc:
            o, _ = e.reset()
    dt = time.time() - t0
    print(f"{n} adim {dt:.2f}s -> {n/dt:.0f} fps (Gazebo ~40 fps)")
    print(f"son: vox={info['explored_voxels']} rooms={info['visited_rooms']}")
