"""Her seed icin AYRI grafikler: ogrenme egrisi, eval egrisi, loss egrisi.

Ayrica her seed icin 2x2 dashboard ve tum seedleri ust uste koyan karsilastirma.

Cikti dizini: ../sunum/grafikler/per_seed/
  seed_<N>_dashboard.png              -> 2x2 ozet (getiri/eval/coverage/oda)
  tum_seedler_karsilastirma.png       -> tum seedler ust uste
  ogrenme_egrisi/seed_<N>.png         -> tek seed egitim getirisi
  eval_egrisi/seed_<N>.png            -> tek seed deterministik eval
  loss_egrisi/seed_<N>.png            -> tek seed actor & critic loss

Eval verisi iki kaynaktan gelir:
  1) runs/seed_<N>/eval/evaluations.npz  (egitim boyunca eval EGRISI; varsa)
  2) eval_per_episode.csv                 (evaluate.py'nin final eval'i; npz yoksa)
  Boylece eval npz'si olmayan seedler de bos kalmaz (evaluate.py verisini kullanir).

Kullanim:
    python plot_per_seed.py
    python plot_per_seed.py --runs-root runs --seeds-file seeds.txt \\
        --eval-csv ../sonuclar/eval_per_episode.csv \\
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
    df = pd.read_csv(p)
    return df if len(df) else None


def load_eval_curve(runs_root: Path, seed: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Egitim boyunca eval egrisi (evaluations.npz)."""
    p = runs_root / f"seed_{seed}" / "eval" / "evaluations.npz"
    if not p.exists():
        return None, None
    data = np.load(p)
    return data["timesteps"], data["results"].mean(axis=1)


def load_eval_csv(eval_csv: Path | None) -> pd.DataFrame | None:
    if eval_csv is None or not eval_csv.exists():
        return None
    df = pd.read_csv(eval_csv)
    return df if len(df) else None


def _fmt_ax(ax, title: str, xlabel: str, ylabel: str):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.3)


