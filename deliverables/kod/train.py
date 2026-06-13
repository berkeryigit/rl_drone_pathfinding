"""
train.py — DQN ile Fast2DDroneExplorationEnv eğitimi
=====================================================
Kullanım:
    python train.py                              # config.yaml'dan oku
    python train.py --config config.yaml --seed 42
    python train.py --seed 7 --timesteps 500000

Çıktı:
    runs/<seed>/model_final.zip       ← eğitilmiş model
    runs/<seed>/logs/progress.csv     ← SB3 Monitor logu
    runs/<seed>/training_log.csv      ← episode bazlı özel log
    runs/<seed>/run_meta.json         ← seed, config, versiyon bilgisi
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.logger import configure

# ---------------------------------------------------------------------------
# CUDA otomatik tespiti
# ---------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ---------------------------------------------------------------------------
# env paketi bu dosyayla aynı klasörde
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from env import Fast2DDroneExplorationEnv, Fast2DConfig


# ---------------------------------------------------------------------------
# Özel loglama callback'i
# ---------------------------------------------------------------------------
class EpisodeLogger(BaseCallback):
    """Her episode sonunda episode_reward ve diğer metrikleri CSV'ye yazar."""

    def __init__(self, log_path: str, verbose: int = 0):
        super().__init__(verbose)
        self._log_path = log_path
        self._episode = 0
        self._file = None
        self._writer = None

    def _on_training_start(self) -> None:
        self._file = open(self._log_path, "w", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "episode", "timestep", "episode_reward",
            "episode_length", "visited_rooms", "explored_pct",
        ])

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if "episode" in info:
                ep = info["episode"]
                self._episode += 1
                rooms = info.get("visited_rooms", 0)
                explored = info.get("explored_voxels", 0) / (32 * 32) * 100
                self._writer.writerow([
                    self._episode,
                    self.num_timesteps,
                    round(ep["r"], 4),
                    ep["l"],
                    rooms,
                    round(explored, 2),
                ])
        return True

    def _on_training_end(self) -> None:
        if self._file:
            self._file.close()


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------
def _load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _make_env(env_cfg: dict, seed: int):
    """Monitor sarılı env factory."""
    def _factory():
        cfg = Fast2DConfig(
            dt=env_cfg.get("dt", 0.12),
            max_episode_steps=env_cfg.get("max_episode_steps", 600),
            lidar_noise_std=env_cfg.get("lidar_noise_std", 0.015),
            odom_noise_std=env_cfg.get("odom_noise_std", 0.004),
            wind_std=env_cfg.get("wind_std", 0.015),
            collision_penalty=env_cfg.get("collision_penalty", -40.0),
            all_rooms_bonus=env_cfg.get("all_rooms_bonus", 60.0),
            random_start=env_cfg.get("random_start", True),
        )
        env = Fast2DDroneExplorationEnv(config=cfg, seed=seed)
        return Monitor(env)
    return _factory


# ---------------------------------------------------------------------------
# Ana eğitim fonksiyonu
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="DQN eğitimi")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed (config'deki değeri ezer)")
    parser.add_argument("--timesteps", type=int, default=None,
                        help="Toplam adım (config'deki değeri ezer)")
    args, _ = parser.parse_known_args(argv)

    cfg = _load_config(args.config)
    env_cfg  = cfg["env"]
    dqn_cfg  = cfg["dqn"]
    tr_cfg   = cfg["train"]

    seed = args.seed if args.seed is not None else int(tr_cfg.get("seed", 42))
    total_timesteps = args.timesteps if args.timesteps is not None \
                      else int(tr_cfg["total_timesteps"])

    # Çıktı dizini
    run_dir = Path(__file__).parent.parent / "sonuclar" / "loglar" / f"seed_{seed}"
    log_dir = run_dir / "logs"
    ckpt_dir = run_dir / "checkpoints"
    for d in [log_dir, ckpt_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Discrete action wrapper
    import gymnasium as gym

    class DiscreteActionWrapper(gym.ActionWrapper):
        """Sürekli [vx,vy,wz] uzayını 9 discrete aksiyona indirger."""
        ACTIONS = [
            [ 1.0,  0.0,  0.0],  # 0: ileri
            [-1.0,  0.0,  0.0],  # 1: geri
            [ 0.0,  1.0,  0.0],  # 2: sola
            [ 0.0, -1.0,  0.0],  # 3: sağa
            [ 0.0,  0.0,  1.0],  # 4: sola dön
            [ 0.0,  0.0, -1.0],  # 5: sağa dön
            [ 1.0,  0.0,  1.0],  # 6: ileri + sola dön
            [ 1.0,  0.0, -1.0],  # 7: ileri + sağa dön
            [ 0.0,  0.0,  0.0],  # 8: dur
        ]
        def __init__(self, env):
            super().__init__(env)
            self.action_space = gym.spaces.Discrete(len(self.ACTIONS))

        def action(self, act: int) -> np.ndarray:
            return np.array(self.ACTIONS[act], dtype=np.float32)

    def _make_discrete_env():
        raw = _make_env(env_cfg, seed)()
        return DiscreteActionWrapper(raw)

    vec_env = DummyVecEnv([_make_discrete_env])

    # Model oluştur / devam ettir
    resume_from = tr_cfg.get("resume_from")
    if resume_from and Path(resume_from).exists():
        print(f"[train] Devam ediliyor: {resume_from}")
        model = DQN.load(resume_from, env=vec_env)
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
            tensorboard_log=str(log_dir),
            device=DEVICE,          # otomatik CUDA/CPU seçimi
            verbose=1,
            seed=seed,
        )
    
    # Logger yapılandırması (CSV ve Tensorboard)
    new_logger = configure(str(log_dir), ["stdout", "csv", "tensorboard"])
    model.set_logger(new_logger)

    # Callback'ler
    ckpt_cb = CheckpointCallback(
        save_freq=int(tr_cfg.get("save_freq", 50000)),
        save_path=str(ckpt_dir),
        name_prefix="dqn_drone",
    )
    ep_logger = EpisodeLogger(str(run_dir / "training_log.csv"))

    # Meta bilgi kaydet
    meta = {
        "seed": seed,
        "total_timesteps": total_timesteps,
        "config_file": args.config,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "dqn_config": dqn_cfg,
        "env_config": env_cfg,
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Cihaz bilgisi
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[train] ✅ CUDA aktif → {gpu_name}")
    else:
        print("[train] ⚠️  CUDA bulunamadı → CPU kullanılıyor")
    print(f"[train] seed={seed} | timesteps={total_timesteps:,} | cihaz={DEVICE} | çıktı={run_dir}")

    # Eğitim
    final_path = ckpt_dir / "dqn_drone_final.zip"
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=[ckpt_cb, ep_logger],
            progress_bar=True,
            log_interval=100,
        )
    except KeyboardInterrupt:
        final_path = ckpt_dir / "dqn_drone_interrupted.zip"
        print(f"\n[train] Kesildi → {final_path}")

    model.save(str(final_path))
    print(f"[train] Model kaydedildi: {final_path}")

    vec_env.close()


if __name__ == "__main__":
    main()
