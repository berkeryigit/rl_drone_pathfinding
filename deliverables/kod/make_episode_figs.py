"""x-ekseni = EPISODE olan grafikler (hocanin 'episode sayisina gore' istegi).

Rehber: 'x: episode veya kumulatif adim -- ikisi de gecerli, etiket net olmali.'
Bu script ana 5-seed training_log'larindan episode-eksenli versiyonlari uretir:
  EP1_ogrenme_episode.png   -> episode getirisi (mean +/- std), x=episode
  EP2_oda_episode.png       -> kesfedilen oda (mean +/- std), x=episode
  EP3_carpisma_episode.png  -> carpisma orani (kayan ort), x=episode
  EP4_seed_episode.png      -> per-seed getiri, x=episode

Cikti: ../sunum/grafikler/EP*.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True, "grid.alpha": 0.25,
                     "figure.dpi": 140, "savefig.dpi": 150})
GR = Path(__file__).resolve().parent.parent / "sunum" / "grafikler"
RUNS = Path(__file__).resolve().parent / "runs"
SEEDS = [7, 13, 42, 123, 2025]
SEED_COLORS = {7: "#1565c0", 13: "#2e7d32", 42: "#c62828", 123: "#6a1b9a", 2025: "#ef6c00"}
PPO_C = "#1565c0"
N_ROOMS = 6
SMOOTH = 25


def smooth(y, w=SMOOTH):
    y = np.asarray(y, float)
    return pd.Series(y).rolling(w, min_periods=1, center=True).mean().to_numpy() if len(y) > 1 else y


def load():
    out = {}
    for s in SEEDS:
        p = RUNS / f"seed_{s}" / "training_log.csv"
        if p.exists():
            d = pd.read_csv(p)
            if len(d):
                out[s] = d
    return out


def _save(fig, name):
    fig.savefig(str(GR / name), bbox_inches="tight"); plt.close(fig)
    print(f"[ep] {name}")


def band(dfs, col, smooth_w=SMOOTH):
    """Per-seed seriyi episode-index'e hizalar (min episode), mean +/- std."""
    n = min(len(d) for d in dfs.values())
    x = np.arange(n)
    stack = np.vstack([smooth(d[col].to_numpy(float)[:n], smooth_w) for d in dfs.values()])
    return x, stack.mean(0), stack.std(0), len(dfs)


def ep1_ogrenme(dfs):
    x, m, sd, n = band(dfs, "ep_return")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(x, m - sd, m + sd, alpha=0.2, color=PPO_C, label="+/- std (seed)")
    ax.plot(x, m, color=PPO_C, lw=2.3, label="Ortalama episode getirisi (PPO)")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("Öğrenme Eğrisi — x = Episode (bölüm) sayısı", fontweight="bold", fontsize=13)
    ax.set_xlabel("Episode (bölüm) sayısı"); ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{n} seed | pencere={SMOOTH}")
    _save(fig, "EP1_ogrenme_episode.png")


def ep2_oda(dfs):
    x, m, sd, n = band(dfs, "visited_rooms")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(x, m - sd, m + sd, alpha=0.2, color="#00897b", label="+/- std (seed)")
    ax.plot(x, m, color="#00897b", lw=2.3, label="Ortalama keşfedilen oda (PPO)")
    ax.axhline(N_ROOMS, color="#c62828", ls="--", lw=1.2, label=f"hedef {N_ROOMS} oda")
    ax.set_title("Oda Keşif Süreci — x = Episode sayısı", fontweight="bold", fontsize=13)
    ax.set_xlabel("Episode (bölüm) sayısı"); ax.set_ylabel("Keşfedilen oda sayısı (0-6)")
    ax.set_ylim(0, N_ROOMS + 0.4); ax.legend(title=f"{n} seed | pencere={SMOOTH}")
    _save(fig, "EP2_oda_episode.png")


def ep3_carpisma(dfs):
    fig, ax = plt.subplots(figsize=(11, 6))
    for s, d in dfs.items():
        y = pd.Series(d["crashed"].to_numpy(float)).rolling(80, min_periods=1).mean().to_numpy() * 100
        ax.plot(np.arange(len(d)), y, color=SEED_COLORS.get(s, "#888"), lw=0.9, alpha=0.5, label=f"seed {s}")
    x, m, sd, n = band(dfs, "crashed", smooth_w=80)
    ax.plot(x, m * 100, color="#212121", lw=2.6, label="Ortalama (5 seed)")
    ax.set_title("Çarpışma Oranı — x = Episode sayısı (kayan ortalama)", fontweight="bold", fontsize=13)
    ax.set_xlabel("Episode (bölüm) sayısı"); ax.set_ylabel("Çarpışma oranı (%)")
    ax.set_ylim(0, 105); ax.legend(ncol=2, fontsize=8)
    _save(fig, "EP3_carpisma_episode.png")


def ep4_seed(dfs):
    fig, ax = plt.subplots(figsize=(11, 6))
    for s, d in dfs.items():
        ax.plot(np.arange(len(d)), smooth(d["ep_return"].to_numpy(float)),
                color=SEED_COLORS.get(s, "#888"), lw=1.5, alpha=0.9, label=f"seed {s}")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("Seed Karşılaştırması — x = Episode sayısı", fontweight="bold", fontsize=13)
    ax.set_xlabel("Episode (bölüm) sayısı"); ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{len(dfs)} seed | pencere={SMOOTH}")
    _save(fig, "EP4_seed_episode.png")


if __name__ == "__main__":
    dfs = load()
    print(f"[ep] seed logu: {sorted(dfs)}")
    ep1_ogrenme(dfs); ep2_oda(dfs); ep3_carpisma(dfs); ep4_seed(dfs)
