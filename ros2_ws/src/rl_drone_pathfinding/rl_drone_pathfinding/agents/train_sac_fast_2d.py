from __future__ import annotations

import argparse
import csv
from pathlib import Path

from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback, EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from rl_drone_pathfinding.envs.fast_2d_drone_env import (
    Fast2DConfig, Fast2DDroneExplorationEnv, N_ROOMS, GRID_NXY, LIDAR_MAX,
)

_TOTAL_CELLS = GRID_NXY * GRID_NXY


try:
    import torch

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"


class Fast2DMetricsCallback(BaseCallback):
    def __init__(self, csv_path: Path, verbose: int = 0):
        super().__init__(verbose)
        self.csv_path = csv_path
        self._episode = 0
        self._ep_reward = 0.0
        self._file = None
        self._writer = None

    def _on_training_start(self):
        self._file = open(self.csv_path, "w", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "episode", "timestep", "ep_reward", "steps",
            "explored_voxels", "coverage_pct", "visited_rooms", "success", "crashed",
            "min_lidar", "ent_coef", "actor_loss", "critic_loss",
        ])

    def _on_step(self) -> bool:
        for done, info in zip(self.locals.get("dones", []), self.locals.get("infos", [])):
            if not done:
                continue
            self._episode += 1
            ep_info = info.get("episode")
            ep_reward = float(ep_info["r"]) if ep_info else 0.0
            ep_len    = int(ep_info["l"]) if ep_info else 0

            voxels  = int(info.get("explored_voxels", 0))
            rooms   = int(info.get("visited_rooms", 0))
            cover   = round(voxels / _TOTAL_CELLS * 100.0, 1)
            success = int(rooms >= N_ROOMS)
            crash   = int(bool(info.get("collision", False)))
            min_lid = round(float(info.get("min_lidar", LIDAR_MAX)), 3)

            ent = self.model.ent_coef_tensor.item() if hasattr(self.model, "ent_coef_tensor") else 0.0
            a_l = float(self.logger.name_to_value.get("train/actor_loss",  0.0))
            c_l = float(self.logger.name_to_value.get("train/critic_loss", 0.0))

            self._writer.writerow([
                self._episode, self.num_timesteps, round(ep_reward, 2), ep_len,
                voxels, cover, rooms, success, crash,
                min_lid, round(ent, 4), round(a_l, 4), round(c_l, 4),
            ])

            self.logger.record("fast_2d/explored_voxels", voxels)
            self.logger.record("fast_2d/coverage_pct", cover)
            self.logger.record("fast_2d/visited_rooms", rooms)
            self.logger.record("fast_2d/success", success)
            self.logger.record("fast_2d/crashed", crash)
        return True

    def _on_training_end(self):
        if self._file:
            self._file.close()


def build_env(max_steps: int, seed: int | None):
    def _make():
        cfg = Fast2DConfig(max_episode_steps=max_steps, random_start=True)
        return Monitor(Fast2DDroneExplorationEnv(config=cfg, seed=seed))

    return _make


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=300_000)
    parser.add_argument("--num-envs", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("runs/sac_fast_2d"))
    parser.add_argument("--no-eval", action="store_true")
    args, _ = parser.parse_known_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "checkpoints").mkdir(parents=True, exist_ok=True)
    (args.out / "logs").mkdir(parents=True, exist_ok=True)

    env = make_vec_env(
        build_env(args.max_steps, args.seed),
        n_envs=max(1, args.num_envs),
        vec_env_cls=SubprocVecEnv if args.num_envs > 1 else DummyVecEnv,
    )

    eval_env = None
    callbacks = [
        CheckpointCallback(
            save_freq=max(10_000 // max(1, args.num_envs), 1),
            save_path=str(args.out / "checkpoints"),
            name_prefix="sac_fast_2d",
        ),
        Fast2DMetricsCallback(args.out / "training_log.csv"),
    ]
    if not args.no_eval:
        eval_env = Monitor(Fast2DDroneExplorationEnv(
            config=Fast2DConfig(max_episode_steps=args.max_steps, random_start=True),
            seed=args.seed + 1000,
        ))
        callbacks.append(
            EvalCallback(
                eval_env,
                best_model_save_path=str(args.out / "best"),
                log_path=str(args.out / "eval"),
                eval_freq=max(5_000 // max(1, args.num_envs), 1),
                n_eval_episodes=5,
                deterministic=False,
            )
        )

    model = SAC(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        # --- hiz / replay buffer: uzun egitim + yuksek throughput ---
        buffer_size=600_000,           # 250k -> 600k (100k+ step icin yeterli replay)
        batch_size=512,                # 256 -> 512 (GPU verimliligi)
        learning_starts=10_000,
        tau=0.02,
        gamma=0.98,
        train_freq=(32, "step"),       # burst toplama: 32 vec-step -> Python dongu yuku azalir
        gradient_steps=32,             # ~1:8 update:data orani (hizli + ogrenme dengeli)
        ent_coef="auto",
        policy_kwargs={"net_arch": [256, 256]},
        tensorboard_log=str(args.out / "tb"),
        verbose=1,
        seed=args.seed,
        device=DEVICE,
    )
    model.set_logger(configure(str(args.out / "logs"), ["stdout", "csv", "tensorboard"]))

    try:
        model.learn(total_timesteps=args.timesteps, callback=callbacks, progress_bar=True)
    except KeyboardInterrupt:
        model.save(args.out / "interrupted_model")
        raise
    finally:
        env.close()
        if eval_env is not None:
            eval_env.close()

    model.save(args.out / "final_model")
    print(f"[train_sac_fast_2d] final model: {args.out / 'final_model.zip'}")


if __name__ == "__main__":
    main()
