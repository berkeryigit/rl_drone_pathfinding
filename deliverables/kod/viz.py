"""Kapsamli gorsellestirme motoru -- PPO teslimi + ekip-esdeger grafikler + PPO/SAC kiyas.

Tek modul, cok grafik. Her grafik: baslik, birimli eksen etiketi, lejant, >=5 seed
(ana grafiklerde) ortalama +/- std bandi, hareketli ortalama. y-ekseni ASLA anlik
odul degil -> EPISODE GETIRISI.

Veri kaynaklari (hepsi opsiyonel; yoksa o grafik atlanir):
  runs/seed_<s>/training_log.csv          ana 5-seed PPO (ep_return, coverage, rooms, crash, loss)
  runs/seed_<s>/eval/evaluations.npz      deterministik eval egrisi
  runs/seed_<s>/logs/progress.csv         PPO-ozel: clip_fraction, approx_kl, entropy, explained_variance
  runs_hp5/<param>/<value>/seed_<s>/...    hiperparametre sweep'leri
  runs_grid/g<g>_lr<lr>/seed_<s>/...       gamma x lr grid (heatmap)
  runs_long/seed_123/training_log.csv      bonus uzun-ufuk (5M)
  runs_sac/seed_<s>/...                     SAC (kiyas)
  ../sonuclar/eval_per_episode.csv          per-seed deterministik eval (bar)
  ../sonuclar/baseline_per_episode.csv      random/heuristic baseline

Kullanim:
    python viz.py --all
    python viz.py --section main           # 1..9, per-seed, long
    python viz.py --section compare        # PPO vs SAC
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401

# -- Turkce karakterler icin DejaVu Sans (matplotlib varsayilani; ş,ğ,ı,İ icerir) --
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13, "axes.labelsize": 11,
    "figure.dpi": 140, "savefig.dpi": 150,
    "axes.grid": True, "grid.alpha": 0.25,
    "legend.fontsize": 9,
})

SMOOTH = 15
N_BINS = 60
SEEDS = [7, 13, 42, 123, 2025]
PPO_C = "#1565c0"      # PPO mavi
SAC_C = "#e65100"      # SAC turuncu
SEED_COLORS = {7: "#1565c0", 13: "#2e7d32", 42: "#c62828", 123: "#6a1b9a", 2025: "#ef6c00"}
TOTAL_CELLS = 32 * 32
N_ROOMS = 6


# --------------------------------------------------------------------------- #
# yardimcilar
# --------------------------------------------------------------------------- #
def smooth(y, window=SMOOTH):
    y = np.asarray(y, dtype=float)
    if len(y) < 2:
        return y
    return pd.Series(y).rolling(window, min_periods=1, center=True).mean().to_numpy()


def load_logs(root: Path, seeds=SEEDS, fname="training_log.csv"):
    out = {}
    for s in seeds:
        p = root / f"seed_{s}" / fname
        if p.exists():
            df = pd.read_csv(p)
            if len(df):
                out[s] = df
    return out


def load_progress(root: Path, seeds=SEEDS):
    """SB3 progress.csv (PPO ek metrikler). x ekseni = time/total_timesteps."""
    out = {}
    for s in seeds:
        p = root / f"seed_{s}" / "logs" / "progress.csv"
        if p.exists():
            df = pd.read_csv(p)
            if len(df) and "time/total_timesteps" in df.columns:
                out[s] = df
    return out


def aligned(dfs, ycol, xcol="timestep", n_bins=N_BINS, xmax=None):
    """Seed'leri ortak x binlerine hizalar -> (centers, mean, std, n)."""
    valid = {s: d for s, d in dfs.items() if ycol in d.columns and xcol in d.columns}
    if not valid:
        return None
    x_max = xmax if xmax is not None else min(float(d[xcol].max()) for d in valid.values())
    if x_max <= 0:
        return None
    edges = np.linspace(0.0, x_max, n_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    per = []
    for d in valid.values():
        x = d[xcol].to_numpy(float)
        y = d[ycol].to_numpy(float)
        idx = np.clip(np.digitize(x, edges) - 1, 0, n_bins - 1)
        b = np.full(n_bins, np.nan)
        for k in range(n_bins):
            sel = y[idx == k]
            if sel.size:
                b[k] = sel.mean()
        b = pd.Series(b).ffill().bfill().to_numpy()
        per.append(b)
    stack = np.vstack(per)
    return centers, np.nanmean(stack, axis=0), np.nanstd(stack, axis=0), len(per)


def _save(fig, path: Path, msg=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), bbox_inches="tight")
    plt.close(fig)
    print(f"[viz] {path.name} {msg}")


