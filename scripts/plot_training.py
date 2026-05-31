"""Egitim log dosyasindan rapor grafikleri olusturur.

Kullanim:
    python3 scripts/plot_training.py
    python3 scripts/plot_training.py --log runs/sac/training_log.csv --out runs/sac/plots
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


def smooth(y, window=20):
    """Hareketli ortalama ile yumusat."""
    if len(y) < window:
        return y
    return pd.Series(y).rolling(window, min_periods=1, center=True).mean().values


def plot_all(df: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = df["timestep"].values
    ep    = df["episode"].values

    # ------------------------------------------------------------------ #
    # 1. Ana performans ozeti (2x3 grid)
    # ------------------------------------------------------------------ #
    fig = plt.figure(figsize=(18, 10))
    fig.suptitle("SAC Egitim Ozeti", fontsize=15, fontweight="bold")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32)

    # --- Reward ---
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(steps, df["ep_reward"], alpha=0.25, color="#4fc3f7", linewidth=0.8)
    ax.plot(steps, smooth(df["ep_reward"]), color="#0288d1", linewidth=2, label="Hareketli Ort.")
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_title("Episode Odulu"); ax.set_xlabel("Timestep"); ax.set_ylabel("Reward")
    ax.legend(fontsize=8)

    # --- Voxel ---
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(steps, df["explored_voxels"], alpha=0.25, color="#81c784", linewidth=0.8)
    ax.plot(steps, smooth(df["explored_voxels"]), color="#388e3c", linewidth=2)
    ax.set_title("Kesfedilen Voxel"); ax.set_xlabel("Timestep"); ax.set_ylabel("Voxel")

    # --- Rooms ---
    ax = fig.add_subplot(gs[0, 2])
    ax.plot(steps, df["visited_rooms"], alpha=0.25, color="#ffb74d", linewidth=0.8)
    ax.plot(steps, smooth(df["visited_rooms"]), color="#f57c00", linewidth=2)
    ax.axhline(6, color="red", linestyle="--", linewidth=1, label="Max (6)")
    ax.set_ylim(0, 7); ax.set_title("Ziyaret Edilen Oda")
    ax.set_xlabel("Timestep"); ax.set_ylabel("Oda Sayisi"); ax.legend(fontsize=8)

    # --- Actor Loss ---
    ax = fig.add_subplot(gs[1, 0])
    ax.plot(steps, df["actor_loss"], alpha=0.3, color="#ef9a9a", linewidth=0.8)
    ax.plot(steps, smooth(df["actor_loss"]), color="#c62828", linewidth=2)
    ax.set_title("Actor Loss"); ax.set_xlabel("Timestep"); ax.set_ylabel("Loss")

    # --- Critic Loss ---
    ax = fig.add_subplot(gs[1, 1])
    ax.plot(steps, df["critic_loss"], alpha=0.3, color="#ce93d8", linewidth=0.8)
    ax.plot(steps, smooth(df["critic_loss"]), color="#6a1b9a", linewidth=2)
    ax.set_title("Critic Loss"); ax.set_xlabel("Timestep"); ax.set_ylabel("Loss")

    # --- Oda dagilimi histogram ---
    ax = fig.add_subplot(gs[1, 2])
    counts = df["visited_rooms"].value_counts().sort_index()
    ax.bar(counts.index, counts.values, color="#80cbc4", edgecolor="white")
    ax.set_title("Oda Dagilimi (tum episodeler)")
    ax.set_xlabel("Ziyaret Edilen Oda"); ax.set_ylabel("Episode Sayisi")
    ax.set_xticks(range(1, 7))

    path = out_dir / "training_overview.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {path}")

    # ------------------------------------------------------------------ #
    # 2. Reward dagilimi histogram
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df["ep_reward"], bins=40, color="#4fc3f7", edgecolor="white", alpha=0.85)
    ax.axvline(df["ep_reward"].mean(), color="red", linestyle="--",
               label=f"Ortalama: {df['ep_reward'].mean():.1f}")
    ax.axvline(df["ep_reward"].median(), color="orange", linestyle="--",
               label=f"Medyan: {df['ep_reward'].median():.1f}")
    ax.set_title("Reward Dagilimi"); ax.set_xlabel("Reward"); ax.set_ylabel("Frekans")
    ax.legend()
    path = out_dir / "reward_distribution.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {path}")

    # ------------------------------------------------------------------ #
    # 3. Ogrenme egrileri (reward + voxel birlikte, ikincil eksen)
    # ------------------------------------------------------------------ #
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax2 = ax1.twinx()
    ax1.plot(steps, smooth(df["ep_reward"], 30), color="#0288d1", linewidth=2, label="Reward (ort.)")
    ax1.axhline(0, color="gray", linestyle=":", linewidth=0.8)
    ax2.plot(steps, smooth(df["explored_voxels"], 30), color="#388e3c", linewidth=2,
             linestyle="--", label="Voxel (ort.)")
    ax1.set_xlabel("Timestep"); ax1.set_ylabel("Reward", color="#0288d1")
    ax2.set_ylabel("Voxel", color="#388e3c")
    ax1.tick_params(axis="y", labelcolor="#0288d1")
    ax2.tick_params(axis="y", labelcolor="#388e3c")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("Ogrenme Egrisi — Reward ve Kesif")
    path = out_dir / "learning_curve.png"
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {path}")

    # ------------------------------------------------------------------ #
    # 4. Istatistik ozeti
    # ------------------------------------------------------------------ #
    last_n = min(50, len(df))
    recent = df.tail(last_n)
    stats = {
        "Toplam Episode":        len(df),
        "Toplam Timestep":       int(df["timestep"].max()),
        "En Iyi Reward":         round(df["ep_reward"].max(), 1),
        "Ort. Reward (son 50)":  round(recent["ep_reward"].mean(), 1),
        "Max Voxel":             int(df["explored_voxels"].max()),
        "Ort. Voxel (son 50)":   round(recent["explored_voxels"].mean(), 1),
        "Max Oda":               int(df["visited_rooms"].max()),
        "Ort. Oda (son 50)":     round(recent["visited_rooms"].mean(), 2),
        "6 Oda Orani (son 50)":  f"{(recent['visited_rooms'] == 6).mean()*100:.1f}%",
    }
    if "success" in df.columns:
        stats["Success Orani (son 50)"] = f"{recent['success'].mean()*100:.1f}%"
    if "crashed" in df.columns:
        stats["Crash Orani (son 50)"] = f"{recent['crashed'].mean()*100:.1f}%"
    if "timeout" in df.columns:
        stats["Timeout Orani (son 50)"] = f"{recent['timeout'].mean()*100:.1f}%"
    stats_path = out_dir / "stats.txt"
    with open(stats_path, "w") as f:
        for k, v in stats.items():
            f.write(f"{k:<30} {v}\n")
    print(f"[plot] {stats_path}")
    for k, v in stats.items():
        print(f"  {k:<30} {v}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="runs/sac/training_log.csv")
    parser.add_argument("--out", default="runs/sac/plots")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"[plot] Log bulunamadi: {log_path}")
        return

    df = pd.read_csv(log_path)
    print(f"[plot] {len(df)} episode yuklendi — {df['timestep'].max():,} toplam step")
    plot_all(df, Path(args.out))
    print(f"\n[plot] Tum grafikler: {args.out}/")


if __name__ == "__main__":
    main()
