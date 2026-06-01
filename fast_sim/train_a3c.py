"""A3C (≈ A2C) eğitimi — HIZLI numpy sim (Gazebo'suz, ROS'suz).

================================================================================
A3C = Asynchronous Advantage Actor-Critic. SB3'te birebir "A3C" sınıfı yoktur;
SENKRON eşdeğeri A2C'dir (aynı actor-critic + advantage; "asenkron işçiler"
yerine n_envs paralel env = senkron çoklu-işçi). Literatürde A2C, A3C'nin
pratik/senkron biçimi olarak kabul edilir. Raporda böyle belirt.

n_envs paralel env (SubprocVecEnv) = A3C'nin paralel işçileri.
Aksiyon DISCRETE (FastDroneEnvDiscrete). Ortam/ödül Berker'in PPO'su ile AYNI.

Çalıştır:  python3 fast_sim/train_a3c.py --config configs/a3c_v1.yaml
================================================================================
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys
from pathlib import Path

import numpy as np
import yaml
from stable_baselines3 import A2C
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fast_drone_env_discrete import FastDroneEnvDiscrete  # noqa: E402


def _load(p):
    return yaml.safe_load(open(p))


def _lr(cfg):
    base = float(cfg["learning_rate"])
    if cfg.get("lr_schedule") == "linear":
        final = float(cfg.get("lr_final", base * 0.1))
        return lambda pr: final + pr * (base - final)
    return base


def _make_env(env_cfg, i=0):
    def f():
        return Monitor(
            FastDroneEnvDiscrete(max_episode_steps=env_cfg["max_episode_steps"],
                                 seed=(env_cfg.get("seed") or 0) + i, env_id=i,
                                 lidar_history=int(env_cfg.get("lidar_history", 1)),
                                 room_bonus=float(env_cfg.get("room_bonus", 10.0)),
                                 idle_penalty=float(env_cfg.get("idle_penalty", 0.05)),
                                 idle_grace=int(env_cfg.get("idle_grace", 40)),
                                 collision_penalty=float(env_cfg.get("collision_penalty", 10.0)),
                                 far_voxel_bonus=float(env_cfg.get("far_voxel_bonus", 0.0))),
            info_keywords=("explored_voxels", "visited_rooms"))
    return f


class ExplorationLogger(BaseCallback):
    """TB + progress.csv (rapor kıyası için). PPO trainer'daki ile aynı format."""
    def __init__(self, log_dir, version, ckpt_dir=None, verbose=0):
        super().__init__(verbose)
        self.csv_path = Path(log_dir) / "progress.csv"
        self.version = version
        self.vn_path = Path(ckpt_dir) / "vec_normalize.pkl" if ckpt_dir else None
        self._hdr = self.csv_path.exists()

    def _mean(self, k):
        vals = [e[k] for e in self.model.ep_info_buffer if k in e]
        return (float(np.mean(vals)), float(np.max(vals))) if vals else (0.0, 0.0)

    def _on_step(self):
        return True

    def _on_rollout_end(self):
        buf = self.model.ep_info_buffer
        if not buf:
            return
        rm = float(np.mean([e["r"] for e in buf])); lm = float(np.mean([e["l"] for e in buf]))
        vm, vx = self._mean("explored_voxels"); rmn, rx = self._mean("visited_rooms")
        self.logger.record("explore/voxels_mean", vm); self.logger.record("explore/voxels_max", vx)
        self.logger.record("explore/rooms_mean", rmn); self.logger.record("explore/rooms_max", rx)
        with open(self.csv_path, "a", newline="") as f:
            w = csv.writer(f)
            if not self._hdr:
                w.writerow(["timestamp", "version", "step", "ep_rew_mean", "ep_len_mean",
                            "voxels_mean", "voxels_max", "rooms_mean", "rooms_max"])
                self._hdr = True
            w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.version,
                        int(self.num_timesteps), round(rm, 3), round(lm, 1),
                        round(vm, 2), int(vx), round(rmn, 3), int(rx)])
        if self.vn_path:
            vn = self.model.get_vec_normalize_env()
            if vn is not None:
                try:
                    vn.save(str(self.vn_path))
                except Exception:
                    pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/a3c_v1.yaml")
    args, _ = ap.parse_known_args(argv)
    cfg = _load(args.config)
    # 'a2c' bolumu (A3C ayarlari); geriye uyum icin 'ppo' da kabul
    env_cfg = cfg["env"]; ac_cfg = cfg.get("a2c", cfg.get("ppo")); tr = cfg["train"]

    log_dir = Path(tr["log_dir"]); log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb = Path(tr["tb_log"]); tb.mkdir(parents=True, exist_ok=True)

    n = int(tr.get("n_envs", 8))
    facs = [_make_env(env_cfg, i) for i in range(n)]
    # SubprocVecEnv = A3C'nin paralel isçileri. macOS'ta sorun olursa n_envs=1 -> DummyVecEnv.
    venv = SubprocVecEnv(facs) if n > 1 else DummyVecEnv(facs)
    print(f"[train_a3c] A2C(~A3C) | {n} paralel isçi (env) | DISCRETE aksiyon | numpy sim (Gazebo YOK)")

    vn = tr.get("vec_normalize", {}) or {}
    use_vn = bool(vn.get("enabled", True))
    resuming = bool(tr.get("resume_from"))
    if use_vn:
        vnp = ckpt_dir / "vec_normalize.pkl"
        if resuming and vnp.exists():
            venv = VecNormalize.load(str(vnp), venv); venv.training = True
            venv.norm_reward = bool(vn.get("norm_reward", True))
        else:
            venv = VecNormalize(venv, norm_obs=bool(vn.get("norm_obs", False)),
                                norm_reward=bool(vn.get("norm_reward", True)),
                                clip_reward=float(vn.get("clip_reward", 10.0)),
                                gamma=float(ac_cfg.get("gamma", 0.99)))

    if resuming:
        print(f"[train_a3c] resuming from {tr['resume_from']}")
        model = A2C.load(tr["resume_from"], env=venv, tensorboard_log=str(tb))
        model.learning_rate = _lr(ac_cfg)
    else:
        model = A2C(ac_cfg["policy"], venv, learning_rate=_lr(ac_cfg),
                    n_steps=int(ac_cfg["n_steps"]), gamma=float(ac_cfg["gamma"]),
                    gae_lambda=float(ac_cfg.get("gae_lambda", 1.0)),
                    ent_coef=float(ac_cfg["ent_coef"]), vf_coef=float(ac_cfg["vf_coef"]),
                    max_grad_norm=float(ac_cfg["max_grad_norm"]),
                    use_rms_prop=bool(ac_cfg.get("use_rms_prop", True)),
                    normalize_advantage=bool(ac_cfg.get("normalize_advantage", False)),
                    policy_kwargs={"net_arch": ac_cfg["policy_kwargs"]["net_arch"]},
                    tensorboard_log=str(tb), verbose=1, seed=env_cfg.get("seed"))

    ckpt_cb = CheckpointCallback(save_freq=max(1, int(tr["save_freq"]) // n),
                                 save_path=str(ckpt_dir), name_prefix="a3c_drone")
    explo = ExplorationLogger(log_dir, str(tr.get("version", "a3c")),
                              ckpt_dir if use_vn else None)
    cbs = CallbackList([ckpt_cb, explo])

    target = int(tr["total_timesteps"])
    learn = (target - int(model.num_timesteps)) if resuming else target
    if resuming and learn <= 0:
        print("[train_a3c] target reached"); return
    final = ckpt_dir / "a3c_drone_final.zip"
    try:
        model.learn(total_timesteps=learn, callback=cbs, progress_bar=True,
                    reset_num_timesteps=not resuming)
    except KeyboardInterrupt:
        final = ckpt_dir / "a3c_drone_interrupted.zip"
        print("[train_a3c] interrupted")
    model.save(str(final))
    if use_vn:
        venv.save(str(ckpt_dir / "vec_normalize.pkl"))
    print(f"[train_a3c] saved {final}")


if __name__ == "__main__":
    main()
