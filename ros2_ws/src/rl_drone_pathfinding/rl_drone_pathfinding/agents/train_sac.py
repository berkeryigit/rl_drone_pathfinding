"""Train SAC on DroneExplorationEnv. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CallbackList,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from rl_drone_pathfinding.envs import DroneExplorationEnv


class DroneMetricsCallback(BaseCallback):
    """Episode sonunda drone metriklerini TensorBoard'a yazar."""

    def _on_step(self) -> bool:
        for done, info in zip(self.locals.get("dones", []),
                              self.locals.get("infos", [])):
            if done and info:
                self.logger.record("drone/explored_voxels", info.get("explored_voxels", 0))
                self.logger.record("drone/visited_rooms",   info.get("visited_rooms", 0))
                self.logger.record("drone/visited_floors",  info.get("visited_floors", 0))
                self.logger.dump(self.num_timesteps)
        return True


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
    parser.add_argument("--config", default="configs/sac.yaml")
    args, _ = parser.parse_known_args(argv)

    cfg     = _load_config(args.config)
    env_cfg = cfg["env"]
    sac_cfg = cfg["sac"]
    tr_cfg  = cfg["train"]

    log_dir  = Path(tr_cfg["log_dir"]);  log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr_cfg["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb_log   = Path(tr_cfg["tb_log"]);   tb_log.mkdir(parents=True, exist_ok=True)
    best_dir = ckpt_dir / "best";        best_dir.mkdir(parents=True, exist_ok=True)

    vec_env  = DummyVecEnv([_make_env(env_cfg)])
    eval_env = DummyVecEnv([_make_env(env_cfg)])

    if tr_cfg.get("resume_from"):
        print(f"[train_sac] resuming from {tr_cfg['resume_from']}")
        model = SAC.load(tr_cfg["resume_from"], env=vec_env,
                         tensorboard_log=str(tb_log))
    else:
        train_freq = sac_cfg["train_freq"]
        model = SAC(
            policy=sac_cfg["policy"],
            env=vec_env,
            learning_rate=float(sac_cfg["learning_rate"]),
            buffer_size=int(sac_cfg["buffer_size"]),
            learning_starts=int(sac_cfg["learning_starts"]),
            batch_size=int(sac_cfg["batch_size"]),
            tau=float(sac_cfg["tau"]),
            gamma=float(sac_cfg["gamma"]),
            train_freq=(int(train_freq[0]), str(train_freq[1])),
            gradient_steps=int(sac_cfg["gradient_steps"]),
            ent_coef=sac_cfg["ent_coef"],
            target_entropy=sac_cfg["target_entropy"],
            use_sde=bool(sac_cfg.get("use_sde", False)),
            policy_kwargs={"net_arch": sac_cfg["policy_kwargs"]["net_arch"]},
            tensorboard_log=str(tb_log),
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    callbacks = CallbackList([
        # Her 10k step'te checkpoint
        CheckpointCallback(
            save_freq=int(tr_cfg["save_freq"]),
            save_path=str(ckpt_dir),
            name_prefix="sac_drone",
        ),
        # Her 20k step'te 5 episode eval, en iyisini best/best_model.zip'e kaydet
        EvalCallback(
            eval_env,
            best_model_save_path=str(best_dir),
            log_path=str(log_dir / "eval_logs"),
            eval_freq=int(tr_cfg.get("eval_freq", 20000)),
            n_eval_episodes=int(tr_cfg.get("n_eval_episodes", 5)),
            deterministic=True,
            render=False,
            verbose=1,
        ),
        # Drone metriklerini TensorBoard'a yaz
        DroneMetricsCallback(),
    ])

    final = ckpt_dir / "sac_drone_final.zip"
    try:
        model.learn(
            total_timesteps=int(tr_cfg["total_timesteps"]),
            callback=callbacks,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        final = ckpt_dir / "sac_drone_interrupted.zip"
        print(f"\n[train_sac] interrupted -> saving to {final}")
    model.save(str(final))
    print(f"[train_sac] model kaydedildi: {final}")
    print(f"[train_sac] en iyi model:     {best_dir}/best_model.zip")


if __name__ == "__main__":
    main()
