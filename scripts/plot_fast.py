#!/usr/bin/env python3
"""Hızlı-sim eğitim loglarını GÖRSEL kaydet — tüm fast versiyonlarını kıyaslar.
    python3 scripts/plot_fast.py
Çıktı: docs/figures/fast_curves.png (reward/voxel/oda/ep_len 4-panel, versiyon bazlı).
"""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MAXEP = 2500


def load():
    data = {}
    for csv_path in sorted((REPO / "runs").glob("fast*/progress.csv")):
        d = defaultdict(list)
        try:
            for row in csv.DictReader(open(csv_path)):
                try:
                    d["step"].append(int(row["step"]))
                    d["rew"].append(float(row["ep_rew_mean"]))
                    d["eplen"].append(float(row["ep_len_mean"]))
                    d["vox"].append(float(row["voxels_mean"]))
                    d["rooms"].append(float(row["rooms_mean"]))
                except (KeyError, ValueError):
                    continue
        except OSError:
            continue
        if d["step"]:
            data[csv_path.parent.name] = d
    return data


def main():
    data = load()
    if not data:
        print("fast progress.csv yok"); return
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    panels = [("rew", "ep_rew_mean (reward)"), ("vox", "voxels_mean (kapsama)"),
              ("rooms", "rooms_mean (oda /6)"), ("eplen", f"ep_len_mean (carpisma proxy /{MAXEP})")]
    for ax, (key, title) in zip(axes.flat, panels):
        for ver in sorted(data):
            d = data[ver]
            ax.plot(d["step"], d[key], linewidth=1.6, label=ver, alpha=0.85)
        ax.set_title(title); ax.set_xlabel("step"); ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle("HIZLI numpy sim — versiyon kiyas (egitim egrileri)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = REPO / "docs" / "figures" / "fast_curves.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120); plt.close(fig)
    print(f"saved {out}")
    # son-deger ozet tablosu (stdout)
    print("\nversiyon | son_step | reward | voxels_mean | rooms_mean | ep_len/2500")
    for ver in sorted(data):
        d = data[ver]
        print(f"{ver:12s} | {d['step'][-1]:>8} | {d['rew'][-1]:6.1f} | "
              f"{d['vox'][-1]:6.1f} | {d['rooms'][-1]:4.2f} | {d['eplen'][-1]/MAXEP:.2f}")


if __name__ == "__main__":
    main()
