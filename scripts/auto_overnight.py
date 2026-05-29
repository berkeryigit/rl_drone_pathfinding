#!/usr/bin/env python3
"""Otonom gece egitim monitoru ve mudahale scripti.

Sabah 07:30'a kadar her CHECK_INTERVAL_MIN dakikada bir:
  1. Egitim processi calisiyorsa devam et
  2. Olmuyorsa yeniden baslt (crash recovery)
  3. TensorBoard metriklerini oku
  4. Peak-regress, entropy explosion, plateau tespit et
  5. Gerekirse mudahale (checkpoint'ten resume, hyperparams guncelle)
  6. Her COMMIT_STEPS_INTERVAL step'te git commit at

Cikti dosyalari:
  docs/PROGRESS.md -> ek log blogu
  fixes.txt        -> kararlar + nedenler
  /tmp/auto_overnight.log -> detayli runtime log
"""
from __future__ import annotations

import datetime
import glob
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import yaml
from pathlib import Path

# ============================================================
PROJ = Path("/home/berkerygt/Desktop/RLProje/rl_drone_pathfinding")
CONFIG = PROJ / "configs/ppo.yaml"
STOP_HOUR, STOP_MIN = 7, 30          # sabah 07:30'da dur
CHECK_INTERVAL_MIN = 20              # her 20 dakikada bir kontrol
COMMIT_STEPS_INTERVAL = 400_000     # her 400k step'te commit
PEAK_REGRESS_RATIO = 0.60           # peak'in %60'ina dusunce mudahale
PEAK_REGRESS_MIN_STEPS = 80_000     # peak sonrasi en az bu kadar step gec
PEAK_MIN_VALUE = 15.0               # peak en az bu kadar olmazsa mudahale yok
PLATEAU_WINDOW = 300_000            # bu kadar step'te ilerleme yoksa plateau
PLATEAU_IMPROVEMENT_THR = 3.0      # min gelisme (reward birimi)
LOG_FILE = Path("/tmp/auto_overnight.log")
# ============================================================

_last_commit_step = 0
_intervention_count = 0
_run_version = 9  # v9 ile basliyoruz


def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_config() -> dict:
    with open(CONFIG) as f:
        return yaml.safe_load(f)


def save_config(cfg: dict):
    with open(CONFIG, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def is_training_running() -> bool:
    r = subprocess.run(["pgrep", "-f", "train_ppo --config"],
                       capture_output=True)
    return r.returncode == 0


def kill_training():
    subprocess.run(["pkill", "-INT", "-f", "train_ppo --config"],
                   capture_output=True)
    time.sleep(5)
    subprocess.run(["pkill", "-TERM", "-f", "gz sim"], capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "parameter_bridge"], capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "ros2 launch rl_drone"], capture_output=True)
    time.sleep(5)


def start_training():
    log("Egitim baslatiliyor...")
    train_log = open("/tmp/train_ppo.log", "a")
    subprocess.Popen(
        ["bash", str(PROJ / "scripts/train.sh"), str(CONFIG)],
        stdout=train_log, stderr=train_log,
        cwd=str(PROJ),
    )
    # Sim'in ayaga kalkmasini bekle
    for i in range(60):
        time.sleep(5)
        if is_training_running():
            log(f"train_ppo processi gorundu ({i*5}s sonra)")
            return
    log("UYARI: train_ppo 300s'de baslamadi, sim log: /tmp/rl_drone_sim_0.log")


# ---------- TensorBoard metric reader ----------

def read_tb_scalars(tb_dir: Path, tag: str):
    """Returns sorted list of (step, value) from TB event files."""
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        return []

    event_files = sorted(glob.glob(str(tb_dir / "**" / "events.out.tfevents.*"),
                                   recursive=True))
    if not event_files:
        return []

    points = []
    for ef in event_files[-3:]:  # sadece son 3 event dosyasi (hizli)
        try:
            ea = EventAccumulator(ef)
            ea.Reload()
            tags = ea.Tags().get("scalars", [])
            if tag in tags:
                points.extend([(s.step, s.value) for s in ea.Scalars(tag)])
        except Exception:
            pass
    return sorted(set(points), key=lambda x: x[0])


