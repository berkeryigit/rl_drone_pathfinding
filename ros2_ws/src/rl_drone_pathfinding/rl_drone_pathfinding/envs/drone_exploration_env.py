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

Gozlem (43-d):
    [0:32]  : 32-bin yatay lidar
    [32:34] : (cos(yaw), sin(yaw))
    [34:37] : (vx/v_max, vz/vz_max, wz/w_max)
    [37:39] : kesif_orani (scaled x2), oda_scalari
    [39:41] : min_lidar/max_range, idle_counter
    [41:42] : nearest_door_dist (normalized)
    [42:43] : wall_proximity (0=far, 1=near wall)

Aksiyon (3-d, surekli):
    a[0] -> vx, a[1] -> vy, a[2] -> wz

Odul (Improvement Shaping):
    +3.0 yeni voxel
    +15  yeni oda kesfedildi
    +30  kapidan gecis (odalar arasi)
    +door_reward: kapiya yaklasma (duvara yakın olduğunda 2x)
    +wall_follow_bonus: duvara yaklaş (0-0.3 range)
    -stay_penalty: aynı odada kalma (200+ step, explore oranına göre azalır)
    -20  carpisme (episode biter)
    -0.05 ayni voxelde kalma
    -0.001 her step zaman
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

LIDAR_BINS = 32
LIDAR_MAX  = 10.0
V_MAX      = 1.2
VZ_MAX     = 0.4
W_MAX      = 1.5
DRONE_FOOTPRINT_RADIUS = 0.22
DRONE_VERTICAL_RADIUS  = 0.08
COLLISION_DIST      = 0.02
NEAR_COLLISION_DIST = 0.5
OBS_UPDATE_PERIOD = 3.0

# Kapi merkez pozisyonlari — door proximity reward icin
# Sol duvar (x=-2): kapi y in [-4.5,-1.5] → merkez y=-3
# Sag duvar (x= 4): kapi y in [ 2.5, 5.5] → merkez y= 4
# Yatay duvar kapilar: merkez (-6,0), (1,0), (6,0)
DOOR_POSITIONS = [
    (-2.0, -3.0),
    ( 4.0,  4.0),
    (-6.0,  0.0),
    ( 1.0,  0.0),
    ( 6.0,  0.0),
]
ROOM_STAY_THRESHOLD   = 100
ROOM_STAY_PENALTY     = 0.10
RECENT_VISIT_MEMORY   = 60    # son kac adim hatirlanir
REVISIT_PENALTY       = 0.10  # o hucreye tekrar gelirse ceza
STEP_DT = 0.02   # 0.01 cok kisa, fizik kararsizlasiyordu

# ---------- Oda sinirlari (asimetrik) ----------
ROOM_X1 = -2.0   # sol dikey duvar
ROOM_X2 =  4.0   # sag dikey duvar
ROOM_Y0 =  0.0   # yatay duvar
N_ROOMS =  6

# ---------- Spawn noktalari (her odadan biri) ----------
SPAWN_CANDIDATES = [
    (-5.0, -5.5, 1.2,  0.0 ),   # R0  (obs_moving_1'den uzak)
    ( 1.0, -5.5, 1.2,  1.57),   # R1
    ( 6.5, -6.0, 1.2,  3.14),   # R2  (obs_moving_3'ten uzak)
    (-5.0,  6.0, 1.2,  0.0 ),   # R3
    ( 2.5,  5.5, 1.2, -1.57),   # R4  (obs_moving_2'den uzak)
    ( 6.5,  6.0, 1.2,  3.14),   # R5
]

MAX_COLLISIONS_PER_EPISODE = 8

# ---------- Hareketli engeller ----------
MOVING_OBS = [
    {"name": "obs_moving_1", "x0": -5.0, "y0": -3.0, "z": 1.25, "axis": "y", "amp": 0.8, "T": 7.0},
    {"name": "obs_moving_2", "x0":  1.0, "y0":  4.0, "z": 1.25, "axis": "x", "amp": 1.0, "T": 9.0},
    {"name": "obs_moving_3", "x0":  6.0, "y0": -4.0, "z": 1.25, "axis": "y", "amp": 1.0, "T": 5.0},
]

# Aksiyon yumusatma: hafif EMA — titreme azaltir ama hareketi bastirmaz
ACTION_SMOOTH = 0.15


def _floor_id(z: float) -> int:
    return 0


def _room_id(x: float, y: float) -> int:
    col = 0 if x < ROOM_X1 else (1 if x < ROOM_X2 else 2)
    row = 0 if y < ROOM_Y0 else 1
    return row * 3 + col


def _global_room_id(x: float, y: float, z: float) -> int:
    return _room_id(x, y)


