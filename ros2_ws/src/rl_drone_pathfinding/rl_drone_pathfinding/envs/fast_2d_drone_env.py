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
LIDAR_BINS = 32
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
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(43,), dtype=np.float32)

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
        self._mark_voxels(*self.pos)
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
        new_voxels = self._mark_voxels(float(self.pos[0]), float(self.pos[1]))
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

        min_lidar = float(np.min(self._compute_lidar(self._step_count)))
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
        lidar = self._compute_lidar(self._step_count)
        min_lidar = float(np.min(lidar))
        progress = np.clip(self._explored.sum() / float(GRID_NXY * GRID_NXY) * 2.0, 0.0, 1.0)
        rooms_scalar = (max(1, len(self._visited_rooms)) - 1) / float(N_ROOMS - 1)
        idle_norm = min(1.0, self._steps_since_new_voxel / float(self.max_episode_steps))
        door_dist_norm = np.clip(_nearest_door_dist(float(self.pos[0]), float(self.pos[1])) / LIDAR_MAX, 0.0, 1.0)
        wall_proximity = np.clip((NEAR_COLLISION_DIST - min_lidar) / NEAR_COLLISION_DIST, 0.0, 1.0)
        return np.concatenate([
            np.clip(lidar / LIDAR_MAX, 0.0, 1.0),
            np.array([math.cos(self.yaw), math.sin(self.yaw)], dtype=np.float32),
            np.array([self._prev_action[0], self._prev_action[1], self._prev_action[2]], dtype=np.float32),
            np.array([progress, rooms_scalar], dtype=np.float32),
            np.array([np.clip(min_lidar / LIDAR_MAX, 0.0, 1.0), idle_norm], dtype=np.float32),
            np.array([door_dist_norm, wall_proximity], dtype=np.float32),
        ]).astype(np.float32)

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
        rays = np.empty(LIDAR_BINS, dtype=np.float32)
        for i in range(LIDAR_BINS):
            angle = self.yaw + (2.0 * math.pi * i / LIDAR_BINS)
            rays[i] = self._ray_distance(angle, step)
        if self.cfg.lidar_noise_std > 0:
            rays += self._rng.normal(0.0, self.cfg.lidar_noise_std, size=rays.shape).astype(np.float32)
        self._last_lidar = np.clip(rays, 0.0, LIDAR_MAX)
        return self._last_lidar

    def _ray_distance(self, angle: float, step: int) -> float:
        origin = self.pos
        direction = np.array([math.cos(angle), math.sin(angle)], dtype=np.float32)
        distance = LIDAR_MAX
        for wall in self._walls:
            hit = self._ray_rect_distance(origin, direction, wall)
            if hit is not None:
                distance = min(distance, hit)
        for obstacle in self._moving_obstacles(step):
            hit = self._ray_circle_distance(origin, direction, obstacle, self.cfg.moving_obstacle_radius)
            if hit is not None:
                distance = min(distance, hit)
        return distance

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

    @staticmethod
    def _ray_circle_distance(origin: np.ndarray, direction: np.ndarray, center: np.ndarray, radius: float):
        oc = origin - center
        b = 2.0 * float(np.dot(oc, direction))
        c = float(np.dot(oc, oc) - radius * radius)
        disc = b * b - 4.0 * c
        if disc < 0:
            return None
        root = math.sqrt(disc)
        hits = [t for t in ((-b - root) / 2.0, (-b + root) / 2.0) if t >= 0.0]
        return min(hits) if hits else None

    def _ray_rect_distance(self, origin: np.ndarray, direction: np.ndarray, rect: tuple[float, float, float, float]):
        x0, y0, x1, y1 = rect
        inv = np.divide(1.0, direction, out=np.full_like(direction, 1e9), where=np.abs(direction) > 1e-8)
        tmin = (np.array([x0, y0], dtype=np.float32) - origin) * inv
        tmax = (np.array([x1, y1], dtype=np.float32) - origin) * inv
        t1 = np.minimum(tmin, tmax)
        t2 = np.maximum(tmin, tmax)
        enter = float(np.max(t1))
        exit_ = float(np.min(t2))
        if exit_ < 0.0 or enter > exit_:
            return None
        distance = max(0.0, enter)
        return distance if distance <= LIDAR_MAX else None

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