def get_latest_metrics(cfg: dict):
    """
    Returns dict:
      current_step, current_reward, peak_reward, peak_step,
      mean_last20, std_last20, all_points
    or None if no data.
    """
    tb_dir = PROJ / cfg["train"]["tb_log"]
    points = read_tb_scalars(tb_dir, "rollout/ep_rew_mean")
    if len(points) < 5:
        return None

    steps = [p[0] for p in points]
    vals  = [p[1] for p in points]

    peak_idx   = int(max(range(len(vals)), key=lambda i: vals[i]))
    peak_step  = steps[peak_idx]
    peak_val   = vals[peak_idx]
    current_step = steps[-1]
    current_val  = vals[-1]
    last20 = vals[-20:] if len(vals) >= 20 else vals
    mean20 = sum(last20) / len(last20)
    std20  = math.sqrt(sum((v - mean20)**2 for v in last20) / len(last20))

    return {
        "current_step":  current_step,
        "current_reward": current_val,
        "peak_reward":   peak_val,
        "peak_step":     peak_step,
        "mean_last20":   mean20,
        "std_last20":    std20,
        "all_points":    points,
    }


def get_best_checkpoint_near_step(ckpt_dir: Path, target_step: int) -> Path | None:
    """Find checkpoint zip closest to target_step."""
    zips = sorted(ckpt_dir.glob("ppo_drone_*_steps.zip"))
    if not zips:
        return None
    best = min(zips, key=lambda p: abs(_extract_step(p.name) - target_step))
    return best


def _extract_step(name: str) -> int:
    m = re.search(r"(\d+)_steps", name)
    return int(m.group(1)) if m else 0


# ---------- Intervention logic ----------

def decide_intervention(metrics: dict, cfg: dict) -> str | None:
    """
    Returns action string or None:
      'resume_from_peak' — peak'in yakinindaki checkpoint'ten devam et
      'reduce_ent_coef'  — entropy cok yuksek, ent_coef dusur
      'reduce_lr'        — plateau, lr dusur
      'none'             — mudahale gerekmez
    """
    if metrics is None:
        return None

    peak    = metrics["peak_reward"]
    current = metrics["current_reward"]
    current_step = metrics["current_step"]
    peak_step    = metrics["peak_step"]
    std20   = metrics["std_last20"]

    # 1. Peak-regress: peak yeterince yuksek, dustu, ve peak'ten bu yana fazla step gec
    if (peak >= PEAK_MIN_VALUE
            and current < peak * PEAK_REGRESS_RATIO
            and current_step - peak_step > PEAK_REGRESS_MIN_STEPS):
        return "resume_from_peak"

    # 2. Yuksek varyans (oscillation): std son 20 > 35 ve ortalama dusuk
    if std20 > 35 and metrics["mean_last20"] < peak * 0.7:
        ppo_cfg = cfg.get("ppo", {})
        ent = float(ppo_cfg.get("ent_coef", 0.001))
        if ent > 0.001:
            return "reduce_ent_coef"

    # 3. Plateau: uzun suredir ilerleme yok
    points = metrics["all_points"]
    if len(points) >= 20 and current_step > PLATEAU_WINDOW:
        start_idx = next((i for i, (s, v) in enumerate(points)
                          if s >= current_step - PLATEAU_WINDOW), 0)
        window_vals = [v for s, v in points[start_idx:]]
        if window_vals:
            window_peak = max(window_vals)
            window_first = window_vals[0]
            if window_peak - window_first < PLATEAU_IMPROVEMENT_THR:
                return "reduce_lr"

    return None


