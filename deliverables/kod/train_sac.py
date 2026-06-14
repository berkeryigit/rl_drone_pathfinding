"""2D Gymnasium ortaminda SAC egitimi (tek seed) -- PPO ile ADIL KIYAS icin.

Bu script, PPO train.py ile BIREBIR AYNI ortami (env/fast_2d_drone_env.py,
md5 ozdes), AYNI eval protokolunu (deterministik EvalCallback) ve AYNI CSV log
semasini kullanir. Tek fark algoritmadir: SAC (off-policy, replay buffer'li,
entropi maksimizasyonlu aktor-kritik). Hiperparametreler, ekipteki SAC teslimi
(M. A. Albayrak, 220202082) raporundaki degerlerle ayni secilmistir:

    learning_rate = 3e-4, gamma = 0.98, buffer_size = 600000, batch_size = 512,
    learning_starts = 10000, tau = 0.02, train_freq = 32, gradient_steps = 32,
    ent_coef = auto, net_arch = [256, 256].

Amac: ayni env + ayni 5 seed + ayni protokolle PPO (on-policy) ile SAC
(off-policy) arasinda ornek-verimliligi / final performans karsilastirmasi.
CSV semasi PPO ile ayni oldugundan plot_results.py degismeden okur:
SAC icin actor_loss = train/actor_loss, critic_loss = train/critic_loss.

Kullanim:
    python3 train_sac.py --seed 7 --timesteps 600000
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import (
    BaseCallback, CheckpointCallback, EvalCallback,
)
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env.fast_2d_drone_env import (  # noqa: E402
    Fast2DConfig, Fast2DDroneExplorationEnv, N_ROOMS, GRID_NXY, LIDAR_MAX,
)

_TOTAL_CELLS = GRID_NXY * GRID_NXY

# SAC hiperparametreleri (ekip SAC teslimi ile ayni). Tek kaynak: bu dict.
SAC_HP = dict(
    learning_rate=3.0e-4,
    buffer_size=600_000,
    batch_size=512,
    learning_starts=10_000,
    tau=0.02,
    gamma=0.98,
    train_freq=32,
    gradient_steps=32,
    ent_coef="auto",
    net_arch=[256, 256],
)


class Fast2DMetricsCallback(BaseCallback):
    """Her episode bittiginde EPISODE GETIRISI + kesif metriklerini CSV'e yazar.

    PPO callback'i ile AYNI sema; SAC icin actor_loss = train/actor_loss,
    critic_loss = train/critic_loss (rollout sirasinda son guncellemenin degeri
    tasinir -- carry-forward).
    """

    def __init__(self, csv_path: Path, ent_coef_label: float, verbose: int = 0):
        super().__init__(verbose)
        self.csv_path = csv_path
        self._ent_label = float(ent_coef_label)
        self._episode = 0
        self._file = None
        self._writer = None
        self._last_a_l = 0.0
        self._last_c_l = 0.0

    def _on_training_start(self) -> None:
        header = [
            "episode", "timestep", "ep_return", "steps",
            "explored_voxels", "coverage_pct", "visited_rooms", "success", "crashed",
            "min_lidar", "ent_coef", "actor_loss", "critic_loss",
        ]
        self._file = open(self.csv_path, "w", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        self._writer.writerow(header)

    def _on_step(self) -> bool:
        a_now = self.logger.name_to_value.get("train/actor_loss", None)
        c_now = self.logger.name_to_value.get("train/critic_loss", None)
        if a_now is not None:
            self._last_a_l = float(a_now)
        if c_now is not None:
            self._last_c_l = float(c_now)

        for done, info in zip(self.locals.get("dones", []), self.locals.get("infos", [])):
            if not done:
                continue
            self._episode += 1
            ep_info = info.get("episode")
            ep_return = float(ep_info["r"]) if ep_info else 0.0
            ep_len = int(ep_info["l"]) if ep_info else 0
            voxels = int(info.get("explored_voxels", 0))
            rooms = int(info.get("visited_rooms", 0))
            cover = round(voxels / _TOTAL_CELLS * 100.0, 1)
            success = int(rooms >= N_ROOMS)
            crash = int(bool(info.get("collision", False)))
            min_lid = round(float(info.get("min_lidar", LIDAR_MAX)), 3)
            self._writer.writerow([
                self._episode, self.num_timesteps, round(ep_return, 2), ep_len,
                voxels, cover, rooms, success, crash,
                min_lid, round(self._ent_label, 4),
                round(self._last_a_l, 4), round(self._last_c_l, 4),
            ])
        return True

    def _on_training_end(self) -> None:
        if self._file:
            self._file.close()


def _make_cfg(env_cfg: dict) -> Fast2DConfig:
    return Fast2DConfig(
        max_episode_steps=int(env_cfg["max_episode_steps"]),
        random_start=bool(env_cfg["random_start"]),
        lidar_noise_std=float(env_cfg["lidar_noise_std"]),
        odom_noise_std=float(env_cfg["odom_noise_std"]),
        wind_std=float(env_cfg["wind_std"]),
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="2D SAC egitimi (PPO ile adil kiyas)")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--timesteps", type=int, default=600_000)
    parser.add_argument("--out", type=Path, default=None, help="varsayilan: runs_sac/seed_<N>")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-eval", action="store_true")
    args = parser.parse_args(argv)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    env_cfg, train_cfg = cfg["env"], cfg["train"]

    out = args.out or Path("runs_sac") / f"seed_{args.seed}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "checkpoints").mkdir(exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)

    # SAC: tek ortam (kanonik off-policy kurulum). Ortam/seed/eval PPO ile ayni.
    env = make_vec_env(
        lambda: Monitor(Fast2DDroneExplorationEnv(config=_make_cfg(env_cfg), seed=args.seed)),
        n_envs=1, vec_env_cls=DummyVecEnv,
    )

    callbacks: list[BaseCallback] = [
        CheckpointCallback(save_freq=50_000, save_path=str(out / "checkpoints"), name_prefix="sac_2d"),
        Fast2DMetricsCallback(out / "training_log.csv", ent_coef_label=0.0),
    ]
    eval_env = None
    if not args.no_eval:
        eval_env = DummyVecEnv([lambda: Monitor(Fast2DDroneExplorationEnv(
            config=_make_cfg(env_cfg), seed=args.seed + 10_000))])
        callbacks.append(EvalCallback(
            eval_env,
            best_model_save_path=str(out / "best"),
            log_path=str(out / "eval"),
            eval_freq=int(train_cfg["eval_freq"]),   # PPO ile ayni eval sikligi (step bazinda)
            n_eval_episodes=int(train_cfg["n_eval_episodes"]),
            deterministic=True,
        ))

    model = SAC(
        "MlpPolicy", env,
        learning_rate=SAC_HP["learning_rate"],
        buffer_size=SAC_HP["buffer_size"],
        batch_size=SAC_HP["batch_size"],
        learning_starts=SAC_HP["learning_starts"],
        tau=SAC_HP["tau"],
        gamma=SAC_HP["gamma"],
        train_freq=SAC_HP["train_freq"],
        gradient_steps=SAC_HP["gradient_steps"],
        ent_coef=SAC_HP["ent_coef"],
        policy_kwargs={"net_arch": SAC_HP["net_arch"]},
        tensorboard_log=str(out / "tb"),
        verbose=0,
        seed=args.seed,
        device=args.device,
    )
    model.set_logger(configure(str(out / "logs"), ["stdout", "csv", "tensorboard"]))

    with open(out / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "seed": args.seed, "algo": "SAC", "total_timesteps": int(args.timesteps),
            "num_envs": 1, "device": args.device, "sac": SAC_HP, "env": env_cfg,
        }, f, indent=2, ensure_ascii=False)

    print(f"[train_sac] SAC seed={args.seed} hedef={args.timesteps} -> {out}")
    try:
        model.learn(total_timesteps=int(args.timesteps), callback=callbacks, progress_bar=False)
    finally:
        env.close()
        if eval_env is not None:
            eval_env.close()
    model.save(out / "final_model")
    print(f"[train_sac] SAC seed={args.seed} bitti -> {out / 'final_model.zip'}")


if __name__ == "__main__":
    main()
