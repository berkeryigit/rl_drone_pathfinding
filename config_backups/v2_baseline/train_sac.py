"""Train SAC on DroneExplorationEnv. Reads hyperparameters from a YAML config."""
from __future__ import annotations

import argparse
import csv
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

# ---------- GPU Kurulumu ----------
try:
    import torch

    CUDA_AVAILABLE = torch.cuda.is_available()
    DEVICE = "cuda" if CUDA_AVAILABLE else "cpu"

    if CUDA_AVAILABLE:
        _props = torch.cuda.get_device_properties(0)
        print(f"[train_sac] GPU: {torch.cuda.get_device_name(0)}")
        print(f"[train_sac] VRAM: {_props.total_memory / 1e9:.1f} GB  |  "
              f"SM: {_props.major}.{_props.minor}")
        # CuDNN en hizli conv algoritmasini otomatik sec (sabit boyutlu girdi icin kazanc var)
        torch.backends.cudnn.benchmark = True
        # TF32: Ampere+ (RTX 30xx/40xx) serisinde matmul ~2x hizlanir
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.cuda.empty_cache()
    else:
        print("[train_sac] CUDA bulunamadi, CPU kullaniliyor")

    TORCH_COMPILE = hasattr(torch, "compile")

except ImportError:
    DEVICE = "cpu"
    TORCH_COMPILE = False
    print("[train_sac] PyTorch bulunamadi, CPU kullaniliyor")


# ---------- Callback ----------

class DroneMetricsCallback(BaseCallback):
    """Episode sonunda metrikleri TensorBoard + CSV dosyasina yazar."""

    def __init__(self, csv_path: Path, verbose=0):
        super().__init__(verbose)
        self.csv_path   = csv_path
        self._episode   = 0
        self._ep_reward = 0.0
        self._file      = None
        self._writer    = None

    def _on_training_start(self):
        self._file = open(self.csv_path, "w", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "episode", "timestep", "ep_reward",
            "explored_voxels", "visited_rooms",
            "ent_coef", "actor_loss", "critic_loss",
        ])

    def _on_step(self) -> bool:
        self._ep_reward += float(self.locals.get("rewards", [0])[0])

        for done, info in zip(self.locals.get("dones", []),
                              self.locals.get("infos", [])):
            if done and info:
                self._episode += 1
                ent = self.model.ent_coef_tensor.item() if hasattr(self.model, "ent_coef_tensor") else 0
                a_l = float(self.logger.name_to_value.get("train/actor_loss",  0))
                c_l = float(self.logger.name_to_value.get("train/critic_loss", 0))

                # Monitor en ictedir; episode["r"] HAM odul (VecNormalize'dan etkilenmez).
                # Boylece CSV/grafikler normalize edilmemis gercek odulu gosterir.
                ep_info = info.get("episode")
                ep_reward = float(ep_info["r"]) if ep_info else self._ep_reward

                self._writer.writerow([
                    self._episode,
                    self.num_timesteps,
                    round(ep_reward, 2),
                    info.get("explored_voxels", 0),
                    info.get("visited_rooms",   0),
                    round(ent, 4),
                    round(a_l, 4),
                    round(c_l, 4),
                ])

                self.logger.record("drone/explored_voxels", info.get("explored_voxels", 0))
                self.logger.record("drone/visited_rooms",   info.get("visited_rooms",   0))
                self.logger.dump(self.num_timesteps)
                self._ep_reward = 0.0
        return True

    def _on_training_end(self):
        if self._file:
            self._file.close()


# ---------- Yardimci ----------

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


def _apply_torch_compile(model, use_sde: bool = False) -> None:
    """torch.compile destekleniyorsa critic'i derle (PyTorch 2.0+).

    use_sde=True oldugunda actor derlenmez: SDE her sde_sample_freq adimda yeni
    exploration_mat uretir → dynamo cache_size_limit'e carpar → warning + yavaslama.
    """
    if not TORCH_COMPILE or DEVICE == "cpu":
        return
    try:
        import torch
        if not use_sde:
            model.policy.actor = torch.compile(model.policy.actor, mode="reduce-overhead")
        model.policy.critic  = torch.compile(model.policy.critic,  mode="reduce-overhead")
        model.policy.critic_target = torch.compile(
            model.policy.critic_target, mode="reduce-overhead"
        )
        compiled = "critic + critic_target" if use_sde else "actor + critic + critic_target"
        print(f"[train_sac] torch.compile aktif ({compiled})")
    except Exception as e:
        print(f"[train_sac] torch.compile basarisiz, devam ediliyor: {e}")


# ---------- Ana ----------

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
        model = SAC.load(
            tr_cfg["resume_from"],
            env=vec_env,
            tensorboard_log=str(tb_log),
            device=DEVICE,
        )
    else:
        train_freq = sac_cfg["train_freq"]

        # gradient_steps=-1: her toplanan ornek icin 1 guncelleme adimi
        # gradient_steps>1 : GPU'ya daha fazla is yükle
        gs_raw = sac_cfg["gradient_steps"]
        gradient_steps = int(gs_raw) if gs_raw != "auto" else -1

        policy_kwargs = {"net_arch": sac_cfg["policy_kwargs"]["net_arch"]}
        # Buyuk aglarda optimizer icin 64-bit bellek hizalamasini zorla
        if CUDA_AVAILABLE:
            policy_kwargs["optimizer_kwargs"] = {"eps": 1e-5}

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
            gradient_steps=gradient_steps,
            ent_coef=sac_cfg["ent_coef"],
            target_entropy=sac_cfg["target_entropy"],
            use_sde=bool(sac_cfg.get("use_sde", False)),
            optimize_memory_usage=bool(sac_cfg.get("optimize_memory_usage", False)),
            policy_kwargs=policy_kwargs,
            tensorboard_log=str(tb_log),
            device=DEVICE,
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    _apply_torch_compile(model, use_sde=bool(sac_cfg.get("use_sde", False)))

    if CUDA_AVAILABLE:
        import torch
        allocated = torch.cuda.memory_allocated(0) / 1e6
        print(f"[train_sac] GPU bellek kullanimi (model sonrasi): {allocated:.1f} MB")

    callbacks = CallbackList([
        CheckpointCallback(
            save_freq=int(tr_cfg["save_freq"]),
            save_path=str(ckpt_dir),
            name_prefix="sac_drone",
        ),
        EvalCallback(
            eval_env,
            best_model_save_path=str(best_dir),
            log_path=str(log_dir / "eval_logs"),
            eval_freq=int(tr_cfg.get("eval_freq", 20000)),
            n_eval_episodes=int(tr_cfg.get("n_eval_episodes", 5)),
            deterministic=False,   # gercek eval de stochastic — best_model'i ayni moda gore sec
            render=False,
            verbose=1,
        ),
        DroneMetricsCallback(csv_path=log_dir / "training_log.csv"),
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
