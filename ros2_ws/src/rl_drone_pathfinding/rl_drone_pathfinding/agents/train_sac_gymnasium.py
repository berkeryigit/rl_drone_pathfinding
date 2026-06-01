"""Gymnasium-first SAC trainer for the existing Gazebo-backed environment.

This entry point mirrors the lightweight trainer in the sibling rl_drone
project, but it still uses DroneExplorationEnv unchanged. It assumes Gazebo and
the ROS bridge are already running; use scripts/train_sac.sh when you want the
simulator started automatically.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.vec_env import DummyVecEnv

from rl_drone_pathfinding.agents.train_sac import (
    DEVICE,
    DroneMetricsCallback,
    _apply_torch_compile,
    _load_config,
    _make_env,
)


def _override_config(cfg: dict, args: argparse.Namespace) -> dict:
    cfg = {
        "env": dict(cfg["env"]),
        "sac": dict(cfg["sac"]),
        "train": dict(cfg["train"]),
    }
    if args.timesteps is not None:
        cfg["train"]["total_timesteps"] = args.timesteps
    if args.out is not None:
        out = Path(args.out)
        cfg["train"]["log_dir"] = str(out)
        cfg["train"]["ckpt_dir"] = str(out / "checkpoints")
        cfg["train"]["tb_log"] = str(out / "tb")
    if args.resume_from is not None:
        cfg["train"]["resume_from"] = str(args.resume_from)
    if args.seed is not None:
        cfg["env"]["seed"] = args.seed
    if args.no_obstacles:
        cfg["env"]["manage_obstacles"] = False
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/sac.yaml")
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--resume-from", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument("--no-obstacles", action="store_true")
    args, _ = parser.parse_known_args(argv)

    cfg = _override_config(_load_config(args.config), args)
    env_cfg = cfg["env"]
    sac_cfg = cfg["sac"]
    tr_cfg = cfg["train"]

    log_dir = Path(tr_cfg["log_dir"])
    ckpt_dir = Path(tr_cfg["ckpt_dir"])
    tb_log = Path(tr_cfg["tb_log"])
    best_dir = ckpt_dir / "best"
    for path in (log_dir, ckpt_dir, tb_log, best_dir):
        path.mkdir(parents=True, exist_ok=True)

    env = DummyVecEnv([_make_env(env_cfg)])

    if tr_cfg.get("resume_from"):
        model = SAC.load(
            tr_cfg["resume_from"],
            env=env,
            tensorboard_log=str(tb_log),
            device=DEVICE,
        )
    else:
        train_freq = sac_cfg["train_freq"]
        gs_raw = sac_cfg["gradient_steps"]
        gradient_steps = int(gs_raw) if gs_raw != "auto" else -1
        model = SAC(
            policy=sac_cfg["policy"],
            env=env,
            learning_rate=float(sac_cfg["learning_rate"]),
            buffer_size=int(sac_cfg["buffer_size"]),
            learning_starts=int(sac_cfg["learning_starts"]),
            batch_size=int(sac_cfg["batch_size"]),
            tau=float(sac_cfg["tau"]),
            gamma=float(sac_cfg["gamma"]),
            train_freq=(int(train_freq[0]), str(train_freq[1])),
            gradient_steps=gradient_steps,
            target_update_interval=int(sac_cfg.get("target_update_interval", 1)),
            ent_coef=sac_cfg["ent_coef"],
            target_entropy=sac_cfg["target_entropy"],
            use_sde=bool(sac_cfg.get("use_sde", False)),
            optimize_memory_usage=bool(sac_cfg.get("optimize_memory_usage", False)),
            policy_kwargs={"net_arch": sac_cfg["policy_kwargs"]["net_arch"]},
            tensorboard_log=str(tb_log),
            device=DEVICE,
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    model.set_logger(configure(str(log_dir / "logs"), ["stdout", "csv", "tensorboard"]))

    if bool(sac_cfg.get("torch_compile", False)):
        _apply_torch_compile(model, use_sde=bool(sac_cfg.get("use_sde", False)))

    callbacks = [
        CheckpointCallback(
            save_freq=int(tr_cfg["save_freq"]),
            save_path=str(ckpt_dir),
            name_prefix="sac_drone_gym",
        ),
        DroneMetricsCallback(csv_path=log_dir / "training_log.csv"),
    ]
    eval_env = None
    if not args.no_eval:
        eval_env_cfg = dict(env_cfg)
        eval_env_cfg["eval_mode"] = True
        eval_env_cfg["manage_obstacles"] = False
        eval_env = DummyVecEnv([_make_env(eval_env_cfg)])
        callbacks.append(
            EvalCallback(
                eval_env,
                best_model_save_path=str(best_dir),
                log_path=str(log_dir / "eval_logs"),
                eval_freq=int(tr_cfg.get("eval_freq", 20000)),
                n_eval_episodes=int(tr_cfg.get("n_eval_episodes", 5)),
                deterministic=False,
                render=False,
                verbose=1,
            )
        )

    final = ckpt_dir / "sac_drone_gym_final.zip"
    try:
        model.learn(
            total_timesteps=int(tr_cfg["total_timesteps"]),
            callback=CallbackList(callbacks),
            progress_bar=True,
        )
    except KeyboardInterrupt:
        final = ckpt_dir / "sac_drone_gym_interrupted.zip"
        print(f"\n[train_sac_gymnasium] interrupted -> saving to {final}")
    finally:
        env.close()
        if eval_env is not None:
            eval_env.close()

    model.save(str(final))
    print(f"[train_sac_gymnasium] model kaydedildi: {final}")
    print(f"[train_sac_gymnasium] en iyi model:     {best_dir}/best_model.zip")


if __name__ == "__main__":
    main()
