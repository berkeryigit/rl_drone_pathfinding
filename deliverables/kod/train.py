"""2D Gymnasium ortaminda SAC egitimi (tek seed).

Egitim SADECE Fast2DDroneExplorationEnv (saf Python + numpy + gymnasium)
uzerinde yapilir; Gazebo egitim icin KULLANILMAZ. Gazebo yalnizca test/gosterim.

Kullanim:
    python3 train.py --seed 7 --timesteps 300000          # yeni egitim
    python3 train.py --seed 7 --timesteps 1000000         # daha uzun
    python3 train.py --seed 7 --resume                    # en son checkpoint'tan devam
    python3 train.py --seed 7 --resume --timesteps 500000 # devam + hedef adim guncelle
    bash run_all.sh                                        # tum seed'ler + eval + grafik

Kaldigi yerden devam (--resume):
    runs/seed_<N>/checkpoints/ altindaki en son .zip otomatik bulunur ve yuklenir.
    training_log.csv'e ekleme yapilir (uzerine yazmaz).
    Replay buffer sifirdan dolar (ilk birkaç bin adim biraz daha az verimli, sonra normal).

En iyi model nerede:
    runs/seed_<N>/best/best_model.zip  -> deterministik eval'da en yuksek ortalama getiri
    runs/seed_<N>/final_model.zip      -> egitim sonu / ctrl+c anindaki model

Ne zaman durdurmali:
    --stop-patience N  -> N ardisik eval'da iyilesme olmazsa otomatik dur (varsayilan: kapali)
    Manuel: training_log.csv'de son 50 episode'un ortalama getirisi platoya ulasinca
            VEYA visited_rooms=6 orani %80+ olunca dur. 1M step genellikle yeterinden fazla.

Cikti (out dizini):
    training_log.csv         -> her episode: episode getirisi (ANLIK odul DEGIL) + metrikler
    eval/evaluations.npz     -> deterministik eval egrisi (SB3 EvalCallback)
    checkpoints/             -> periyodik model kayitlari
    best/best_model.zip      -> en iyi eval modeli
    final_model.zip          -> egitim sonu modeli
    run_meta.json            -> seed, config, surum bilgisi
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
    BaseCallback, CheckpointCallback, EvalCallback, StopTrainingOnNoModelImprovement,
)
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

# Self-contained: kod/ dizini cwd oldugunda 'env' paketi import edilir.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from env.fast_2d_drone_env import (  # noqa: E402
    Fast2DConfig, Fast2DDroneExplorationEnv, N_ROOMS, GRID_NXY, LIDAR_MAX,
)

_TOTAL_CELLS = GRID_NXY * GRID_NXY

try:
    import torch
    _DEFAULT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:  # pragma: no cover
    _DEFAULT_DEVICE = "cpu"


def _find_latest_checkpoint(checkpoints_dir: Path) -> Path | None:
    """checkpoints/ altindaki en son .zip'i bulur (adim numarasina gore)."""
    zips = sorted(checkpoints_dir.glob("sac_2d_*.zip"),
                  key=lambda p: int(p.stem.rsplit("_", 1)[-1]) if p.stem.rsplit("_", 1)[-1].isdigit() else 0)
    return zips[-1] if zips else None


class Fast2DMetricsCallback(BaseCallback):
    """Her episode bittiginde EPISODE GETIRISI + kesif metriklerini CSV'e yazar.

    resume=True ise mevcut CSV'e ekleme yapar (uzerine yazmaz).
    """

    def __init__(self, csv_path: Path, resume: bool = False, verbose: int = 0):
        super().__init__(verbose)
        self.csv_path = csv_path
        self.resume = resume
        self._episode = 0
        self._file = None
        self._writer = None

    def _on_training_start(self) -> None:
        _HEADER = [
            "episode", "timestep", "ep_return", "steps",
            "explored_voxels", "coverage_pct", "visited_rooms", "success", "crashed",
            "min_lidar", "ent_coef", "actor_loss", "critic_loss",
        ]
        if self.resume and self.csv_path.exists():
            # Mevcut episode sayisini bul, devam icin sayaci ayarla
            with open(self.csv_path, "r", newline="") as f:
                rows = list(csv.reader(f))
            self._episode = max((int(r[0]) for r in rows[1:] if r and r[0].isdigit()), default=0)
            self._file = open(self.csv_path, "a", newline="", buffering=1)
            self._writer = csv.writer(self._file)
            print(f"[train] CSV'e ekleme modu: {self.csv_path} (onceki episode sayisi: {self._episode})")
        else:
            self._file = open(self.csv_path, "w", newline="", buffering=1)
            self._writer = csv.writer(self._file)
            self._writer.writerow(_HEADER)

    def _on_step(self) -> bool:
        for done, info in zip(self.locals.get("dones", []), self.locals.get("infos", [])):
            if not done:
                continue
            self._episode += 1
            ep_info = info.get("episode")
            ep_return = float(ep_info["r"]) if ep_info else 0.0   # EPISODE GETIRISI
            ep_len = int(ep_info["l"]) if ep_info else 0

            voxels = int(info.get("explored_voxels", 0))
            rooms = int(info.get("visited_rooms", 0))
            cover = round(voxels / _TOTAL_CELLS * 100.0, 1)
            success = int(rooms >= N_ROOMS)
            crash = int(bool(info.get("collision", False)))
            min_lid = round(float(info.get("min_lidar", LIDAR_MAX)), 3)

            ent = self.model.ent_coef_tensor.item() if hasattr(self.model, "ent_coef_tensor") else 0.0
            a_l = float(self.logger.name_to_value.get("train/actor_loss", 0.0))
            c_l = float(self.logger.name_to_value.get("train/critic_loss", 0.0))

            self._writer.writerow([
                self._episode, self.num_timesteps, round(ep_return, 2), ep_len,
                voxels, cover, rooms, success, crash,
                min_lid, round(ent, 4), round(a_l, 4), round(c_l, 4),
            ])
        return True

    def _on_training_end(self) -> None:
        if self._file:
            self._file.close()


