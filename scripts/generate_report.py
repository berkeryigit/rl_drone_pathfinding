#!/home/berkerygt/Desktop/RLProje/rl_drone_pathfinding/.venv/bin/python3
"""CSV loglarından eğitim raporu ve grafikler üretir.

Kullanım:
    python3 scripts/generate_report.py

Çıktı:
    docs/TRAINING_REPORT.md
    docs/figures/reward_curve.png
    docs/figures/fps_timeline.png
    docs/figures/entropy_curve.png
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

PROJ_ROOT = Path(__file__).parent.parent.resolve()
METRICS_CSV = PROJ_ROOT / "logs" / "training_metrics.csv"
INTERVENTIONS_JSONL = PROJ_ROOT / "logs" / "interventions.jsonl"
FIGURES_DIR = PROJ_ROOT / "docs" / "figures"
REPORT_PATH = PROJ_ROOT / "docs" / "TRAINING_REPORT.md"

FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Veri yükleme
# ---------------------------------------------------------------------------

def load_metrics() -> list[dict]:
    if not METRICS_CSV.exists():
        print(f"Metrik dosyası bulunamadı: {METRICS_CSV}")
        return []
    rows = []
    with open(METRICS_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append({
                    "timestamp": row["timestamp"],
                    "step": int(row["step"]) if row["step"] else 0,
                    "ep_rew_mean": float(row["ep_rew_mean"]) if row["ep_rew_mean"] else None,
                    "ep_len_mean": float(row["ep_len_mean"]) if row["ep_len_mean"] else None,
                    "fps": float(row["fps"]) if row["fps"] else None,
                    "entropy_loss": float(row["entropy_loss"]) if row["entropy_loss"] else None,
                    "std": float(row["std"]) if row["std"] else None,
                    "ckpt_file": row.get("ckpt_file", ""),
                })
            except (ValueError, KeyError):
                continue
    return rows


def load_interventions() -> list[dict]:
    if not INTERVENTIONS_JSONL.exists():
        return []
    entries = []
    with open(INTERVENTIONS_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


# ---------------------------------------------------------------------------
# Grafik üretme
# ---------------------------------------------------------------------------

def plot_reward_curve(rows: list[dict], interventions: list[dict]) -> Path:
    steps = [r["step"] for r in rows if r["ep_rew_mean"] is not None]
    rewards = [r["ep_rew_mean"] for r in rows if r["ep_rew_mean"] is not None]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(steps, rewards, color="#2196F3", linewidth=1.5, label="ep_rew_mean")

    # Hareketli ortalama
    if len(rewards) >= 5:
        window = min(5, len(rewards))
        ma = np.convolve(rewards, np.ones(window) / window, mode="valid")
        ma_steps = steps[window - 1:]
        ax.plot(ma_steps, ma, color="#FF5722", linewidth=2.0,
                linestyle="--", label=f"MA-{window}")

    # Müdahale noktaları
    crash_steps = [iv["step"] for iv in interventions if iv.get("type") == "crash_recovery"]
    v10_steps = [iv["step"] for iv in interventions if iv.get("type") == "v10_transition"]

    for s in crash_steps:
        ax.axvline(x=s, color="red", linestyle=":", alpha=0.7, linewidth=1.5)
    for s in v10_steps:
        ax.axvline(x=s, color="green", linestyle="--", alpha=0.8, linewidth=2)

    legend_patches = [mpatches.Patch(color="red", label="crash recovery"),
                      mpatches.Patch(color="green", label="v10 geçişi")]
    ax.legend(handles=[*ax.get_lines(), *legend_patches])

    ax.set_xlabel("Timestep")
    ax.set_ylabel("ep_rew_mean")
    ax.set_title("PPO v9/v10 — Öğrenme Eğrisi")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out = FIGURES_DIR / "reward_curve.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"Kaydedildi: {out}")
    return out


def plot_fps_timeline(rows: list[dict], interventions: list[dict]) -> Path:
    steps = [r["step"] for r in rows if r["fps"] is not None]
    fps_vals = [r["fps"] for r in rows if r["fps"] is not None]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(steps, fps_vals, color="#4CAF50", linewidth=1.5, label="FPS")
    ax.axhline(y=np.mean(fps_vals) if fps_vals else 0,
               color="orange", linestyle="--", alpha=0.7, label="Ort. FPS")

    for iv in interventions:
        s = iv.get("step", 0)
        color = "red" if iv.get("type") == "crash_recovery" else "green"
        ax.axvline(x=s, color=color, linestyle=":", alpha=0.6, linewidth=1.5)

    ax.set_xlabel("Timestep")
    ax.set_ylabel("FPS")
    ax.set_title("PPO v9/v10 — FPS Zaman Çizelgesi")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out = FIGURES_DIR / "fps_timeline.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"Kaydedildi: {out}")
    return out


def plot_entropy_curve(rows: list[dict]) -> Path:
    steps = [r["step"] for r in rows if r["entropy_loss"] is not None]
    entropy = [r["entropy_loss"] for r in rows if r["entropy_loss"] is not None]

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(steps, entropy, color="#9C27B0", linewidth=1.5, label="entropy_loss")
    ax1.set_xlabel("Timestep")
    ax1.set_ylabel("entropy_loss", color="#9C27B0")

    # std ikincil eksen
    steps_std = [r["step"] for r in rows if r["std"] is not None]
    std_vals = [r["std"] for r in rows if r["std"] is not None]
    if steps_std:
        ax2 = ax1.twinx()
        ax2.plot(steps_std, std_vals, color="#FF9800", linewidth=1.5,
                 linestyle="--", label="std")
        ax2.set_ylabel("policy std", color="#FF9800")
        ax2.legend(loc="upper right")

    ax1.set_title("PPO v9/v10 — Entropy & Policy Std")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    plt.tight_layout()

    out = FIGURES_DIR / "entropy_curve.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"Kaydedildi: {out}")
    return out


# ---------------------------------------------------------------------------
# Markdown rapor
# ---------------------------------------------------------------------------

def generate_report(rows: list[dict], interventions: list[dict]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if rows:
        valid_rew = [r["ep_rew_mean"] for r in rows if r["ep_rew_mean"] is not None]
        valid_fps = [r["fps"] for r in rows if r["fps"] is not None]
        max_step = max(r["step"] for r in rows)
        peak_rew = max(valid_rew) if valid_rew else "—"
        peak_rew_step = next(
            (r["step"] for r in rows if r["ep_rew_mean"] == peak_rew), "—"
        ) if valid_rew else "—"
        avg_fps = f"{np.mean(valid_fps):.0f}" if valid_fps else "—"
        first_positive_step = next(
            (r["step"] for r in rows if (r["ep_rew_mean"] or -1) > 0), "henüz yok"
        )
    else:
        max_step = 0
        peak_rew = "—"
        peak_rew_step = "—"
        avg_fps = "—"
        first_positive_step = "—"

    crashes = [iv for iv in interventions if iv.get("type") == "crash_recovery"]
    v10_ivs = [iv for iv in interventions if iv.get("type") == "v10_transition"]

    lines = [
        f"# PPO Eğitim Raporu — v9/v10",
        f"",
        f"*Üretildi: {now}*",
        f"",
        f"## Özet",
        f"",
        f"| Metrik | Değer |",
        f"|--------|-------|",
        f"| Toplam step (şu an) | {max_step:,} |",
        f"| Peak ep_rew_mean | {peak_rew} @ step {peak_rew_step:,} |" if isinstance(peak_rew_step, int) else f"| Peak ep_rew_mean | {peak_rew} |",
        f"| Ortalama FPS | {avg_fps} |",
        f"| İlk pozitif reward | step {first_positive_step:,} |" if isinstance(first_positive_step, int) else f"| İlk pozitif reward | {first_positive_step} |",
        f"| Crash recovery sayısı | {len(crashes)} |",
        f"| v10 geçiş sayısı | {len(v10_ivs)} |",
        f"",
        f"## Öğrenme Eğrisi",
        f"",
        f"![Öğrenme Eğrisi](figures/reward_curve.png)",
        f"",
        f"## FPS Zaman Çizelgesi",
        f"",
        f"![FPS](figures/fps_timeline.png)",
        f"",
        f"## Entropy & Policy Std",
        f"",
        f"![Entropy](figures/entropy_curve.png)",
        f"",
        f"## Müdahale Kaydı",
        f"",
    ]

    if interventions:
        lines.append("| Zaman | Tip | Step | Detay |")
        lines.append("|-------|-----|------|-------|")
        for iv in interventions:
            ts = iv.get("ts", "")
            typ = iv.get("type", "")
            step = iv.get("step", "")
            if typ == "crash_recovery":
                detail = f"resume: {iv.get('resume_from', '?')}"
            elif typ == "v10_transition":
                changes = iv.get("changes", {})
                ent = changes.get("ent_coef", {})
                detail = f"ent_coef: {ent.get('old')}→{ent.get('new')}"
            else:
                detail = ""
            lines.append(f"| {ts} | {typ} | {step:,} | {detail} |" if isinstance(step, int) else f"| {ts} | {typ} | {step} | {detail} |")
    else:
        lines.append("*Henüz müdahale yok.*")

    lines += [
        f"",
        f"## Ham Metrik Tablosu (Son 10 Kayıt)",
        f"",
        f"| Zaman | Step | ep_rew_mean | ep_len_mean | FPS | Entropy |",
        f"|-------|------|-------------|-------------|-----|---------|",
    ]

    for r in rows[-10:]:
        ts = r["timestamp"]
        s = r["step"]
        rew = f"{r['ep_rew_mean']:.1f}" if r["ep_rew_mean"] is not None else "—"
        elen = f"{r['ep_len_mean']:.0f}" if r["ep_len_mean"] is not None else "—"
        fps = f"{r['fps']:.0f}" if r["fps"] is not None else "—"
        ent = f"{r['entropy_loss']:.3f}" if r["entropy_loss"] is not None else "—"
        lines.append(f"| {ts} | {s:,} | {rew} | {elen} | {fps} | {ent} |")

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Rapor kaydedildi: {REPORT_PATH}")


# ---------------------------------------------------------------------------

def main() -> None:
    print("Veri yükleniyor...")
    rows = load_metrics()
    interventions = load_interventions()
    print(f"  {len(rows)} metrik kaydı, {len(interventions)} müdahale kaydı")

    if not rows:
        print("Veri yok, sadece boş rapor oluşturuluyor")
        generate_report([], [])
        return

    print("Grafikler üretiliyor...")
    plot_reward_curve(rows, interventions)
    plot_fps_timeline(rows, interventions)
    plot_entropy_curve(rows)

    print("Rapor üretiliyor...")
    generate_report(rows, interventions)
    print("Tamamlandı.")


if __name__ == "__main__":
    main()
