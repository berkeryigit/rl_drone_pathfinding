"""A2C (SB3) eğitimi — PAYLAŞILAN DroneExplorationEnv üzerinde, DISCRETE aksiyon.

================================================================================
A3C NOTU (ÖNEMLİ — oku):
  * Stable-Baselines3'te "A3C" diye ayrı bir sınıf YOK. A2C, A3C'nin senkron
    (tek-proses) versiyonudur — aynı advantage actor-critic, sadece worker'lar
    asenkron değil. Dönem projesi için A2C, A3C'nin standart pratik karşılığıdır.
  * BİZİM DERSİMİZ (PPO tarafında acı çekerek öğrendik): ÇOKLU Gazebo / çoklu env
    süreci sürekli BOZUYOR (transport çakışması, IPC bozulması). Bu yüzden n_envs=1.
  * Gerçek async A3C çoklu-worker ister → bu, tek-sim stabilite dersimizle ÇELİŞİR.
    Önerimiz: n_envs=1 ile A2C koş (= tek-worker advantage actor-critic). Hoca için
    "A2C = senkron A3C" notunu rapora yaz. Async A3C şart koşulursa a3c_talimatlar.md'deki
    uyarıları oku.
================================================================================

Continuous (PPO/Berker) ile TEK fark: aksiyon uzayı Discrete(4) (ileri/sol/sağ/dur).
Harita, drone, lidar, ödül, gözlem, spawn — HEPSİ birebir aynı (adil karşılaştırma).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from stable_baselines3 import A2C
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from rl_drone_pathfinding.envs import DroneExplorationEnv
# Paylaşılan yardımcılar PPO trainer'dan tekrar kullanılıyor (test edilmiş kod):
from rl_drone_pathfinding.agents.train_ppo import (
    _build_lr, _start_obstacle_updaters, ExplorationLogger,
)


def _load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _make_env(env_cfg: dict, env_id: int = 0):
    def _factory():
        env = DroneExplorationEnv(
            world_name=env_cfg["world_name"],
            drone_name=env_cfg["drone_name"],
            max_episode_steps=env_cfg["max_episode_steps"],
            seed=env_cfg.get("seed"),
            env_id=env_id,
            discrete=True,                 # A3C/A2C = DISCRETE aksiyon
        )
        return Monitor(env, info_keywords=("explored_voxels", "visited_rooms"))
    return _factory


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/a2c.yaml")
    args, _ = parser.parse_known_args(argv)

    cfg = _load_config(args.config)
    env_cfg, a2c_cfg, tr_cfg = cfg["env"], cfg["a2c"], cfg["train"]

    log_dir = Path(tr_cfg["log_dir"]); log_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = Path(tr_cfg["ckpt_dir"]); ckpt_dir.mkdir(parents=True, exist_ok=True)
    tb_log = Path(tr_cfg["tb_log"]); tb_log.mkdir(parents=True, exist_ok=True)

    n_envs = int(tr_cfg.get("n_envs", 1))
    if n_envs > 1:
        print("[train_a2c] UYARI: n_envs>1 — coklu Gazebo bizim ortamda KARARSIZ. "
              "Bunu yalnizca gercek async A3C deniyorsan ve riski kabul ediyorsan kullan.")
    factories = [_make_env(env_cfg, i) for i in range(n_envs)]
    vec_env = SubprocVecEnv(factories) if n_envs > 1 else DummyVecEnv(factories)

    vn_cfg = tr_cfg.get("vec_normalize", {}) or {}
    use_vn = bool(vn_cfg.get("enabled", False))
    resuming = bool(tr_cfg.get("resume_from"))

    if use_vn:
        vn_pkl = ckpt_dir / "vec_normalize.pkl"
        if resuming and vn_pkl.exists():
            vec_env = VecNormalize.load(str(vn_pkl), vec_env)
            vec_env.training = True
            vec_env.norm_reward = bool(vn_cfg.get("norm_reward", True))
        else:
            vec_env = VecNormalize(
                vec_env,
                norm_obs=bool(vn_cfg.get("norm_obs", False)),
                norm_reward=bool(vn_cfg.get("norm_reward", True)),
                clip_reward=float(vn_cfg.get("clip_reward", 10.0)),
                gamma=float(a2c_cfg.get("gamma", 0.99)),
            )

    if resuming:
        print(f"[train_a2c] resuming from {tr_cfg['resume_from']}")
        model = A2C.load(tr_cfg["resume_from"], env=vec_env, tensorboard_log=str(tb_log))
        model.ent_coef = float(a2c_cfg["ent_coef"])
        model.learning_rate = _build_lr(a2c_cfg)
        model.policy.optimizer.param_groups[0]["lr"] = float(a2c_cfg["learning_rate"])
    else:
        model = A2C(
            policy=a2c_cfg["policy"],
            env=vec_env,
            learning_rate=_build_lr(a2c_cfg),
            n_steps=int(a2c_cfg["n_steps"]),
            gamma=float(a2c_cfg["gamma"]),
            gae_lambda=float(a2c_cfg["gae_lambda"]),
            ent_coef=float(a2c_cfg["ent_coef"]),
            vf_coef=float(a2c_cfg["vf_coef"]),
            max_grad_norm=float(a2c_cfg["max_grad_norm"]),
            policy_kwargs={"net_arch": a2c_cfg["policy_kwargs"]["net_arch"]},
            tensorboard_log=str(tb_log),
            verbose=1,
            seed=env_cfg.get("seed"),
        )

    ckpt_cb = CheckpointCallback(
        save_freq=int(tr_cfg["save_freq"]), save_path=str(ckpt_dir), name_prefix="a2c_drone")
    explo_cb = ExplorationLogger(
        log_dir=log_dir, version=str(tr_cfg.get("version", "a2c")),
        ckpt_dir=ckpt_dir if use_vn else None)
    callbacks = CallbackList([ckpt_cb, explo_cb])

    final = ckpt_dir / "a2c_drone_final.zip"
    target = int(tr_cfg["total_timesteps"])
    if resuming:
        remaining = target - int(model.num_timesteps)
        if remaining <= 0:
            print(f"[train_a2c] target {target} reached (current={model.num_timesteps})")
            return
        learn_steps = remaining
    else:
        learn_steps = target

    obs_threads, obs_stop = _start_obstacle_updaters(env_cfg["world_name"], n_envs)
    try:
        model.learn(total_timesteps=learn_steps, callback=callbacks,
                    progress_bar=True, reset_num_timesteps=not resuming)
    except KeyboardInterrupt:
        final = ckpt_dir / "a2c_drone_interrupted.zip"
        print(f"\n[train_a2c] interrupted -> saving to {final}")
    finally:
        obs_stop.set()

    model.save(str(final))
    print(f"[train_a2c] saved model to {final}")
    if use_vn:
        vec_env.save(str(ckpt_dir / "vec_normalize.pkl"))


if __name__ == "__main__":
    main()
