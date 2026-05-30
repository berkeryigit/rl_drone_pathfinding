#!/home/berkerygt/Desktop/RLProje/rl_drone_pathfinding/.venv/bin/python3
"""PPO eğitim monitörü — her 20dk gözlemler, log stale veya process ölüyse otomatik restart.

Çalıştır:
    nohup python3 scripts/monitor_agent.py > /tmp/monitor.log 2>&1 &
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import subprocess
import time
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
PROJ_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = PROJ_ROOT / "configs" / "ppo.yaml"
TRAIN_LOG   = Path("/tmp/train_ppo.log")
LOCK_FILE   = Path("/tmp/rl_drone_train.lock")

LOGS_DIR           = PROJ_ROOT / "logs"
METRICS_CSV        = LOGS_DIR / "training_metrics.csv"
INTERVENTIONS_JSONL = LOGS_DIR / "interventions.jsonl"

CHECK_INTERVAL_SEC = 20 * 60   # 20 dakika
DEADLINE           = datetime.datetime(2026, 5, 31, 4, 0, 0)
LOG_STALE_SEC      = 12 * 60   # 12 dk güncellenmemişse sorunlu say

# ---------------------------------------------------------------------------

def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{now_str()}] {msg}", flush=True)

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

def run_dirs() -> tuple[Path, Path, Path]:
    cfg = load_config()
    tr = cfg["train"]
    return (
        PROJ_ROOT / tr["log_dir"].lstrip("./"),
        PROJ_ROOT / tr["ckpt_dir"].lstrip("./"),
        PROJ_ROOT / tr["tb_log"].lstrip("./"),
    )

# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------

def find_train_pids() -> list[int]:
    r = subprocess.run(["pgrep", "-f", "train_ppo"], capture_output=True, text=True)
    return [int(p) for p in r.stdout.strip().split() if p.strip()]

def is_healthy() -> bool:
    """Process var VE log son LOG_STALE_SEC içinde güncellendi."""
    pids = find_train_pids()
    if not pids:
        return False
    if TRAIN_LOG.exists():
        age = time.time() - TRAIN_LOG.stat().st_mtime
        if age > LOG_STALE_SEC:
            log(f"UYARI: process var {pids} ama log {age/60:.1f}dk stale")
            return False
    return True

# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def latest_checkpoint() -> Path | None:
    _, ckpt_dir, _ = run_dirs()
    zips = sorted(ckpt_dir.glob("ppo_drone_*_steps.zip"))
    if zips:
        return zips[-1]
    interrupted = ckpt_dir / "ppo_drone_interrupted.zip"
    return interrupted if interrupted.exists() else None

def ckpt_step(ckpt: Path) -> int:
    for p in ckpt.stem.split("_"):
        if p.isdigit():
            return int(p)
    return 0

# ---------------------------------------------------------------------------
# TensorBoard
# ---------------------------------------------------------------------------

def read_tb_metrics() -> dict:
    _, _, tb_base = run_dirs()
    dirs = sorted(tb_base.glob("PPO_*"))
    if not dirs:
        return {}
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        ea = EventAccumulator(str(dirs[-1]))
        ea.Reload()

        def last(tag):
            try:
                evs = ea.Scalars(tag)
                return (evs[-1].step, evs[-1].value) if evs else (0, None)
            except Exception:
                return (0, None)

        step, rew   = last("rollout/ep_rew_mean")
        _,    elen  = last("rollout/ep_len_mean")
        _,    fps   = last("time/fps")
        _,    ent   = last("train/entropy_loss")
        _,    std   = last("train/std")
        return {"step": step, "ep_rew_mean": rew, "ep_len_mean": elen,
                "fps": fps, "entropy_loss": ent, "std": std, "tb_dir": dirs[-1].name}
    except Exception as e:
        log(f"TB okuma hatası: {e}")
        return {}

# ---------------------------------------------------------------------------
# CSV / JSONL
# ---------------------------------------------------------------------------

HEADER = ["timestamp","step","ep_rew_mean","ep_len_mean","fps","entropy_loss","std","ckpt_file"]

def ensure_csv():
    if not METRICS_CSV.exists():
        LOGS_DIR.mkdir(exist_ok=True)
        with open(METRICS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(HEADER)

def append_metrics(m: dict) -> None:
    ensure_csv()
    ckpt = latest_checkpoint()
    with open(METRICS_CSV, "a", newline="") as f:
        csv.writer(f).writerow([
            now_str(), m.get("step",""), m.get("ep_rew_mean",""),
            m.get("ep_len_mean",""), m.get("fps",""), m.get("entropy_loss",""),
            m.get("std",""), ckpt.name if ckpt else "",
        ])

def append_intervention(entry: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    entry["ts"] = now_str()
    with open(INTERVENTIONS_JSONL, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------------------
# Hard kill + restart
# ---------------------------------------------------------------------------

def kill_all_training() -> None:
    for pid in find_train_pids():
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
    subprocess.run(["pkill", "-TERM", "-f", "gz sim"],          capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "parameter_bridge"], capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "ros2 launch rl_drone"], capture_output=True)
    LOCK_FILE.unlink(missing_ok=True)
    time.sleep(5)

def restart(step: int, ckpt: Path | None) -> None:
    resume_val = str(ckpt.relative_to(PROJ_ROOT)) if ckpt else None
    cfg = load_config()
    cfg["train"]["resume_from"] = resume_val
    save_config(cfg)

    append_intervention({
        "type": "crash_recovery",
        "step": step,
        "resume_from": ckpt.name if ckpt else None,
        "reason": "process ölü veya log stale",
    })

    fixes = PROJ_ROOT / "fixes.txt"
    with open(fixes, "a") as f:
        f.write(f"\n[{now_str()}] RESTART — step={step}, resume={ckpt.name if ckpt else 'fresh'}\n")

    log(f"Restart: resume_from={resume_val}")
    subprocess.Popen(
        ["bash", str(PROJ_ROOT / "scripts" / "train.sh"), str(CONFIG_PATH)],
        stdout=open("/tmp/train_ppo.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def git_push(msg: str) -> None:
    try:
        os.chdir(PROJ_ROOT)
        subprocess.run(["git", "add", "configs/ppo.yaml", "logs/", "fixes.txt"],
                       capture_output=True)
        r = subprocess.run(
            ["git", "commit", "-m",
             f"{msg}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"],
            capture_output=True, text=True)
        if r.returncode == 0:
            subprocess.run(["git", "push", "origin", "algo/ppo"], capture_output=True)
            log("Git push OK")
        else:
            log(f"Git: değişiklik yok")
    except Exception as e:
        log(f"Git hata: {e}")

# ---------------------------------------------------------------------------
# Ana döngü
# ---------------------------------------------------------------------------

def main() -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    ensure_csv()
    log(f"Monitor başladı — kontrol: {CHECK_INTERVAL_SEC//60}dk, deadline: {DEADLINE}")

    while datetime.datetime.now() < DEADLINE:
        log("--- kontrol ---")

        m = read_tb_metrics()
        step = m.get("step", 0) if m else 0

        if m:
            log(f"step={step:,} rew={m['ep_rew_mean']:.1f} len={m['ep_len_mean']:.0f} "
                f"fps={m['fps']:.0f} ent={m['entropy_loss']:.3f} std={m['std']:.3f} tb={m['tb_dir']}")
            append_metrics(m)

        if not is_healthy():
            log("Sağlıksız — restart")
            ckpt = latest_checkpoint()
            s    = ckpt_step(ckpt) if ckpt else 0
            kill_all_training()
            restart(s, ckpt)
            git_push(f"auto: restart step={s}")
        else:
            pid = find_train_pids()
            log(f"Sağlıklı {pid}, müdahale yok")
            git_push(f"auto: metrics step={step}")

        log(f"--- bekleniyor {CHECK_INTERVAL_SEC//60}dk ---\n")
        time.sleep(CHECK_INTERVAL_SEC)

    log("Deadline 31 Mayıs 04:00 aşıldı. Monitor duruyor.")

if __name__ == "__main__":
    main()
