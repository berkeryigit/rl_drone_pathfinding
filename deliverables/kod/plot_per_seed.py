"""Her seed icin bireysel 2x2 dashboard grafigi + tum seed karsilastirmasi.

Panel basina (her seed):
  [1] Egitim episode getirisi  (ham soluk + yumusatilmis kalin)
  [2] Deterministik eval getirisi  (EvalCallback'ten evaluations.npz)
  [3] Kesif orani / Coverage %
  [4] Ziyaret edilen oda sayisi

Cikti dizini: ../sunum/grafikler/per_seed/
  seed_7_dashboard.png
  seed_13_dashboard.png
  seed_42_dashboard.png
  seed_123_dashboard.png
  seed_2025_dashboard.png
  tum_seedler_karsilastirma.png

Kullanim:
    python3 plot_per_seed.py
    python3 plot_per_seed.py --runs-root runs --seeds-file seeds.txt \\
        --out ../sunum/grafikler/per_seed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SMOOTH_WINDOW = 30
COLORS = plt.cm.tab10.colors


def read_seeds(path: Path) -> list[int]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(int(line))
    return out


def smooth(y: np.ndarray, window: int = SMOOTH_WINDOW) -> np.ndarray:
    return pd.Series(y).rolling(window, min_periods=1, center=True).mean().values


def load_log(runs_root: Path, seed: int) -> pd.DataFrame | None:
    p = runs_root / f"seed_{seed}" / "training_log.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


def load_eval(runs_root: Path, seed: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    p = runs_root / f"seed_{seed}" / "eval" / "evaluations.npz"
    if not p.exists():
        return None, None
    data = np.load(p)
    timesteps = data["timesteps"]
    results = data["results"].mean(axis=1)
    return timesteps, results


def _fmt_ax(ax, title: str, xlabel: str, ylabel: str):
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.3)


def plot_seed_dashboard(
    seed: int,
    df: pd.DataFrame,
    eval_ts: np.ndarray | None,
    eval_ret: np.ndarray | None,
    out_path: Path,
    color,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(
        f"Seed {seed}  —  Toplam {int(df['timestep'].iloc[-1]):,} step  "
        f"({len(df)} episode)",
        fontsize=13, fontweight="bold",
    )

    steps = df["timestep"].values

    # ── Panel 1: episode getirisi ──────────────────────────────────────
    ax = axes[0, 0]
    raw = df["ep_return"].values
    ax.plot(steps, raw, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(raw), color=color, linewidth=2.0, label=f"seed {seed}")
    _fmt_ax(ax, "Egitim Episode Getirisi", "Adim", "Episode Getirisi")
    ax.legend(fontsize=8)

    # ── Panel 2: deterministik eval ───────────────────────────────────
    ax = axes[0, 1]
    if eval_ts is not None and len(eval_ts) > 0:
        ax.plot(eval_ts, eval_ret, color=color, linewidth=2.0,
                marker="o", markersize=3, label=f"seed {seed}")
        best_idx = int(np.argmax(eval_ret))
        ax.axvline(eval_ts[best_idx], color=color, linestyle="--", alpha=0.4, linewidth=1)
        ax.annotate(
            f"en iyi: {eval_ret[best_idx]:.1f}",
            xy=(eval_ts[best_idx], eval_ret[best_idx]),
            xytext=(8, -12), textcoords="offset points",
            fontsize=7, color=color,
        )
    else:
        ax.text(0.5, 0.5, "eval verisi bulunamadi",
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
    _fmt_ax(ax, "Deterministik Eval Getirisi", "Adim", "Ortalama Getiri")
    ax.legend(fontsize=8)

    # ── Panel 3: coverage % ───────────────────────────────────────────
    ax = axes[1, 0]
    cov = df["coverage_pct"].values
    ax.plot(steps, cov, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(cov), color=color, linewidth=2.0)
    ax.set_ylim(0, 105)
    ax.axhline(100, color="green", linestyle="--", linewidth=1, alpha=0.4, label="%100 hedef")
    _fmt_ax(ax, "Kesif Orani (Coverage %)", "Adim", "Coverage (%)")
    ax.legend(fontsize=8)

    # ── Panel 4: visited rooms ─────────────────────────────────────────
    ax = axes[1, 1]
    rooms = df["visited_rooms"].values
    ax.plot(steps, rooms, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(rooms), color=color, linewidth=2.0)
    ax.axhline(6, color="red", linestyle="--", linewidth=1.2, alpha=0.6, label="hedef (6 oda)")
    ax.set_ylim(0, 7)
    _fmt_ax(ax, "Ziyaret Edilen Oda Sayisi", "Adim", "Oda Sayisi")
    ax.legend(fontsize=8)

    # özet istatistik kutusu
    last_n = min(200, len(df))
    last = df.tail(last_n)
    success_rate = last["success"].mean() * 100
    mean_cov = last["coverage_pct"].mean()
    mean_ret = last["ep_return"].mean()
    txt = (
        f"Son {last_n} ep ortalaması:\n"
        f"  Getiri  : {mean_ret:.1f}\n"
        f"  Coverage: {mean_cov:.1f}%\n"
        f"  Başarı  : %{success_rate:.0f}"
    )
    fig.text(0.01, 0.01, txt, fontsize=7.5, va="bottom",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.7))

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {out_path.name}")


def plot_combined(
    seeds: list[int],
    dfs: dict[int, pd.DataFrame | None],
    eval_data: dict[int, tuple],
    out_path: Path,
    max_steps: int | None = None,
) -> None:
    # max_steps belirtilmemisse tum seedlerin min adim sayisina kırp (adil karsilastirma)
    valid_dfs = {s: df for s, df in dfs.items() if df is not None}
    if max_steps is None:
        max_steps = int(min(df["timestep"].max() for df in valid_dfs.values()))

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(
        f"Tum Seedler — Karsilastirmali Egitim Ozeti (ilk {max_steps//1000}k adim)",
        fontsize=14, fontweight="bold",
    )

    for i, seed in enumerate(seeds):
        df = dfs[seed]
        if df is None:
            continue
        # max_steps'e kadar kes
        df = df[df["timestep"] <= max_steps]
        if df.empty:
            continue
        color = COLORS[i % len(COLORS)]
        label = f"seed {seed}"
        steps = df["timestep"].values

        # return
        axes[0, 0].plot(steps, smooth(df["ep_return"].values),
                        color=color, linewidth=1.6, label=label)
        # eval — max_steps uygulanmaz (eval resumed training'de geç basliyor olabilir)
        ts, ret = eval_data[seed]
        if ts is not None and len(ts) > 0:
            axes[0, 1].plot(ts, ret, color=color, linewidth=1.6,
                            marker="o", markersize=2, label=label)
        # coverage
        axes[1, 0].plot(steps, smooth(df["coverage_pct"].values),
                        color=color, linewidth=1.6, label=label)
        # rooms
        axes[1, 1].plot(steps, smooth(df["visited_rooms"].values),
                        color=color, linewidth=1.6, label=label)

    specs = [
        ("Egitim Episode Getirisi (yumusatilmis)", "Adim", "Episode Getirisi"),
        ("Deterministik Eval Getirisi",             "Adim", "Ortalama Getiri"),
        ("Kesif Orani",                             "Adim", "Coverage (%)"),
        ("Ziyaret Edilen Oda",                      "Adim", "Oda Sayisi"),
    ]
    for ax, (title, xlabel, ylabel) in zip(axes.flat, specs):
        _fmt_ax(ax, title, xlabel, ylabel)
        ax.legend(fontsize=8)

    # Eval verisi yoksa not ekle
    eval_ax = axes[0, 1]
    has_eval = any(
        eval_data[s][0] is not None and len(eval_data[s][0]) > 0
        for s in seeds if dfs.get(s) is not None
    )
    if not has_eval:
        eval_ax.text(0.5, 0.5, "eval verisi yok\n(evaluations.npz eksik)",
                     ha="center", va="center", transform=eval_ax.transAxes,
                     fontsize=9, color="gray")

    axes[1, 0].set_ylim(0, 105)
    axes[1, 1].set_ylim(0, 7)
    axes[1, 1].axhline(6, color="red", linestyle="--", linewidth=1.2,
                       alpha=0.5, label="hedef")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {out_path.name}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Per-seed dashboard grafikleri")
    parser.add_argument(
        "--runs-root", type=Path,
        default=Path(__file__).resolve().parent / "runs",
    )
    parser.add_argument(
        "--seeds-file", type=Path,
        default=Path(__file__).resolve().parent / "seeds.txt",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parent / "../sunum/grafikler/per_seed",
    )
    parser.add_argument(
        "--max-steps", type=int, default=None,
        help="Birlesik grafigi bu adima kadar kes (varsayilan: tum seedlerin minimumu)",
    )
    args = parser.parse_args(argv)

    seeds = read_seeds(args.seeds_file)
    out = args.out.resolve()

    dfs: dict[int, pd.DataFrame | None] = {}
    eval_data: dict[int, tuple] = {}
    for seed in seeds:
        dfs[seed] = load_log(args.runs_root, seed)
        eval_data[seed] = load_eval(args.runs_root, seed)
        if dfs[seed] is None:
            print(f"  [UYARI] seed {seed}: training_log.csv yok, atlaniyor")

    print("Bireysel seed dashboardlari:")
    for i, seed in enumerate(seeds):
        if dfs[seed] is None:
            continue
        ts, ret = eval_data[seed]
        plot_seed_dashboard(
            seed, dfs[seed], ts, ret,
            out / f"seed_{seed}_dashboard.png",
            COLORS[i % len(COLORS)],
        )

    print("Birlesik karsilastirma grafigi:")
    plot_combined(seeds, dfs, eval_data, out / "tum_seedler_karsilastirma.png",
                  max_steps=args.max_steps)
    print(f"\nTum grafikler: {out}")


if __name__ == "__main__":
    main()
