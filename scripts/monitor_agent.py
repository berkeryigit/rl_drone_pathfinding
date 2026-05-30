#!/home/berkerygt/Desktop/RLProje/rl_drone_pathfinding/.venv/bin/python3
"""PPO eğitim monitörü — her 30dk gözlemler, sadece crash durumunda müdahale eder.

Çalıştır:
    nohup python3 scripts/monitor_agent.py > /tmp/monitor.log 2>&1 &
"""
from __future__ import annotations

import csv
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
PROJ_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = PROJ_ROOT / "configs" / "ppo.yaml"
TRAIN_LOG = Path("/tmp/train_ppo.log")
LOCK_FILE = Path("/tmp/rl_drone_train.lock")

LOGS_DIR = PROJ_ROOT / "logs"
METRICS_CSV = LOGS_DIR / "training_metrics.csv"
INTERVENTIONS_JSONL = LOGS_DIR / "interventions.jsonl"

CHECK_INTERVAL_SEC = 30 * 60   # 30 dakika
DEADLINE = datetime.datetime(2026, 5, 31, 4, 0, 0)

TRAIN_LOG_STALE_SEC = 15 * 60  # 15 dakika güncellenmemişse sorun var

TOTAL_STEPS = 2_500_000

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
    """ppo.yaml'dan log_dir, ckpt_dir, tb_log okur."""
    cfg = load_config()
    tr = cfg["train"]
    log_dir  = PROJ_ROOT / tr["log_dir"].lstrip("./")
    ckpt_dir = PROJ_ROOT / tr["ckpt_dir"].lstrip("./")
    tb_dir   = PROJ_ROOT / tr["tb_log"].lstrip("./")
    return log_dir, ckpt_dir, tb_dir


# ---------------------------------------------------------------------------
# Process / liveness check
# ---------------------------------------------------------------------------

def find_train_pid() -> int | None:
    result = subprocess.run(["pgrep", "-f", "train_ppo"], capture_output=True, text=True)
    pids = [int(p) for p in result.stdout.strip().split() if p.strip()]
    return pids[0] if pids else None


def is_training_alive() -> bool:
    pid = find_train_pid()
    if pid is None:
        return False
    if TRAIN_LOG.exists():
        mtime_age = time.time() - TRAIN_LOG.stat().st_mtime
        if mtime_age > TRAIN_LOG_STALE_SEC:
            log(f"UYARI: train_ppo process var (pid={pid}) ama log {mtime_age/60:.1f} dk güncellenmedi")
            return False
    return True


# ---------------------------------------------------------------------------
# Checkpoint: son .zip'i bul
# ---------------------------------------------------------------------------

def latest_checkpoint() -> Path | None:
    _, ckpt_dir, _ = run_dirs()
    zips = sorted(ckpt_dir.glob("ppo_drone_*_steps.zip"))
    if not zips:
        interrupted = ckpt_dir / "ppo_drone_interrupted.zip"
        if interrupted.exists():
            return interrupted
        return None
    return zips[-1]


def checkpoint_step(ckpt: Path) -> int:
    stem = ckpt.stem
    for p in stem.split("_"):
        if p.isdigit():
            return int(p)
    return 0


# ---------------------------------------------------------------------------
# TensorBoard okuma — sadece en güncel PPO_N dizini
# ---------------------------------------------------------------------------

def latest_tb_dir() -> Path | None:
    _, _, tb_base = run_dirs()
    dirs = sorted(tb_base.glob("PPO_*"))
    if not dirs:
        return None
    return dirs[-1]


def read_tb_metrics() -> dict:
    tb_dir = latest_tb_dir()
    if tb_dir is None:
        log("TB dizini bulunamadı")
        return {}
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        ea = EventAccumulator(str(tb_dir))
        ea.Reload()

        def last_val(tag: str) -> float | None:
            try:
                events = ea.Scalars(tag)
                if events:
                    return events[-1].value
            except Exception:
                pass
            return None

        def last_step(tag: str) -> int | None:
            try:
                events = ea.Scalars(tag)
                if events:
                    return events[-1].step
            except Exception:
                pass
            return None

        step = last_step("rollout/ep_rew_mean") or 0
        return {
            "step": step,
            "ep_rew_mean": last_val("rollout/ep_rew_mean"),
            "ep_len_mean": last_val("rollout/ep_len_mean"),
            "fps": last_val("time/fps"),
            "entropy_loss": last_val("train/entropy_loss"),
            "std": last_val("train/std"),
            "tb_dir": tb_dir.name,
        }
    except Exception as e:
        log(f"TB okuma hatası: {e}")
        return {}


# ---------------------------------------------------------------------------
# CSV loglama
# ---------------------------------------------------------------------------

METRICS_HEADER = ["timestamp", "step", "ep_rew_mean", "ep_len_mean", "fps",
                  "entropy_loss", "std", "ckpt_file"]