def _save(fig, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {out_path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Tek seed — ogrenme egrisi
# ─────────────────────────────────────────────────────────────────────────────
def plot_seed_learning(seed: int, df: pd.DataFrame, out_path: Path, color) -> None:
    steps = df["timestep"].values
    raw = df["ep_return"].values
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, raw, alpha=0.15, color=color, linewidth=0.6, label="ham episode getirisi")
    ax.plot(steps, smooth(raw), color=color, linewidth=2.3,
            label=f"hareketli ort. (pencere={SMOOTH_WINDOW})")
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    last = df.tail(min(50, len(df)))
    ax.annotate(f"son 50 ep ort: {last['ep_return'].mean():.1f}",
                xy=(steps[-1], smooth(raw)[-1]), xytext=(-130, 16),
                textcoords="offset points", fontsize=9, color=color,
                arrowprops=dict(arrowstyle="->", color=color, alpha=0.6))
    _fmt_ax(ax, f"Seed {seed} — Öğrenme Eğrisi (eğitim, {int(steps[-1]):,} adım)",
            "Kümülatif adım (timestep)", "Episode getirisi (toplam ödül)")
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Tek seed — eval egrisi (npz egrisi VEYA eval_per_episode.csv dagilimi)
# ─────────────────────────────────────────────────────────────────────────────
def plot_seed_eval(seed: int, eval_ts, eval_ret, eval_df: pd.DataFrame | None,
                   out_path: Path, color) -> None:
    # TUM seedler ayni format: evaluate.py'nin final deterministik eval'i
    # (eval_per_episode.csv) -> episode bazinda dagilim. Boylece eval npz'si
    # olan/olmayan tum seedlerde grafik birebir ayni gorunur.
    fig, ax = plt.subplots(figsize=(10, 6))

    if eval_df is not None and seed in set(eval_df["seed"].unique()):
        es = eval_df[eval_df["seed"] == seed]
        rets = es["ep_return"].values
        eps = np.arange(1, len(rets) + 1)
        ax.bar(eps, rets, color=color, alpha=0.75, edgecolor="white",
               label=f"final eval ({len(rets)} episode)")
        ax.axhline(rets.mean(), color="red", linestyle="--", linewidth=1.6,
                   label=f"ortalama: {rets.mean():.1f} (±{rets.std():.1f})")
        _fmt_ax(ax, f"Seed {seed} — Final Deterministik Eval (en iyi model)",
                "Episode", "Episode getirisi (toplam ödül)")
        ax.legend(loc="best", fontsize=9)
    else:
        ax.text(0.5, 0.5, "eval verisi yok\n(eval_per_episode.csv eksik -> evaluate.py calistirin)",
                ha="center", va="center", transform=ax.transAxes, fontsize=11, color="#b71c1c")
        _fmt_ax(ax, f"Seed {seed} — Eval", "Episode", "Getiri")

    _save(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Tek seed — loss egrisi (actor & critic, ikili eksen)
# ─────────────────────────────────────────────────────────────────────────────
def plot_seed_loss(seed: int, df: pd.DataFrame, out_path: Path) -> None:
    if "actor_loss" not in df.columns and "critic_loss" not in df.columns:
        return
    steps = df["timestep"].values
    fig, ax = plt.subplots(figsize=(10, 6))
    ax2 = ax.twinx()

    if "actor_loss" in df.columns:
        ax.plot(steps, smooth(df["actor_loss"].values), color="#c62828",
                linewidth=2.0, label="actor loss")
        ax.set_ylabel("Actor loss", color="#c62828", fontsize=9)
        ax.tick_params(axis="y", labelcolor="#c62828", labelsize=8)
    if "critic_loss" in df.columns:
        ax2.plot(steps, smooth(df["critic_loss"].values), color="#6a1b9a",
                 linewidth=2.0, label="critic loss")
        ax2.set_ylabel("Critic loss", color="#6a1b9a", fontsize=9)
        ax2.tick_params(axis="y", labelcolor="#6a1b9a", labelsize=8)

    ax.set_title(f"Seed {seed} — Loss Eğrisi (actor & critic, pencere={SMOOTH_WINDOW})",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)", fontsize=9)
    ax.grid(True, alpha=0.3)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], loc="upper right", fontsize=9)
    _save(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Tek seed — 2x2 dashboard
# ─────────────────────────────────────────────────────────────────────────────
def plot_seed_dashboard(seed, df, eval_ts, eval_ret, eval_df, out_path, color) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(f"Seed {seed}  —  Toplam {int(df['timestep'].iloc[-1]):,} adım  "
                 f"({len(df)} episode)", fontsize=13, fontweight="bold")
    steps = df["timestep"].values

    # 1) egitim getirisi
    ax = axes[0, 0]
    raw = df["ep_return"].values
    ax.plot(steps, raw, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(raw), color=color, linewidth=2.0, label=f"seed {seed}")
    _fmt_ax(ax, "Eğitim Episode Getirisi", "Adım", "Episode Getirisi")
    ax.legend(fontsize=8)

    # 2) eval — tum seedler ayni format: final deterministik eval (CSV) barlari
    ax = axes[0, 1]
    if eval_df is not None and seed in set(eval_df["seed"].unique()):
        es = eval_df[eval_df["seed"] == seed]["ep_return"].values
        ax.bar(np.arange(1, len(es) + 1), es, color=color, alpha=0.7)
        ax.axhline(es.mean(), color="red", linestyle="--", label=f"ort {es.mean():.1f}")
        _fmt_ax(ax, "Final Deterministik Eval", "Episode", "Getiri")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "eval verisi yok", ha="center", va="center",
                transform=ax.transAxes, fontsize=9, color="gray")
        _fmt_ax(ax, "Final Deterministik Eval", "Episode", "Getiri")

    # 3) coverage
    ax = axes[1, 0]
    cov = df["coverage_pct"].values
    ax.plot(steps, cov, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(cov), color=color, linewidth=2.0)
    ax.set_ylim(0, 105)
    ax.axhline(100, color="green", linestyle="--", linewidth=1, alpha=0.4, label="%100 hedef")
    _fmt_ax(ax, "Keşif Oranı (Coverage %)", "Adım", "Coverage (%)")
    ax.legend(fontsize=8)

    # 4) rooms
    ax = axes[1, 1]
    rooms = df["visited_rooms"].values
    ax.plot(steps, rooms, alpha=0.12, color=color, linewidth=0.5)
    ax.plot(steps, smooth(rooms), color=color, linewidth=2.0)
    ax.axhline(6, color="red", linestyle="--", linewidth=1.2, alpha=0.6, label="hedef (6 oda)")
    ax.set_ylim(0, 7)
    _fmt_ax(ax, "Ziyaret Edilen Oda Sayısı", "Adım", "Oda Sayısı")
    ax.legend(fontsize=8)

    last_n = min(200, len(df))
    last = df.tail(last_n)
    txt = (f"Son {last_n} ep ortalaması:\n"
           f"  Getiri  : {last['ep_return'].mean():.1f}\n"
           f"  Coverage: {last['coverage_pct'].mean():.1f}%\n"
           f"  Başarı  : %{last['success'].mean()*100:.0f}")
    fig.text(0.01, 0.01, txt, fontsize=7.5, va="bottom",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.7))
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    _save(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Tum seedler ust uste
# ─────────────────────────────────────────────────────────────────────────────
def plot_combined(seeds, dfs, eval_curves, out_path, max_steps=None) -> None:
    valid = {s: d for s, d in dfs.items() if d is not None}
    if not valid:
        return
    if max_steps is None:
        max_steps = int(min(d["timestep"].max() for d in valid.values()))

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"Tüm Seedler — Karşılaştırmalı Eğitim Özeti (ilk {max_steps//1000}k adım)",
                 fontsize=14, fontweight="bold")

    for i, seed in enumerate(seeds):
        df = dfs.get(seed)
        if df is None:
            continue
        df = df[df["timestep"] <= max_steps]
        if df.empty:
            continue
        color = COLORS[i % len(COLORS)]
        label = f"seed {seed}"
        steps = df["timestep"].values
        axes[0, 0].plot(steps, smooth(df["ep_return"].values), color=color, linewidth=1.6, label=label)
        ts, ret = eval_curves.get(seed, (None, None))
        if ts is not None and len(ts) > 0:
            axes[0, 1].plot(ts, ret, color=color, linewidth=1.6, marker="o", markersize=2, label=label)
        axes[1, 0].plot(steps, smooth(df["coverage_pct"].values), color=color, linewidth=1.6, label=label)
        axes[1, 1].plot(steps, smooth(df["visited_rooms"].values), color=color, linewidth=1.6, label=label)

    specs = [
        ("Eğitim Episode Getirisi (yumuşatılmış)", "Adım", "Episode Getirisi"),
        ("Deterministik Eval Eğrisi", "Adım", "Ortalama Getiri"),
        ("Keşif Oranı", "Adım", "Coverage (%)"),
        ("Ziyaret Edilen Oda", "Adım", "Oda Sayısı"),
    ]
    for ax, (title, xlabel, ylabel) in zip(axes.flat, specs):
        _fmt_ax(ax, title, xlabel, ylabel)
        ax.legend(fontsize=8)

    if not any(eval_curves.get(s, (None, None))[0] is not None for s in seeds):
        axes[0, 1].text(0.5, 0.5, "eval eğrisi yok\n(evaluations.npz eksik)",
                        ha="center", va="center", transform=axes[0, 1].transAxes,
                        fontsize=9, color="gray")
    axes[1, 0].set_ylim(0, 105)
    axes[1, 1].set_ylim(0, 7)
    axes[1, 1].axhline(6, color="red", linestyle="--", linewidth=1.2, alpha=0.5)
    plt.tight_layout()
    _save(fig, out_path)


