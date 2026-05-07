"""Train PPO on DroneExplorationEnv. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from rl_drone_pathfinding.envs import DroneExplorationEnv


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

    # v6: VecNormalize for obs + reward normalization. Reward magnitudes
    # in this env span ~3 orders of magnitude (idle -0.1 ... floor +200),
    # which gave value-loss spikes and reward oscillation in v3-v5. Running
    # mean/std normalization makes value targets unit-scale and clip_reward
    # caps single-step outliers. Toggle from yaml so older configs still
    # reproduce.
    vn_cfg = tr_cfg.get("vec_normalize", {}) or {}
    use_vn = bool(vn_cfg.get("enabled", False))
    if use_vn:
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

    resuming = bool(tr_cfg.get("resume_from"))
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

    try:
        model.learn(total_timesteps=learn_steps,
                    callback=ckpt_cb,
                    progress_bar=True,
                    reset_num_timesteps=not resuming)
    except KeyboardInterrupt:
        # SIGINT (Ctrl-C, `timeout --signal=SIGINT`, manual kill -INT) lands here.
        # Save the live policy so no walltime is lost.
        final = ckpt_dir / "ppo_drone_interrupted.zip"
        print(f"\n[train_ppo] interrupted -> saving current policy to {final}")
    model.save(str(final))
    print(f"[train_ppo] saved model to {final}")
    if use_vn:
        vn_path = ckpt_dir / "vec_normalize.pkl"
        vec_env.save(str(vn_path))
        print(f"[train_ppo] saved VecNormalize stats to {vn_path}")


if __name__ == "__main__":
    main()
