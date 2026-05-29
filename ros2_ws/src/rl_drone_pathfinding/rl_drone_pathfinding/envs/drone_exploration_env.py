"""Gymnasium env — tek katli 6-odali bina, 2D lidar, hareketli engeller.

Dunya (multi_room.sdf):
    * 16x16 m, tek kat 2.5 m.
    * 6 asimetrik oda: 3 sutun x 2 satir.
      R3(x<-2,y>0) | R4(-2<x<4,y>0) | R5(x>4,y>0)
      R0(x<-2,y<0) | R1(-2<x<4,y<0) | R2(x>4,y<0)
    * Sol duvar x=-2 : kapi y in [-4,-2]
    * Sag duvar x= 4 : kapi y in [ 3, 5]
    * Yatay duvar y=0 : kapilar x in [-7,-5], [0,2], [5,7]
    * 3 hareketli engel.

Gozlem (41-d, sadece 2D lidar):
    [0:32]  : 32-bin yatay lidar
    [32:34] : (cos(yaw), sin(yaw))
    [34:37] : (vx/v_max, vz/vz_max, wz/w_max)
    [37:39] : kesif_orani, oda_scalari
    [39:41] : min_lidar/max_range, idle_counter

Aksiyon (3-d, surekli):
    a[0] -> vx, a[1] -> vz, a[2] -> wz

Odul (v9 newmap):
    +1.0 yeni voxel
    +15  yeni oda
    -0.3 * max(0, 1 - min_lidar/2.0)  progressif duvar cezasi (0-2m arasi)
    -0.5 duvara cok yakin (<0.5m)
    -10  carpisme (episode biter)
    -0.1 ayni voxelde kalma (<30 step)
    -0.5 ayni voxelde kalma (>=30 step, oda bitmis cik)
    -0.001 her step zaman
    +0..+0.4 frontier bonus (ileri lidar acik oldugunda ileri git)
    +0..+0.1 en uzak sektore don bonus
"""
from __future__ import annotations

import math
import os
import subprocess
import threading
import time
from typing import Optional

import gymnasium as gym
import numpy as np
import rclpy
from gymnasium import spaces
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan

# ---------- Dunya geometrisi ----------
DEFAULT_WORLD_NAME = "multi_room"
DEFAULT_DRONE_NAME = "rl_drone"

WORLD_HALF   = 8.0
FLOOR_HEIGHT = 2.5
N_FLOORS     = 1
TOTAL_HEIGHT = 2.5

GRID_CELL_XY = 0.5
GRID_NXY     = int((2 * WORLD_HALF) / GRID_CELL_XY)  # 32
GRID_NZ      = 1

LIDAR_BINS   = 32
LIDAR_MAX    = 10.0
# Lidar min_angle=-pi (backward), sweeps CCW. Ray 180 -> angle 0 -> body +X.
# Bin 16 = forward.
FORWARD_BIN  = 16
V_MAX        = 0.6
VZ_MAX       = 0.4
W_MAX        = 1.5
COLLISION_DIST      = 0.25
NEAR_COLLISION_DIST = 0.5
WALL_PENALTY_DIST   = 2.0
STEP_DT      = 0.02
IDLE_THRESHOLD = 30

# ---------- Oda sinirlari (asimetrik) ----------
ROOM_X1 = -2.0
ROOM_X2 =  4.0
ROOM_Y0 =  0.0
N_ROOMS =  6

# ---------- Spawn noktalari (her odadan biri) ----------
SPAWN_CANDIDATES = [
    (-5.0, -5.0, 0.6,  0.0 ),   # R0
    ( 1.0, -5.0, 0.6,  1.57),   # R1
    ( 6.0, -4.0, 0.6,  3.14),   # R2
    (-5.0,  4.0, 0.6,  0.0 ),   # R3
    ( 1.0,  4.0, 0.6, -1.57),   # R4
    ( 6.0,  4.0, 0.6,  3.14),   # R5
]

