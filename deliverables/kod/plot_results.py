"""Rehber B bolumu 5 ZORUNLU grafigi (ayri PNG) + sonuclar.csv uretir.

Her grafik: baslik, birimli eksen etiketi, lejant, >=5 seed ortalama +/- std bandi,
hareketli ortalama penceresi. y-ekseni ASLA anlik odul degil -> EPISODE GETIRISI.

Grafikler:
  1) ogrenme_egrisi.png        -> egitim episode getirisi (mean+/-std), x=kumulatif step
  2) eval_egrisi.png           -> deterministik eval getirisi (mean+/-std), x=step
  3) loss_egrisi.png           -> actor & critic loss (mean+/-std)
  4) hiperparametre_duyarlilik.png -> >=2 param x >=3 deger (runs_hp/ varsa)
  5) baseline_karsilastirma.png -> random/heuristic vs egitilmis ajan

Ayrica: ../sonuclar/sonuclar.csv (seed x metrik ozeti)

Kullanim:
    python plot_results.py --runs-root runs --seeds-file seeds.txt \
        --eval-csv ../sonuclar/eval_per_episode.csv \
        --baseline-csv ../sonuclar/baseline_per_episode.csv \
        --hp-root runs_hp \
        --out ../sunum/grafikler --summary-out ../sonuclar/sonuclar.csv
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

SMOOTH_WINDOW = 15      # hareketli ortalama penceresi (grafiklerde belirtilir)
N_BINS = 60


# --------------------------------------------------------------------------- #
# yardimcilar
# --------------------------------------------------------------------------- #
def read_seeds(path: Path) -> list[int]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(int(line))
    return out


def smooth(y: np.ndarray, window: int = SMOOTH_WINDOW) -> np.ndarray:
    if len(y) < 2:
        return y
    return pd.Series(y).rolling(window, min_periods=1, center=True).mean().values


def load_training_logs(runs_root: Path, seeds: list[int]) -> dict[int, pd.DataFrame]:
    out = {}
    for s in seeds:
        p = runs_root / f"seed_{s}" / "training_log.csv"
        if p.exists():
            df = pd.read_csv(p)
            if len(df) > 0:
                out[s] = df
    return out


def aligned_curve(dfs: dict[int, pd.DataFrame], ycol: str, xcol: str = "timestep",
                  n_bins: int = N_BINS):
    """Seed'leri ortak timestep binlerine hizalar; (centers, mean, std, n) doner."""
    valid = {s: d for s, d in dfs.items() if ycol in d.columns and xcol in d.columns}
    if not valid:
        return None
    x_max = min(float(d[xcol].max()) for d in valid.values())
    if x_max <= 0:
        return None
    edges = np.linspace(0.0, x_max, n_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    per_seed = []
    for d in valid.values():
        x = d[xcol].to_numpy(dtype=float)
        y = d[ycol].to_numpy(dtype=float)
        idx = np.clip(np.digitize(x, edges) - 1, 0, n_bins - 1)
        binned = np.full(n_bins, np.nan)
        for b in range(n_bins):
            sel = y[idx == b]
            if sel.size:
                binned[b] = sel.mean()
        # bin bosluklarini doldur (ileri/geri)
        binned = pd.Series(binned).ffill().bfill().to_numpy()
        per_seed.append(binned)
    stack = np.vstack(per_seed)
    return centers, np.nanmean(stack, axis=0), np.nanstd(stack, axis=0), len(per_seed)


def _style(ax, title, xlabel, ylabel, n_seeds):
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=9, title=f"{n_seeds} seed | hareketli ort. pencere={SMOOTH_WINDOW}")


def _placeholder(out_path: Path, title: str, msg: str):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=12, color="#b71c1c", wrap=True)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] (placeholder) {out_path} -- {msg}")


def _save(fig, out_path: Path):
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


