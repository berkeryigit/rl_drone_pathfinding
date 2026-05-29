"""Gymnasium environment for a 3-storey drone exploration task in Gazebo Harmonic.

World layout (built by ros2_ws/.../worlds/multi_room.sdf):
    * 16x16 m building, 3 floors of 2.5 m each (total height 7.5 m).
    * Each floor has a "+" of internal walls dividing it into 4 quadrant rooms,
      each with a 2 m door gap centered at the origin.
    * Floor 0 -> 1 hole: NE quadrant (x in [4, 6], y in [4, 6]).
    * Floor 1 -> 2 hole: SW quadrant (x in [-6, -4], y in [-6, -4]).
    * The drone has a horizontal 360 lidar plus 1-ray up/down lidars.

Observation (45-d, normalized to [-1, 1] / [0, 1]):
    [0:32]  : 32-bin horizontal lidar (sector min / max_range)
    [32:34] : (cos(yaw), sin(yaw))
    [34:37] : (vx_body / v_max, vz_body / vz_max, wz / w_max)
    [37:39] : explored_progress, room_scalar (rooms-1)/11
    [39:41] : min_horiz_lidar / max_range, idle_counter
    [41:43] : z / total_height, floor_id / 2
    [43:45] : scan_up / max_range, scan_down / max_range

Action (3-d, continuous):
    a[0] in [-1, 1] -> linear x velocity in [-0.3*v_max, v_max]   (forward bias)
    a[1] in [-1, 1] -> linear z velocity in [-vz_max, vz_max]
    a[2] in [-1, 1] -> angular z velocity in [-w_max, w_max]

Reward (per-step):
    +1.0 * (#new explored voxels this step)
    +15  on entering a new room (12 rooms total: 4 per floor)
    +25  on entering a new floor (3 floors)
    -10  on collision (terminates)
    -0.5 if any directional clearance < 0.5 m (near-collision, horiz/up/down)
    -0.1 if no new voxel explored this step (idle)
    -0.001 per step (time)

Episode ends:
    terminated: min(horiz lidar, scan_up, scan_down) < `collision_dist`
    truncated : `max_episode_steps` reached
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


# ---------- world geometry / kinematics ----------
DEFAULT_WORLD_NAME = "multi_room"
DEFAULT_DRONE_NAME = "rl_drone"

WORLD_HALF = 8.0          # x, y in [-WORLD_HALF, +WORLD_HALF]
FLOOR_HEIGHT = 2.5        # per floor
N_FLOORS = 3              # 0, 1, 2
TOTAL_HEIGHT = N_FLOORS * FLOOR_HEIGHT  # 7.5 m

GRID_CELL_XY = 0.5
GRID_NXY = int((2 * WORLD_HALF) / GRID_CELL_XY)   # 32
GRID_NZ = N_FLOORS                                # 3

LIDAR_BINS = 32
LIDAR_MAX = 10.0
V_MAX = 0.6                # m/s forward
VZ_MAX = 0.4               # m/s vertical
W_MAX = 1.5                # rad/s yaw
COLLISION_DIST = 0.25
NEAR_COLLISION_DIST = 0.5
STEP_DT = 0.02            # wall-clock sleep per env step. With sim RTF=0 and
                          # lidar @ 50 Hz, sim_time advances >> wall_time so
                          # one wall-step still gives plenty of new sensor data.

# Spawn pose candidates (all on floor 0, varied positions).
SPAWN_CANDIDATES = [
    ( 4.0, -4.0, 0.6,  1.57),
    (-4.0, -4.0, 0.6,  0.0 ),
    (-4.0,  4.0, 0.6, -1.57),
    ( 4.0,  4.0, 0.6,  3.14),
    ( 0.0, -6.0, 0.6,  0.0 ),
]


def _yaw_from_quat(qx: float, qy: float, qz: float, qw: float) -> float:
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def _floor_id(z: float) -> int:
    """Return 0..N_FLOORS-1 based on the drone's altitude."""
    fid = int(z // FLOOR_HEIGHT)
    return max(0, min(N_FLOORS - 1, fid))


def _room_id(x: float, y: float) -> int:
    """0..3 within a single floor (NE, NW, SW, SE)."""
    if x >= 0 and y >= 0: return 0
    if x <  0 and y >= 0: return 1
    if x <  0 and y <  0: return 2
    return 3


def _global_room_id(x: float, y: float, z: float) -> int:
    """0..11 across all floors (room within floor + 4 * floor_id)."""
    return _floor_id(z) * 4 + _room_id(x, y)


class _RosBridge(Node):
    """rclpy node that owns pubs/subs. Spun on a background thread."""

    def __init__(self):
        super().__init__("rl_drone_env_bridge")

        sensor_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )

        self._scan: Optional[np.ndarray] = None
        self._scan_min: float = LIDAR_MAX
        self._scan_up: float = LIDAR_MAX
        self._scan_down: float = LIDAR_MAX
        self._pose = (0.0, 0.0, 0.0, 0.0)        # x, y, z, yaw
        self._twist = (0.0, 0.0, 0.0)            # vx_body, vz_body, wz
        self._lock = threading.Lock()

        self.create_subscription(LaserScan, "scan",      self._on_scan,      sensor_qos)
        self.create_subscription(LaserScan, "scan_up",   self._on_scan_up,   sensor_qos)
        self.create_subscription(LaserScan, "scan_down", self._on_scan_down, sensor_qos)
        self.create_subscription(Odometry,  "odom",      self._on_odom,      10)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)

    @staticmethod
    def _safe_min(ranges) -> float:
        if not ranges:
            return LIDAR_MAX
        arr = np.asarray(ranges, dtype=np.float32)
        arr = np.where(np.isfinite(arr), arr, LIDAR_MAX)
        arr = np.clip(arr, 0.0, LIDAR_MAX)
        return float(arr.min()) if arr.size else LIDAR_MAX

    def _on_scan(self, msg: LaserScan):
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        ranges = np.where(np.isfinite(ranges), ranges, LIDAR_MAX)
        ranges = np.clip(ranges, 0.0, LIDAR_MAX)
        with self._lock:
            self._scan = ranges
            self._scan_min = float(ranges.min()) if ranges.size else LIDAR_MAX

    def _on_scan_up(self, msg: LaserScan):
        v = self._safe_min(msg.ranges)
        with self._lock:
            self._scan_up = v

    def _on_scan_down(self, msg: LaserScan):
        v = self._safe_min(msg.ranges)
        with self._lock:
            self._scan_down = v

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = _yaw_from_quat(q.x, q.y, q.z, q.w)
        vx = msg.twist.twist.linear.x
        vz = msg.twist.twist.linear.z
        wz = msg.twist.twist.angular.z
        with self._lock:
            self._pose = (p.x, p.y, p.z, yaw)
            self._twist = (vx, vz, wz)

    def snapshot(self):
        with self._lock:
            scan = None if self._scan is None else self._scan.copy()
            return (scan, self._scan_min, self._scan_up, self._scan_down,
                    self._pose, self._twist)

    def send_cmd(self, vx: float, vz: float, wz: float):
        msg = Twist()
        msg.linear.x = float(vx)
        msg.linear.z = float(vz)
        msg.angular.z = float(wz)
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
            low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([ 1.0,  1.0,  1.0], dtype=np.float32),
            dtype=np.float32,
        )
        # 32 + 2 + 3 + 2 + 2 + 2 + 2 = 45
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(45,), dtype=np.float32
        )

        if not rclpy.ok():
            rclpy.init(args=None)
        self._node = _RosBridge()
        self._executor_thread = threading.Thread(target=self._spin_node, daemon=True)
        self._executor_thread.start()

        self._step_count = 0
        self._explored = np.zeros((GRID_NXY, GRID_NXY, GRID_NZ), dtype=bool)
        self._visited_global_rooms: set[int] = set()
        self._visited_floors: set[int] = set()
        self._steps_since_new_voxel = 0

        self._np_random, _ = gym.utils.seeding.np_random(seed)

    # ----- internal helpers -----

    def _spin_node(self):
        try:
            rclpy.spin(self._node)
        except Exception:
            pass

    def _wait_for_first_msgs(self, timeout_s: float = 20.0):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            scan, _, _, _, _, _ = self._node.snapshot()
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
        (scan, scan_min, scan_up, scan_down,
         (x, y, z, yaw), (vx, vz, wz)) = self._node.snapshot()
        if scan is None:
            scan = np.full(360, LIDAR_MAX, dtype=np.float32)
            scan_min = LIDAR_MAX
        lidar_obs = self._bin_lidar(scan)

        progress = self._explored.sum() / float(GRID_NXY * GRID_NXY * GRID_NZ)
        rooms_scalar = (max(1, len(self._visited_global_rooms)) - 1) / 11.0

        obs = np.concatenate([
            lidar_obs,                                                       # 32
            np.array([math.cos(yaw), math.sin(yaw)], dtype=np.float32),       # 2
            np.array([np.clip(vx / V_MAX,  -1, 1),                            # 3
                      np.clip(vz / VZ_MAX, -1, 1),
                      np.clip(wz / W_MAX,  -1, 1)], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),             # 2
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1),                    # 2
                      min(1.0, self._steps_since_new_voxel
                          / float(self.max_episode_steps))], dtype=np.float32),
            np.array([np.clip(z / TOTAL_HEIGHT, 0, 1),                        # 2
                      _floor_id(z) / float(max(1, N_FLOORS - 1))], dtype=np.float32),
            np.array([np.clip(scan_up   / LIDAR_MAX, 0, 1),                   # 2
                      np.clip(scan_down / LIDAR_MAX, 0, 1)], dtype=np.float32),
        ])
        return obs.astype(np.float32), scan_min, scan_up, scan_down, (x, y, z, yaw)

    def _mark_voxel(self, x: float, y: float, z: float) -> bool:
        gx = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((y + WORLD_HALF) / GRID_CELL_XY)
        gz = _floor_id(z)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY and 0 <= gz < GRID_NZ \
                and not self._explored[gx, gy, gz]:
            self._explored[gx, gy, gz] = True
            return True
        return False

    def _gz_set_pose(self, x: float, y: float, z: float, yaw: float):
        req = (
            f"name: '{self.drone_name}', "
            f"position: {{x: {x}, y: {y}, z: {z}}}, "
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

    # ----- gym API -----

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)

        self._node.send_cmd(0.0, 0.0, 0.0)
        time.sleep(0.05)

        spawn = SPAWN_CANDIDATES[int(self._np_random.integers(len(SPAWN_CANDIDATES)))]
        self._gz_set_pose(*spawn)

        self._step_count = 0
        self._explored.fill(False)
        self._visited_global_rooms = set()
        self._visited_floors = set()
        self._steps_since_new_voxel = 0

        time.sleep(0.2)
        self._wait_for_first_msgs(timeout_s=5.0)

        obs, _, _, _, (x, y, z, _) = self._make_obs()
        self._mark_voxel(x, y, z)
        self._visited_global_rooms.add(_global_room_id(x, y, z))
        self._visited_floors.add(_floor_id(z))
        return obs, {}

    def step(self, action: np.ndarray):
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        # forward bias: a[0] in [-1,1] -> [-0.3*V_MAX, V_MAX]
        vx = float(np.clip(0.35 * (a[0] + 1.0) * V_MAX - 0.3 * V_MAX,
                           -0.3 * V_MAX, V_MAX))
        vz = float(np.clip(a[1] * VZ_MAX, -VZ_MAX, VZ_MAX))
        wz = float(np.clip(a[2] * W_MAX,  -W_MAX,  W_MAX))
        self._node.send_cmd(vx, vz, wz)

        time.sleep(STEP_DT)
        self._step_count += 1

        obs, scan_min, scan_up, scan_down, (x, y, z, _) = self._make_obs()

        new_voxel = self._mark_voxel(x, y, z)
        groom = _global_room_id(x, y, z)
        new_room = groom not in self._visited_global_rooms
        if new_room:
            self._visited_global_rooms.add(groom)
        fid = _floor_id(z)
        new_floor = fid not in self._visited_floors
        if new_floor:
            self._visited_floors.add(fid)

        reward = -0.001
        if new_voxel:
            reward += 1.0
            self._steps_since_new_voxel = 0
        else:
            reward += -0.1
            self._steps_since_new_voxel += 1

        if new_room:
            reward += 15.0
        if new_floor:
            reward += 25.0

        clearance = min(scan_min, scan_up, scan_down)
        if clearance < NEAR_COLLISION_DIST:
            reward += -0.5

        terminated = False
        if clearance < COLLISION_DIST:
            reward += -10.0
            terminated = True

        truncated = self._step_count >= self.max_episode_steps

        info = {
            "explored_voxels": int(self._explored.sum()),
            "visited_rooms": len(self._visited_global_rooms),
            "visited_floors": len(self._visited_floors),
            "min_lidar": float(scan_min),
            "scan_up": float(scan_up),
            "scan_down": float(scan_down),
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
            self._node.destroy_node()
        except Exception:
            pass
