"""Gymnasium environment that talks to a Gazebo Harmonic + ROS 2 drone sim.

Observation (40-d, all normalized to roughly [-1, 1] / [0, 1]):
    [0:32]  : 32-bin lidar (min over each 360/32 angular sector, /max_range)
    [32:34] : (cos(yaw), sin(yaw))
    [34:36] : (linear_x_vel / v_max, angular_z_vel / w_max)
    [36:38] : exploration progress, room id (one-hot collapsed to scalar)
    [38:40] : min_lidar_dist / max_range, steps_since_new_cell / max_steps

Action (2-d, continuous):
    a[0] in [-1, 1] -> linear x velocity in [-0.3*v_max, v_max]   (mostly forward)
    a[1] in [-1, 1] -> angular z velocity in [-w_max, w_max]

Reward (per-step):
    +1.0 * (#new explored cells this step)
    +15  on first entry to a previously-unentered room
    -10  on collision (terminates)
    -0.5 if min lidar < 0.5 m (near-collision)
    -0.1 if no new cell explored in this step (idle penalty)
    -0.001 per step (tiny time penalty)

Episode ends:
    - terminated: collision (min lidar < `collision_dist`)
    - truncated : `max_episode_steps` reached
"""
from __future__ import annotations

import math
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
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan


# ----- Defaults -----
DEFAULT_WORLD_NAME = "multi_room"
DEFAULT_DRONE_NAME = "rl_drone"
WORLD_HALF = 8.0          # world spans [-8, +8] in x and y
GRID_CELL = 0.5           # exploration grid resolution (m)
GRID_N = int((2 * WORLD_HALF) / GRID_CELL)   # 32
LIDAR_BINS = 32
LIDAR_MAX = 10.0
V_MAX = 0.6               # m/s
W_MAX = 1.5               # rad/s
COLLISION_DIST = 0.25
NEAR_COLLISION_DIST = 0.5
STEP_DT = 0.1             # seconds per env step (sim time)
SPAWN_CANDIDATES = [
    (4.0, -4.0, 1.57),
    (-4.0, -4.0, 0.0),
    (-4.0, 4.0, -1.57),
    (4.0, 4.0, 3.14),
]


def _yaw_from_quat(qx: float, qy: float, qz: float, qw: float) -> float:
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def _room_id(x: float, y: float) -> int:
    """Return 0..3 for the four quadrant rooms (NE, NW, SW, SE)."""
    if x >= 0 and y >= 0:
        return 0
    if x < 0 and y >= 0:
        return 1
    if x < 0 and y < 0:
        return 2
    return 3


class _RosBridge(Node):
    """A small rclpy node holding pubs/subs for the env. Spun in a background thread."""

    def __init__(self):
        super().__init__("rl_drone_env_bridge")

        sensor_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )

        self._scan: Optional[np.ndarray] = None
        self._scan_min: float = LIDAR_MAX
        self._pose = (0.0, 0.0, 0.0)        # x, y, yaw
        self._twist = (0.0, 0.0)            # vx_body, wz
        self._lock = threading.Lock()

        self.create_subscription(LaserScan, "scan", self._on_scan, sensor_qos)
        self.create_subscription(Odometry, "odom", self._on_odom, 10)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)

    def _on_scan(self, msg: LaserScan):
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        # Replace inf / nan / out-of-range with LIDAR_MAX so binning is well-defined.
        ranges = np.where(np.isfinite(ranges), ranges, LIDAR_MAX)
        ranges = np.clip(ranges, 0.0, LIDAR_MAX)
        with self._lock:
            self._scan = ranges
            self._scan_min = float(ranges.min()) if ranges.size else LIDAR_MAX

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = _yaw_from_quat(q.x, q.y, q.z, q.w)
        v = msg.twist.twist.linear.x
        w = msg.twist.twist.angular.z
        with self._lock:
            self._pose = (p.x, p.y, yaw)
            self._twist = (v, w)

    def snapshot(self):
        with self._lock:
            scan = None if self._scan is None else self._scan.copy()
            return scan, self._scan_min, self._pose, self._twist

    def send_cmd(self, v: float, w: float):
        msg = Twist()
        msg.linear.x = float(v)
        msg.angular.z = float(w)
        self.cmd_pub.publish(msg)


class DroneExplorationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        world_name: str = DEFAULT_WORLD_NAME,
        drone_name: str = DEFAULT_DRONE_NAME,
        max_episode_steps: int = 1000,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self.world_name = world_name
        self.drone_name = drone_name
        self.max_episode_steps = max_episode_steps

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        obs_dim = LIDAR_BINS + 2 + 2 + 2 + 2  # = 40
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(obs_dim,), dtype=np.float32
        )

        # ROS init (idempotent across env instances).
        if not rclpy.ok():
            rclpy.init(args=None)
        self._node = _RosBridge()
        self._executor_thread = threading.Thread(
            target=self._spin_node, daemon=True
        )
        self._executor_thread.start()

        # Episode state
        self._step_count = 0
        self._explored: np.ndarray = np.zeros((GRID_N, GRID_N), dtype=bool)
        self._visited_rooms: set[int] = set()
        self._steps_since_new_cell = 0

        self._np_random, _ = gym.utils.seeding.np_random(seed)

    # ---------- internal helpers ----------

    def _spin_node(self):
        try:
            rclpy.spin(self._node)
        except Exception:
            pass

    def _wait_for_first_msgs(self, timeout_s: float = 20.0):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            scan, _, _, _ = self._node.snapshot()
            if scan is not None:
                return True
            time.sleep(0.05)
        return False

    def _bin_lidar(self, ranges: np.ndarray) -> np.ndarray:
        n = ranges.shape[0]
        if n == 0:
            return np.ones(LIDAR_BINS, dtype=np.float32)
        bin_size = max(1, n // LIDAR_BINS)
        binned = np.empty(LIDAR_BINS, dtype=np.float32)
        for i in range(LIDAR_BINS):
            chunk = ranges[i * bin_size : (i + 1) * bin_size]
            binned[i] = chunk.min() if chunk.size else LIDAR_MAX
        return np.clip(binned / LIDAR_MAX, 0.0, 1.0)

    def _make_obs(self):
        scan, scan_min, (x, y, yaw), (v, w) = self._node.snapshot()
        if scan is None:
            scan = np.full(360, LIDAR_MAX, dtype=np.float32)
            scan_min = LIDAR_MAX
        lidar_obs = self._bin_lidar(scan)

        progress = self._explored.sum() / float(GRID_N * GRID_N)
        room_scalar = (len(self._visited_rooms) - 1) / 3.0  # in [0, 1]

        obs = np.concatenate([
            lidar_obs,                                    # 32
            np.array([math.cos(yaw), math.sin(yaw)],      # 2
                     dtype=np.float32),
            np.array([np.clip(v / V_MAX, -1, 1),          # 2
                      np.clip(w / W_MAX, -1, 1)],
                     dtype=np.float32),
            np.array([progress, room_scalar],             # 2
                     dtype=np.float32),
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1),  # 2
                      min(1.0, self._steps_since_new_cell
                          / float(self.max_episode_steps))],
                     dtype=np.float32),
        ])
        return obs.astype(np.float32), scan_min, (x, y, yaw)

    def _mark_cell(self, x: float, y: float) -> bool:
        gx = int((x + WORLD_HALF) / GRID_CELL)
        gy = int((y + WORLD_HALF) / GRID_CELL)
        if 0 <= gx < GRID_N and 0 <= gy < GRID_N and not self._explored[gx, gy]:
            self._explored[gx, gy] = True
            return True
        return False

    def _gz_set_pose(self, x: float, y: float, yaw: float):
        """Teleport the drone via `gz service`. Best-effort, fire-and-forget-ish."""
        req = (
            f"name: '{self.drone_name}', "
            f"position: {{x: {x}, y: {y}, z: 0.6}}, "
            f"orientation: {{x: 0, y: 0, "
            f"z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}"
        )
        subprocess.run(
            [
                "gz", "service", "-s", f"/world/{self.world_name}/set_pose",
                "--reqtype", "gz.msgs.Pose",
                "--reptype", "gz.msgs.Boolean",
                "--timeout", "500",
                "--req", req,
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        )

    # ---------- gym API ----------

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)

        # Stop motion before teleporting
        self._node.send_cmd(0.0, 0.0)
        time.sleep(0.05)

        spawn = SPAWN_CANDIDATES[int(self._np_random.integers(len(SPAWN_CANDIDATES)))]
        self._gz_set_pose(*spawn)

        self._step_count = 0
        self._explored.fill(False)
        self._visited_rooms = set()
        self._steps_since_new_cell = 0

        # Wait for fresh sensor data after teleport.
        time.sleep(0.2)
        self._wait_for_first_msgs(timeout_s=5.0)

        obs, _, (x, y, _) = self._make_obs()
        self._mark_cell(x, y)
        self._visited_rooms.add(_room_id(x, y))
        return obs, {}

    def step(self, action: np.ndarray):
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        # Map action[0] in [-1,1] to [-0.3*V_MAX, V_MAX] (bias forward).
        v_cmd = float(np.clip(0.35 * (a[0] + 1.0) * V_MAX - 0.3 * V_MAX,
                              -0.3 * V_MAX, V_MAX))
        w_cmd = float(np.clip(a[1] * W_MAX, -W_MAX, W_MAX))
        self._node.send_cmd(v_cmd, w_cmd)

        time.sleep(STEP_DT)
        self._step_count += 1

        obs, scan_min, (x, y, _) = self._make_obs()

        new_cell = self._mark_cell(x, y)
        room = _room_id(x, y)
        new_room = room not in self._visited_rooms
        if new_room:
            self._visited_rooms.add(room)

        reward = -0.001
        if new_cell:
            reward += 1.0
            self._steps_since_new_cell = 0
        else:
            reward += -0.1
            self._steps_since_new_cell += 1

        if new_room:
            reward += 15.0

        if scan_min < NEAR_COLLISION_DIST:
            reward += -0.5

        terminated = False
        if scan_min < COLLISION_DIST:
            reward += -10.0
            terminated = True

        truncated = self._step_count >= self.max_episode_steps

        info = {
            "explored_cells": int(self._explored.sum()),
            "visited_rooms": len(self._visited_rooms),
            "min_lidar": float(scan_min),
            "v_cmd": v_cmd,
            "w_cmd": w_cmd,
        }
        return obs, float(reward), terminated, truncated, info

    def close(self):
        try:
            self._node.send_cmd(0.0, 0.0)
        except Exception:
            pass
        try:
            self._node.destroy_node()
        except Exception:
            pass
        # Don't shutdown rclpy here; another env might still need it.