def main(argv=None) -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Per-seed ayri grafikler + dashboard")
    parser.add_argument("--runs-root", type=Path, default=here / "runs")
    parser.add_argument("--seeds-file", type=Path, default=here / "seeds.txt")
    parser.add_argument("--eval-csv", type=Path, default=here / "../sonuclar/eval_per_episode.csv",
                        help="evaluate.py ciktisi; eval npz'si olmayan seedler icin yedek")
    parser.add_argument("--out", type=Path, default=here / "../sunum/grafikler/per_seed")
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args(argv)

    seeds = read_seeds(args.seeds_file)
    out = args.out.resolve()
    eval_df = load_eval_csv(args.eval_csv.resolve())
    if eval_df is None:
        print("  [NOT] eval_per_episode.csv bulunamadi -> once 'python evaluate.py' calistirin "
              "(eval npz'si olmayan seedlerin eval grafigi bos kalir).")

    dfs, eval_curves = {}, {}
    for s in seeds:
        dfs[s] = load_log(args.runs_root, s)
        eval_curves[s] = load_eval_curve(args.runs_root, s)
        if dfs[s] is None:
            print(f"  [UYARI] seed {s}: training_log.csv yok, atlaniyor")

    print("Her seed icin AYRI grafikler (ogrenme / eval / loss / dashboard):")
    for i, s in enumerate(seeds):
        if dfs[s] is None:
            continue
        color = COLORS[i % len(COLORS)]
        ts, ret = eval_curves[s]
        plot_seed_learning(s, dfs[s], out / "ogrenme_egrisi" / f"seed_{s}.png", color)
        plot_seed_eval(s, ts, ret, eval_df, out / "eval_egrisi" / f"seed_{s}.png", color)
        plot_seed_loss(s, dfs[s], out / "loss_egrisi" / f"seed_{s}.png")
        plot_seed_dashboard(s, dfs[s], ts, ret, eval_df, out / f"seed_{s}_dashboard.png", color)

    print("Birlesik karsilastirma:")
    plot_combined(seeds, dfs, eval_curves, out / "tum_seedler_karsilastirma.png",
                  max_steps=args.max_steps)
    print(f"\nTum grafikler: {out}")


if __name__ == "__main__":
    main()