def _make_env(env_cfg: dict, seed: int | None):
    def _factory():
        cfg = Fast2DConfig(
            max_episode_steps=int(env_cfg["max_episode_steps"]),
            random_start=bool(env_cfg["random_start"]),
            lidar_noise_std=float(env_cfg["lidar_noise_std"]),
            odom_noise_std=float(env_cfg["odom_noise_std"]),
            wind_std=float(env_cfg["wind_std"]),
        )
        return Monitor(Fast2DDroneExplorationEnv(config=cfg, seed=seed))
    return _factory


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="2D SAC egitimi (tek seed)")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--timesteps", type=int, default=None, help="config.train.total_timesteps override")
    parser.add_argument("--num-envs", type=int, default=None, help="config.train.num_envs override")
    parser.add_argument("--out", type=Path, default=None, help="varsayilan: runs/seed_<N>")
    parser.add_argument("--device", default=None, help="cuda | cpu (varsayilan: otomatik)")
    parser.add_argument("--lr", type=float, default=None, help="learning_rate override (HP sweep)")
    parser.add_argument("--gamma", type=float, default=None, help="gamma (indirim faktoru) override (HP sweep)")
    parser.add_argument("--ent-coef", default=None, help="ent_coef override, ornek 0.1 (HP sweep)")
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="En son checkpoint'tan devam et (replay buffer sifirlanir, model + adim sayaci yuklenir)")
    parser.add_argument("--stop-patience", type=int, default=0,
                        help="N ardisik eval'da iyilesme olmazsa dur (0=kapali). Ornek: --stop-patience 20")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    env_cfg, sac_cfg, train_cfg = cfg["env"], cfg["sac"], cfg["train"]
    if args.lr is not None:
        sac_cfg["learning_rate"] = args.lr
    if args.gamma is not None:
        sac_cfg["gamma"] = args.gamma
    if args.ent_coef is not None:
        try:
            sac_cfg["ent_coef"] = float(args.ent_coef)  # sabit sicaklik => kesif kontrolu
        except ValueError:
            sac_cfg["ent_coef"] = args.ent_coef         # "auto" / "auto_0.1"

    total_timesteps = int(args.timesteps if args.timesteps is not None else train_cfg["total_timesteps"])
    num_envs = int(args.num_envs if args.num_envs is not None else train_cfg["num_envs"])
    num_envs = max(1, num_envs)
    device = args.device or _DEFAULT_DEVICE
    out = args.out or Path(train_cfg["out_root"]) / f"seed_{args.seed}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "checkpoints").mkdir(exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)

    env = make_vec_env(
        _make_env(env_cfg, args.seed),
        n_envs=num_envs,
        vec_env_cls=SubprocVecEnv if num_envs > 1 else DummyVecEnv,
    )

    callbacks: list[BaseCallback] = [
        CheckpointCallback(
            save_freq=max(int(train_cfg["save_freq"]) // num_envs, 1),
            save_path=str(out / "checkpoints"),
            name_prefix="sac_2d",
        ),
        Fast2DMetricsCallback(out / "training_log.csv", resume=args.resume),
    ]
    eval_env = None
    if not args.no_eval:
        # DummyVecEnv ile sar: SubprocVecEnv (egitim) ile tip uyarisi cikmaz
        eval_env = DummyVecEnv([lambda: Monitor(Fast2DDroneExplorationEnv(
            config=Fast2DConfig(
                max_episode_steps=int(env_cfg["max_episode_steps"]),
                random_start=bool(env_cfg["random_start"]),
                lidar_noise_std=float(env_cfg["lidar_noise_std"]),
                odom_noise_std=float(env_cfg["odom_noise_std"]),
                wind_std=float(env_cfg["wind_std"]),
            ),
            seed=args.seed + 10_000,  # eval icin egitimden ayri RNG akisi
        ))])
        eval_cb_kwargs: dict = dict(
            best_model_save_path=str(out / "best"),
            log_path=str(out / "eval"),
            eval_freq=max(int(train_cfg["eval_freq"]) // num_envs, 1),
            n_eval_episodes=int(train_cfg["n_eval_episodes"]),
            deterministic=True,   # eval egrisi = greedy/deterministik politika
        )
        # Otomatik erken durdurma: N ardisik eval'da iyilesme yoksa dur
        if args.stop_patience > 0:
            stop_cb = StopTrainingOnNoModelImprovement(
                max_no_improvement_evals=args.stop_patience,
                min_evals=max(args.stop_patience, 10),  # en az 10 eval gorme garantisi
                verbose=1,
            )
            eval_cb_kwargs["callback_after_eval"] = stop_cb
            print(f"[train] Otomatik durdurma: {args.stop_patience} ardisik eval'da iyilesme olmazsa dur")
        callbacks.append(EvalCallback(eval_env, **eval_cb_kwargs))

    train_freq = int(sac_cfg["train_freq"])
    sac_kwargs = dict(
        learning_rate=float(sac_cfg["learning_rate"]),
        buffer_size=int(sac_cfg["buffer_size"]),
        batch_size=int(sac_cfg["batch_size"]),
        learning_starts=int(sac_cfg["learning_starts"]),
        tau=float(sac_cfg["tau"]),
        gamma=float(sac_cfg["gamma"]),
        train_freq=(train_freq, "step"),
        gradient_steps=int(sac_cfg["gradient_steps"]),
        target_update_interval=int(sac_cfg["target_update_interval"]),
        ent_coef=sac_cfg["ent_coef"],
        target_entropy=sac_cfg["target_entropy"],
        use_sde=bool(sac_cfg["use_sde"]),
        optimize_memory_usage=bool(sac_cfg["optimize_memory_usage"]),
        policy_kwargs={"net_arch": list(sac_cfg["net_arch"])},
        tensorboard_log=str(out / "tb"),
        verbose=1,
        seed=args.seed,
        device=device,
    )

    resume_checkpoint = None
    if args.resume:
        resume_checkpoint = _find_latest_checkpoint(out / "checkpoints")
        if resume_checkpoint is None:
            # Checkpoint yok ama final_model ya da best_model varsa onu kullan
            for fallback in (out / "final_model.zip", out / "best" / "best_model.zip"):
                if fallback.exists():
                    resume_checkpoint = fallback
                    break
        if resume_checkpoint is None:
            print(f"[train] UYARI: --resume verildi ama {out} altinda kayitli model yok, sifirdan basliyor.")

    if resume_checkpoint is not None:
        print(f"[train] Devam ediliyor: {resume_checkpoint}")
        model = SAC.load(str(resume_checkpoint), env=env, device=device,
                         custom_objects={"learning_rate": float(sac_cfg["learning_rate"])})
        # Replay buffer sifirlanir (orjinal boyuta gore yeniden olusturulur)
        model.buffer_size = int(sac_cfg["buffer_size"])
        model._setup_model()    # buffer'i yeniden init et (boyut degismisse)
        reset_num_timesteps = False
    else:
        model = SAC(sac_cfg["policy"], env, **sac_kwargs)
        reset_num_timesteps = True

    model.set_logger(configure(str(out / "logs"), ["stdout", "csv", "tensorboard"]))

    with open(out / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "seed": args.seed,
            "total_timesteps": total_timesteps,
            "resume": str(resume_checkpoint) if resume_checkpoint else None,
            "num_envs": num_envs,
            "device": device,
            "sac": sac_cfg,
            "env": env_cfg,
        }, f, indent=2, ensure_ascii=False)

    mode_str = f"devam ({resume_checkpoint.name})" if resume_checkpoint else "yeni"
    print(f"[train] seed={args.seed} mod={mode_str} hedef={total_timesteps} num_envs={num_envs} device={device} -> {out}")
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            progress_bar=True,
            reset_num_timesteps=reset_num_timesteps,  # False => adim sayaci kaldigi yerden devam
        )
    except KeyboardInterrupt:
        model.save(out / "interrupted_model")
        print(f"[train] Ctrl+C: model kaydedildi -> {out / 'interrupted_model.zip'}")
        raise
    finally:
        env.close()
        if eval_env is not None:
            eval_env.close()

    model.save(out / "final_model")
    print(f"[train] seed={args.seed} bitti -> {out / 'final_model.zip'}")


if __name__ == "__main__":
    main()
