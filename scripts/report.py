#!/usr/bin/env python3
"""Egitim raporu uretici — runs/*/progress.csv + logs/versions.jsonl'den
figurler ve docs/REPORT.md uretir.

Operator agent versiyon atladikca / periyodik olarak cagirir:
    python3 scripts/report.py

Ciktilar:
    docs/figures/report_reward.png   ep_rew_mean vs step (versiyon bazli)
    docs/figures/report_voxels.png   kesfedilen voxel (mean+max) vs step
    docs/figures/report_rooms.png    ziyaret edilen oda vs step
    docs/REPORT.md                   ozet tablo + versiyon gunlugu + figurler
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
FIG = REPO / "docs" / "figures"
VERSIONS_JSONL = REPO / "logs" / "versions.jsonl"
TOTAL_VOXELS = 1024
N_ROOMS = 6


def load_progress():
    """version -> dict(step,rew,vox_mean,vox_max,room_mean,room_max listeleri)."""
    data = defaultdict(lambda: defaultdict(list))
    for csv_path in sorted(RUNS.glob("*/progress.csv")):
        try:
            with open(csv_path) as f:
                for row in csv.DictReader(f):
                    try:
                        v = row.get("version", csv_path.parent.name)
                        d = data[v]
                        d["step"].append(int(row["step"]))
                        d["rew"].append(float(row["ep_rew_mean"]))
                        d["vox_mean"].append(float(row["voxels_mean"]))
                        d["vox_max"].append(float(row["voxels_max"]))
                        d["room_mean"].append(float(row["rooms_mean"]))
                        d["room_max"].append(float(row["rooms_max"]))
                    except (KeyError, ValueError):
                        continue
        except OSError:
            continue
    return data


def load_versions():
    rows = []
    if VERSIONS_JSONL.exists():
        for line in VERSIONS_JSONL.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def plot_metric(data, key, ylabel, title, out, second_key=None, second_label=None):
    fig, ax = plt.subplots(figsize=(11, 6))
    plotted = False
    for v in sorted(data):
        d = data[v]
        if d.get(key):
            ax.plot(d["step"], d[key], linewidth=1.8, label=f"{v} {ylabel}")
            plotted = True
        if second_key and d.get(second_key):
            ax.plot(d["step"], d[second_key], linewidth=1.0, alpha=0.5,
                    linestyle="--", label=f"{v} {second_label}")
    if not plotted:
        plt.close(fig)
        return False
    ax.axhline(0, color="black", linewidth=0.5, linestyle=":")
    ax.set_xlabel("Egitim adimi (step)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"saved {out}")
    return True


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    data = load_progress()
    versions = load_versions()

    plot_metric(data, "rew", "ep_rew_mean",
                "Episode reward ortalamasi (yuksek = daha cok voxel, az carpisma)",
                FIG / "report_reward.png")
    plot_metric(data, "vox_mean", "voxel",
                f"Kesfedilen voxel / {TOTAL_VOXELS} (kesik cizgi = episode max)",
                FIG / "report_voxels.png",
                second_key="vox_max", second_label="voxels_max")
    plot_metric(data, "room_mean", "oda",
                f"Ziyaret edilen oda / {N_ROOMS} (kesik cizgi = episode max)",
                FIG / "report_rooms.png",
                second_key="room_max", second_label="rooms_max")

    # ---- markdown ozet ----
    lines = ["# PPO Drone Kesif — Egitim Raporu", "",
             "Otomatik uretildi (`scripts/report.py`). Operator agent gunceller.", "",
             "## Versiyon Ozeti", "",
             "| Versiyon | Son step | Son reward | Peak reward | Peak voxel (max) | Peak oda (max) |",
             "|---|---|---|---|---|---|"]
    for v in sorted(data):
        d = data[v]
        if not d.get("step"):
            continue
        last_step = d["step"][-1]
        last_rew = d["rew"][-1]
        peak_rew = max(d["rew"]) if d["rew"] else 0
        peak_vox = int(max(d["vox_max"])) if d["vox_max"] else 0
        peak_room = int(max(d["room_max"])) if d["room_max"] else 0
        lines.append(f"| {v} | {last_step:,} | {last_rew:+.1f} | {peak_rew:+.1f} | "
                     f"{peak_vox}/{TOTAL_VOXELS} | {peak_room}/{N_ROOMS} |")

    lines += ["", "## Versiyon / Mudahale Gunlugu", ""]
    if versions:
        lines += ["| Zaman | Versiyon | Tip | Aciklama |", "|---|---|---|---|"]
        for r in versions:
            lines.append(f"| {r.get('ts','')} | {r.get('version','')} | "
                         f"{r.get('type','')} | {r.get('reason','')} |")
    else:
        lines.append("_(henuz kayit yok)_")

    lines += ["", "## Figurler", "",
              "![reward](figures/report_reward.png)", "",
              "![voxels](figures/report_voxels.png)", "",
              "![rooms](figures/report_rooms.png)", ""]

    (REPO / "docs" / "REPORT.md").write_text("\n".join(lines))
    print(f"saved {REPO / 'docs' / 'REPORT.md'}")


if __name__ == "__main__":
    main()