def _eval_curves(root: Path, seeds=SEEDS):
    series = {}
    for s in seeds:
        npz = root / f"seed_{s}" / "eval" / "evaluations.npz"
        if npz.exists():
            d = np.load(npz)
            ts = d["timesteps"].astype(float)
            res = d["results"].mean(axis=1).astype(float)
            if ts.size:
                series[s] = (ts, res)
    return series


def _eval_band(series, n_bins=N_BINS):
    if not series:
        return None
    x_max = min(ts[-1] for ts, _ in series.values())
    grid = np.linspace(0.0, x_max, n_bins)
    interp = np.vstack([np.interp(grid, ts, res) for ts, res in series.values()])
    return grid, interp.mean(0), interp.std(0), len(series)


# =========================================================================== #
# ANA GRAFIKLER (PPO)
# =========================================================================== #
def g1_learning(dfs, out):
    r = aligned(dfs, "ep_return")
    if not r:
        return
    c, m, sd, n = r
    ms = smooth(m)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(c, ms - sd, ms + sd, alpha=0.2, color=PPO_C, label="+/- std (seed)")
    ax.plot(c, ms, color=PPO_C, lw=2.3, label="Ortalama episode getirisi (PPO)")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("1) Öğrenme Eğrisi (PPO eğitim)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{n} seed | hareketli ort. pencere={SMOOTH}")
    _save(fig, out)


def g1b_learning_episode(dfs, out):
    """Hocanin acik istegi: x ekseni EPISODE sayisi olan ogrenme egrisi."""
    valid = {s: d for s, d in dfs.items() if "ep_return" in d}
    if not valid:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    n_ep = min(len(d) for d in valid.values())
    grid = np.arange(n_ep)
    stack = np.vstack([smooth(d["ep_return"].to_numpy(float)[:n_ep]) for d in valid.values()])
    m, sd = stack.mean(0), stack.std(0)
    ax.fill_between(grid, m - sd, m + sd, alpha=0.2, color=PPO_C, label="+/- std (seed)")
    ax.plot(grid, m, color=PPO_C, lw=2.3, label="Ortalama episode getirisi (PPO)")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("1b) Öğrenme Eğrisi -- x = Episode sayısı", fontweight="bold")
    ax.set_xlabel("Episode (bölüm) sayısı")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{len(valid)} seed | pencere={SMOOTH}")
    _save(fig, out)


