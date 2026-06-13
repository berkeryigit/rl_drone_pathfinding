"""
2D Drone Ortamını Görüntüle
---------------------------
Kullanım:
    python view_2d_env.py              # rastgele aksiyon ile
    python view_2d_env.py --steps 300  # 300 adım
    python view_2d_env.py --fps 30     # daha hızlı

Çıkmak için: pencereyi kapatın veya Ctrl+C
"""
from __future__ import annotations

import sys
import os
import argparse

# --- Python path: bu script proje kökünden çalıştırılırsa paketi bulur ---
_PKG_ROOT = os.path.join(os.path.dirname(__file__),
                         "ros2_ws", "src", "rl_drone_pathfinding")
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from rl_drone_pathfinding.envs import Fast2DDroneExplorationEnv
from rl_drone_pathfinding.envs.fast_2d_drone_env import Fast2DConfig, N_ROOMS


def main():
    parser = argparse.ArgumentParser(description="2D Drone Ortamı Görüntüleyici")
    parser.add_argument("--steps", type=int, default=600, help="Maksimum adım sayısı")
    parser.add_argument("--fps", type=float, default=20.0, help="Görüntüleme FPS")
    parser.add_argument("--seed", type=int, default=42, help="Rastgele seed")
    parser.add_argument("--no-random-start", action="store_true",
                        help="Drone her zaman sabit başlangıç noktasından başlar")
    args = parser.parse_args()

    cfg = Fast2DConfig(random_start=not args.no_random_start)
    env = Fast2DDroneExplorationEnv(
        config=cfg,
        render_mode="rgb_array",
        seed=args.seed,
    )

    obs, info = env.reset()

    # --- Matplotlib kurulumu ---
    plt.ion()
    fig, (ax_env, ax_stats) = plt.subplots(1, 2, figsize=(12, 6),
                                            gridspec_kw={"width_ratios": [2, 1]})
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle("2D Drone Keşif Ortamı", color="white", fontsize=14, fontweight="bold")

    # Sol panel: ortam görüntüsü
    ax_env.set_facecolor("#1a1a2e")
    ax_env.set_title("Ortam", color="white", fontsize=11)
    ax_env.axis("off")
    frame = env.render()
    im = ax_env.imshow(frame)

    # Sağ panel: istatistikler
    ax_stats.set_facecolor("#16213e")
    ax_stats.set_xlim(0, 1)
    ax_stats.set_ylim(0, 1)
    ax_stats.axis("off")
    ax_stats.set_title("İstatistikler", color="white", fontsize=11)

    stat_texts = {}
    labels = {
        "step":     ("Adım",         0.90),
        "reward":   ("Toplam Ödül",  0.80),
        "rooms":    ("Oda",          0.68),
        "explored": ("Keşif %",      0.56),
        "collision":("Çarpışma",     0.44),
        "episode":  ("Episode",      0.32),
    }
    for key, (label, y) in labels.items():
        ax_stats.text(0.05, y + 0.03, label + ":", color="#8ecae6",
                      fontsize=10, transform=ax_stats.transAxes)
        stat_texts[key] = ax_stats.text(
            0.05, y - 0.03, "—", color="white",
            fontsize=12, fontweight="bold", transform=ax_stats.transAxes
        )

    # Renk açıklaması
    legend_items = [
        mpatches.Patch(color="#2d962d", label="Drone"),
        mpatches.Patch(color="#d2554b", label="Hareketli engel"),
        mpatches.Patch(color="#2d2d32", label="Duvar"),
    ]
    ax_stats.legend(handles=legend_items, loc="lower center",
                    facecolor="#0f3460", labelcolor="white",
                    fontsize=9, framealpha=0.8)

    # Oda ilerleme barları
    bar_y_start = 0.10
    room_bars = []
    for i in range(N_ROOMS):
        bar = ax_stats.barh(
            bar_y_start + i * 0.025, 0.0,
            height=0.018, left=0.05, color="#444", align="center"
        )
        room_bars.append(bar)
    ax_stats.text(0.05, bar_y_start + N_ROOMS * 0.025 + 0.01,
                  f"Odalar (0/{N_ROOMS})", color="#8ecae6",
                  fontsize=9, transform=ax_stats.transAxes)
    room_label = ax_stats.texts[-1]

    plt.tight_layout()

    # --- Ana döngü ---
    total_reward = 0.0
    episode = 1
    step = 0
    interval = 1.0 / args.fps

    print(f"[view_2d_env] Başlatıldı — seed={args.seed}, fps={args.fps}")
    print("Pencereyi kapatın veya Ctrl+C ile çıkın.\n")

    try:
        while plt.fignum_exists(fig.number):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            step += 1

            # Görüntüyü güncelle
            frame = env.render()
            im.set_data(frame)

            # İstatistikleri güncelle
            rooms = info["visited_rooms"]
            explored_pct = info["explored_voxels"] / (32 * 32) * 100
            stat_texts["step"].set_text(f"{step} / {args.steps}")
            stat_texts["reward"].set_text(f"{total_reward:+.1f}")
            stat_texts["rooms"].set_text(f"{rooms} / {N_ROOMS}")
            stat_texts["explored"].set_text(f"{explored_pct:.1f}%")
            stat_texts["collision"].set_text(
                "💥 EVET" if info["collision"] else "Yok"
            )
            stat_texts["collision"].set_color("#ff6b6b" if info["collision"] else "#69db7c")
            stat_texts["episode"].set_text(str(episode))

            # Oda barlarını güncelle
            room_label.set_text(f"Odalar ({rooms}/{N_ROOMS})")
            for i, bar in enumerate(room_bars):
                filled = i < rooms
                bar[0].set_width(0.90 if filled else 0.0)
                bar[0].set_color("#4ecdc4" if filled else "#444")

            fig.canvas.draw_idle()
            plt.pause(interval)

            if terminated or truncated or step >= args.steps:
                reason = "çarpışma" if info["collision"] else \
                         "tüm odalar keşfedildi" if rooms >= N_ROOMS else \
                         "adım limiti"
                print(f"Episode {episode} bitti ({reason}) | "
                      f"adım={step} ödül={total_reward:.1f} "
                      f"oda={rooms}/{N_ROOMS} keşif={explored_pct:.1f}%")
                obs, info = env.reset()
                total_reward = 0.0
                step = 0
                episode += 1

    except KeyboardInterrupt:
        print("\nKullanıcı çıkışı.")
    finally:
        env.close()
        plt.close("all")
        print("Ortam kapatıldı.")


if __name__ == "__main__":
    main()