# --------------------------------------------------------------------------- #
# 1) Ogrenme egrisi
# --------------------------------------------------------------------------- #
def graph_learning(dfs, out_path: Path):
    res = aligned_curve(dfs, "ep_return")
    if res is None:
        _placeholder(out_path, "1) Ogrenme Egrisi", "training_log.csv bulunamadi -> once train.py calistirin")
        return
    centers, mean, std, n = res
    mean_s = smooth(mean)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(centers, mean_s - std, mean_s + std, alpha=0.2, color="#0288d1", label="+/- std (seed)")
    ax.plot(centers, mean_s, color="#0288d1", linewidth=2.2, label="Ortalama episode getirisi")
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    _style(ax, "1) Ogrenme Egrisi (egitim)", "Kumulatif adim (timestep)", "Episode getirisi (toplam odul)", n)
    _save(fig, out_path)


# --------------------------------------------------------------------------- #
# 2) Eval (deterministik) egrisi
# --------------------------------------------------------------------------- #
def graph_eval_curve(runs_root: Path, seeds: list[int], out_path: Path):
    series = []
    for s in seeds:
        npz = runs_root / f"seed_{s}" / "eval" / "evaluations.npz"
        if not npz.exists():
            continue
        data = np.load(npz)
        ts = data["timesteps"].astype(float)
        res = data["results"].mean(axis=1).astype(float)
        if ts.size:
            series.append((ts, res))
    if len(series) == 0:
        _placeholder(out_path, "2) Eval Egrisi", "eval/evaluations.npz yok -> train.py'yi --no-eval'siz calistirin")
        return
    x_max = min(ts[-1] for ts, _ in series)
    grid = np.linspace(0.0, x_max, N_BINS)
    interp = np.vstack([np.interp(grid, ts, res) for ts, res in series])
    mean, std = interp.mean(axis=0), interp.std(axis=0)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(grid, mean - std, mean + std, alpha=0.2, color="#2e7d32", label="+/- std (seed)")
    ax.plot(grid, mean, color="#2e7d32", linewidth=2.2, label="Deterministik eval getirisi")
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    _style(ax, "2) Test (Eval) Egrisi -- greedy/deterministik politika",
           "Kumulatif adim (timestep)", "Episode getirisi (toplam odul)", len(series))
    _save(fig, out_path)


# --------------------------------------------------------------------------- #
# 3) Loss egrisi
# --------------------------------------------------------------------------- #
def graph_loss(dfs, out_path: Path):
    a = aligned_curve(dfs, "actor_loss")
    c = aligned_curve(dfs, "critic_loss")
    if a is None and c is None:
        _placeholder(out_path, "3) Loss Egrisi", "actor/critic loss verisi yok")
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    ax2 = ax.twinx()
    n = 0
    if a is not None:
        ca, ma, sa, n = a
        ma = smooth(ma)
        ax.fill_between(ca, ma - sa, ma + sa, alpha=0.15, color="#c62828")
        ax.plot(ca, ma, color="#c62828", linewidth=2, label="Actor loss")
        ax.set_ylabel("Actor loss", color="#c62828")
        ax.tick_params(axis="y", labelcolor="#c62828")
    if c is not None:
        cc, mc, sc, n = c
        mc = smooth(mc)
        ax2.fill_between(cc, mc - sc, mc + sc, alpha=0.15, color="#6a1b9a")
        ax2.plot(cc, mc, color="#6a1b9a", linewidth=2, label="Critic loss")
        ax2.set_ylabel("Critic loss", color="#6a1b9a")
        ax2.tick_params(axis="y", labelcolor="#6a1b9a")
    ax.set_title("3) Loss Egrisi (actor & critic)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Kumulatif adim (timestep)")
    ax.grid(alpha=0.25)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [ln.get_label() for ln in lines], loc="best",
              fontsize=9, title=f"{n} seed | pencere={SMOOTH_WINDOW}")
    _save(fig, out_path)


