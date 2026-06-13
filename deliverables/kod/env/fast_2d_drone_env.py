from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

WORLD_HALF = 8.0
GRID_CELL_XY = 0.5
GRID_NXY = int((2 * WORLD_HALF) / GRID_CELL_XY)
LIDAR_BINS = 64
LIDAR_MAX = 10.0
V_MAX = 1.2
W_MAX = 1.5
DRONE_FOOTPRINT_RADIUS = 0.22
NEAR_COLLISION_DIST = 0.5
ACTION_SMOOTH = 0.15
ROOM_X1 = -2.0
ROOM_X2 = 4.0
ROOM_Y0 = 0.0
N_ROOMS = 6
DOOR_POSITIONS = [(-2.0, -3.0), (4.0, 4.0), (-6.0, 0.0), (1.0, 0.0), (6.0, 0.0)]

# Visibility-based keşif sabitlieri
# Adım boyutu hücre kenarının yarısından küçük → hiçbir hücre atlanmaz
_VIS_STEP = GRID_CELL_XY * 0.5          # 0.25 m
_VIS_MAX_STEPS = int(LIDAR_MAX / _VIS_STEP) + 2  # maks. ışın adım sayısı


def _room_id(x: float, y: float) -> int:
    col = 0 if x < ROOM_X1 else (1 if x < ROOM_X2 else 2)
    row = 0 if y < ROOM_Y0 else 1
    return row * 3 + col


def _global_room_id(x: float, y: float, z: float) -> int:
    return _room_id(x, y)


def _nearest_door_dist(x: float, y: float) -> float:
    return min(math.hypot(x - dx, y - dy) for dx, dy in DOOR_POSITIONS)


@dataclass(frozen=True)
class Fast2DConfig:
    dt: float = 0.12
    max_episode_steps: int = 600
    lidar_noise_std: float = 0.015
    odom_noise_std: float = 0.004
    wind_std: float = 0.015
    static_obstacle_radius: float = 0.32
    moving_obstacle_radius: float = 0.34
    collision_penalty: float = -40.0
    all_rooms_bonus: float = 60.0
    random_start: bool = True