def do_resume_from_peak(cfg: dict, metrics: dict) -> dict:
    global _intervention_count, _run_version
    _intervention_count += 1

    ckpt_dir  = PROJ / cfg["train"]["ckpt_dir"]
    peak_step = metrics["peak_step"]
    peak_val  = metrics["peak_reward"]
    best_ckpt = get_best_checkpoint_near_step(ckpt_dir, peak_step)

    if best_ckpt is None:
        log("resume_from_peak: checkpoint bulunamadi, egitim devam ediyor")
        return cfg

    log(f"MUDAHALE #{_intervention_count}: peak-regress "
        f"(peak={peak_val:.1f}@{peak_step}, current={metrics['current_reward']:.1f}) "
        f"-> resume from {best_ckpt.name}")

    # VecNormalize pkl de varsa yedekle
    vn_pkl = ckpt_dir / "vec_normalize.pkl"
    if vn_pkl.exists():
        vn_bak = ckpt_dir / f"vec_normalize_bak_{_intervention_count}.pkl"
        shutil.copy(vn_pkl, vn_bak)

    cfg["train"]["resume_from"] = str(best_ckpt)
    return cfg


def do_reduce_ent_coef(cfg: dict, metrics: dict) -> dict:
    global _intervention_count
    _intervention_count += 1
    old = float(cfg["ppo"]["ent_coef"])
    new = max(0.001, old * 0.5)
    log(f"MUDAHALE #{_intervention_count}: entropy oscillation "
        f"(std={metrics['std_last20']:.1f}) -> ent_coef {old} -> {new}")
    cfg["ppo"]["ent_coef"] = new
    cfg["train"]["resume_from"] = None
    return cfg


def do_reduce_lr(cfg: dict, metrics: dict) -> dict:
    global _intervention_count
    _intervention_count += 1
    old = float(cfg["ppo"]["learning_rate"])
    new = max(5e-5, old * 0.5)
    log(f"MUDAHALE #{_intervention_count}: plateau "
        f"(step={metrics['current_step']}) -> lr {old:.2e} -> {new:.2e}")
    cfg["ppo"]["learning_rate"] = new
    cfg["ppo"]["lr_schedule"] = "constant"
    cfg["train"]["resume_from"] = None
    return cfg


# ---------- Git commit ----------

def git_commit(message: str):
    try:
        subprocess.run(["git", "-C", str(PROJ), "add",
                        "configs/ppo.yaml",
                        "docs/PROGRESS.md",
                        "fixes.txt",
                        "ros2_ws/src/rl_drone_pathfinding/worlds/multi_room.sdf",
                        "ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env.py",
                        "scripts/auto_overnight.py"],
                       capture_output=True)
        result = subprocess.run(
            ["git", "-C", str(PROJ), "commit", "-m", message],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log(f"Git commit OK: {message[:60]}")
        else:
            if "nothing to commit" in result.stdout + result.stderr:
                log("Git commit: nothing new to commit")
            else:
                log(f"Git commit FAIL: {result.stderr[:200]}")
    except Exception as e:
        log(f"Git commit exception: {e}")


def git_push():
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJ), "push", "origin", "algo/ppo"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            log("Git push OK")
        else:
            log(f"Git push FAIL: {result.stderr[:200]}")
    except Exception as e:
        log(f"Git push exception: {e}")


def append_progress(text: str):
    progress_file = PROJ / "docs" / "PROGRESS.md"
    with open(progress_file, "a") as f:
        f.write("\n" + text + "\n")


def append_fixes(text: str):
    fixes_file = PROJ / "fixes.txt"
    with open(fixes_file, "a") as f:
        f.write("\n" + text + "\n")


# ---------- Main loop ----------

