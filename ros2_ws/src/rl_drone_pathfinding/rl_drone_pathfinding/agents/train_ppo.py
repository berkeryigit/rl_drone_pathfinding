"""Train PPO on DroneExplorationEnv. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from rl_drone_pathfinding.envs import DroneExplorationEnv


def _load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _make_env(env_cfg: dict):
    def _factory():
        env = DroneExplorationEnv(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
            seed=env_cfg.get("seed"),
        )
        return Monitor(env)
    return _factory


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

    vec_env = DummyVecEnv([_make_env(env_cfg)])

    if tr_cfg.get("resume_from"):
        print(f"[train_ppo] resuming from {tr_cfg['resume_from']}")
        model = PPO.load(tr_cfg["resume_from"], env=vec_env,
                         tensorboard_log=str(tb_log))
    else:
        model = PPO(
            policy=ppo_cfg["policy"],
            env=vec_env,
            learning_rate=float(ppo_cfg["learning_rate"]),
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

    final = ckpt_dir / "ppo_drone_final.zip"
    try:
        model.learn(total_timesteps=int(tr_cfg["total_timesteps"]),
                    callback=ckpt_cb,
                    progress_bar=True)
    except KeyboardInterrupt:
        # SIGINT (Ctrl-C, `timeout --signal=SIGINT`, manual kill -INT) lands here.
        # Save the live policy so no walltime is lost.
        final = ckpt_dir / "ppo_drone_interrupted.zip"
        print(f"\n[train_ppo] interrupted -> saving current policy to {final}")
    model.save(str(final))
    print(f"[train_ppo] saved model to {final}")


if __name__ == "__main__":
    main()
