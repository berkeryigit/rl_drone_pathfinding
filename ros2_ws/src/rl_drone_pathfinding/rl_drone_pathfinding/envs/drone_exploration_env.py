"""Gymnasium env — tek katli 6-odali sabit bina, 2D planar lidar, hareketli engeller.

================================================================================
v2 TEMIZ TASARIM (2026-05-31, sifirdan yeniden yazildi)
================================================================================
Berker'in kurallari:
  * Harita SABIT  : tek katli 6 oda (multi_room.sdf degismez).
  * Drone HEP AYNI yerden baslar : R0 (sol-alt kose), (-5, -5, 0.6), yaw=0.
  * Engeller HAREKETLI : 3 salinan engel (train_ppo daemon thread'i tasir).
  * Hedef : carpismadan MAKSIMUM voxel (zemin hucresi) gezmek.
  * BASIT tutulur : tek sim, tek env (n_envs=1). Coklu env/gazebo YOK.

Aksiyon uzayi 2D (odev tanimina birebir: lineer hiz v + acisal hiz w):
    a[0] -> v  (ileri hiz)   in [-1, 1]
    a[1] -> w  (donus hizi)  in [-1, 1]
    Irtifa SABIT (vz=0). Model gravity=false oldugu icin z=0.6'da asili kalir.

Gozlem (40-d, hepsi normalize [-1,1] / [0,1]):
    [0:32]  : 32-bin yatay lidar (min-pool, /LIDAR_MAX)            -> [0,1]
    [32:34] : (cos(yaw), sin(yaw))                                 -> [-1,1]
    [34:36] : (v/V_MAX, w/W_MAX)                                   -> [-1,1]
    [36:38] : (kesif_orani, ziyaret_edilen_oda_orani)              -> [0,1]
    [38:40] : (min_lidar/LIDAR_MAX, idle_orani)                    -> [0,1]

Odul (v2.1 — YON-DUYARLI ceza; v2.0 eval'inde %70 carpisma -> kapi/engel-bilincli):
    bir adimda toplam r =
        -0.01                          her adim zaman cezasi
        +1.0   * yeni_voxel            yeni zemin hucresi kesfi (ANA sinyal)
        +10.0  * yeni_oda              yeni odaya gecis (kilometre tasi)
        -0.05  (idle)                  IDLE_GRACE adimdir yeni voxel yoksa
        -0.6 * (1 - fwd/1.5)           ILERI-ARK engel yakin (gidilen yon) -> kapi-bilincli
        -0.3 * (1 - d/0.5)             her yon cok yakin (siyirma; kapi 0.85m -> guvende)
        +0.10 * acik_on * ileri        ileri-acik bonus (acikliklardan gec)
        -10.0  (terminal)              CARPISMA (d < COLLISION_DIST) -> episode biter

    v2.0 -> v2.1 farki: duvar cezasi YONSUZ (scan_min) idi -> 2m kapilarda yan
    duvarlar ~0.85m'de oldugu icin dogru kapi gecisini cezalandiriyordu. v2.1'de
    ceza GIDILEN yondeki (ileri-ark) engele bagli; ayrica episode 1000->1500.
    Episodik getiri ~= kesfedilen voxel sayisi. "return'u maksimize et" = "voxel'i maksimize et".

NOT: Engelleri bu env TASIMAZ. SubprocVecEnv/worker icinden gz service
cagrisi IPC pipe'ini bozabiliyordu; bu yuzden hareket train_ppo'daki
ana-proses daemon thread'inde yapilir.
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

# ---------- Dunya geometrisi (multi_room.sdf ile birebir) ----------
DEFAULT_WORLD_NAME = "multi_room"
DEFAULT_DRONE_NAME = "rl_drone"

WORLD_HALF   = 8.0          # dunya [-8, 8] x [-8, 8]
GRID_CELL_XY = 0.5
GRID_NXY     = int((2 * WORLD_HALF) / GRID_CELL_XY)  # 32 -> 1024 hucre

# ---------- Lidar / hareket sabitleri ----------
LIDAR_BINS   = 32
LIDAR_MAX    = 10.0
# Lidar min_angle=-pi, CCW tarar. Ray 180 -> aci 0 -> govde +X. Bin 16 = on.
FORWARD_BIN  = 16
V_MAX        = 0.6          # m/s ileri hiz tavani
W_MAX        = 1.5          # rad/s donus hizi tavani
HOVER_Z      = 0.6          # sabit irtifa
V_REVERSE    = -0.25        # izin verilen kucuk geri hiz (duvardan kurtulma)

COLLISION_DIST    = 0.30    # bu mesafenin altinda carpisma kabul (episode biter)
# --- v2.1: YON-DUYARLI (kapi-bilincli) lidar cezasi ---
# Kapilar 2m genis, drone 0.3m -> kapi ortasinda yan duvarlar ~0.85m'de.
# Eski yonsuz ceza (scan_min<1.0) dogru kapi gecisini cezalandiriyordu.
# v2.1: cezayi GIDILEN yondeki (ileri-ark) engele bagla; yanlar yakin ama
# on acik (=kapidan geciyor) ise cezalandirma.
FWD_ARC_HALF      = 2       # ileri-ark = FORWARD_BIN +/- 2 bin (~+/-22 derece)
FWD_PENALTY_DIST  = 1.5     # ileri yonde bu mesafeden yakin engel/duvar -> progresif ceza
SCRAPE_DIST       = 0.5     # her yonde siyirma cezasi (kapi 0.85m'nin altinda -> kapilar guvende)
FWD_OPEN_BONUS    = 0.10    # ileri acikken ileri gitme bonusu (acikliklardan gecmeyi tesvik)
# --- v2.2: HER-YON (omnidirectional) caution GERI getirildi ---
# v2.1 eval'i: directional-only ceza carpismayi DUSURMEDI (%70 -> %79). Demek ki
# v2.0'in her-yon cezasi koruyucuymus (yanlardan/capraz hareketli engelden kaciniyordu).
# v2.2 = v2.0'in her-yon cezasi + v2.1'in ileri-ark cezasi BIRLESIK.
OMNI_PENALTY_DIST = 1.0     # her yonde bu mesafeden yakin -> progresif caution (v2.0 tarzi)
STEP_DT           = 0.02    # her adim wall-clock bekleme
IDLE_GRACE        = 40      # bu kadar adim yeni voxel yoksa idle cezasi

# ---------- Oda sinirlari (asimetrik 3x2) ----------
ROOM_X1 = -2.0
ROOM_X2 =  4.0
ROOM_Y0 =  0.0
N_ROOMS =  6

# ---------- SABIT spawn: R0 (sol-alt kose) ----------
SPAWN_X, SPAWN_Y, SPAWN_Z, SPAWN_YAW = -5.0, -5.0, HOVER_Z, 0.0

# ---------- Hareketli engeller (train_ppo tarafindan tasinir) ----------
MOVING_OBS = [
    {"name": "obs_moving_1", "x0": -5.0, "y0": -3.0, "z": 0.5, "axis": "y", "amp": 2.0, "T": 7.0},
    {"name": "obs_moving_2", "x0":  1.0, "y0":  4.0, "z": 0.3, "axis": "x", "amp": 2.5, "T": 9.0},
    {"name": "obs_moving_3", "x0":  6.0, "y0": -4.0, "z": 0.5, "axis": "y", "amp": 2.5, "T": 5.0},
]


def _room_id(x: float, y: float) -> int:
    col = 0 if x < ROOM_X1 else (1 if x < ROOM_X2 else 2)
    row = 0 if y < ROOM_Y0 else 1
    return row * 3 + col


def _yaw_from_quat(qx, qy, qz, qw):
    return math.atan2(2.0 * (qw * qz + qx * qy),
                      1.0 - 2.0 * (qy * qy + qz * qz))


class _RosBridge(Node):
    """Sadece ihtiyac duyulan 3 topic: scan (yatay lidar), odom, cmd_vel."""

    def __init__(self):
        super().__init__("rl_drone_env_bridge")
        qos = QoSProfile(depth=10,
                         reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST)
        self._scan: Optional[np.ndarray] = None
        self._scan_min: float = LIDAR_MAX
        self._pose  = (SPAWN_X, SPAWN_Y, SPAWN_Z, SPAWN_YAW)
        self._twist = (0.0, 0.0)          # (v_lin_x, w_ang_z)
        self._lock  = threading.Lock()

        self.create_subscription(LaserScan, "scan", self._on_scan, qos)
        self.create_subscription(Odometry,  "odom", self._on_odom, 10)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)

    def _on_scan(self, msg: LaserScan):
        r = np.asarray(msg.ranges, dtype=np.float32)
        r = np.clip(np.where(np.isfinite(r), r, LIDAR_MAX), 0.0, LIDAR_MAX)
        with self._lock:
            self._scan = r
            self._scan_min = float(r.min()) if r.size else LIDAR_MAX

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        with self._lock:
            self._pose  = (p.x, p.y, p.z, _yaw_from_quat(q.x, q.y, q.z, q.w))
            self._twist = (msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def snapshot(self):
        with self._lock:
            scan = None if self._scan is None else self._scan.copy()
            return scan, self._scan_min, self._pose, self._twist

    def send_cmd(self, v, w):
        msg = Twist()
        msg.linear.x  = float(v)
        msg.linear.z  = 0.0            # irtifa sabit
        msg.angular.z = float(w)
        self.cmd_pub.publish(msg)


class DroneExplorationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, world_name=DEFAULT_WORLD_NAME, drone_name=DEFAULT_DRONE_NAME,
                 max_episode_steps=1000, seed=None, env_id=0):
        super().__init__()
        self.world_name = world_name
        self.drone_name = drone_name
        self.max_episode_steps = max_episode_steps

        # Tek env olsa da izolasyonu koru (gz partition / ros domain).
        os.environ['ROS_DOMAIN_ID'] = str(env_id)
        os.environ['GZ_PARTITION']  = f'sim{env_id}'

        # Aksiyon: [v, w] in [-1, 1]^2
        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        # Gozlem: 32 lidar + 2 yaw + 2 vel + 2 explore + 2 stats = 40
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(40,), dtype=np.float32
        )

        if not rclpy.ok():
            rclpy.init(args=None)
        self._node = _RosBridge()
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._executor_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._executor_thread.start()

        self._step_count = 0
        self._explored = np.zeros((GRID_NXY, GRID_NXY), dtype=bool)
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
        scan, scan_min, (x, y, z, yaw), (v, w) = self._node.snapshot()
        if scan is None:
            scan = np.full(360, LIDAR_MAX, dtype=np.float32)
            scan_min = LIDAR_MAX

        lidar_obs    = self._bin_lidar(scan)
        progress     = self._explored.sum() / float(GRID_NXY * GRID_NXY)
        rooms_scalar = (max(1, len(self._visited_rooms)) - 1) / float(max(1, N_ROOMS - 1))
        idle_norm    = min(1.0, self._steps_since_new_voxel / float(self.max_episode_steps))

        obs = np.concatenate([
            lidar_obs,                                                      # 32
            np.array([math.cos(yaw), math.sin(yaw)], dtype=np.float32),     # 2
            np.array([np.clip(v / V_MAX, -1, 1),                           # 2
                      np.clip(w / W_MAX, -1, 1)], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),          # 2
            np.array([np.clip(scan_min / LIDAR_MAX, 0, 1),                 # 2
                      idle_norm], dtype=np.float32),
        ])
        return obs.astype(np.float32), scan_min, (x, y, z, yaw), lidar_obs

    def _mark_voxel(self, x, y) -> bool:
        gx = int((x + WORLD_HALF) / GRID_CELL_XY)
        gy = int((y + WORLD_HALF) / GRID_CELL_XY)
        if 0 <= gx < GRID_NXY and 0 <= gy < GRID_NXY and not self._explored[gx, gy]:
            self._explored[gx, gy] = True
            return True
        return False

    # ----- gz set_pose (sadece drone teleport / reset) -----

    def _gz_set_pose(self, name: str, x: float, y: float, z: float, yaw: float = 0.0):
        req = (f"name: '{name}', position: {{x: {x}, y: {y}, z: {z}}}, "
               f"orientation: {{x: 0, y: 0, "
               f"z: {math.sin(yaw/2):.6f}, w: {math.cos(yaw/2):.6f}}}")
        # KRITIK: subprocess.run'a Python-seviyesi timeout SART. gz transport
        # "Host unreachable" verirse gz service CLI sonsuza kadar asilabilir;
        # python timeout olmadan reset() butun egitimi dondurur (step 2048 bug'i).
        try:
            subprocess.run(
                ["gz", "service", "-s", f"/world/{self.world_name}/set_pose",
                 "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                 "--timeout", "500", "--req", req],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=3.0,
            )
        except subprocess.TimeoutExpired:
            pass

    # ----- Gym API -----

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._np_random, _ = gym.utils.seeding.np_random(seed)
        self._node.send_cmd(0.0, 0.0)
        time.sleep(0.05)
        # HEP AYNI yerden basla (R0 sol-alt kose).
        self._gz_set_pose(self.drone_name, SPAWN_X, SPAWN_Y, SPAWN_Z, SPAWN_YAW)
        self._step_count = 0
        self._explored.fill(False)
        self._visited_rooms = set()
        self._steps_since_new_voxel = 0
        time.sleep(0.2)
        for _ in range(100):
            if self._node.snapshot()[0] is not None:
                break
            time.sleep(0.05)
        obs, _, (x, y, z, _), _ = self._make_obs()
        self._mark_voxel(x, y)
        self._visited_rooms.add(_room_id(x, y))
        return obs, {}

    def step(self, action: np.ndarray):
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        v = float(np.clip(a[0], -1.0, 1.0))
        v = V_MAX * (v if v >= 0 else max(V_REVERSE, v))   # geri en fazla V_REVERSE*V_MAX
        w = float(np.clip(a[1], -1.0, 1.0) * W_MAX)
        self._node.send_cmd(v, w)
        time.sleep(STEP_DT)
        self._step_count += 1

        obs, scan_min, (x, y, z, _), lidar_obs = self._make_obs()

        new_voxel = self._mark_voxel(x, y)
        groom     = _room_id(x, y)
        new_room  = groom not in self._visited_rooms
        if new_room:
            self._visited_rooms.add(groom)

        # ----- ODUL (v3.0 = v2.0 sade ceza; eval'de en iyi) -----
        reward = -0.01                                   # zaman

        if new_voxel:
            reward += 1.0                                # ANA kesif sinyali
            self._steps_since_new_voxel = 0
        else:
            self._steps_since_new_voxel += 1
            if self._steps_since_new_voxel > IDLE_GRACE:
                reward -= 0.05                           # bir yerde takilma

        if new_room:
            reward += 10.0                               # oda kilometre tasi

        # v3.0 = v2.0 ODULU (uclu 100-ep eval'de KANITLANMIS EN IYI: %70 carpisma / %36 kapsama).
        # v2.1 (yon-duyarli) ve v2.2 (birlesik caution) ceza-sekillendirmeleri ELENDI
        # (carpismayi %79/%88'e cikarip kapsamayi dusurdu). Sade her-yon yaklasma cezasi:
        if scan_min < OMNI_PENALTY_DIST:
            reward -= 0.5 * (OMNI_PENALTY_DIST - scan_min) / OMNI_PENALTY_DIST

        # Ileri-acik bonus (v2.0: 0.05): on lidar acikken ileri gitmeyi hafifce odullendir
        forward_open = float(lidar_obs[FORWARD_BIN])
        forward_act  = float(np.clip(a[0], 0.0, 1.0))
        reward += 0.05 * forward_open * forward_act

        # Carpisma -> terminal (her yon, fiziksel temas)
        terminated = False
        if scan_min < COLLISION_DIST:
            reward -= 10.0
            terminated = True

        truncated = self._step_count >= self.max_episode_steps

        info = {
            "explored_voxels": int(self._explored.sum()),
            "visited_rooms":   len(self._visited_rooms),
            "min_lidar":       float(scan_min),
            "x": float(x), "y": float(y),
            "v_cmd": v, "w_cmd": w,
            "collision": bool(terminated),
        }
        return obs, float(reward), terminated, truncated, info

    def close(self):
        try:
            self._node.send_cmd(0.0, 0.0)
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
