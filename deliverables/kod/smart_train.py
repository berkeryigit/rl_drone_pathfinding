"""smart_train.py — 3 Fazli Otomatik Egitim Pipeline'i

FAZ 1 — HP Arama (kisa egitim):
  gamma x learning_rate kombinasyonlarini karsilastirir.
  Her combo: search_seeds x search_steps adim.
  En iyi ortalama performans (oda sayisi + getiri) secilir.
  Cikti: hp_search/hp_search_results.json

FAZ 2 — Tam Egitim (en iyi HP ile):
  Secilen gamma+lr ile tum seedleri egitir.
  Max full_steps adim, ogrenme duruyorsa erken durur.
  Her seed icin best_model.zip kaydedilir.
  Cikti: runs/ (her seed ayri klasor)

FAZ 3 — Grafikler:
  Her seed icin bireysel 4-panel dashboard (plot_per_seed.py).
  Birlesik rubrik grafikleri (plot_results.py).
  Cikti: sunum/grafikler/per_seed/ + sunum/grafikler/

Kullanim:
    python3 smart_train.py                        # 3 faz birden
    python3 smart_train.py --phase search         # sadece FAZ 1
    python3 smart_train.py --phase train          # sadece FAZ 2 (onceki aramayi kullanir)
    python3 smart_train.py --phase plot           # sadece FAZ 3

    python3 smart_train.py --search-steps 40000  # daha hizli arama
    python3 smart_train.py --search-seeds "7 13" # daha az search seed
    python3 smart_train.py --full-steps 1500000  # 1.5M hedef
    python3 smart_train.py --patience 50         # daha sabırli durdurma
    python3 smart_train.py --gammas "0.97 0.99"  # sadece 2 gamma
    python3 smart_train.py --lrs "1e-4 3e-4"     # sadece 2 lr

Notlar:
  - FAZ 2 her seferinde sifirdan baslar (--resume yok).
    Mevcut runs/ uzerine yazar. Yedek: runs_backup_500k/ zaten mevcut.
  - Erken durdurma: --patience N ardisik eval'da iyilesme yoksa dur.
    eval_freq=10000 step ile patience=40 => ~400k step iyilesme olmadan durur.
  - FAZ 1 aramasinda eval devre disi (--no-eval) => daha hizli.
    Arama metriği: 10*oda_sayisi + 0.05*getiri (son 30 episode ortalaması).
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from itertools import product
from pathlib import Path

PYTHON = sys.executable
HERE = Path(__file__).resolve().parent
SEARCH_OUT = HERE / "hp_search"


# ──────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ──────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> bool:
    """Komutu calistir; basari durumunu dondur."""
    print("  $", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd)
    return result.returncode == 0


def _read_metrics(log_path: Path, n: int = 30) -> dict | None:
    """training_log.csv'den son n episode metriklerini oku."""
    if not log_path.exists():
        return None
    rows = list(csv.DictReader(open(log_path, newline="")))
    if not rows:
        return None
    last = rows[-min(n, len(rows)):]
    return {
        "mean_return":   sum(float(r["ep_return"])      for r in last) / len(last),
        "mean_rooms":    sum(float(r["visited_rooms"])  for r in last) / len(last),
        "mean_coverage": sum(float(r["coverage_pct"])   for r in last) / len(last),
        "n_episodes":    len(rows),
    }


def _score(m: dict | None) -> float:
    """Arama metriği: oda sayisi birincil, getiri ikincil kriter."""
    if m is None:
        return -999.0
    return m["mean_rooms"] * 10.0 + m["mean_return"] * 0.05


def _load_best_hp() -> tuple[float, float] | tuple[None, None]:
    p = SEARCH_OUT / "hp_search_results.json"
    if not p.exists():
        return None, None
    data = json.loads(p.read_text())
    return float(data["best"]["gamma"]), float(data["best"]["lr"])


def _hr(char: str = "─", n: int = 62) -> None:
    print(char * n)


# ──────────────────────────────────────────────────────────────────────────────
# FAZ 1 — HP Arama
# ──────────────────────────────────────────────────────────────────────────────

