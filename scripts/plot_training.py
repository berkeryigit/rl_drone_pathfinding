"""Generate diagnostic plots from TensorBoard event files for PPO runs.

Reads scalar metrics from each version's TB log directory and saves
PNGs into `docs/figures/`. Run from the repo root:

    python3 scripts/plot_training.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402
from tensorboard.backend.event_processing.event_accumulator import (  # noqa: E402
    EventAccumulator,
)

REPO = Path(__file__).resolve().parents[1]

# Each entry: label -> path to the directory containing events.out.tfevents.*
VERSIONS = {
    "v1 baseline": REPO / "runs/ppo/tb/PPO_4",
    "v2 rewards 3x + sdf 3x3": REPO / "runs/ppo_v2_explore/tb/PPO_1",
    "v3 multi-floor spawn + 200 floor": REPO / "runs/ppo_v3_floors/tb/PPO_0",
    "v4 ent_coef 0.001 + idle decay": REPO / "runs/ppo_v4_low_ent/tb/PPO_1",
}

METRICS = [
    ("rollout/ep_rew_mean", "Episode reward mean"),
    ("rollout/ep_len_mean", "Episode length mean (max=1000)"),
    ("train/entropy_loss", "Entropy loss (low = less exploration)"),
    ("train/value_loss", "Value loss"),
    ("train/explained_variance", "Explained variance (value fn quality)"),
    ("train/approx_kl", "Approx KL (policy update size)"),
]


def load_scalars(event_dir: Path, tag: str):
    if not event_dir.exists():
        return [], []
    ea = EventAccumulator(str(event_dir), size_guidance={"scalars": 100000})
    ea.Reload()
    tags = ea.Tags().get("scalars", [])
    if tag not in tags:
        return [], []
    events = ea.Scalars(tag)
    return [e.step for e in events], [e.value for e in events]


def main():
    out_dir = REPO / "docs/figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 6-panel grid ----
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    for ax, (tag, title) in zip(axes.flat, METRICS):
        for label, dir_ in VERSIONS.items():
            steps, vals = load_scalars(dir_, tag)
            if steps:
                ax.plot(steps, vals, label=label, alpha=0.85, linewidth=1.5)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Step")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=8)
    fig.suptitle("PPO training metrics — v1 vs v2 vs v3", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    p = out_dir / "training_curves_all.png"
    fig.savefig(p, dpi=120)
    print(f"saved {p}")

    # ---- single reward summary plot, annotated ----
    fig2, ax = plt.subplots(figsize=(11, 6))
    for label, dir_ in VERSIONS.items():
        steps, vals = load_scalars(dir_, "rollout/ep_rew_mean")
        if steps:
            ax.plot(steps, vals, label=label, linewidth=2)
    ax.axhline(0, color="black", linewidth=0.5, linestyle=":")
    ax.set_xlabel("Step")
    ax.set_ylabel("ep_rew_mean")
    ax.set_title(
        "Episode reward mean across exploration interventions\n"
        "(higher = drone exploring more rooms/floors without dying)"
    )
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig2.tight_layout()
    p2 = out_dir / "reward_curve_summary.png"
    fig2.savefig(p2, dpi=120)
    print(f"saved {p2}")

    # ---- v3-only zoom: the plateau question ----
    fig3, ax = plt.subplots(figsize=(11, 6))
    steps, vals = load_scalars(VERSIONS["v3 multi-floor spawn + 200 floor"],
                                "rollout/ep_rew_mean")
    if steps:
        ax.plot(steps, vals, color="green", linewidth=1.5, label="ep_rew_mean")
        # rolling mean
        if len(vals) > 20:
            window = 20
            roll = [sum(vals[max(0, i - window):i + 1]) / min(i + 1, window)
                    for i in range(len(vals))]
            ax.plot(steps, roll, color="darkgreen", linewidth=2.5,
                    label=f"rolling mean (w={window})")
    ax.axhline(0, color="black", linewidth=0.5, linestyle=":")
    ax.axvline(310_000, color="red", linewidth=1, linestyle="--",
               label="310k eval (rooms=1 in 10/11 eps)")
    ax.set_xlabel("Step")
    ax.set_ylabel("ep_rew_mean")
    ax.set_title("v3 zoom: ep_rew_mean over 140k -> 1.45M (looking for plateau)")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig3.tight_layout()
    p3 = out_dir / "v3_plateau_zoom.png"
    fig3.savefig(p3, dpi=120)
    print(f"saved {p3}")

    plt.close("all")


def entropy_zoom():
    """Standalone entropy + std plot — the key v3 finding."""
    out = REPO / "docs/figures"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for label, dir_ in VERSIONS.items():
        s, v = load_scalars(dir_, "train/entropy_loss")
        if s:
            ax1.plot(s, v, label=label, linewidth=1.5)
        s2, v2 = load_scalars(dir_, "train/std")
        if s2:
            ax2.plot(s2, v2, label=label, linewidth=1.5)
    ax1.set_ylabel("entropy_loss")
    ax1.set_title(
        "Entropy collapse check\n"
        "(more negative = lower entropy = less exploration)")
    ax1.grid(True, alpha=0.3); ax1.legend(loc="best", fontsize=9)
    ax2.set_ylabel("action std")
    ax2.set_xlabel("Step")
    ax2.set_title("Action distribution std (PPO Gaussian policy)")
    ax2.grid(True, alpha=0.3); ax2.legend(loc="best", fontsize=9)
    fig.tight_layout()
    p = out / "entropy_zoom.png"
    fig.savefig(p, dpi=120)
    print(f"saved {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
    entropy_zoom()
