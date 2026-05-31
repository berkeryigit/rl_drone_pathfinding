#!/usr/bin/env python3
"""TensorBoard metriklerini JSON olarak ozetler — operator agent'in 'gozu'.

Kullanim (repo kokunden, venv aktifken):
    python3 scripts/tb_metrics.py                 # configs/ppo.yaml'daki aktif run
    python3 scripts/tb_metrics.py --config X.yaml
    python3 scripts/tb_metrics.py --history       # tum (step, reward) noktalari da

Cikti (JSON), operator bunu okuyup karar verir:
    {
      "version", "tb_dir", "n_points",
      "current_step", "current_reward",
      "peak_reward", "peak_step",
      "mean_last10", "std_last10",
      "voxels_mean", "voxels_max", "rooms_mean", "rooms_max",
      "entropy_loss", "action_std", "value_loss", "explained_variance", "fps",
      "plateau_window_improvement"   # son ~300k step'te reward kazanci
    }
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def _read_scalars(tb_dir: Path, tag: str):
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        return []
    files = sorted(glob.glob(str(tb_dir / "**" / "events.out.tfevents.*"), recursive=True))
    pts = []
    for ef in files:
        try:
            ea = EventAccumulator(ef)
            ea.Reload()
            if tag in ea.Tags().get("scalars", []):
                pts.extend((s.step, s.value) for s in ea.Scalars(tag))
        except Exception:
            pass
    return sorted(set(pts), key=lambda x: x[0])


def _last(pts):
    return pts[-1][1] if pts else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(REPO / "configs/ppo.yaml"))
    ap.add_argument("--history", action="store_true")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(open(args.config))
    tr = cfg["train"]
    tb_base = REPO / tr["tb_log"].lstrip("./")
    version = str(tr.get("version", "v?"))

    dirs = sorted(tb_base.glob("PPO_*"))
    out = {"version": version, "tb_dir": str(tb_base), "n_points": 0}
    if not dirs:
        print(json.dumps(out))
        return
    tb_dir = dirs[-1]
    out["tb_dir"] = tb_dir.name

    rew = _read_scalars(tb_dir, "rollout/ep_rew_mean")
    out["n_points"] = len(rew)
    if rew:
        steps = [p[0] for p in rew]
        vals  = [p[1] for p in rew]
        pk = max(range(len(vals)), key=lambda i: vals[i])
        last10 = vals[-10:]
        mean10 = sum(last10) / len(last10)
        std10  = math.sqrt(sum((v - mean10) ** 2 for v in last10) / len(last10))
        out.update({
            "current_step": steps[-1],
            "current_reward": round(vals[-1], 3),
            "peak_reward": round(vals[pk], 3),
            "peak_step": steps[pk],
            "mean_last10": round(mean10, 3),
            "std_last10": round(std10, 3),
        })
        # plateau: son ~300k step'teki kazanc
        win = 300_000
        cur = steps[-1]
        widx = next((i for i, s in enumerate(steps) if s >= cur - win), 0)
        wvals = vals[widx:]
        if wvals:
            out["plateau_window_improvement"] = round(max(wvals) - wvals[0], 3)
        if args.history:
            out["history"] = [[s, round(v, 3)] for s, v in rew]

    for tag, key in [("rollout/ep_len_mean", "ep_len_mean"),
                     ("explore/voxels_mean", "voxels_mean"),
                     ("explore/voxels_max", "voxels_max"),
                     ("explore/rooms_mean", "rooms_mean"),
                     ("explore/rooms_max", "rooms_max"),
                     ("train/entropy_loss", "entropy_loss"),
                     ("train/std", "action_std"),
                     ("train/value_loss", "value_loss"),
                     ("train/explained_variance", "explained_variance"),
                     ("time/fps", "fps")]:
        v = _last(_read_scalars(tb_dir, tag))
        if v is not None:
            out[key] = round(float(v), 4)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