class Fast2DDroneExplorationEnv(gym.Env):
    """Fast 2D Gymnasium approximation of the existing Gazebo multi_room world."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 15}

    def __init__(
        self,
        config: Fast2DConfig | None = None,
        render_mode: str | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        self.cfg = config or Fast2DConfig()
        self.render_mode = render_mode
        self.max_episode_steps = self.cfg.max_episode_steps

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        # gozlem = lidar(LIDAR_BINS) + yaw cos/sin(2) + prev_action(3)
        #          + [progress,rooms](2) + [min_lidar,idle](2) + [door_dist,wall](2)
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(LIDAR_BINS + 11,), dtype=np.float32
        )

        self._rng = np.random.default_rng(seed)
        self._walls = self._build_walls()
        self._moving_base = np.array([[-5.0, -3.0], [1.0, 4.0], [6.0, -4.0]], dtype=np.float32)
        self._moving_axes = np.array([[0.0, 0.8], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        self._moving_periods = np.array([7.0, 9.0, 5.0], dtype=np.float32)

        self.pos = np.zeros(2, dtype=np.float32)
        self.yaw = 0.0
        self._prev_action = np.zeros(3, dtype=np.float32)
        self._last_lidar = np.full(LIDAR_BINS, LIDAR_MAX, dtype=np.float32)
        self._explored = np.zeros((GRID_NXY, GRID_NXY, 1), dtype=bool)
        self._visited_rooms: set[int] = set()
        self._steps_since_new_voxel = 0
        self._step_count = 0
        self._pos_history: list[tuple[int, int]] = []

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self.pos = self._sample_start()
        self.yaw = float(self._rng.uniform(-math.pi, math.pi))
        self._prev_action[:] = 0.0
        self._explored.fill(False)
        self._visited_rooms = set()
        self._steps_since_new_voxel = 0
        self._step_count = 0
        self._pos_history = []
        # Başlangıç görünürlük taraması: drone başladığı noktada
        # etrafını görür, ayak izinden çok daha geniş alan keşfedilir.
        initial_lidar = self._compute_lidar(0)
        self._mark_visible_voxels(initial_lidar)
        self._visited_rooms.add(_global_room_id(float(self.pos[0]), float(self.pos[1]), 1.2))
        return self._make_obs(), self._info(False, 0)

    def step(self, action):
        a = np.asarray(action, dtype=np.float32).reshape(-1)
        a = np.clip(a, self.action_space.low, self.action_space.high)
        a = ACTION_SMOOTH * self._prev_action + (1.0 - ACTION_SMOOTH) * a
        self._prev_action = a.copy()

        vx = float(np.clip(a[0] * V_MAX, -V_MAX, V_MAX))
        vy = float(np.clip(a[1] * V_MAX, -V_MAX, V_MAX))
        wz = float(np.clip(a[2] * W_MAX, -W_MAX, W_MAX))
        vx += float(self._rng.normal(0.0, self.cfg.wind_std))
        vy += float(self._rng.normal(0.0, self.cfg.wind_std))
        wz += float(self._rng.normal(0.0, self.cfg.wind_std))

        c, s = math.cos(self.yaw), math.sin(self.yaw)
        world_delta = np.array([c * vx - s * vy, s * vx + c * vy], dtype=np.float32) * self.cfg.dt
        self.pos = self.pos + world_delta
        self.yaw = self._wrap_angle(self.yaw + wz * self.cfg.dt)
        self._step_count += 1

        collision = self._is_collision(self.pos, self._step_count)

        # Lidar bir kez hesaplanır; hem keşif hem gözlem hem ödül için kullanılır.
        # Önceden iki kere çağrılıyordu (step + _make_obs) → farklı gürültü örnekleri.
        lidar = self._compute_lidar(self._step_count)   # → self._last_lidar güncellenir
        min_lidar = float(np.min(lidar))

        # Görünürlük tabanlı keşif: lidar ışınlarının geçtiği TÜM hücreler keşfedilir.
        # Eskiden sadece drone'un ayak izi (~0.22 m) keşfediliyordu.
        new_voxels = self._mark_visible_voxels(lidar)
        new_voxel = new_voxels > 0
        room = _global_room_id(float(self.pos[0]), float(self.pos[1]), 1.2)
        new_room = room not in self._visited_rooms
        self._visited_rooms.add(room)

        reward = -0.01
        if new_voxel:
            reward += 3.0
            self._steps_since_new_voxel = 0
        else:
            self._steps_since_new_voxel += 1
        if new_room:
            reward += 20.0
        if self._steps_since_new_voxel > 50:
            reward -= 0.10

        if min_lidar < 0.7:
            reward -= ((0.7 - min_lidar) / 0.7) * 0.3
        if collision:
            reward += self.cfg.collision_penalty
        if len(self._visited_rooms) >= N_ROOMS:
            reward += self.cfg.all_rooms_bonus

        gx = int((self.pos[0] + WORLD_HALF) / GRID_CELL_XY)
        gy = int((self.pos[1] + WORLD_HALF) / GRID_CELL_XY)
        cell = (gx, gy)
        if cell in self._pos_history:
            reward -= 0.10
        self._pos_history.append(cell)
        if len(self._pos_history) > 60:
            self._pos_history.pop(0)

        terminated = bool(collision or len(self._visited_rooms) >= N_ROOMS)
        truncated = self._step_count >= self.max_episode_steps
        return self._make_obs(), float(reward), terminated, truncated, self._info(collision, new_voxels)

    def _build_walls(self) -> list[tuple[float, float, float, float]]:
        return [
            (-8.2, 7.9, 8.2, 8.1),
            (-8.2, -8.1, 8.2, -7.9),
            (-8.1, -8.0, -7.9, 8.0),
            (7.9, -8.0, 8.1, 8.0),
            (-2.1, -8.0, -1.9, -5.0),
            (-2.1, -1.0, -1.9, 8.0),
            (3.9, -8.0, 4.1, 2.0),
            (3.9, 6.0, 4.1, 8.0),
            (-4.0, -0.1, -2.0, 0.1),
            (2.0, -0.1, 4.0, 0.1),
        ]

    def _moving_obstacles(self, step: int) -> np.ndarray:
        t = step * self.cfg.dt
        phase = 2.0 * math.pi * t / self._moving_periods
        return self._moving_base + self._moving_axes * np.sin(phase)[:, None]

    def _sample_start(self) -> np.ndarray:
        candidates = [
            (-5.0, -5.5), (1.0, -5.5), (6.5, -6.0),
            (-5.0, 6.0), (2.5, 5.5), (6.5, 6.0),
        ]
        if not self.cfg.random_start:
            return np.array(candidates[0], dtype=np.float32)
        for _ in range(200):
            x, y = candidates[int(self._rng.integers(len(candidates)))]
            pos = np.array([x, y], dtype=np.float32) + self._rng.uniform(-0.5, 0.5, size=2)
            if not self._is_collision(pos, 0):
                return pos.astype(np.float32)
        return np.array(candidates[0], dtype=np.float32)

    def _make_obs(self) -> np.ndarray:
        # self._last_lidar: step() veya reset()'teki _compute_lidar() tarafından
        # doldurulur. İkinci bir hesaplama yapılmaz (farklı gürültü örneği riski yok).
        lidar = self._last_lidar
        min_lidar = float(np.min(lidar))
        progress = np.clip(self._explored.sum() / float(GRID_NXY * GRID_NXY) * 2.0, 0.0, 1.0)
        rooms_scalar = (max(1, len(self._visited_rooms)) - 1) / float(N_ROOMS - 1)
        idle_norm = min(1.0, self._steps_since_new_voxel / float(self.max_episode_steps))
        # Odometri sensoru gurultulu: GERCEK poz/yaw (dinamik+carpisma) bozulmaz;
        # yalnizca OLCULEN poz gozleme gurultulu girer => stokastik gozlem (POMDP).
        # odom_noise_std burada kullanilir (artik olu parametre degil).
        odom = self.cfg.odom_noise_std
        meas_x = float(self.pos[0]) + float(self._rng.normal(0.0, odom))
        meas_y = float(self.pos[1]) + float(self._rng.normal(0.0, odom))
        meas_yaw = self.yaw + float(self._rng.normal(0.0, odom))
        door_dist_norm = np.clip(_nearest_door_dist(meas_x, meas_y) / LIDAR_MAX, 0.0, 1.0)
        wall_proximity = np.clip((NEAR_COLLISION_DIST - min_lidar) / NEAR_COLLISION_DIST, 0.0, 1.0)
        return np.concatenate([
            np.clip(lidar / LIDAR_MAX, 0.0, 1.0),
            np.array([math.cos(meas_yaw), math.sin(meas_yaw)], dtype=np.float32),
            np.array([self._prev_action[0], self._prev_action[1], self._prev_action[2]], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),
            np.array([np.clip(min_lidar / LIDAR_MAX, 0.0, 1.0), idle_norm], dtype=np.float32),
            np.array([door_dist_norm, wall_proximity], dtype=np.float32),
        ]).astype(np.float32)

    def _mark_visible_voxels(self, lidar_dists: np.ndarray) -> int:
        """Her lidar ışınının görebileceği tüm hücreleri keşfedilmiş işaretler.

        Her ışın boyunca engele kadar adım adım ilerler; geçilen her hücre
        keşfedilmiş sayılır. Vectorize: Python döngüsü yok.

        Fiziksel anlam: drone 360° lidar ile etrafını "görür" —
        sadece bastığı yeri değil, gözlemleyebildiği tüm alanı keşfeder.
        """
        angles = self.yaw + np.linspace(0.0, 2.0 * math.pi, LIDAR_BINS,
                                        endpoint=False, dtype=np.float32)
        t = np.arange(_VIS_MAX_STEPS, dtype=np.float32) * _VIS_STEP  # (S,)

        # Tüm ışın × adım koordinatları: (N, S)
        x_pts = self.pos[0] + np.cos(angles)[:, None] * t[None, :]
        y_pts = self.pos[1] + np.sin(angles)[:, None] * t[None, :]

        gx = np.floor((x_pts + WORLD_HALF) / GRID_CELL_XY).astype(np.int32)
        gy = np.floor((y_pts + WORLD_HALF) / GRID_CELL_XY).astype(np.int32)

        in_bounds = (gx >= 0) & (gx < GRID_NXY) & (gy >= 0) & (gy < GRID_NXY)
        in_range  = t[None, :] <= lidar_dists[:, None]   # engele kadar

        valid = in_bounds & in_range

        # Benzersiz hücre indeksleri (flat = gx*GRID_NXY + gy)
        flat = gx * GRID_NXY + gy
        flat[~valid] = -1
        unique_flat = np.unique(flat)
        unique_flat = unique_flat[unique_flat >= 0]

        if unique_flat.size == 0:
            return 0

        gx_u = (unique_flat // GRID_NXY).astype(np.int32)
        gy_u = (unique_flat  % GRID_NXY).astype(np.int32)

        prev = self._explored[gx_u, gy_u, 0].copy()
        self._explored[gx_u, gy_u, 0] = True
        return int((~prev).sum())

    def _mark_voxels(self, x: float, y: float) -> int:
        new_count = 0
        gx0 = math.floor((x - DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gx1 = math.floor((x + DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gy0 = math.floor((y - DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        gy1 = math.floor((y + DRONE_FOOTPRINT_RADIUS + WORLD_HALF) / GRID_CELL_XY)
        for gx in range(max(0, gx0), min(GRID_NXY - 1, gx1) + 1):
            for gy in range(max(0, gy0), min(GRID_NXY - 1, gy1) + 1):
                if not self._circle_overlaps_cell(x, y, DRONE_FOOTPRINT_RADIUS, gx, gy):
                    continue
                if not self._explored[gx, gy, 0]:
                    self._explored[gx, gy, 0] = True
                    new_count += 1
        return new_count

    def _compute_lidar(self, step: int) -> np.ndarray:
        # Vektorize: tum LIDAR_BINS isini tek numpy operasyonuyla hesapla.
        # Onceki Python for-loop (64 iter x 13 nesne) yerine array broadcast =>
        # her env adiminda ~5-8x hiz artisi.
        angles = self.yaw + np.linspace(0.0, 2.0 * math.pi, LIDAR_BINS, endpoint=False, dtype=np.float32)
        dirs = np.stack([np.cos(angles), np.sin(angles)], axis=1)  # (N,2)
        dist = np.full(LIDAR_BINS, LIDAR_MAX, dtype=np.float32)

        walls_arr = np.array(self._walls, dtype=np.float32)         # (W,4)
        np.minimum(dist, self._rays_vs_rects(self.pos, dirs, walls_arr), out=dist)

        for obs_center in self._moving_obstacles(step):
            np.minimum(dist, self._rays_vs_circle(self.pos, dirs, obs_center,
                                                   self.cfg.moving_obstacle_radius), out=dist)

        if self.cfg.lidar_noise_std > 0:
            dist += self._rng.normal(0.0, self.cfg.lidar_noise_std, size=dist.shape).astype(np.float32)
        self._last_lidar = np.clip(dist, 0.0, LIDAR_MAX)
        return self._last_lidar

    @staticmethod
    def _rays_vs_rects(origin: np.ndarray, dirs: np.ndarray,
                       rects: np.ndarray) -> np.ndarray:
        """Tum isimlari tum dikdortgenlere karsi toplu test eder.

        origin: (2,)   dirs: (N,2)   rects: (W,4) [x0,y0,x1,y1]
        Donus: (N,) minimum mesafe
        """
        N = dirs.shape[0]
        W = rects.shape[0]
        # dirs  -> (N,1,2),  rects -> (1,W,4)
        d = dirs[:, np.newaxis, :]                          # (N,1,2)
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = np.where(np.abs(d) > 1e-8, 1.0 / d, 1e9 * np.sign(d + 1e-30))  # (N,1,2)
        lo = rects[np.newaxis, :, :2] - origin              # (1,W,2)
        hi = rects[np.newaxis, :, 2:] - origin              # (1,W,2)
        t1 = np.minimum(lo * inv, hi * inv)                 # (N,W,2)
        t2 = np.maximum(lo * inv, hi * inv)                 # (N,W,2)
        enter = t1.max(axis=2)                              # (N,W)
        exit_ = t2.min(axis=2)                              # (N,W)
        hit = np.where((exit_ >= 0) & (enter <= exit_),
                       np.maximum(0.0, enter), LIDAR_MAX)   # (N,W)
        return hit.min(axis=1).astype(np.float32)           # (N,)

    @staticmethod
    def _rays_vs_circle(origin: np.ndarray, dirs: np.ndarray,
                        center: np.ndarray, radius: float) -> np.ndarray:
        """Tum isimlari tek bir daireye karsi toplu test eder.

        origin: (2,)  dirs: (N,2)  center: (2,)
        Donus: (N,) mesafe (isabet yoksa LIDAR_MAX)
        """
        oc = origin - center                                # (2,)
        b = 2.0 * (dirs @ oc)                              # (N,)
        c = float(np.dot(oc, oc)) - radius * radius
        disc = b * b - 4.0 * c                             # (N,)
        safe_disc = np.maximum(disc, 0.0)
        sq = np.sqrt(safe_disc)
        t1 = (-b - sq) / 2.0
        t2 = (-b + sq) / 2.0
        t = np.where(t1 >= 0.0, t1, np.where(t2 >= 0.0, t2, LIDAR_MAX))
        t = np.where(disc >= 0.0, t, LIDAR_MAX)
        return np.minimum(t, LIDAR_MAX).astype(np.float32)

    def _is_collision(self, pos: np.ndarray, step: int) -> bool:
        if not (-WORLD_HALF <= pos[0] <= WORLD_HALF and -WORLD_HALF <= pos[1] <= WORLD_HALF):
            return True
        for wall in self._walls:
            if self._circle_rect_collision(pos, DRONE_FOOTPRINT_RADIUS, wall):
                return True
        for obstacle in self._moving_obstacles(step):
            if np.linalg.norm(pos - obstacle) <= DRONE_FOOTPRINT_RADIUS + self.cfg.moving_obstacle_radius:
                return True
        return False

    def _info(self, collision: bool, new_voxels: int) -> dict[str, Any]:
        return {
            "collision": bool(collision),
            "explored_voxels": int(self._explored.sum()),
            "visited_rooms": len(self._visited_rooms),
            "visited_floors": 1,
            "min_lidar": float(np.min(self._last_lidar)),
            "x": float(self.pos[0]),
            "y": float(self.pos[1]),
            "z": 1.2,
            "room_id": int(_global_room_id(float(self.pos[0]), float(self.pos[1]), 1.2)),
            "door_dist": float(_nearest_door_dist(float(self.pos[0]), float(self.pos[1]))),
            "new_voxels": int(new_voxels),
        }

    @staticmethod
    def _wrap_angle(angle: float) -> float:
        return (angle + math.pi) % (2.0 * math.pi) - math.pi

    @staticmethod
    def _circle_overlaps_cell(x: float, y: float, radius: float, gx: int, gy: int) -> bool:
        x0 = gx * GRID_CELL_XY - WORLD_HALF
        y0 = gy * GRID_CELL_XY - WORLD_HALF
        x1 = x0 + GRID_CELL_XY
        y1 = y0 + GRID_CELL_XY
        cx = min(max(x, x0), x1)
        cy = min(max(y, y0), y1)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

    @staticmethod
    def _circle_rect_collision(center: np.ndarray, radius: float, rect: tuple[float, float, float, float]) -> bool:
        x0, y0, x1, y1 = rect
        closest = np.array([np.clip(center[0], x0, x1), np.clip(center[1], y0, y1)], dtype=np.float32)
        return bool(np.linalg.norm(center - closest) <= radius)


    def render(self):
        scale = 48
        size = int(WORLD_HALF * 2 * scale)
        img = np.full((size, size, 3), 245, dtype=np.uint8)

        def to_px(point):
            x, y = point
            return int((x + WORLD_HALF) * scale), int((y + WORLD_HALF) * scale)

        for x0, y0, x1, y1 in self._walls:
            px0, py0 = to_px((x0, y0))
            px1, py1 = to_px((x1, y1))
            img[max(0, py0):min(size, py1), max(0, px0):min(size, px1)] = (45, 45, 50)
        for obstacle in self._moving_obstacles(self._step_count):
            self._draw_circle(img, obstacle, self.cfg.moving_obstacle_radius, scale, np.array([210, 85, 75], dtype=np.uint8))
        self._draw_circle(img, self.pos, DRONE_FOOTPRINT_RADIUS, scale, np.array([30, 150, 95], dtype=np.uint8))
        return np.flipud(img)

    @staticmethod
    def _draw_circle(img: np.ndarray, center: np.ndarray, radius: float, scale: int, color: np.ndarray) -> None:
        cx = int((center[0] + WORLD_HALF) * scale)
        cy = int((center[1] + WORLD_HALF) * scale)
        rr = int(radius * scale)
        y, x = np.ogrid[-cy: img.shape[0] - cy, -cx: img.shape[1] - cx]
        img[x * x + y * y <= rr * rr] = color