def phase_search(args) -> tuple[float, float]:
    gammas = [float(g) for g in args.gammas.split()]
    lrs    = [float(l) for l in args.lrs.split()]
    seeds  = [int(s)   for s in args.search_seeds.split()]
    combos = list(product(gammas, lrs))

    SEARCH_OUT.mkdir(exist_ok=True)

    _hr("=")
    print(f" FAZ 1 — HP ARAMA")
    print(f" gamma        : {gammas}")
    print(f" learning_rate: {lrs}")
    print(f" search seeds : {seeds}  ({args.search_steps:,} step/run)")
    print(f" toplam run   : {len(combos)} kombinasyon × {len(seeds)} seed = {len(combos)*len(seeds)}")
    _hr("=")

    all_results: list[dict] = []

    for ci, (gamma, lr) in enumerate(combos):
        tag = f"g{gamma}_lr{lr:.0e}"
        seed_scores: list[float] = []
        seed_metrics: list[dict] = []

        print(f"\n[{ci+1}/{len(combos)}] {tag}")
        _hr()

        for seed in seeds:
            out_dir = SEARCH_OUT / tag / f"seed_{seed}"
            print(f"  seed={seed} ...")
            ok = _run([
                PYTHON, str(HERE / "train.py"),
                "--seed", str(seed),
                "--timesteps", str(args.search_steps),
                "--out", str(out_dir),
                "--config", str(HERE / "config.yaml"),
                "--gamma", str(gamma),
                "--lr", str(lr),
                "--no-eval",
            ])
            m = _read_metrics(out_dir / "training_log.csv") if ok else None
            s = _score(m)
            seed_scores.append(s)
            seed_metrics.append(m or {})
            if m:
                print(f"         getiri={m['mean_return']:.1f}  oda={m['mean_rooms']:.2f}"
                      f"  kapsam={m['mean_coverage']:.1f}%  skor={s:.2f}")
            else:
                print(f"         HATA veya log yok  (skor=-999)")

        mean_score = sum(seed_scores) / len(seed_scores) if seed_scores else -999.0
        all_results.append({
            "gamma": gamma,
            "lr": lr,
            "tag": tag,
            "seed_scores": seed_scores,
            "seed_metrics": seed_metrics,
            "mean_score": mean_score,
        })

    all_results.sort(key=lambda r: r["mean_score"], reverse=True)
    best = all_results[0]

    print(f"\n{'─'*62}")
    print(f" ARAMA SONUÇLARI  (metrik: 10×oda + 0.05×getiri)")
    print(f"{'─'*62}")
    print(f"  {'Kombinasyon':<22} {'Ort.Skor':>10}  Seedler")
    print(f"  {'─'*22} {'─'*10}  {'─'*20}")
    for r in all_results:
        arrow = "  <── EN IYI" if r is best else ""
        seed_str = "  ".join(f"{s:.1f}" for s in r["seed_scores"])
        print(f"  {r['tag']:<22} {r['mean_score']:>10.2f}  [{seed_str}]{arrow}")
    print(f"{'─'*62}")
    print(f"\n Seçilen: gamma={best['gamma']}  lr={best['lr']:.0e}")

    result_path = SEARCH_OUT / "hp_search_results.json"
    result_path.write_text(json.dumps({
        "best": {"gamma": best["gamma"], "lr": best["lr"]},
        "search_steps": args.search_steps,
        "search_seeds": seeds,
        "all_results": all_results,
    }, indent=2, ensure_ascii=False))
    print(f" Sonuçlar kaydedildi: {result_path}\n")

    return best["gamma"], best["lr"]


# ──────────────────────────────────────────────────────────────────────────────
# FAZ 2 — Tam Egitim
# ──────────────────────────────────────────────────────────────────────────────

def phase_train(args, gamma: float | None = None, lr: float | None = None) -> None:
    if gamma is None or lr is None:
        gamma, lr = _load_best_hp()
        if gamma is None:
            print("HATA: hp_search/hp_search_results.json bulunamadi.")
            print("      Once FAZ 1'i calistirin: python3 smart_train.py --phase search")
            sys.exit(1)

    seeds   = [int(s) for s in args.full_seeds.split()]
    runs_out = HERE / "runs"

    _hr("=")
    print(f" FAZ 2 — TAM EGİTİM")
    print(f" En iyi HP  : gamma={gamma}  lr={lr:.0e}")
    print(f" Seeds      : {seeds}")
    print(f" Max step   : {args.full_steps:,}")
    print(f" Patience   : {args.patience} ardisik eval'da iyilesme yoksa dur")
    print(f" Cikti      : {runs_out}/seed_<N>/")
    _hr("=")

    failed: list[int] = []
    for seed in seeds:
        out_dir = runs_out / f"seed_{seed}"
        print(f"\n{'─'*62}")
        print(f" seed {seed} başlıyor → {out_dir}")
        print(f"{'─'*62}")
        ok = _run([
            PYTHON, str(HERE / "train.py"),
            "--seed", str(seed),
            "--timesteps", str(args.full_steps),
            "--out", str(out_dir),
            "--config", str(HERE / "config.yaml"),
            "--gamma", str(gamma),
            "--lr", str(lr),
            "--stop-patience", str(args.patience),
        ])
        if not ok:
            print(f" UYARI: seed {seed} hatayla bitti.")
            failed.append(seed)

    print(f"\n{'─'*62}")
    if failed:
        print(f" UYARI: Hatalı seedler: {failed}")
    else:
        print(f" FAZ 2 tamamlandı — tüm {len(seeds)} seed başarılı.")
    print(f"{'─'*62}\n")