def g2_eval(root, out):
    band = _eval_band(_eval_curves(root))
    if not band:
        return
    g, m, sd, n = band
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(g, m - sd, m + sd, alpha=0.2, color="#2e7d32", label="+/- std (seed)")
    ax.plot(g, m, color="#2e7d32", lw=2.3, label="Deterministik eval getirisi (PPO)")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("2) Test (Eval) Eğrisi -- greedy/deterministik politika", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{n} seed | pencere={SMOOTH}")
    _save(fig, out)


def g3_loss(dfs, out):
    a = aligned(dfs, "actor_loss")
    c = aligned(dfs, "critic_loss")
    if not a and not c:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    ax2 = ax.twinx()
    n = 0
    if a:
        ca, ma, sa, n = a
        ma = smooth(ma)
        ax.fill_between(ca, ma - sa, ma + sa, alpha=0.15, color="#c62828")
        ax.plot(ca, ma, color="#c62828", lw=2, label="Policy gradient loss (actor)")
        ax.set_ylabel("Policy gradient loss (actor)", color="#c62828")
        ax.tick_params(axis="y", labelcolor="#c62828")
    if c:
        cc, mc, sc, n = c
        mc = smooth(mc)
        ax2.fill_between(cc, mc - sc, mc + sc, alpha=0.15, color="#6a1b9a")
        ax2.plot(cc, mc, color="#6a1b9a", lw=2, label="Value loss (critic)")
        ax2.set_ylabel("Value loss (critic)", color="#6a1b9a")
        ax2.tick_params(axis="y", labelcolor="#6a1b9a")
    ax.set_title("3) Loss Eğrisi (PPO: policy gradient & value loss)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.grid(alpha=0.25)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc="center right",
              title=f"{n} seed | pencere={SMOOTH}")
    _save(fig, out)


def _num(name: str) -> float:
    try:
        return float(name)
    except ValueError:
        return float(abs(hash(name)) % 1000)


def _hp_collect(hp_root: Path):
    """runs_hp5/<param>/<value>/seed_<s>/ -> {param: (xs, ys_ret, es_ret, ys_room, es_room)}."""
    data = {}
    if not hp_root.exists():
        return data
    for param_dir in sorted(p for p in hp_root.iterdir() if p.is_dir()):
        xs, yr, er, yo, eo = [], [], [], [], []
        for vdir in sorted(param_dir.iterdir(), key=lambda p: _num(p.name)):
            if not vdir.is_dir():
                continue
            rets, rooms = [], []
            for sdir in vdir.glob("seed_*"):
                log = sdir / "training_log.csv"
                if log.exists():
                    df = pd.read_csv(log)
                    if len(df):
                        tail = df.tail(max(5, len(df) // 10))
                        rets.append(tail["ep_return"].mean())
                        rooms.append(tail["visited_rooms"].mean())
            if rets:
                xs.append(_num(vdir.name)); yr.append(np.mean(rets)); er.append(np.std(rets))
                yo.append(np.mean(rooms)); eo.append(np.std(rooms))
        if xs:
            o = np.argsort(xs)
            data[param_dir.name] = tuple(np.array(v)[o] for v in (xs, yr, er, yo, eo))
    return data


def g4_hp(hp_root, out):
    data = _hp_collect(hp_root)
    if not data:
        return
    order = [k for k in ("clip_range", "ent_coef", "gamma", "learning_rate", "vf_coef") if k in data]
    order += [k for k in data if k not in order]
    n = len(order)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4.8))
    if n == 1:
        axes = [axes]
    palette = {"clip_range": "#00838f", "ent_coef": "#1565c0", "gamma": "#6a1b9a",
               "learning_rate": "#ef6c00", "vf_coef": "#2e7d32"}
    for ax, name in zip(axes, order):
        xs, yr, er, _, _ = data[name]
        ax.errorbar(xs, yr, yerr=er, marker="o", ms=7, capsize=4, lw=2, color=palette.get(name, "#555"))
        ax.set_title(name, fontweight="bold")
        ax.set_xlabel(f"{name} değeri")
        ax.set_ylabel("Final episode getirisi (mean±std)" if ax is axes[0] else "")
        if name == "learning_rate":
            ax.set_xscale("log")
        else:
            pad = max(1e-3, (xs.max() - xs.min()) * 0.18)
            ax.set_xlim(xs.min() - pad, xs.max() + pad)
        for x, y in zip(xs, yr):
            ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8)
    fig.suptitle("4) Hiperparametre Duyarlılığı (final episode getirisi, 5 seed) "
                 "-- düşük => sömürü, yüksek => keşif", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _save(fig, out)


def g5_baseline(eval_csv, baseline_csv, out):
    groups = {}
    if Path(baseline_csv).exists():
        b = pd.read_csv(baseline_csv)
        for name, g in b.groupby("policy"):
            groups[str(name)] = g["ep_return"].to_numpy(float)
    if Path(eval_csv).exists():
        e = pd.read_csv(eval_csv)
        groups["ajan (PPO)"] = e["ep_return"].to_numpy(float)
    if not groups:
        return
    order = [k for k in ("random", "heuristic", "ajan (PPO)") if k in groups]
    means = [groups[k].mean() for k in order]
    stds = [groups[k].std() for k in order]
    colors = ["#9e9e9e", "#ff9800", PPO_C][:len(order)]
    fig, ax = plt.subplots(figsize=(8.5, 6))
    ax.bar(order, means, yerr=stds, capsize=6, color=colors, edgecolor="white")
    for i, (m, s) in enumerate(zip(means, stds)):
        ax.text(i, m + (max(stds) * 0.08 if max(stds) else 1), f"{m:.0f}", ha="center", fontsize=10)
    ax.set_title("5) Baseline Karşılaştırma (deterministik eval, ortalama getiri)", fontweight="bold")
    ax.set_xlabel("Politika"); ax.set_ylabel("Episode getirisi (mean±std)")
    ax.grid(alpha=0.25, axis="y")
    _save(fig, out)


def g5b_baseline_4metric(eval_csv, baseline_csv, out):
    """SAC-tarzi 4 metrik: getiri / oda / kapsama / basari."""
    def grp(df, col):
        return {str(k): g[col].to_numpy(float) for k, g in df.groupby("policy")}
    if not (Path(baseline_csv).exists() and Path(eval_csv).exists()):
        return
    b = pd.read_csv(baseline_csv)
    e = pd.read_csv(eval_csv)
    pols = ["random", "heuristic", "ajan (PPO)"]
    metrics = [("ep_return", "Ortalama Episode Getirisi", "Getiri"),
               ("visited_rooms", "Keşfedilen Oda Sayısı", "Oda (0-6)"),
               ("coverage_pct", "Alan Kapsama (%)", "Kapsama %"),
               ("success", "Tam-Keşif Başarı Oranı (%)", "Başarı %")]
    colors = {"random": "#9e9e9e", "heuristic": "#ff9800", "ajan (PPO)": PPO_C}
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6))
    for ax, (col, title, ylab) in zip(axes, metrics):
        vals, errs = [], []
        for p in pols:
            if p == "ajan (PPO)":
                arr = e[col].to_numpy(float)
            else:
                sub = b[b["policy"] == p]
                arr = sub[col].to_numpy(float)
            if col == "success":
                arr = arr * 100.0
            vals.append(arr.mean()); errs.append(arr.std())
        ax.bar(["random", "heuristic", "PPO"], vals, yerr=errs, capsize=5,
               color=[colors[p] for p in pols], edgecolor="white")
        for i, v in enumerate(vals):
            ax.text(i, v + (max(errs) * 0.06 if max(errs) else 0.5), f"{v:.1f}", ha="center", fontsize=9)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(ylab); ax.grid(alpha=0.25, axis="y")
    fig.suptitle("5b) Baseline Karşılaştırma -- Görev Metrikleri (random / heuristic / PPO)",
                 fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _save(fig, out)


def g6_ppo_internal(prog, out):
    """PPO-ozel ic dinamikler (DQN epsilon yerine): clip_fraction, approx_kl, entropy."""
    if not prog:
        return
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    specs = [("train/clip_fraction", "Clip Oranı (clip_fraction)", "Kırpılan örnek oranı", "#00838f"),
             ("train/approx_kl", "Yaklaşık KL (approx_kl)", "KL(eski||yeni)", "#c62828"),
             ("train/entropy_loss", "Politika Entropisi (entropy_loss)", "Entropi kaybı", "#6a1b9a")]
    for ax, (col, title, ylab, color) in zip(axes, specs):
        any_data = False
        xs_all = []
        for s, df in prog.items():
            if col in df.columns and "time/total_timesteps" in df.columns:
                x = df["time/total_timesteps"].to_numpy(float)
                y = df[col].to_numpy(float)
                m = np.isfinite(y)
                if m.sum() > 1:
                    ax.plot(x[m], smooth(y[m], 9), color=SEED_COLORS.get(s, color), lw=1.4, alpha=0.85,
                            label=f"seed {s}")
                    any_data = True
                    xs_all.append(x[m].max())
        if any_data:
            ax.set_title(title, fontsize=11, fontweight="bold")
            ax.set_xlabel("Kümülatif adım"); ax.set_ylabel(ylab)
            ax.legend(fontsize=7)
    fig.suptitle("6) PPO İç Dinamikleri -- klips oranı, KL sapması ve entropi (keşif→sömürü)",
                 fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _save(fig, out)


def g7_rooms(dfs, out):
    r = aligned(dfs, "visited_rooms")
    if not r:
        return
    c, m, sd, n = r
    ms = smooth(m)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.fill_between(c, ms - sd, ms + sd, alpha=0.2, color="#00897b", label="+/- std (seed)")
    ax.plot(c, ms, color="#00897b", lw=2.3, label="Ortalama keşfedilen oda (PPO)")
    ax.axhline(N_ROOMS, color="#c62828", ls="--", lw=1.2, label=f"Hedef: {N_ROOMS} oda")
    ax.set_title("7) Oda Keşif Süreci (eğitim boyunca)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Keşfedilen oda sayısı (0-6)")
    ax.set_ylim(0, N_ROOMS + 0.4)
    ax.legend(title=f"{n} seed | pencere={SMOOTH}")
    _save(fig, out)


def g8_crash(dfs, out):
    """Carpisma orani (kayan ortalama) -- per seed + ortalama."""
    valid = {s: d for s, d in dfs.items() if "crashed" in d}
    if not valid:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    bands = []
    for s, d in valid.items():
        x = d["timestep"].to_numpy(float)
        y = pd.Series(d["crashed"].to_numpy(float)).rolling(50, min_periods=1).mean().to_numpy() * 100
        ax.plot(x, y, color=SEED_COLORS.get(s, "#888"), lw=1.0, alpha=0.55, label=f"seed {s}")
    r = aligned(valid, "crashed")
    if r:
        c, m, sd, n = r
        ax.plot(c, smooth(m) * 100, color="#212121", lw=2.6, label="Ortalama (5 seed)")
    ax.set_title("8) Çarpışma Oranı (eğitim boyunca, kayan ortalama)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Çarpışma oranı (%)")
    ax.set_ylim(0, 105)
    ax.legend(ncol=2, fontsize=8)
    _save(fig, out)


def g9_seed_compare(dfs, out):
    valid = {s: d for s, d in dfs.items() if "ep_return" in d}
    if not valid:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    for s, d in valid.items():
        ax.plot(d["timestep"].to_numpy(float), smooth(d["ep_return"].to_numpy(float)),
                color=SEED_COLORS.get(s, "#888"), lw=1.5, alpha=0.9, label=f"seed {s}")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("9) Seed Karşılaştırması (per-seed öğrenme yörüngeleri)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"{len(valid)} seed | pencere={SMOOTH}")
    _save(fig, out)


def g10_heatmap(grid_root: Path, out):
    """gamma x lr grid -> 3 panel heatmap: getiri, oda, kombinasyon skoru."""
    if not grid_root.exists():
        return
    rows = []
    for d in grid_root.glob("g*_lr*"):
        try:
            g = float(d.name.split("_lr")[0][1:]); lr = float(d.name.split("_lr")[1])
        except (ValueError, IndexError):
            continue
        rets, rooms = [], []
        for sd in d.glob("seed_*"):
            log = sd / "training_log.csv"
            if log.exists():
                df = pd.read_csv(log)
                if len(df):
                    tail = df.tail(max(5, len(df) // 10))
                    rets.append(tail["ep_return"].mean()); rooms.append(tail["visited_rooms"].mean())
        if rets:
            rows.append((g, lr, np.mean(rets), np.mean(rooms)))
    if not rows:
        return
    gammas = sorted({r[0] for r in rows}); lrs = sorted({r[1] for r in rows})
    R = np.full((len(gammas), len(lrs)), np.nan)
    O = np.full((len(gammas), len(lrs)), np.nan)
    for g, lr, ret, room in rows:
        R[gammas.index(g), lrs.index(lr)] = ret
        O[gammas.index(g), lrs.index(lr)] = room
    score = 10 * O + 0.05 * R   # SAC raporundaki skor metrigi
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    mats = [(R, "Final Getiri", "RdYlGn"), (O, "Keşfedilen Oda", "YlGn"),
            (score, "Kombinasyon Skoru (10·oda+0.05·getiri)", "viridis")]
    for ax, (M, title, cmap) in zip(axes, mats):
        im = ax.imshow(M, cmap=cmap, aspect="auto", origin="lower")
        ax.set_xticks(range(len(lrs))); ax.set_xticklabels([f"{x:.0e}" for x in lrs])
        ax.set_yticks(range(len(gammas))); ax.set_yticklabels([f"{y:.2f}" for y in gammas])
        ax.set_xlabel("learning_rate"); ax.set_ylabel("gamma (γ)")
        ax.set_title(title, fontsize=11, fontweight="bold")
        for i in range(len(gammas)):
            for j in range(len(lrs)):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:.0f}" if title != "Keşfedilen Oda" else f"{M[i, j]:.2f}",
                            ha="center", va="center", fontsize=9,
                            color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("10) Hiperparametre Arama -- γ × learning_rate Izgarası (3 seed)", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _save(fig, out)


def g11_per_seed(runs_root, eval_csv, out_dir: Path):
    """Her seed icin 2x2 panel (SAC-tarzi): egitim getiri, eval bar, kapsama, oda."""
    dfs = load_logs(runs_root)
    ev = pd.read_csv(eval_csv) if Path(eval_csv).exists() else None
    for s, d in dfs.items():
        color = SEED_COLORS.get(s, PPO_C)
        x = d["timestep"].to_numpy(float)
        n_ep = len(d); total = int(d["timestep"].iloc[-1])
        fig, axes = plt.subplots(2, 2, figsize=(13, 7.5))
        fig.suptitle(f"Seed {s} -- Toplam {total:,} adım ({n_ep} episode)", fontweight="bold", fontsize=13)
        # (0,0) egitim getiri
        ax = axes[0, 0]
        ax.plot(x, d["ep_return"], color=color, lw=0.5, alpha=0.25)
        ax.plot(x, smooth(d["ep_return"].to_numpy(float)), color=color, lw=2, label=f"seed {s}")
        ax.set_title("Eğitim Episode Getirisi"); ax.set_xlabel("Adım"); ax.set_ylabel("Episode getirisi")
        ax.legend(fontsize=8)
        # (0,1) eval bar
        ax = axes[0, 1]
        if ev is not None and s in set(ev["seed"].unique()):
            es = ev[ev["seed"] == s]["ep_return"].to_numpy(float)
            ax.bar(range(len(es)), es, color=color, alpha=0.8)
            ax.axhline(es.mean(), color="#c62828", ls="--", lw=1.2, label=f"ort {es.mean():.1f}")
            ax.legend(fontsize=8)
        ax.set_title("Final Deterministik Eval"); ax.set_xlabel("Eval episode"); ax.set_ylabel("Getiri")
        # (1,0) kapsama
        ax = axes[1, 0]
        ax.plot(x, smooth(d["coverage_pct"].to_numpy(float)), color=color, lw=2)
        ax.axhline(100, color="#c62828", ls="--", lw=1, label="%100 hedef")
        ax.set_title("Keşif Oranı (Coverage %)"); ax.set_xlabel("Adım"); ax.set_ylabel("Kapsama (%)")
        ax.legend(fontsize=8)
        # (1,1) oda
        ax = axes[1, 1]
        ax.plot(x, smooth(d["visited_rooms"].to_numpy(float)), color=color, lw=2)
        ax.axhline(N_ROOMS, color="#c62828", ls="--", lw=1, label=f"hedef {N_ROOMS} oda")
        ax.set_title("Ziyaret Edilen Oda Sayısı"); ax.set_xlabel("Adım"); ax.set_ylabel("Oda (0-6)")
        ax.set_ylim(0, N_ROOMS + 0.4); ax.legend(fontsize=8)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        _save(fig, out_dir / f"per_seed_{s}.png")


def g12_long_horizon(long_root: Path, out):
    p = long_root / "seed_123" / "training_log.csv"
    if not p.exists():
        return
    d = pd.read_csv(p)
    if len(d) < 10:
        return
    x = d["timestep"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(x, d["ep_return"], color="#6a1b9a", lw=0.4, alpha=0.2)
    ax.plot(x, smooth(d["ep_return"].to_numpy(float), 25), color="#6a1b9a", lw=2.2,
            label="seed 123 (ham + hareketli ort.)")
    ax.axvline(1.5e6, color="#c62828", ls="--", lw=1.2, label="ana teslim sınırı (1.5M)")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("12) Uzun-Ufuk Kararlılık (seed 123, 5M adıma kadar)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend()
    _save(fig, out)


def g13_explained_variance(prog, out):
    if not prog:
        return
    have = any("train/explained_variance" in df.columns for df in prog.values())
    if not have:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    for s, df in prog.items():
        if "train/explained_variance" in df.columns:
            x = df["time/total_timesteps"].to_numpy(float)
            y = df["train/explained_variance"].to_numpy(float)
            ax.plot(x, smooth(y, 9), color=SEED_COLORS.get(s, "#888"), lw=1.6, alpha=0.85, label=f"seed {s}")
    ax.axhline(1.0, color="#2e7d32", ls="--", lw=1, label="ideal (=1)")
    ax.set_title("13) Değer Fonksiyonu Kalitesi (explained_variance)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Açıklanan varyans (kritik tahmin kalitesi)")
    ax.set_ylim(-0.1, 1.05); ax.legend(fontsize=8)
    _save(fig, out)


# =========================================================================== #
# PPO vs SAC KIYAS
# =========================================================================== #
def c1_learning(ppo_dfs, sac_dfs, out):
    rp = aligned(ppo_dfs, "ep_return")
    rs = aligned(sac_dfs, "ep_return")
    if not (rp or rs):
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    for r, color, lab in ((rp, PPO_C, "PPO (on-policy)"), (rs, SAC_C, "SAC (off-policy)")):
        if r:
            c, m, sd, n = r
            ms = smooth(m)
            ax.fill_between(c, ms - sd, ms + sd, alpha=0.15, color=color)
            ax.plot(c, ms, color=color, lw=2.4, label=f"{lab} (n={n})")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("PPO vs SAC -- Öğrenme Eğrisi (aynı ortam, aynı 5 seed)", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend(title=f"hareketli ort. pencere={SMOOTH}")
    _save(fig, out)


def c2_sample_efficiency(ppo_dfs, sac_dfs, out):
    """Ornek-verimliligi: getiri vs env-adim, ortak x-aralikta (SAC'in adimina kadar)."""
    if not sac_dfs:
        return
    sac_xmax = min(float(d["timestep"].max()) for d in sac_dfs.values())
    rp = aligned(ppo_dfs, "ep_return", xmax=sac_xmax)
    rs = aligned(sac_dfs, "ep_return", xmax=sac_xmax)
    fig, ax = plt.subplots(figsize=(11, 6))
    for r, color, lab in ((rp, PPO_C, "PPO"), (rs, SAC_C, "SAC")):
        if r:
            c, m, sd, n = r
            ms = smooth(m)
            ax.fill_between(c, ms - sd, ms + sd, alpha=0.15, color=color)
            ax.plot(c, ms, color=color, lw=2.4, label=lab)
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title(f"PPO vs SAC -- Örnek Verimliliği (ilk {sac_xmax/1e3:.0f}k adım)", fontweight="bold")
    ax.set_xlabel("Kümülatif env adımı (örnek verimliliği)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend()
    _save(fig, out)


def c3_eval(ppo_root, sac_root, out):
    bp = _eval_band(_eval_curves(ppo_root))
    bs = _eval_band(_eval_curves(sac_root))
    if not (bp or bs):
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    for b, color, lab in ((bp, PPO_C, "PPO"), (bs, SAC_C, "SAC")):
        if b:
            g, m, sd, n = b
            ax.fill_between(g, m - sd, m + sd, alpha=0.15, color=color)
            ax.plot(g, m, color=color, lw=2.4, label=f"{lab} (n={n})")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title("PPO vs SAC -- Deterministik Eval Eğrisi", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)")
    ax.set_ylabel("Episode getirisi (toplam ödül)")
    ax.legend()
    _save(fig, out)


def c4_final_bars(ppo_eval_csv, sac_eval_csv, out):
    """PPO vs SAC final metrik karsilastirmasi (gruplu bar)."""
    if not (Path(ppo_eval_csv).exists() and Path(sac_eval_csv).exists()):
        return
    p = pd.read_csv(ppo_eval_csv); s = pd.read_csv(sac_eval_csv)
    metrics = [("ep_return", "Getiri"), ("visited_rooms", "Oda (0-6)"),
               ("coverage_pct", "Kapsama %"), ("success", "Başarı %"), ("crashed", "Çarpışma %")]
    fig, axes = plt.subplots(1, 5, figsize=(18, 4.4))
    for ax, (col, lab) in zip(axes, metrics):
        pv = p[col].to_numpy(float); sv = s[col].to_numpy(float)
        if col in ("success", "crashed"):
            pv = pv * 100; sv = sv * 100
        means = [pv.mean(), sv.mean()]; errs = [pv.std(), sv.std()]
        ax.bar(["PPO", "SAC"], means, yerr=errs, capsize=5, color=[PPO_C, SAC_C], edgecolor="white")
        for i, v in enumerate(means):
            ax.text(i, v + (max(errs) * 0.06 if max(errs) else 0.5), f"{v:.1f}", ha="center", fontsize=9)
        ax.set_title(lab, fontsize=11, fontweight="bold"); ax.grid(alpha=0.25, axis="y")
    fig.suptitle("PPO vs SAC -- Final Deterministik Eval Metrikleri (aynı ortam/protokol)", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _save(fig, out)


def c5_rooms(ppo_dfs, sac_dfs, out):
    rp = aligned(ppo_dfs, "visited_rooms")
    rs = aligned(sac_dfs, "visited_rooms")
    if not (rp or rs):
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    for r, color, lab in ((rp, PPO_C, "PPO"), (rs, SAC_C, "SAC")):
        if r:
            c, m, sd, n = r
            ax.fill_between(c, smooth(m) - sd, smooth(m) + sd, alpha=0.13, color=color)
            ax.plot(c, smooth(m), color=color, lw=2.4, label=lab)
    ax.axhline(N_ROOMS, color="#c62828", ls="--", lw=1.2, label=f"hedef {N_ROOMS} oda")
    ax.set_title("PPO vs SAC -- Oda Keşif Süreci", fontweight="bold")
    ax.set_xlabel("Kümülatif adım (timestep)"); ax.set_ylabel("Keşfedilen oda (0-6)")
    ax.set_ylim(0, N_ROOMS + 0.4); ax.legend()
    _save(fig, out)


# =========================================================================== #
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--hp", type=Path, default=Path("runs_hp5"))
    ap.add_argument("--grid", type=Path, default=Path("runs_grid"))
    ap.add_argument("--long", type=Path, default=Path("runs_long"))
    ap.add_argument("--sac", type=Path, default=Path("runs_sac"))
    ap.add_argument("--eval-csv", type=Path, default=Path("../sonuclar/eval_per_episode.csv"))
    ap.add_argument("--sac-eval-csv", type=Path, default=Path("../sonuclar/sac_eval_per_episode.csv"))
    ap.add_argument("--baseline-csv", type=Path, default=Path("../sonuclar/baseline_per_episode.csv"))
    ap.add_argument("--out", type=Path, default=Path("figs"))
    ap.add_argument("--section", choices=["main", "compare", "all"], default="all")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    if args.section in ("main", "all"):
        dfs = load_logs(args.runs)
        prog = load_progress(args.runs)
        print(f"[viz] ana PPO seed logu: {sorted(dfs)} | progress: {sorted(prog)}")
        g1_learning(dfs, args.out / "1_ogrenme_egrisi.png")
        g1b_learning_episode(dfs, args.out / "1b_ogrenme_egrisi_episode.png")
        g2_eval(args.runs, args.out / "2_eval_egrisi.png")
        g3_loss(dfs, args.out / "3_loss_egrisi.png")
        g4_hp(args.hp, args.out / "4_hiperparametre_duyarlilik.png")
        g5_baseline(args.eval_csv, args.baseline_csv, args.out / "5_baseline_karsilastirma.png")
        g5b_baseline_4metric(args.eval_csv, args.baseline_csv, args.out / "5b_baseline_4metrik.png")
        g6_ppo_internal(prog, args.out / "6_ppo_ic_dinamikler.png")
        g7_rooms(dfs, args.out / "7_oda_kesif_sureci.png")
        g8_crash(dfs, args.out / "8_carpisma_orani.png")
        g9_seed_compare(dfs, args.out / "9_seed_karsilastirma.png")
        g10_heatmap(args.grid, args.out / "10_gamma_lr_heatmap.png")
        g11_per_seed(args.runs, args.eval_csv, args.out)
        g12_long_horizon(args.long, args.out / "12_uzun_ufuk_kararlilik.png")
        g13_explained_variance(prog, args.out / "13_explained_variance.png")

    if args.section in ("compare", "all"):
        ppo = load_logs(args.runs)
        sac = load_logs(args.sac)
        print(f"[viz] kiyas: PPO seed {sorted(ppo)} | SAC seed {sorted(sac)}")
        c1_learning(ppo, sac, args.out / "C1_ogrenme_ppo_vs_sac.png")
        c2_sample_efficiency(ppo, sac, args.out / "C2_ornek_verimliligi.png")
        c3_eval(args.runs, args.sac, args.out / "C3_eval_ppo_vs_sac.png")
        c4_final_bars(args.eval_csv, args.sac_eval_csv, args.out / "C4_final_metrik_bar.png")
        c5_rooms(ppo, sac, args.out / "C5_oda_ppo_vs_sac.png")


if __name__ == "__main__":
    main()
