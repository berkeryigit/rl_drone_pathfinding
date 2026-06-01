"""Train DQN on DroneExplorationEnvDiscrete. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack

from rl_drone_pathfinding.envs import DroneExplorationEnvDiscrete


def _load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _make_env(env_cfg: dict, log_dir: Path):
    def _factory():
        env = DroneExplorationEnvDiscrete(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
            seed=env_cfg.get("seed"),
        )
        return Monitor(env, str(log_dir), info_keywords=("explored_voxels", "visited_rooms"))
    return _factory


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dqn.yaml",
                        help="Path to DQN YAML config")
    args, _ = parser.parse_known_args(argv)

    cfg = _load_config(args.config)
    env_cfg = cfg["env"]
    dqn_cfg = cfg["dqn"]
    tr_cfg = cfg["train"]

    log_dir = Path(tr_cfg["log_dir"]); log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr_cfg["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb_log = Path(tr_cfg["tb_log"]); tb_log.mkdir(parents=True, exist_ok=True)

    vec_env = DummyVecEnv([_make_env(env_cfg, log_dir)])
    vec_env = VecFrameStack(vec_env, n_stack=4)

    if tr_cfg.get("resume_from"):
        print(f"[train_dqn] resuming from {tr_cfg['resume_from']}")
        model = DQN.load(tr_cfg["resume_from"], env=vec_env,
                         tensorboard_log=str(tb_log))
        
        # Load replay buffer if exists (DQN specific)
        buffer_path = tr_cfg["resume_from"].replace(".zip", "_replay_buffer.pkl")
        if os.path.exists(buffer_path):
            model.load_replay_buffer(buffer_path)
            print(f"[train_dqn] loaded replay buffer from {buffer_path}")
        else:
            print(f"[train_dqn] warning: no replay buffer found at {buffer_path}")
    else:
        model = DQN(
            policy=dqn_cfg.get("policy", "MlpPolicy"),
            env=vec_env,
            learning_rate=float(dqn_cfg["learning_rate"]),
            buffer_size=int(dqn_cfg["buffer_size"]),
            learning_starts=int(dqn_cfg["learning_starts"]),
            batch_size=int(dqn_cfg["batch_size"]),
            tau=float(dqn_cfg["tau"]),
            gamma=float(dqn_cfg["gamma"]),
            train_freq=int(dqn_cfg["train_freq"]),
            gradient_steps=int(dqn_cfg["gradient_steps"]),
            target_update_interval=int(dqn_cfg["target_update_interval"]),
            exploration_fraction=float(dqn_cfg["exploration_fraction"]),
            exploration_initial_eps=float(dqn_cfg["exploration_initial_eps"]),
            exploration_final_eps=float(dqn_cfg["exploration_final_eps"]),
            policy_kwargs={"net_arch": dqn_cfg["policy_kwargs"]["net_arch"]},
            tensorboard_log=str(tb_log),
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    ckpt_cb = CheckpointCallback(
        save_freq=int(tr_cfg["save_freq"]),
        save_path=str(ckpt_dir),
        name_prefix="dqn_drone",
    )

    final = ckpt_dir / "dqn_drone_final.zip"
    try:
        model.learn(total_timesteps=int(tr_cfg["total_timesteps"]),
                    callback=ckpt_cb,
                    progress_bar=True)
    except KeyboardInterrupt:
        # SIGINT (Ctrl-C, `timeout --signal=SIGINT`, manual kill -INT) lands here.
        # Save the live policy so no walltime is lost.
        final = ckpt_dir / "dqn_drone_interrupted.zip"
        print(f"\n[train_dqn] interrupted -> saving current policy to {final}")
    
    model.save(str(final))
    print(f"[train_dqn] saved model to {final}")
    
    try:
        buffer_path = str(final).replace(".zip", "_replay_buffer.pkl")
        model.save_replay_buffer(buffer_path)
        print(f"[train_dqn] saved replay buffer to {buffer_path}")
    except Exception as e:
        print(f"[train_dqn] warning: could not save replay buffer: {e}")


if __name__ == "__main__":
    main()
