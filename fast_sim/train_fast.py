"""HIZLI numpy sim üzerinde PPO eğitimi (Gazebo'suz, ROS'suz). n_envs>1 SERBEST
(çoklu-env sorunu Gazebo'ya özeldi). v2.0 ödülü = üçlü eval'de en iyi.

Çalıştır:  python3 fast_sim/train_fast.py --config configs/fast.yaml
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys
from pathlib import Path

import numpy as np
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fast_drone_env import FastDroneEnv  # noqa: E402


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
            FastDroneEnv(max_episode_steps=env_cfg["max_episode_steps"],
                         seed=(env_cfg.get("seed") or 0) + i, env_id=i,
                         lidar_history=int(env_cfg.get("lidar_history", 1))),
            info_keywords=("explored_voxels", "visited_rooms"))
    return f


class ExplorationLogger(BaseCallback):
    """Gazebo trainer'daki ile aynı: TB + progress.csv (rapor kıyası için)."""
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
    ap.add_argument("--config", default="configs/fast.yaml")
    args, _ = ap.parse_known_args(argv)
    cfg = _load(args.config)
    env_cfg, ppo_cfg, tr = cfg["env"], cfg["ppo"], cfg["train"]

    log_dir = Path(tr["log_dir"]); log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb = Path(tr["tb_log"]); tb.mkdir(parents=True, exist_ok=True)

    n = int(tr.get("n_envs", 8))
    facs = [_make_env(env_cfg, i) for i in range(n)]
    venv = SubprocVecEnv(facs) if n > 1 else DummyVecEnv(facs)
    print(f"[train_fast] {n} paralel env (SubprocVecEnv) — Gazebo YOK, hizli numpy sim")

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
                                gamma=float(ppo_cfg.get("gamma", 0.99)))

    if resuming:
        print(f"[train_fast] resuming from {tr['resume_from']}")
        model = PPO.load(tr["resume_from"], env=venv, tensorboard_log=str(tb))
        model.learning_rate = _lr(ppo_cfg)
        model.policy.optimizer.param_groups[0]["lr"] = float(ppo_cfg["learning_rate"])
    else:
        model = PPO(ppo_cfg["policy"], venv, learning_rate=_lr(ppo_cfg),
                    n_steps=int(ppo_cfg["n_steps"]), batch_size=int(ppo_cfg["batch_size"]),
                    n_epochs=int(ppo_cfg["n_epochs"]), gamma=float(ppo_cfg["gamma"]),
                    gae_lambda=float(ppo_cfg["gae_lambda"]), clip_range=float(ppo_cfg["clip_range"]),
                    ent_coef=float(ppo_cfg["ent_coef"]), vf_coef=float(ppo_cfg["vf_coef"]),
                    max_grad_norm=float(ppo_cfg["max_grad_norm"]),
                    policy_kwargs={"net_arch": ppo_cfg["policy_kwargs"]["net_arch"]},
                    tensorboard_log=str(tb), verbose=1, seed=env_cfg.get("seed"))

    ckpt_cb = CheckpointCallback(save_freq=max(1, int(tr["save_freq"]) // n),
                                 save_path=str(ckpt_dir), name_prefix="fast_drone")
    explo = ExplorationLogger(log_dir, str(tr.get("version", "fast")),
                              ckpt_dir if use_vn else None)
    cbs = CallbackList([ckpt_cb, explo])

    target = int(tr["total_timesteps"])
    learn = (target - int(model.num_timesteps)) if resuming else target
    if resuming and learn <= 0:
        print("[train_fast] target reached"); return
    final = ckpt_dir / "fast_drone_final.zip"
    try:
        model.learn(total_timesteps=learn, callback=cbs, progress_bar=True,
                    reset_num_timesteps=not resuming)
    except KeyboardInterrupt:
        final = ckpt_dir / "fast_drone_interrupted.zip"
        print("[train_fast] interrupted")
    model.save(str(final))
    if use_vn:
        venv.save(str(ckpt_dir / "vec_normalize.pkl"))
    print(f"[train_fast] saved {final}")


if __name__ == "__main__":
    main()
