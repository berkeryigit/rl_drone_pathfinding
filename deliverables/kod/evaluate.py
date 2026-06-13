"""
evaluate.py — Eğitilmiş DQN modelini değerlendir
=================================================
Kullanım:
    python evaluate.py --model runs/seed_42/checkpoints/dqn_drone_final.zip
    python evaluate.py --model <model.zip> --episodes 20 --deterministic
    python evaluate.py --model <model.zip> --render

Çıktı:
    Terminale episode bazlı tablo + özet istatistik
    sonuclar/eval_per_episode.csv  (--save-csv ile)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from env import Fast2DDroneExplorationEnv, Fast2DConfig


def _make_env(env_cfg: dict, seed: int, render: bool):
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
    return Fast2DDroneExplorationEnv(
        config=cfg,
        render_mode="rgb_array" if render else None,
        seed=seed,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="DQN model değerlendirme")
    parser.add_argument("--model", required=True, help="Model .zip dosyası")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--deterministic", action="store_true",
                        help="Greedy (deterministic) politika kullan")
    parser.add_argument("--render", action="store_true",
                        help="Matplotlib ile canlı render")
    parser.add_argument("--save-csv", default="../sonuclar/sonuclar.csv",
                        help="Episode sonuçlarını bu CSV dosyasına kaydet")
    args, _ = parser.parse_known_args(argv)

    import gymnasium as gym
    from stable_baselines3 import DQN

    # Config yükle
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    env_cfg = cfg["env"]

    # Discrete wrapper
    class DiscreteActionWrapper(gym.ActionWrapper):
        ACTIONS = [
            [ 1.0,  0.0,  0.0],
            [-1.0,  0.0,  0.0],
            [ 0.0,  1.0,  0.0],
            [ 0.0, -1.0,  0.0],
            [ 0.0,  0.0,  1.0],
            [ 0.0,  0.0, -1.0],
            [ 1.0,  0.0,  1.0],
            [ 1.0,  0.0, -1.0],
            [ 0.0,  0.0,  0.0],
        ]
        def __init__(self, env):
            super().__init__(env)
            self.action_space = gym.spaces.Discrete(len(self.ACTIONS))

        def action(self, act: int) -> np.ndarray:
            return np.array(self.ACTIONS[act], dtype=np.float32)

    raw_env = _make_env(env_cfg, args.seed, args.render)
    env = DiscreteActionWrapper(raw_env)

    model = DQN.load(args.model, env=env)

    # Render kurulumu
    if args.render:
        import matplotlib.pyplot as plt
        plt.ion()
        fig, ax = plt.subplots(figsize=(7, 7))
        im = ax.imshow(raw_env.render())
        ax.axis("off")
        plt.tight_layout()

    # Değerlendirme döngüsü
    results = []
    print(f"\n{'EP':>4} {'ÖDÜL':>10} {'ADIM':>6} {'ODA':>5} {'KEŞİF%':>8} {'ÇARPIŞ':>8}")
    print("-" * 50)

    for ep in range(1, args.episodes + 1):
        obs, _ = env.reset()
        ep_reward = 0.0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            done = terminated or truncated

            if args.render:
                frame = raw_env.render()
                im.set_data(frame)
                fig.canvas.draw_idle()
                plt.pause(0.02)

        explored_pct = info.get("explored_voxels", 0) / (32 * 32) * 100
        rooms = info.get("visited_rooms", 0)
        collision = info.get("collision", False)

        results.append({
            "episode": ep,
            "reward": ep_reward,
            "length": info.get("_step_count", 0),
            "visited_rooms": rooms,
            "explored_pct": explored_pct,
            "collision": int(collision),
        })
        print(f"{ep:>4} {ep_reward:>10.2f} {results[-1]['length']:>6} "
              f"{rooms:>5} {explored_pct:>7.1f}% {'EVET' if collision else 'yok':>8}")

    env.close()
    if args.render:
        plt.close("all")

    # Özet istatistik
    rewards = [r["reward"] for r in results]
    rooms_l = [r["visited_rooms"] for r in results]
    print("-" * 50)
    print(f"Ödül  → ort={np.mean(rewards):.2f}  std={np.std(rewards):.2f}  "
          f"min={np.min(rewards):.2f}  max={np.max(rewards):.2f}")
    print(f"Oda   → ort={np.mean(rooms_l):.2f}")
    print(f"Başarı oranı (tüm odalar): "
          f"{sum(1 for r in results if r['visited_rooms'] >= 6) / len(results) * 100:.1f}%")

    # CSV kaydet
    if args.save_csv:
        Path(args.save_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(args.save_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSonuçlar kaydedildi: {args.save_csv}")


if __name__ == "__main__":
    main()
