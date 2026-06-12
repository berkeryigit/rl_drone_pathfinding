"""hp_search/ sonuclarindan sunum grafigi uretir.

Cikti: ../sunum/grafikler/hp_arama_sonuclari.png
  Panel 1: gamma x lr heatmap (return degerleri)
  Panel 2: Tum kombinasyonlar siralı bar chart (return + oda)
  Panel 3: Her kombinasyon icin ogrenme egrisi (200k adim)
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

HERE = Path(__file__).resolve().parent
SMOOTH = 20


def smooth(y, w=SMOOTH):
    return pd.Series(y).rolling(w, min_periods=1, center=True).mean().values


def load_results(hp_root: Path):
    results = []
    for log in sorted(hp_root.rglob("training_log.csv")):
        parts = log.parts
        tag = parts[list(hp_root.parts).__len__()]
        # tag: g0.98_lr3e-04 gibi
        try:
            g_part, lr_part = tag.split("_lr")
            gamma = float(g_part[1:])
            lr    = float(lr_part)
        except Exception:
            continue
        rows = list(csv.DictReader(open(log)))
        if not rows:
            continue
        last30 = rows[-30:]
        df = pd.read_csv(log)
        results.append({
            "tag": tag,
            "gamma": gamma,
            "lr": lr,
            "mean_return": sum(float(r["ep_return"]) for r in last30) / len(last30),
            "mean_rooms":  sum(float(r["visited_rooms"]) for r in last30) / len(last30),
            "success_pct": sum(float(r["success"]) for r in last30) / len(last30) * 100,
            "df": df,
        })
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hp-root", type=Path, default=HERE / "hp_search")
    parser.add_argument("--out", type=Path,
                        default=HERE / "../sunum/grafikler/hp_arama_sonuclari.png")
    args = parser.parse_args(argv)

    results = load_results(args.hp_root)
    if not results:
        print("hp_search/ altinda sonuc bulunamadi.")
        return

    gammas = sorted(set(r["gamma"] for r in results))
    lrs    = sorted(set(r["lr"] for r in results))
    results_sorted = sorted(results, key=lambda r: r["mean_return"], reverse=True)

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle("Hiperparametre Arama Sonuçları  (seed=42, 200k adım)",
                 fontsize=14, fontweight="bold")

    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.32)
    ax_heat_ret  = fig.add_subplot(gs[0, 0])
    ax_heat_room = fig.add_subplot(gs[0, 1])
    ax_bar       = fig.add_subplot(gs[0, 2])
    ax_curve     = fig.add_subplot(gs[1, :])

    # ── Panel 1: Heatmap — return ─────────────────────────────────────
    ret_grid = np.full((len(gammas), len(lrs)), np.nan)
    for r in results:
        gi = gammas.index(r["gamma"])
        li = lrs.index(r["lr"])
        ret_grid[gi, li] = r["mean_return"]

    im1 = ax_heat_ret.imshow(ret_grid, cmap="RdYlGn", aspect="auto",
                              vmin=np.nanmin(ret_grid), vmax=np.nanmax(ret_grid))
    ax_heat_ret.set_xticks(range(len(lrs)))
    ax_heat_ret.set_xticklabels([f"{lr:.0e}" for lr in lrs], fontsize=9)
    ax_heat_ret.set_yticks(range(len(gammas)))
    ax_heat_ret.set_yticklabels([str(g) for g in gammas], fontsize=9)
    ax_heat_ret.set_xlabel("learning rate", fontsize=9)
    ax_heat_ret.set_ylabel("gamma", fontsize=9)
    ax_heat_ret.set_title("Return (son 30 ep ort.)", fontsize=10, fontweight="bold")
    for gi in range(len(gammas)):
        for li in range(len(lrs)):
            v = ret_grid[gi, li]
            if not np.isnan(v):
                ax_heat_ret.text(li, gi, f"{v:.0f}", ha="center", va="center",
                                 fontsize=9, fontweight="bold",
                                 color="white" if v < np.nanmean(ret_grid) else "black")
    fig.colorbar(im1, ax=ax_heat_ret, shrink=0.8)

    # ── Panel 2: Heatmap — oda ───────────────────────────────────────
    room_grid = np.full((len(gammas), len(lrs)), np.nan)
    for r in results:
        gi = gammas.index(r["gamma"])
        li = lrs.index(r["lr"])
        room_grid[gi, li] = r["mean_rooms"]

    im2 = ax_heat_room.imshow(room_grid, cmap="RdYlGn", aspect="auto",
                               vmin=1, vmax=6)
    ax_heat_room.set_xticks(range(len(lrs)))
    ax_heat_room.set_xticklabels([f"{lr:.0e}" for lr in lrs], fontsize=9)
    ax_heat_room.set_yticks(range(len(gammas)))
    ax_heat_room.set_yticklabels([str(g) for g in gammas], fontsize=9)
    ax_heat_room.set_xlabel("learning rate", fontsize=9)
    ax_heat_room.set_ylabel("gamma", fontsize=9)
    ax_heat_room.set_title("Oda Sayısı (son 30 ep ort.)", fontsize=10, fontweight="bold")
    for gi in range(len(gammas)):
        for li in range(len(lrs)):
            v = room_grid[gi, li]
            if not np.isnan(v):
                ax_heat_room.text(li, gi, f"{v:.2f}", ha="center", va="center",
                                  fontsize=9, fontweight="bold",
                                  color="white" if v < 3.5 else "black")
    fig.colorbar(im2, ax=ax_heat_room, shrink=0.8)

    # ── Panel 3: Bar chart — sıralı ──────────────────────────────────
    tags   = [r["tag"].replace("g", "γ=").replace("_lr", "\nlr=") for r in results_sorted]
    rets   = [r["mean_return"] for r in results_sorted]
    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.9, len(rets)))[::-1]
    bars = ax_bar.barh(range(len(tags)), rets, color=colors, edgecolor="gray", linewidth=0.5)
    ax_bar.set_yticks(range(len(tags)))
    ax_bar.set_yticklabels(tags, fontsize=7.5)
    ax_bar.set_xlabel("Return (son 30 ep)", fontsize=9)
    ax_bar.set_title("Kombinasyon Sıralaması", fontsize=10, fontweight="bold")
    ax_bar.invert_yaxis()
    for i, (bar, r) in enumerate(zip(bars, results_sorted)):
        ax_bar.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                    f"{r['mean_return']:.0f}  ({r['mean_rooms']:.1f} oda)",
                    va="center", fontsize=7.5)
    # en iyi işaretle
    ax_bar.get_yticklabels()[0].set_color("green")
    ax_bar.get_yticklabels()[0].set_fontweight("bold")

    # ── Panel 4: Öğrenme eğrileri ─────────────────────────────────────
    cmap = plt.cm.tab10
    for i, r in enumerate(results_sorted):
        df = r["df"]
        color = cmap(i / len(results_sorted))
        lbl = r["tag"].replace("g", "γ=").replace("_lr", " lr=")
        ax_curve.plot(df["timestep"], smooth(df["ep_return"].values),
                      color=color, linewidth=1.5, label=lbl,
                      linestyle="-" if i == 0 else ("--" if i < 4 else ":"))

    ax_curve.set_title("Öğrenme Eğrileri — Tüm Kombinasyonlar (200k adım)",
                        fontsize=10, fontweight="bold")
    ax_curve.set_xlabel("Adım", fontsize=9)
    ax_curve.set_ylabel("Episode Getirisi (yumuşatılmış)", fontsize=9)
    ax_curve.legend(fontsize=7.5, ncol=3, loc="upper left")
    ax_curve.grid(True, alpha=0.3)
    ax_curve.tick_params(labelsize=8)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {args.out}")
    print(f"\nEn iyi: {results_sorted[0]['tag']}  "
          f"return={results_sorted[0]['mean_return']:.1f}  "
          f"oda={results_sorted[0]['mean_rooms']:.2f}  "
          f"basari=%{results_sorted[0]['success_pct']:.0f}")


if __name__ == "__main__":
    main()
