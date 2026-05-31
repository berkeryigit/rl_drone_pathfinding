"""Train PPO on DroneExplorationEnv. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
import csv
import datetime
import math
import os
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from rl_drone_pathfinding.envs import DroneExplorationEnv
from rl_drone_pathfinding.envs.drone_exploration_env import MOVING_OBS


def _load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _build_lr(ppo_cfg: dict):
    """Return a learning_rate value or callable schedule per yaml config."""
    base = float(ppo_cfg["learning_rate"])
    sched = ppo_cfg.get("lr_schedule")
    if sched is None or sched == "constant":
        return base
    if sched == "linear":
        final = float(ppo_cfg.get("lr_final", base * 0.1))

        def f(progress_remaining: float) -> float:
            # progress_remaining: 1.0 at start -> 0.0 at end
            return final + progress_remaining * (base - final)
        return f
    raise ValueError(f"unknown lr_schedule={sched!r}")


def _make_env(env_cfg: dict, env_id: int = 0):
    def _factory():
        env = DroneExplorationEnv(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
            seed=env_cfg.get("seed"),
            env_id=env_id,
        )
        # info_keywords -> bu anahtarlar episode sonunda ep_info_buffer'a tasinir,
        # boylece ExplorationLogger keşif metriklerini TB + CSV'ye yazabilir.
        return Monitor(env, info_keywords=("explored_voxels", "visited_rooms"))
    return _factory


class ExplorationLogger(BaseCallback):
    """Her rollout sonunda kesif metriklerini TB'ye kaydeder ve <log_dir>/progress.csv'ye ekler.

    Rapor grafikleri (voxel kapsami, oda sayisi, reward) bu verilerden uretilir.
    """

    def __init__(self, log_dir: Path, version: str, ckpt_dir: Path = None, verbose: int = 0):
        super().__init__(verbose)
        self.csv_path = Path(log_dir) / "progress.csv"
        self.version = version
        # Restart dayanikliligi: vec_normalize.pkl'i her rollout sonunda taze tut,
        # boylece crash sonrasi resume'da reward istatistikleri checkpoint'le uyumlu.
        self.vn_path = Path(ckpt_dir) / "vec_normalize.pkl" if ckpt_dir else None
        self._header_written = self.csv_path.exists()

    def _safe_mean(self, key):
        buf = self.model.ep_info_buffer
        vals = [ep[key] for ep in buf if key in ep]
        return (float(np.mean(vals)), float(np.max(vals))) if vals else (0.0, 0.0)

    def _on_step(self) -> bool:  # gerekli ama is rollout sonunda yapilir
        return True

    def _on_rollout_end(self) -> None:
        buf = self.model.ep_info_buffer
        if not buf:
            return
        rew_mean = float(np.mean([ep["r"] for ep in buf]))
        len_mean = float(np.mean([ep["l"] for ep in buf]))
        vox_mean, vox_max = self._safe_mean("explored_voxels")
        room_mean, room_max = self._safe_mean("visited_rooms")

        # TensorBoard
        self.logger.record("explore/voxels_mean", vox_mean)
        self.logger.record("explore/voxels_max", vox_max)
        self.logger.record("explore/rooms_mean", room_mean)
        self.logger.record("explore/rooms_max", room_max)

        # CSV (rapor icin)
        write_header = not self._header_written
        with open(self.csv_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["timestamp", "version", "step", "ep_rew_mean",
                            "ep_len_mean", "voxels_mean", "voxels_max",
                            "rooms_mean", "rooms_max"])
                self._header_written = True
            w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        self.version, int(self.num_timesteps),
                        round(rew_mean, 3), round(len_mean, 1),
                        round(vox_mean, 2), int(vox_max),
                        round(room_mean, 3), int(room_max)])

        # VecNormalize istatistiklerini taze tut (varsa)
        if self.vn_path is not None:
            vn = self.model.get_vec_normalize_env()
            if vn is not None:
                try:
                    vn.save(str(self.vn_path))
                except Exception:
                    pass


def _obstacle_updater(world_name: str, env_id: int, stop_event: threading.Event) -> None:
    """Main-process daemon thread: updates moving obstacles in sim{env_id} at 10 Hz.

    Runs in the MAIN process (not a SubprocVecEnv worker), so subprocess.run
    here cannot corrupt the worker↔main IPC pipe. Each thread owns one
    GZ_PARTITION so multiple sims stay independent.
    """
    env = {**os.environ, "GZ_PARTITION": f"sim{env_id}"}
    t0 = time.time()
    interval = 0.1  # 10 Hz — smooth enough for T≥5s periods

    while not stop_event.is_set():
        t = time.time() - t0
        for obs in MOVING_OBS:
            phase = 2.0 * math.pi * t / obs["T"]
            x = obs["x0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "x" else 0.0)
            y = obs["y0"] + (obs["amp"] * math.sin(phase) if obs["axis"] == "y" else 0.0)
            req = (f"name: '{obs['name']}', "
                   f"position: {{x: {x:.4f}, y: {y:.4f}, z: {obs['z']:.4f}}}, "
                   f"orientation: {{x: 0, y: 0, z: 0, w: 1}}")
            subprocess.run(
                ["gz", "service", "-s", f"/world/{world_name}/set_pose",
                 "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                 "--timeout", "80", "--req", req],
                env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        stop_event.wait(interval)


def _start_obstacle_updaters(world_name: str, n_envs: int) -> tuple[list[threading.Thread], threading.Event]:
    stop = threading.Event()
    threads = []
    for i in range(n_envs):
        t = threading.Thread(
            target=_obstacle_updater, args=(world_name, i, stop), daemon=True
        )
        t.start()
        threads.append(t)
    print(f"[train_ppo] obstacle updater başlatıldı: {n_envs} sim × {len(MOVING_OBS)} engel")
    return threads, stop


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ppo.yaml",
                        help="Path to PPO YAML config")
    args, _ = parser.parse_known_args(argv)

    cfg = _load_config(args.config)
    env_cfg = cfg["env"]
    ppo_cfg = cfg["ppo"]
    tr_cfg = cfg["train"]

    log_dir = Path(tr_cfg["log_dir"]); log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr_cfg["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb_log = Path(tr_cfg["tb_log"]); tb_log.mkdir(parents=True, exist_ok=True)

    n_envs = int(tr_cfg.get("n_envs", 1))
    factories = [_make_env(env_cfg, i) for i in range(n_envs)]
    if n_envs > 1:
        print(f"[train_ppo] SubprocVecEnv: {n_envs} parallel envs (domain IDs 0..{n_envs-1})")
        vec_env = SubprocVecEnv(factories)
    else:
        vec_env = DummyVecEnv(factories)

    # v6: VecNormalize for obs + reward normalization. Reward magnitudes
    # in this env span ~3 orders of magnitude (idle -0.1 ... floor +200),
    # which gave value-loss spikes and reward oscillation in v3-v5. Running
    # mean/std normalization makes value targets unit-scale and clip_reward
    # caps single-step outliers. Toggle from yaml so older configs still
    # reproduce.
    vn_cfg = tr_cfg.get("vec_normalize", {}) or {}
    use_vn = bool(vn_cfg.get("enabled", False))
    resuming = bool(tr_cfg.get("resume_from"))

    if use_vn:
        vn_pkl = ckpt_dir / "vec_normalize.pkl"
        if resuming and vn_pkl.exists():
            print(f"[train_ppo] VecNormalize: loading stats from {vn_pkl}")
            vec_env = VecNormalize.load(str(vn_pkl), vec_env)
            vec_env.training = True
            vec_env.norm_reward = bool(vn_cfg.get("norm_reward", True))
        else:
            vec_env = VecNormalize(
                vec_env,
                norm_obs=bool(vn_cfg.get("norm_obs", True)),
                norm_reward=bool(vn_cfg.get("norm_reward", True)),
                clip_reward=float(vn_cfg.get("clip_reward", 10.0)),
                gamma=float(ppo_cfg.get("gamma", 0.99)),
            )
        print(f"[train_ppo] VecNormalize enabled: norm_obs="
              f"{vn_cfg.get('norm_obs', True)}, norm_reward="
              f"{vn_cfg.get('norm_reward', True)}, "
              f"clip_reward={vn_cfg.get('clip_reward', 10.0)}")

    if resuming:
        print(f"[train_ppo] resuming from {tr_cfg['resume_from']}")
        model = PPO.load(tr_cfg["resume_from"], env=vec_env,
                         tensorboard_log=str(tb_log))
        # PPO.load restores the saved hyperparameters; override the ones we
        # commonly retune so YAML edits actually take effect on resume.
        new_ent = float(ppo_cfg["ent_coef"])
        if abs(model.ent_coef - new_ent) > 1e-9:
            print(f"[train_ppo] override ent_coef {model.ent_coef} -> {new_ent}")
            model.ent_coef = new_ent
        new_lr = _build_lr(ppo_cfg)
        model.learning_rate = new_lr
        model.policy.optimizer.param_groups[0]["lr"] = float(ppo_cfg["learning_rate"])
        print(f"[train_ppo] override learning_rate -> {ppo_cfg['learning_rate']} ({ppo_cfg.get('lr_schedule','constant')})")
    else:
        model = PPO(
            policy=ppo_cfg["policy"],
            env=vec_env,
            learning_rate=_build_lr(ppo_cfg),
            n_steps=int(ppo_cfg["n_steps"]),
            batch_size=int(ppo_cfg["batch_size"]),
            n_epochs=int(ppo_cfg["n_epochs"]),
            gamma=float(ppo_cfg["gamma"]),
            gae_lambda=float(ppo_cfg["gae_lambda"]),
            clip_range=float(ppo_cfg["clip_range"]),
            ent_coef=float(ppo_cfg["ent_coef"]),
            vf_coef=float(ppo_cfg["vf_coef"]),
            max_grad_norm=float(ppo_cfg["max_grad_norm"]),
            policy_kwargs={"net_arch": ppo_cfg["policy_kwargs"]["net_arch"]},
            tensorboard_log=str(tb_log),
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    ckpt_cb = CheckpointCallback(
        save_freq=int(tr_cfg["save_freq"]),
        save_path=str(ckpt_dir),
        name_prefix="ppo_drone",
    )
    explo_cb = ExplorationLogger(
        log_dir=log_dir,
        version=str(tr_cfg.get("version", "v?")),
        ckpt_dir=ckpt_dir if use_vn else None,
    )
    callbacks = CallbackList([ckpt_cb, explo_cb])

    final = ckpt_dir / "ppo_drone_final.zip"
    target = int(tr_cfg["total_timesteps"])
    if resuming:
        # SB3 with reset_num_timesteps=False treats `total_timesteps` as a
        # *delta* (it adds num_timesteps internally). Convert our YAML
        # convention (target = absolute) to that delta so the run actually
        # stops at the configured target step count.
        remaining = target - int(model.num_timesteps)
        if remaining <= 0:
            print(f"[train_ppo] target {target} already reached "
                  f"(current={model.num_timesteps}); nothing to train")
            return
        print(f"[train_ppo] target={target}, current={model.num_timesteps}, "
              f"training {remaining} more steps")
        learn_steps = remaining
    else:
        learn_steps = target

    obs_threads, obs_stop = _start_obstacle_updaters(env_cfg["world_name"], n_envs)

    try:
        model.learn(total_timesteps=learn_steps,
                    callback=callbacks,
                    progress_bar=True,
                    reset_num_timesteps=not resuming)
    except KeyboardInterrupt:
        # SIGINT (Ctrl-C, `timeout --signal=SIGINT`, manual kill -INT) lands here.
        # Save the live policy so no walltime is lost.
        final = ckpt_dir / "ppo_drone_interrupted.zip"
        print(f"\n[train_ppo] interrupted -> saving current policy to {final}")
    finally:
        obs_stop.set()

    model.save(str(final))
    print(f"[train_ppo] saved model to {final}")
    if use_vn:
        vn_path = ckpt_dir / "vec_normalize.pkl"
        vec_env.save(str(vn_path))
        print(f"[train_ppo] saved VecNormalize stats to {vn_path}")


if __name__ == "__main__":
    main()