def ensure_csv_header() -> None:
    if not METRICS_CSV.exists():
        LOGS_DIR.mkdir(exist_ok=True)
        with open(METRICS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(METRICS_HEADER)


def append_metrics(metrics: dict) -> None:
    ensure_csv_header()
    ckpt = latest_checkpoint()
    row = [
        now_str(),
        metrics.get("step", ""),
        metrics.get("ep_rew_mean", ""),
        metrics.get("ep_len_mean", ""),
        metrics.get("fps", ""),
        metrics.get("entropy_loss", ""),
        metrics.get("std", ""),
        ckpt.name if ckpt else "",
    ]
    with open(METRICS_CSV, "a", newline="") as f:
        csv.writer(f).writerow(row)


def append_intervention(entry: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    entry["ts"] = now_str()
    with open(INTERVENTIONS_JSONL, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------

def crash_recovery() -> None:
    log("CRASH TESPİT EDİLDİ — recovery başlıyor")
    ckpt = latest_checkpoint()
    if ckpt is None:
        log("Checkpoint bulunamadı, fresh start yapılıyor")
        resume_val = None
        step = 0
    else:
        step = checkpoint_step(ckpt)
        resume_val = str(ckpt.relative_to(PROJ_ROOT))
        log(f"Son checkpoint: {ckpt.name} (step={step})")

    cfg = load_config()
    cfg["train"]["resume_from"] = resume_val
    save_config(cfg)

    reason = f"Process ölü, log stale; checkpoint={ckpt.name if ckpt else 'yok'}"
    append_intervention({
        "type": "crash_recovery",
        "step": step,
        "resume_from": ckpt.name if ckpt else None,
        "reason": reason,
    })

    fixes_path = PROJ_ROOT / "fixes.txt"
    with open(fixes_path, "a") as f:
        f.write(f"\n[{now_str()}] CRASH RECOVERY\n")
        f.write(f"  Sebep: {reason}\n")
        f.write(f"  Resume: {ckpt.name if ckpt else 'fresh'}\n")

    log("Eski process'ler temizleniyor...")
    subprocess.run(["pkill", "-TERM", "-f", "gz sim"], capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "parameter_bridge"], capture_output=True)
    subprocess.run(["pkill", "-TERM", "-f", "ros2 launch rl_drone"], capture_output=True)
    subprocess.run(["rm", "-f", str(LOCK_FILE)], capture_output=True)
    time.sleep(5)

    train_sh = PROJ_ROOT / "scripts" / "train.sh"
    log(f"train.sh yeniden başlatılıyor: {train_sh}")
    subprocess.Popen(
        ["bash", str(train_sh), str(CONFIG_PATH)],
        stdout=open("/tmp/train_ppo.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log("Recovery tamamlandı")
    git_commit(f"auto: crash-recovery step={step}")


# ---------------------------------------------------------------------------
# Git commit
# ---------------------------------------------------------------------------

def git_commit(msg: str) -> None:
    try:
        os.chdir(PROJ_ROOT)
        subprocess.run(
            ["git", "add",
             "configs/ppo.yaml",
             "docs/",
             "fixes.txt",
             "logs/"],
            capture_output=True
        )
        full_msg = f"{msg}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
        result = subprocess.run(
            ["git", "commit", "-m", full_msg],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log(f"Git commit: {msg}")
            subprocess.run(["git", "push", "origin", "algo/ppo"], capture_output=True)
            log("Push tamamlandı")
        else:
            log(f"Git commit atlandı (değişiklik yok): {result.stderr.strip()[:80]}")
    except Exception as e:
        log(f"Git hata: {e}")


# ---------------------------------------------------------------------------
# Ana döngü
# ---------------------------------------------------------------------------

def main() -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    ensure_csv_header()
    _, _, tb_base = run_dirs()
    log(f"Monitor başladı. Kontrol aralığı: {CHECK_INTERVAL_SEC // 60} dk. Deadline: {DEADLINE}")
    log(f"TB dizini: {tb_base}")

    while datetime.datetime.now() < DEADLINE:
        log("--- Kontrol başlıyor ---")

        metrics = read_tb_metrics()
        if metrics:
            step = metrics.get("step", 0)
            log(f"step={step:,}  ep_rew={metrics.get('ep_rew_mean'):.1f}  "
                f"ep_len={metrics.get('ep_len_mean'):.0f}  "
                f"fps={metrics.get('fps'):.0f}  "
                f"entropy={metrics.get('entropy_loss'):.3f}  "
                f"std={metrics.get('std'):.3f}  "
                f"tb={metrics.get('tb_dir')}")
            append_metrics(metrics)
        else:
            log("Metrik okunamadı")
            step = 0

        if not is_training_alive():
            log("Process ölü, crash recovery yapılıyor")
            crash_recovery()
        else:
            pid = find_train_pid()
            log(f"Eğitim sağlıklı (pid={pid}), müdahale yok")

        # Her kontrolde CSV + JSONL'i commit et — remote PPO uzman ajanı okuyabilsin
        git_commit(f"auto: metrics step={step}")

        log(f"--- Kontrol bitti, {CHECK_INTERVAL_SEC // 60} dk bekleniyor ---\n")
        time.sleep(CHECK_INTERVAL_SEC)

    log("Deadline aşıldı (31 Mayıs 04:00). Monitor duruyor.")


if __name__ == "__main__":
    main()