def main():
    global _last_commit_step, _run_version

    log("=" * 60)
    log("auto_overnight.py basladi")
    log(f"Bitis: {STOP_HOUR:02d}:{STOP_MIN:02d} | Check interval: {CHECK_INTERVAL_MIN}min")
    log("=" * 60)

    # Baslangic durumu
    cfg = load_config()
    log_dir_name = cfg["train"]["log_dir"].split("/")[-1]
    log(f"Config: {CONFIG}, log_dir: {log_dir_name}")

    iter_count = 0

    while True:
        now = datetime.datetime.now()
        if (now.hour > STOP_HOUR or
                (now.hour == STOP_HOUR and now.minute >= STOP_MIN)):
            log("Bitis saatine ulasildi (07:30). Son commit + push yapiliyor.")
            cfg_now = load_config()
            metrics = get_latest_metrics(cfg_now)
            if metrics:
                final_msg = (f"auto: overnight done — "
                             f"step={metrics['current_step']}, "
                             f"reward={metrics['current_reward']:.1f}, "
                             f"peak={metrics['peak_reward']:.1f}")
            else:
                final_msg = "auto: overnight done (no metrics)"
            git_commit(final_msg)
            git_push()
            break

        iter_count += 1
        log(f"--- Iterasyon #{iter_count} ({now.strftime('%H:%M')}) ---")

        # Egitim calisiyorsa kontrol et
        training_alive = is_training_running()
        log(f"Egitim {'calisiyor' if training_alive else 'DURMIS'}")

        # Config'i taze oku (mudahalelerden sonra degisebilir)
        cfg = load_config()
        metrics = get_latest_metrics(cfg)

        if metrics:
            log(f"Metrikler: step={metrics['current_step']}, "
                f"reward={metrics['current_reward']:.2f}, "
                f"peak={metrics['peak_reward']:.2f}@{metrics['peak_step']}, "
                f"std20={metrics['std_last20']:.2f}")

        # Crash recovery
        if not training_alive:
            if metrics:
                # Son checkpoint'ten devam et
                ckpt_dir = PROJ / cfg["train"]["ckpt_dir"]
                zips = sorted(ckpt_dir.glob("ppo_drone_*_steps.zip"),
                              key=lambda p: _extract_step(p.name))
                interrupted = ckpt_dir / "ppo_drone_interrupted.zip"
                if interrupted.exists():
                    resume_from = str(interrupted)
                elif zips:
                    resume_from = str(zips[-1])
                else:
                    resume_from = None

                if resume_from:
                    log(f"Crash recovery: resume_from={Path(resume_from).name}")
                    cfg["train"]["resume_from"] = resume_from
                    save_config(cfg)
            start_training()
            time.sleep(60)
            continue

        # Mudahale karari
        if metrics:
            action = decide_intervention(metrics, cfg)
            if action and action != "none":
                log(f"Mudahale karari: {action}")
                if action == "resume_from_peak":
                    cfg = do_resume_from_peak(cfg, metrics)
                elif action == "reduce_ent_coef":
                    cfg = do_reduce_ent_coef(cfg, metrics)
                elif action == "reduce_lr":
                    cfg = do_reduce_lr(cfg, metrics)

                save_config(cfg)

                # Mudahale logu
                msg = (f"auto: {action} intervention #{_intervention_count} "
                       f"at step={metrics['current_step']}, "
                       f"peak={metrics['peak_reward']:.1f}")
                append_fixes(f"\n--- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} "
                             f"AUTO INTERVENTION: {action} ---\n"
                             f"Step: {metrics['current_step']}\n"
                             f"Peak: {metrics['peak_reward']:.1f} @ {metrics['peak_step']}\n"
                             f"Current: {metrics['current_reward']:.1f}\n"
                             f"Karar: {action}\n")

                # Egitimi yeniden baslt
                kill_training()
                time.sleep(10)
                start_training()

                git_commit(msg)
                git_push()

                # Interval'i gec (yeniden basladiktan sonra birkac dakika bekle)
                log("Mudahale sonrasi 5 dakika bekleniyor...")
                time.sleep(300)
                continue

        # Periyodik commit (her COMMIT_STEPS_INTERVAL)
        if metrics:
            step = metrics["current_step"]
            milestone = (step // COMMIT_STEPS_INTERVAL) * COMMIT_STEPS_INTERVAL
            if milestone > _last_commit_step and milestone > 0:
                _last_commit_step = milestone
                commit_msg = (f"auto: v9 step={step} "
                              f"reward={metrics['current_reward']:.1f} "
                              f"peak={metrics['peak_reward']:.1f}")
                git_commit(commit_msg)
                git_push()

        # Bir sonraki kontrole kadar bekle
        log(f"Sonraki kontrol {CHECK_INTERVAL_MIN} dakika sonra...")
        time.sleep(CHECK_INTERVAL_MIN * 60)


if __name__ == "__main__":
    main()