# ---------- Hareketli engeller ----------
MOVING_OBS = [
    {"name": "obs_moving_1", "x0": -5.0, "y0": -3.0, "z": 0.5, "axis": "y", "amp": 2.0, "T": 7.0},
    {"name": "obs_moving_2", "x0":  1.0, "y0":  4.0, "z": 0.3, "axis": "x", "amp": 2.5, "T": 9.0},
    {"name": "obs_moving_3", "x0":  6.0, "y0": -4.0, "z": 0.5, "axis": "y", "amp": 2.5, "T": 5.0},
]
OBS_UPDATE_FREQ = 5


def _room_id(x: float, y: float) -> int:
    col = 0 if x < ROOM_X1 else (1 if x < ROOM_X2 else 2)
    row = 0 if y < ROOM_Y0 else 1
    return row * 3 + col


def _yaw_from_quat(qx, qy, qz, qw):
    return math.atan2(2.0 * (qw * qz + qx * qy),
                      1.0 - 2.0 * (qy * qy + qz * qz))


class _RosBridge(Node):
    def __init__(self):
        super().__init__("rl_drone_env_bridge")
        qos = QoSProfile(depth=10,
                         reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST)
        self._scan: Optional[np.ndarray] = None
        self._scan_min: float = LIDAR_MAX
        self._scan_up: float  = LIDAR_MAX
        self._scan_down: float = LIDAR_MAX
        self._pose  = (0.0, 0.0, 0.0, 0.0)
        self._twist = (0.0, 0.0, 0.0)
        self._lock  = threading.Lock()

        self.create_subscription(LaserScan, "scan",      self._on_scan,      qos)
        self.create_subscription(LaserScan, "scan_up",   self._on_scan_up,   qos)
        self.create_subscription(LaserScan, "scan_down", self._on_scan_down, qos)
        self.create_subscription(Odometry,  "odom",      self._on_odom,      10)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)

    @staticmethod
    def _safe_min(ranges) -> float:
        if not ranges:
            return LIDAR_MAX
        a = np.asarray(ranges, dtype=np.float32)
        a = np.where(np.isfinite(a), a, LIDAR_MAX)
        return float(np.clip(a, 0.0, LIDAR_MAX).min()) if a.size else LIDAR_MAX

    def _on_scan(self, msg: LaserScan):
        r = np.asarray(msg.ranges, dtype=np.float32)
        r = np.clip(np.where(np.isfinite(r), r, LIDAR_MAX), 0.0, LIDAR_MAX)
        with self._lock:
            self._scan = r
            self._scan_min = float(r.min()) if r.size else LIDAR_MAX

    def _on_scan_up(self, msg: LaserScan):
        with self._lock:
            self._scan_up = self._safe_min(msg.ranges)

    def _on_scan_down(self, msg: LaserScan):
        with self._lock:
            self._scan_down = self._safe_min(msg.ranges)

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        with self._lock:
            self._pose  = (p.x, p.y, p.z, _yaw_from_quat(q.x, q.y, q.z, q.w))
            self._twist = (msg.twist.twist.linear.x,
                           msg.twist.twist.linear.z,
                           msg.twist.twist.angular.z)

    def snapshot(self):
        with self._lock:
            scan = None if self._scan is None else self._scan.copy()
            return scan, self._scan_min, self._scan_up, self._scan_down, self._pose, self._twist

    def send_cmd(self, vx, vz, wz):
        msg = Twist()
        msg.linear.x  = float(vx)
        msg.linear.z  = float(vz)
        msg.angular.z = float(wz)
        self.cmd_pub.publish(msg)


class DroneExplorationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, world_name=DEFAULT_WORLD_NAME, drone_name=DEFAULT_DRONE_NAME,
                 max_episode_steps=1000, seed=None, env_id=0):
        super().__init__()
        self.world_name = world_name
        self.drone_name = drone_name
        self.max_episode_steps = max_episode_steps

        # Isolate each parallel env's ROS domain and gz partition.
        os.environ['ROS_DOMAIN_ID'] = str(env_id)
        os.environ['GZ_PARTITION']  = f'sim{env_id}'

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([ 1.0,  1.0,  1.0], dtype=np.float32),
            dtype=np.float32,
        )
        # 32 lidar + 2 yaw + 3 vel + 2 explore + 2 lidar_stats = 41
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(41,), dtype=np.float32
        )

        if not rclpy.ok():
            rclpy.init(args=None)
        self._node = _RosBridge()
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._executor_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._executor_thread.start()

        self._step_count   = 0
        self._explored     = np.zeros((GRID_NXY, GRID_NXY, GRID_NZ), dtype=bool)
        self._visited_rooms: set[int] = set()
        self._steps_since_new_voxel = 0
        self._np_random, _ = gym.utils.seeding.np_random(seed)

    # ----- Gozlem -----

    def _bin_lidar(self, ranges: np.ndarray) -> np.ndarray:
        n = ranges.shape[0]
        if n == 0:
            return np.ones(LIDAR_BINS, dtype=np.float32)
        bs = max(1, n // LIDAR_BINS)
        out = np.array([ranges[i*bs:(i+1)*bs].min() if ranges[i*bs:(i+1)*bs].size else LIDAR_MAX
                        for i in range(LIDAR_BINS)], dtype=np.float32)
        return np.clip(out / LIDAR_MAX, 0.0, 1.0)

    def _make_obs(self):
        scan, scan_min, scan_up, scan_down, (x, y, z, yaw), (vx, vz, wz) = self._node.snapshot()
        if scan is None:
            scan = np.full(360, LIDAR_MAX, dtype=np.float32)
            scan_min = LIDAR_MAX

        lidar_obs = self._bin_lidar(scan)
        progress     = self._explored.sum() / float(GRID_NXY * GRID_NXY * GRID_NZ)
        rooms_scalar = (max(1, len(self._visited_rooms)) - 1) / float(max(1, N_ROOMS - 1))
        idle_norm    = min(1.0, self._steps_since_new_voxel / float(self.max_episode_steps))

        obs = np.concatenate([
            lidar_obs,                                                         # 32
            np.array([math.cos(yaw), math.sin(yaw)], dtype=np.float32),        # 2
            np.array([np.clip(vx / V_MAX,  -1, 1),                             # 3
                      np.clip(vz / VZ_MAX, -1, 1),
                      np.clip(wz / W_MAX,  -1, 1)], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),              # 2
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1),                     # 2
                      idle_norm], dtype=np.float32),
        ])
        return obs.astype(np.float32), scan_min, scan_up, scan_down, (x, y, z, yaw), lidar_obs

    def _mark_voxel(self, x, y, z) -> bool:
        gx = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((y + WORLD_HALF) / GRID_CELL_XY)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY and not self._explored[gx, gy, 0]:
            self._explored[gx, gy, 0] = True
            return True
        return False

    # ----- gz service -----

    def _gz_set_pose(self, name: str, x: float, y: float, z: float, yaw: float = 0.0):
        req = (f"name: '{name}', position: {{x: {x}, y: {y}, z: {z}}}, "
               f"orientation: {{x: 0, y: 0, "
               f"z: {math.sin(yaw/2):.6f}, w: {math.cos(yaw/2):.6f}}}")
        subprocess.run(
            ["gz", "service", "-s", f"/world/{self.world_name}/set_pose",
             "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
             "--timeout", "500", "--req", req],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )

    def _gz_set_pose_async(self, name: str, x: float, y: float, z: float):
        req = (f"name: '{name}', position: {{x: {x:.4f}, y: {y:.4f}, z: {z:.4f}}}, "
               f"orientation: {{x: 0, y: 0, z: 0, w: 1}}")
        subprocess.Popen(
            ["gz", "service", "-s", f"/world/{self.world_name}/set_pose",
             "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
             "--timeout", "200", "--req", req],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def _update_obstacles(self):
        t = self._step_count * STEP_DT
        for obs in MOVING_OBS:
            phase = 2.0 * math.pi * t / obs["T"]
            x = obs["x0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "x" else 0.0)
            y = obs["y0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "y" else 0.0)
            self._gz_set_pose_async(obs["name"], x, y, obs["z"])

    # ----- Gym API -----

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)
        self._node.send_cmd(0.0, 0.0, 0.0)
        time.sleep(0.05)
        sp = SPAWN_CANDIDATES[int(self._np_random.integers(len(SPAWN_CANDIDATES)))]
        self._gz_set_pose(self.drone_name, sp[0], sp[1], sp[2], sp[3])
        self._step_count = 0
        self._explored.fill(False)
        self._visited_rooms = set()
        self._steps_since_new_voxel = 0
        time.sleep(0.2)
        for _ in range(100):
            if self._node.snapshot()[0] is not None:
                break
            time.sleep(0.05)
        obs, _, _, _, (x, y, z, _), _ = self._make_obs()
        self._mark_voxel(x, y, z)
        self._visited_rooms.add(_room_id(x, y))
        return obs, {}

    def step(self, action: np.ndarray):
        a   = np.asarray(action, dtype=np.float32).reshape(-1)
        vx  = float(np.clip(0.35 * (a[0] + 1.0) * V_MAX - 0.3 * V_MAX, -0.3 * V_MAX, V_MAX))
        vz  = float(np.clip(a[1] * VZ_MAX, -VZ_MAX, VZ_MAX))
        wz  = float(np.clip(a[2] * W_MAX,  -W_MAX,  W_MAX))
        self._node.send_cmd(vx, vz, wz)
        time.sleep(STEP_DT)
        self._step_count += 1

        if self._step_count % OBS_UPDATE_FREQ == 0:
            self._update_obstacles()

        obs, scan_min, scan_up, scan_down, (x, y, z, _), lidar_obs = self._make_obs()

        new_voxel = self._mark_voxel(x, y, z)
        groom     = _room_id(x, y)
        new_room  = groom not in self._visited_rooms
        if new_room:
            self._visited_rooms.add(groom)

        # ----- Odul -----
        reward = -0.001

        if new_voxel:
            reward += 1.0
            self._steps_since_new_voxel = 0
        else:
            reward -= 0.1 if self._steps_since_new_voxel < IDLE_THRESHOLD else 0.5
            self._steps_since_new_voxel += 1

        if new_room:
            reward += 15.0

        # Progressive duvar cezasi
        if scan_min < WALL_PENALTY_DIST:
            reward -= (WALL_PENALTY_DIST - scan_min) / WALL_PENALTY_DIST * 0.3

        clearance = min(scan_min, scan_up, scan_down)
        if clearance < NEAR_COLLISION_DIST:
            reward -= 0.5

        terminated = False
        if clearance < COLLISION_DIST:
            reward -= 10.0
            terminated = True

        # Frontier bonus: ileri lidar acik + ileri gidiyorsa odullendir
        forward_openness = float(lidar_obs[FORWARD_BIN])
        fwd_action = float(np.clip(a[0], 0.0, 1.0))
        reward += 0.4 * forward_openness * fwd_action

        # En uzak sektore don bonusu
        max_bin = int(np.argmax(lidar_obs))
        max_val = float(lidar_obs[max_bin])
        if max_val > 0.5 and max_val - forward_openness > 0.2 and max_bin != FORWARD_BIN:
            dir_sign = 1.0 if max_bin > FORWARD_BIN else -1.0
            turn_align = float(dir_sign * a[2])
            if turn_align > 0.0:
                reward += 0.1 * max_val * turn_align

        truncated = self._step_count >= self.max_episode_steps

        info = {
            "explored_voxels": int(self._explored.sum()),
            "visited_rooms":   len(self._visited_rooms),
            "visited_floors":  1,
            "min_lidar":       float(scan_min),
            "scan_up":         float(scan_up),
            "scan_down":       float(scan_down),
            "x": float(x), "y": float(y), "z": float(z),
            "vx_cmd": vx, "vz_cmd": vz, "wz_cmd": wz,
        }
        return obs, float(reward), terminated, truncated, info

    def close(self):
        try:
            self._node.send_cmd(0.0, 0.0, 0.0)
        except Exception:
            pass
        try:
            self._executor.shutdown()
        except Exception:
            pass
        try:
            self._node.destroy_node()
        except Exception:
            pass