# ──────────────────────────────────────────────────────────────────────────────
# FAZ 3 — Grafikler
# ──────────────────────────────────────────────────────────────────────────────

def phase_plot(args) -> None:
    runs_root    = str(HERE / "runs")
    seeds_file   = str(HERE / "seeds.txt")
    eval_csv     = str(HERE / "../sonuclar/eval_per_episode.csv")
    baseline_csv = str(HERE / "../sonuclar/baseline_per_episode.csv")
    hp_root      = str(HERE / "runs_hp")
    grafik_out   = str(HERE / "../sunum/grafikler")
    per_seed_out = str(HERE / "../sunum/grafikler/per_seed")
    summary_out  = str(HERE / "../sonuclar/sonuclar.csv")

    _hr("=")
    print(" FAZ 3 — GRAFİKLER")
    _hr("=")

    # 1) Eval güncelle
    print("\n[3a] evaluate.py — deterministik eval CSV güncelleniyor...")
    _run([
        PYTHON, str(HERE / "evaluate.py"),
        "--runs-root", runs_root,
        "--seeds-file", seeds_file,
        "--out", eval_csv,
    ])

    # 2) Per-seed dashboardlar
    print("\n[3b] plot_per_seed.py — bireysel seed dashboardları...")
    _run([
        PYTHON, str(HERE / "plot_per_seed.py"),
        "--runs-root", runs_root,
        "--seeds-file", seeds_file,
        "--out", per_seed_out,
    ])

    # 3) Birleşik rubrik grafikleri
    print("\n[3c] plot_results.py — birleşik rubrik grafikleri...")
    _run([
        PYTHON, str(HERE / "plot_results.py"),
        "--runs-root", runs_root,
        "--seeds-file", seeds_file,
        "--eval-csv", eval_csv,
        "--baseline-csv", baseline_csv,
        "--hp-root", hp_root,
        "--out", grafik_out,
        "--summary-out", summary_out,
    ])

    print(f"\n Tüm grafikler üretildi:")
    print(f"   Per-seed : {per_seed_out}/")
    print(f"   Rubrik   : {grafik_out}/")
    print(f"   Özet CSV : {summary_out}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="smart_train: HP arama → tam egitim → grafik",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--phase", choices=["search", "train", "plot", "all"], default="all",
        help="Hangi fazlar calistirilsin (varsayilan: all)",
    )

    # FAZ 1 parametreleri
    g1 = parser.add_argument_group("FAZ 1 — HP Arama")
    g1.add_argument("--gammas", default="0.97 0.98 0.99",
                    help="Aranacak gamma degerleri, boslukla ayrilmis (varsayilan: '0.97 0.98 0.99')")
    g1.add_argument("--lrs", default="1e-4 3e-4 1e-3",
                    help="Aranacak learning_rate degerleri (varsayilan: '1e-4 3e-4 1e-3')")
    g1.add_argument("--search-seeds", default="7 13 42",
                    help="HP arama icin kullanilacak seedler (varsayilan: '7 13 42')")
    g1.add_argument("--search-steps", type=int, default=60000,
                    help="Her arama run'u icin adim sayisi (varsayilan: 60000)")

    # FAZ 2 parametreleri
    g2 = parser.add_argument_group("FAZ 2 — Tam Egitim")
    g2.add_argument("--full-seeds", default="7 13 42 123 2025",
                    help="Tam egitimde kullanilacak seedler (varsayilan: tum 5 seed)")
    g2.add_argument("--full-steps", type=int, default=1_000_000,
                    help="Tam egitim hedef adim sayisi (varsayilan: 1000000)")
    g2.add_argument("--patience", type=int, default=40,
                    help="Ardisik eval'da iyilesme olmayinca dur (varsayilan: 40)")

    args = parser.parse_args(argv)

    gamma, lr = None, None

    if args.phase in ("search", "all"):
        gamma, lr = phase_search(args)

    if args.phase in ("train", "all"):
        phase_train(args, gamma, lr)

    if args.phase in ("plot", "all"):
        phase_plot(args)

    _hr("=")
    print(" TAMAMLANDI")
    _hr("=")


if __name__ == "__main__":
    main()
