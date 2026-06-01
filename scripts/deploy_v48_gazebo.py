#!/usr/bin/env python3
"""Numpy-eğitimli PPO politikasını (v4.8 / v4.10) GAZEBO 3B'de çalıştır — görselleştirme + eval.

Politika numpy hızlı sim'de lidar_history=2 (72-d gözlem) ile eğitildi. Gazebo env'i 40-d
(tek lidar karesi) üretir. Bir gym Wrapper, Gazebo'nun ardışık 2 lidar karesini biriktirip
numpy'nin 72-d gözlemini BİREBİR üretir. Hareketli engeller bir updater thread'iyle taşınır;
engel fazı HER BÖLÜMDE t=0'a sıfırlanır (numpy ile aynı: bölüm başında spawn'a denk gelmez).

NOT: numpy DT=0.15  idealize kinematik vs Gazebo gerçek fizik — bir sim-to-sim transferdir;
davranış numpy eval'ine yakın ama birebir aynı olmayabilir.

    python3 scripts/deploy_v48_gazebo.py --model runs/fast_v4_10/checkpoints/fast_drone_final.zip --episodes -1
"""
import argparse
import math
import os
import subprocess
import threading
import time

import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO

from rl_drone_pathfinding.envs.drone_exploration_env import DroneExplorationEnv, MOVING_OBS

LIDAR_BINS = 32
OBS_DT = 0.15   # numpy ile aynı: engel fazı bölüm-zamanına göre (engel hızı obs'ta doğru görünür)


class LidarHistory(gym.Wrapper):
    """Gazebo 40-d gözlemini -> numpy'nin 32*k+8 gözlemine çevirir (frame-stack)."""

    def __init__(self, env, k=2, extra_sleep=0.0, clock=None):
        super().__init__(env)
        self.k = int(k)
        self.extra_sleep = float(extra_sleep)
        self.clock = clock  # {"t0": ...} — reset'te engel fazını sıfırlamak için paylaşılır
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (LIDAR_BINS * self.k + 8,), np.float32)
        self._hist = None

    def reset(self, **kw):
        obs, info = self.env.reset(**kw)
        if self.clock is not None:
            self.clock["t0"] = time.time()   # engel fazı bu bölüm için t=0'dan başlasın
        f = obs[:LIDAR_BINS].copy()
        self._hist = [f.copy() for _ in range(self.k)]
        return self._stack(obs), info

    def step(self, action):
        obs, r, term, trunc, info = self.env.step(action)
        if self.extra_sleep:
            time.sleep(self.extra_sleep)
        self._hist.append(obs[:LIDAR_BINS].copy())
        self._hist = self._hist[-self.k:]
        return self._stack(obs), r, term, trunc, info

    def _stack(self, obs):
        return np.concatenate(self._hist + [obs[LIDAR_BINS:]]).astype(np.float32)


def obstacle_updater(world, stop, clock, hz=10.0):
    """Engelleri gz set_pose ile salındır; faz clock['t0']'a göre (her bölümde sıfırlanır)."""
    env = {**os.environ}
    interval = 1.0 / hz
    while not stop.is_set():
        t = time.time() - clock["t0"]
        for o in MOVING_OBS:
            ph = 2.0 * math.pi * t / o["T"]
            x = o["x0"] + (o["amp"] * math.sin(ph) if o["axis"] == "x" else 0.0)
            y = o["y0"] + (o["amp"] * math.sin(ph) if o["axis"] == "y" else 0.0)
            req = (f"name: '{o['name']}', position: {{x: {x:.4f}, y: {y:.4f}, z: {o['z']:.4f}}}, "
                   f"orientation: {{x: 0, y: 0, z: 0, w: 1}}")
            try:
                subprocess.run(["gz", "service", "-s", f"/world/{world}/set_pose",
                                "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                                "--timeout", "150", "--req", req], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        stop.wait(interval)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/fast_v4_10/checkpoints/fast_drone_final.zip")
    ap.add_argument("--episodes", type=int, default=-1, help="-1 = sonsuz (dur denene kadar)")
    ap.add_argument("--max-steps", type=int, default=2500)
    ap.add_argument("--lidar-history", type=int, default=2)
    ap.add_argument("--step-sleep", type=float, default=0.10)
    a = ap.parse_args()

    clock = {"t0": time.time()}
    base = DroneExplorationEnv(max_episode_steps=a.max_steps)
    env = LidarHistory(base, k=a.lidar_history, extra_sleep=a.step_sleep, clock=clock)
    model = PPO.load(a.model)
    tag = os.path.basename(os.path.dirname(os.path.dirname(a.model)))  # runs/<tag>/checkpoints
    print(f"[deploy] model={a.model} ({tag})", flush=True)
    print(f"[deploy] gözlem boyutu={env.observation_space.shape} (beklenen {LIDAR_BINS*a.lidar_history+8})", flush=True)

    stop = threading.Event()
    th = threading.Thread(target=obstacle_updater, args=(base.world_name, stop, clock), daemon=True)
    th.start()
    print(f"[deploy] hareketli engel updater başladı ({len(MOVING_OBS)} engel, faz bölüme-bağlı)", flush=True)

    infinite = a.episodes <= 0
    cols = 0
    voxs, rooms, lens = [], [], []
    ep = 0
    try:
        while infinite or ep < a.episodes:
            obs, _ = env.reset()
            done = False
            n = 0
            info = {}
            while not done:
                act, _ = model.predict(obs, deterministic=True)
                obs, r, term, trunc, info = env.step(act)
                n += 1
                done = term or trunc
            ep += 1
            voxs.append(info.get("explored_voxels", 0))
            rooms.append(info.get("visited_rooms", 0))
            lens.append(n)
            if info.get("collision"):
                cols += 1
            tot = "∞" if infinite else str(a.episodes)
            print(f"  bölüm {ep}/{tot}: voxel={info.get('explored_voxels',0)} "
                  f"oda={info.get('visited_rooms',0)} adım={n} "
                  f"{'ÇARPTI' if info.get('collision') else 'hayatta'} | "
                  f"toplam: çarpışma %{100*cols/ep:.0f} voxel~{np.mean(voxs):.0f} oda~{np.mean(rooms):.2f}", flush=True)
    except KeyboardInterrupt:
        print("\n[deploy] durduruldu (KeyboardInterrupt)", flush=True)
    finally:
        stop.set()
        if ep:
            print(f"\n=== {tag} GAZEBO 3B ÖZET: {ep} bölüm | çarpışma %{100*cols/ep:.0f} | "
                  f"voxel ort {np.mean(voxs):.0f} | oda ort {np.mean(rooms):.2f} | adım ort {np.mean(lens):.0f}", flush=True)
        try:
            env.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