def _nearest_door_dist(x: float, y: float) -> float:
    return min(math.hypot(x - dx, y - dy) for dx, dy in DOOR_POSITIONS)


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
                           msg.twist.twist.linear.y,   # 2D env ile uyum: planar yanal hiz (dikey vz degil)
                           msg.twist.twist.angular.z)

    def snapshot(self):
        with self._lock:
            scan = None if self._scan is None else self._scan.copy()
            return scan, self._scan_min, self._scan_up, self._scan_down, self._pose, self._twist

    def send_cmd(self, vx, vy, wz):
        msg = Twist()
        msg.linear.x  = float(vx)
        msg.linear.y  = float(vy)
        msg.angular.z = float(wz)
        self.cmd_pub.publish(msg)


class DroneExplorationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, world_name=DEFAULT_WORLD_NAME, drone_name=DEFAULT_DRONE_NAME,
                 max_episode_steps=1000, seed=None, eval_mode=False,
                 manage_obstacles=True):
        super().__init__()
        self.world_name = world_name
        self.drone_name = drone_name
        self.eval_mode  = eval_mode
        self.max_episode_steps = max_episode_steps
        self.manage_obstacles = manage_obstacles

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([ 1.0,  1.0,  1.0], dtype=np.float32),
            dtype=np.float32,
        )
        # 32 lidar + 2 yaw + 3 vel + 2 explore + 2 lidar_stats + 1 door_dist + 1 wall_proximity = 43
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(43,), dtype=np.float32
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
        self._room_explored_voxels: dict[int, int] = {}
        self._steps_since_new_voxel = 0
        self._prev_door_dist = 0.0
        self._prev_room = -1
        self._room_steps   = 0    # mevcut odada kac step gecti
        self._current_room = -1   # hangi odada
        self._prev_action      = np.zeros(3, dtype=np.float32)
        self._collision_count  = 0
        self._grace_steps      = 0
        self._pos_history: list[tuple[int,int]] = []
        self._np_random, _ = gym.utils.seeding.np_random(seed)

        # Hareketli engel: tek kalici thread, episode baslarindan bagimsiz
        self._sim_time     = 0.0
        self._obs_stop     = threading.Event()
        self._obs_worker   = None
        if self.manage_obstacles:
            self._obs_worker = threading.Thread(target=self._obstacle_loop, daemon=True)
            self._obs_worker.start()

    # ----- Gozlem -----

    def _bin_lidar(self, ranges: np.ndarray) -> np.ndarray:
        n = ranges.shape[0]
        if n == 0:
            return np.ones(LIDAR_BINS, dtype=np.float32)
        # Ham /scan -pi'den baslar (index 0 = ARKA). 2D env ile uyum icin ileri yonu
        # (index n//2) bin 0'a getir → bin 0 = ON, CCW. Aksi halde 2D'de egitilen model
        # Gazebo'da lidar'i yarim tur donuk gorur ve onundeki duvari fark edemez.
        ranges = np.roll(ranges, -(n // 2))
        bs = max(1, n // LIDAR_BINS)
        out = np.array([ranges[i*bs:(i+1)*bs].min() if ranges[i*bs:(i+1)*bs].size else LIDAR_MAX
                        for i in range(LIDAR_BINS)], dtype=np.float32)
        return np.clip(out / LIDAR_MAX, 0.0, 1.0)

    def _make_obs(self):
        scan, scan_min, scan_up, scan_down, (x, y, z, yaw), (vx, vy, wz) = self._node.snapshot()
        if scan is None:
            scan = np.full(360, LIDAR_MAX, dtype=np.float32)
            scan_min = LIDAR_MAX

        progress     = np.clip(self._explored.sum() / float(GRID_NXY * GRID_NXY * GRID_NZ) * 2.0, 0.0, 1.0)
        rooms_scalar = (max(1, len(self._visited_rooms)) - 1) / float(N_ROOMS - 1)
        idle_norm    = min(1.0, self._steps_since_new_voxel / float(self.max_episode_steps))

        door_dist = _nearest_door_dist(x, y)
        door_dist_norm = np.clip(door_dist / LIDAR_MAX, 0.0, 1.0)
        wall_proximity = np.clip((NEAR_COLLISION_DIST - scan_min) / NEAR_COLLISION_DIST, 0.0, 1.0)

        obs = np.concatenate([
            self._bin_lidar(scan),                                             # 32
            np.array([math.cos(yaw), math.sin(yaw)], dtype=np.float32),        # 2
            np.array([np.clip(vx / V_MAX, -1, 1),                              # 3 (planar vx,vy,wz)
                      np.clip(vy / V_MAX, -1, 1),
                      np.clip(wz / W_MAX, -1, 1)], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),              # 2
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1),                     # 2
                      idle_norm], dtype=np.float32),
            np.array([door_dist_norm, wall_proximity], dtype=np.float32),      # 2
        ])
        return obs.astype(np.float32), scan_min, scan_up, scan_down, (x, y, z, yaw), door_dist

    @staticmethod
    def _circle_overlaps_cell(x: float, y: float, radius: float, gx: int, gy: int) -> bool:
        cell_x0 = gx * GRID_CELL_XY - WORLD_HALF
        cell_y0 = gy * GRID_CELL_XY - WORLD_HALF
        cell_x1 = cell_x0 + GRID_CELL_XY
        cell_y1 = cell_y0 + GRID_CELL_XY
        closest_x = min(max(x, cell_x0), cell_x1)
        closest_y = min(max(y, cell_y0), cell_y1)
        return (x - closest_x) ** 2 + (y - closest_y) ** 2 <= radius ** 2

    def _covered_grid_cells(self, x: float, y: float):
        gx0 = math.floor((x - DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gx1 = math.floor((x + DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gy0 = math.floor((y - DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gy1 = math.floor((y + DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        for gx in range(max(0, gx0), min(GRID_NXY - 1, gx1) + 1):
            for gy in range(max(0, gy0), min(GRID_NXY - 1, gy1) + 1):
                if self._circle_overlaps_cell(x, y, DRONE_FOOTPRINT_RADIUS, gx, gy):
                    yield gx, gy

    def _mark_voxel(self, x, y, z) -> int:
        new_count = 0
        for gx, gy in self._covered_grid_cells(x, y):
            if not self._explored[gx, gy, 0]:
                self._explored[gx, gy, 0] = True
                new_count += 1
        return new_count

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

    def _move_one_obstacle(self, obs: dict, t: float):
        """Tek engeli gz service ile gunceller (thread'den cagirilir)."""
        phase = 2.0 * math.pi * t / obs["T"]
        x = obs["x0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "x" else 0.0)
        y = obs["y0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "y" else 0.0)
        req = (f"name: '{obs['name']}', "
               f"position: {{x: {x:.4f}, y: {y:.4f}, z: {obs['z']:.4f}}}, "
               f"orientation: {{x: 0, y: 0, z: 0, w: 1}}")
        subprocess.run(
            ["gz", "service", "-s", f"/world/{self.world_name}/set_pose",
             "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
             "--timeout", "150", "--req", req],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )

    def _obstacle_loop(self):
        """Her OBS_UPDATE_PERIOD saniyede engelleri paralel thread ile gunceller."""
        t0 = time.time()
        while not self._obs_stop.is_set():
            if self._obs_stop.is_set():
                return
            t = time.time() - t0
            threads = [
                threading.Thread(target=self._move_one_obstacle, args=(obs, t), daemon=True)
                for obs in MOVING_OBS
            ]
            for th in threads:
                th.start()
            for th in threads:
                th.join(timeout=0.12)
            self._obs_stop.wait(timeout=OBS_UPDATE_PERIOD)

    # ----- Gym API -----

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)
        # Onceki episode'un momentumunu temizle
        for _ in range(3):
            self._node.send_cmd(0.0, 0.0, 0.0)
            time.sleep(0.05)
        # options={"spawn_index": i} verilirse o spawn'dan basla (sabit/tekrarlanabilir eval);
        # aksi halde rastgele spawn (egitim).
        spawn_index = None
        if options is not None:
            spawn_index = options.get("spawn_index")
        if spawn_index is None:
            spawn_index = int(self._np_random.integers(len(SPAWN_CANDIDATES)))
        sp = SPAWN_CANDIDATES[int(spawn_index) % len(SPAWN_CANDIDATES)]
        self._gz_set_pose(self.drone_name, sp[0], sp[1], sp[2], sp[3])
        self._step_count = 0
        self._explored.fill(False)
        self._visited_rooms = set()
        self._room_explored_voxels = {}
        self._steps_since_new_voxel = 0
        self._prev_door_dist = 0.0
        self._prev_room = -1
        self._room_steps   = 0
        self._current_room = -1
        self._prev_action[:] = 0.0
        self._collision_count = 0
        self._grace_steps     = 20
        self._pos_history     = []
        time.sleep(0.2)
        for _ in range(100):
            if self._node.snapshot()[0] is not None:
                break
            time.sleep(0.05)
        obs, _, _, _, (x, y, z, _), _ = self._make_obs()
        self._mark_voxel(x, y, z)
        self._visited_rooms.add(_global_room_id(x, y, z))
        self._prev_door_dist = _nearest_door_dist(x, y)
        return obs, {}

    def step(self, action: np.ndarray):
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        # EMA ile aksiyon yumusatma — titreme onler, ani yon degisimlerini azaltir
        a = ACTION_SMOOTH * self._prev_action + (1.0 - ACTION_SMOOTH) * a
        self._prev_action = a.copy()
        vx = float(np.clip(a[0] * V_MAX, -V_MAX, V_MAX))
        vy = float(np.clip(a[1] * V_MAX, -V_MAX, V_MAX))
        wz = float(np.clip(a[2] * W_MAX,  -W_MAX,  W_MAX))
        self._node.send_cmd(vx, vy, wz)
        time.sleep(STEP_DT)
        self._step_count += 1

        obs, scan_min, scan_up, scan_down, (x, y, z, _), door_dist = self._make_obs()

        new_voxels = self._mark_voxel(x, y, z)
        new_voxel = new_voxels > 0
        groom     = _global_room_id(x, y, z)
        new_room  = groom not in self._visited_rooms
        if new_room:
            self._visited_rooms.add(groom)
            self._room_explored_voxels[groom] = 0

        # Oda-içi voxel tracking
        if groom not in self._room_explored_voxels:
            self._room_explored_voxels[groom] = 0
        if new_voxel:
            self._room_explored_voxels[groom] += new_voxels

        # Oda kalma sayaci
        if groom == self._current_room:
            self._room_steps += 1
        else:
            self._room_steps   = 0
            self._current_room = groom

        # ----- Odul (sadeleştirildi) -----
        reward = -0.01  # kucuk zaman cezasi

        # Keşif: yeni voxel
        if new_voxel:
            reward += 3.0
            self._steps_since_new_voxel = 0
        else:
            self._steps_since_new_voxel += 1

        # Keşif: yeni oda
        if new_room:
            reward += 20.0

        # Oda degisimi (loglama icin)
        room_changed = (groom != self._prev_room and self._prev_room != -1)
        self._prev_room = groom

        # Tekrar ziyaret cezasi — daire cizmeyi engeller
        gx_cur = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy_cur = int((y + WORLD_HALF) / GRID_CELL_XY)
        cell = (gx_cur, gy_cur)
        if cell in self._pos_history:
            reward -= REVISIT_PENALTY
        self._pos_history.append(cell)
        if len(self._pos_history) > RECENT_VISIT_MEMORY:
            self._pos_history.pop(0)

        # Uzun sure yeni voxel bulamazsa ceza — hareketsizligi engeller
        if self._steps_since_new_voxel > 50:
            reward -= 0.10

        room_explore_ratio = 0.0  # info icin

        # Duvara yakin olma cezasi
        if scan_min < 0.7:
            wall_penalty = ((0.7 - scan_min) / 0.7) * 0.3
            reward -= wall_penalty

        # Carpışma kontrolü
        xy_clearance = max(0.0, scan_min - DRONE_FOOTPRINT_RADIUS)
        up_clearance = max(0.0, scan_up - DRONE_VERTICAL_RADIUS)
        down_clearance = max(0.0, scan_down - DRONE_VERTICAL_RADIUS)
        clearance = min(xy_clearance, up_clearance, down_clearance)
        terminated = False
        if self._grace_steps > 0:
            self._grace_steps -= 1
        elif clearance < COLLISION_DIST:
            self._collision_count += 1
            reward -= 10.0
            if self._collision_count >= MAX_COLLISIONS_PER_EPISODE:
                terminated = True

        # Eval modunda: tum odalar kesfedilince episode biter
        if self.eval_mode and len(self._visited_rooms) >= N_ROOMS:
            terminated = True

        truncated = self._step_count >= self.max_episode_steps

        info = {
            "explored_voxels": int(self._explored.sum()),
            "visited_rooms":   len(self._visited_rooms),
            "visited_floors":  1,
            "min_lidar":       float(scan_min),
            "scan_up":         float(scan_up),
            "scan_down":       float(scan_down),
            "x": float(x), "y": float(y), "z": float(z),
            "vx_cmd": vx, "vy_cmd": vy, "wz_cmd": wz,
            "room_id": int(groom),
            "door_dist": float(door_dist),
            "room_explore_ratio": float(room_explore_ratio),
            "new_room": bool(new_room),
            "new_voxel": bool(new_voxel),
            "new_voxels": int(new_voxels),
            "body_clearance": float(clearance),
            "room_changed": bool(room_changed),
            "collision_count": int(self._collision_count),
        }
        return obs, float(reward), terminated, truncated, info

    def close(self):
        self._obs_stop.set()
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