# --------------------------------------------------------------------------- #
# 4) Hiperparametre duyarliligi
# --------------------------------------------------------------------------- #
def graph_hp(hp_root: Path, out_path: Path):
    """runs_hp/<param>/<value>/seed_<s>/training_log.csv yapisindan okur.

    Iki panel: (sol) final episode getirisi, (sag) keşfedilen oda — her ikisi
    de hiperparametre degerine karsi, seed'ler uzerinden mean +/- std.
    """
    if not hp_root.exists():
        _placeholder(out_path, "4) Hiperparametre Duyarliligi",
                     f"{hp_root} yok -> sweep.sh calistirin (>=2 param x >=3 deger)")
        return

    # param -> liste[(value, ret_mean, ret_std, room_mean, room_std)]
    data: dict[str, list] = {}
    for param_dir in sorted(p for p in hp_root.iterdir() if p.is_dir()):
        rows = []
        for value_dir in sorted(param_dir.iterdir(), key=lambda p: _num(p.name)):
            if not value_dir.is_dir():
                continue
            rets, rooms = [], []
            for seed_dir in value_dir.glob("seed_*"):
                log = seed_dir / "training_log.csv"
                if log.exists():
                    df = pd.read_csv(log)
                    if len(df):
                        tail = df.tail(max(5, len(df) // 10))
                        rets.append(tail["ep_return"].mean())
                        if "visited_rooms" in df.columns:
                            rooms.append(tail["visited_rooms"].mean())
            if rets:
                rows.append((_num(value_dir.name),
                             float(np.mean(rets)), float(np.std(rets)),
                             float(np.mean(rooms)) if rooms else np.nan,
                             float(np.std(rooms)) if rooms else 0.0))
        if rows:
            data[param_dir.name] = rows
    if not data:
        _placeholder(out_path, "4) Hiperparametre Duyarliligi", f"{hp_root} icinde gecerli kosu yok")
        return

    # Her parametre KENDI satirinda (farkli deger olcekleri cakismasin);
    # sutunlar: [getiri, oda]. Her satir kendi x-olcegini (gerekirse log) kullanir.
    params = sorted(data.keys())
    n = len(params)
    fig, axes = plt.subplots(n, 2, figsize=(15, 4.6 * n), squeeze=False)
    fig.suptitle("4) Hiperparametre Duyarlılığı (eğitim sonu, seed ortalaması ± std)",
                 fontsize=14, fontweight="bold")
    c_ret, c_room = "#0288d1", "#2e7d32"

    for ri, param in enumerate(params):
        rows = sorted(data[param], key=lambda r: r[0])
        xs  = np.array([r[0] for r in rows])
        ret = np.array([r[1] for r in rows]); ret_s = np.array([r[2] for r in rows])
        rm  = np.array([r[3] for r in rows]); rm_s  = np.array([r[4] for r in rows])
        # bu parametrenin kendi araligi genis mi? -> log eksen
        rng = xs.max() / max(xs.min(), 1e-12)
        use_log = rng >= 8

        axL, axR = axes[ri]
        # --- getiri ---
        axL.errorbar(xs, ret, yerr=ret_s, marker="o", markersize=9, capsize=5,
                     linewidth=2.2, color=c_ret)
        for x, y in zip(xs, ret):
            axL.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                         xytext=(0, 11), ha="center", fontsize=10, fontweight="bold", color=c_ret)
        best = int(np.argmax(ret))
        axL.scatter([xs[best]], [ret[best]], s=200, facecolors="none",
                    edgecolors="red", linewidths=2.2, zorder=5,
                    label=f"en iyi: {param}={_fmt_val(xs[best])}")
        axL.set_title(f"{param} → Final Episode Getirisi", fontsize=12, fontweight="bold")
        axL.set_ylabel("Episode getirisi (mean ± std)", fontsize=10)
        axL.legend(loc="best", fontsize=9)

        # --- oda ---
        if not np.isnan(rm).all():
            axR.errorbar(xs, rm, yerr=rm_s, marker="s", markersize=9, capsize=5,
                         linewidth=2.2, color=c_room)
            for x, y in zip(xs, rm):
                axR.annotate(f"{y:.2f}", (x, y), textcoords="offset points",
                             xytext=(0, 11), ha="center", fontsize=10, fontweight="bold", color=c_room)
            axR.axhline(6, color="green", linestyle="--", linewidth=1.2, alpha=0.5, label="hedef (6)")
            axR.set_ylim(0, 6.5)
            axR.legend(loc="best", fontsize=9)
        axR.set_title(f"{param} → Keşfedilen Oda", fontsize=12, fontweight="bold")
        axR.set_ylabel("Oda (6 üzerinden, mean ± std)", fontsize=10)

        for ax in (axL, axR):
            if use_log:
                ax.set_xscale("log")
            ax.set_xticks(xs)
            ax.set_xticklabels([_fmt_val(v) for v in xs], fontsize=9)
            ax.set_xlabel(f"{param} değeri" + (" (log eksen)" if use_log else ""), fontsize=10)
            ax.grid(alpha=0.3, which="both")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    _save(fig, out_path)


def _fmt_val(v: float) -> str:
    """Hiperparametre degerini okunabilir bicimde yaz: 0.0003 -> 3e-04, 0.1 -> 0.1."""
    if v != 0 and (abs(v) < 1e-2 or abs(v) >= 1e4):
        return f"{v:.0e}"
    return f"{v:g}"


def _num(name: str) -> float:
    # "lr=3e-4" veya "3e-4" -> 3e-4
    token = name.split("=")[-1]
    try:
        return float(token)
    except ValueError:
        return float(abs(hash(token)) % 1000)


# --------------------------------------------------------------------------- #
# 5) Baseline karsilastirma — cok metrikli (getiri + oda + kapsama)
# --------------------------------------------------------------------------- #
def graph_baseline(eval_csv: Path, baseline_csv: Path, out_path: Path):
    # Her politika icin tum metrik kolonlarini topla
    frames: dict[str, pd.DataFrame] = {}
    if baseline_csv.exists():
        b = pd.read_csv(baseline_csv)
        for name, g in b.groupby("policy"):
            frames[str(name)] = g
    if eval_csv.exists():
        frames["agent (SAC)"] = pd.read_csv(eval_csv)
    if not frames:
        _placeholder(out_path, "5) Baseline Karsilastirma",
                     "baseline/eval csv yok -> baseline.py ve evaluate.py calistirin")
        return

    order = [k for k in ("random", "heuristic", "agent (SAC)") if k in frames]
    order += [k for k in frames if k not in order]
    bar_colors = {"random": "#9e9e9e", "heuristic": "#ff9800", "agent (SAC)": "#0288d1"}
    colors = [bar_colors.get(k, "#607d8b") for k in order]

    # 4 metrik: getiri, ziyaret edilen oda, kapsama %, basari orani
    metrics = [
        ("ep_return",     "Ortalama Episode Getirisi", "Getiri (toplam ödül)", False, "{:.0f}"),
        ("visited_rooms", "Keşfedilen Oda Sayısı",     "Oda (6 üzerinden)",     6.0,   "{:.2f}"),
        ("coverage_pct",  "Alan Kapsama (Coverage)",   "Kapsama (%)",          100.0,  "{:.1f}"),
        ("success",       "Tam-Keşif Başarı Oranı",    "Başarı (%)",           100.0,  "{:.0f}"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("5) Baseline Karşılaştırması — Rastgele / Heuristik / SAC (deterministik eval)",
                 fontsize=14, fontweight="bold")

    for ax, (col, title, ylabel, target, fmt) in zip(axes.flat, metrics):
        means, stds, labels = [], [], []
        for k in order:
            if col not in frames[k].columns:
                continue
            vals = frames[k][col].to_numpy(dtype=float)
            if col == "success":
                vals = vals * 100.0   # orani yuzdeye cevir
            means.append(vals.mean())
            stds.append(vals.std())
            labels.append(k.replace("agent (SAC)", "SAC"))
        x = np.arange(len(labels))
        ax.bar(x, means, yerr=stds, capsize=5,
               color=[bar_colors.get(o, "#607d8b") for o in order[:len(labels)]],
               edgecolor="white")
        for i, (m, s) in enumerate(zip(means, stds)):
            ax.text(i, m + (max(stds) * 0.12 if max(stds) else 0.5),
                    fmt.format(m), ha="center", fontsize=10, fontweight="bold")
        if target:
            ax.axhline(target, color="green", linestyle="--", linewidth=1.2,
                       alpha=0.5, label="hedef")
            ax.legend(loc="upper left", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(alpha=0.25, axis="y")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    _save(fig, out_path)


# --------------------------------------------------------------------------- #
# sonuclar.csv (seed x metrik ozeti)
# --------------------------------------------------------------------------- #
def write_summary(dfs, eval_csv: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    eval_df = pd.read_csv(eval_csv) if eval_csv.exists() else None
    fields = ["seed", "n_episode", "train_final_return", "train_max_return",
              "train_success_rate", "train_crash_rate",
              "eval_mean_return", "eval_std_return", "eval_success_rate", "eval_mean_coverage_pct"]
    rows = []
    for s, df in sorted(dfs.items()):
        tail = df.tail(max(5, len(df) // 10))
        row = {
            "seed": s,
            "n_episode": len(df),
            "train_final_return": round(tail["ep_return"].mean(), 2),
            "train_max_return": round(df["ep_return"].max(), 2),
            "train_success_rate": round(tail["success"].mean(), 3) if "success" in df else "",
            "train_crash_rate": round(tail["crashed"].mean(), 3) if "crashed" in df else "",
            "eval_mean_return": "", "eval_std_return": "",
            "eval_success_rate": "", "eval_mean_coverage_pct": "",
        }
        if eval_df is not None and s in set(eval_df["seed"].unique()):
            es = eval_df[eval_df["seed"] == s]
            row["eval_mean_return"] = round(es["ep_return"].mean(), 2)
            row["eval_std_return"] = round(es["ep_return"].std(), 2)
            row["eval_success_rate"] = round(es["success"].mean(), 3)
            row["eval_mean_coverage_pct"] = round(es["coverage_pct"].mean(), 2)
        rows.append(row)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[plot] ozet -> {out_path} ({len(rows)} seed)")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="5 zorunlu grafik + sonuclar.csv")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--seeds-file", type=Path, default=Path(__file__).resolve().parent / "seeds.txt")
    parser.add_argument("--eval-csv", type=Path, default=Path("../sonuclar/eval_per_episode.csv"))
    parser.add_argument("--baseline-csv", type=Path, default=Path("../sonuclar/baseline_per_episode.csv"))
    parser.add_argument("--hp-root", type=Path, default=Path("runs_hp"))
    parser.add_argument("--out", type=Path, default=Path("../sunum/grafikler"))
    parser.add_argument("--summary-out", type=Path, default=Path("../sonuclar/sonuclar.csv"))
    args = parser.parse_args(argv)

    seeds = read_seeds(args.seeds_file)
    args.out.mkdir(parents=True, exist_ok=True)
    dfs = load_training_logs(args.runs_root, seeds)
    if len(dfs) < 5:
        print(f"[plot] UYARI: {len(dfs)} seed log'u bulundu (>=5 onerilir).")

    graph_learning(dfs, args.out / "1_ogrenme_egrisi.png")
    graph_eval_curve(args.runs_root, seeds, args.out / "2_eval_egrisi.png")
    graph_loss(dfs, args.out / "3_loss_egrisi.png")
    graph_hp(args.hp_root, args.out / "4_hiperparametre_duyarlilik.png")
    graph_baseline(args.eval_csv, args.baseline_csv, args.out / "5_baseline_karsilastirma.png")
    write_summary(dfs, args.eval_csv, args.summary_out)


if __name__ == "__main__":
    main()
