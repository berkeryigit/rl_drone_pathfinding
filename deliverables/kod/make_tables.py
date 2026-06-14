"""Rapor LaTeX tablo fragmanlarini ham CSV'lerden uretir (sentetik degil).

  sonuclar_tablo.tex      -> PPO seed x eval metrik ozeti
  karsilastirma_tablo.tex -> PPO vs SAC ortalama kiyas (ayni ortam/protokol)

Kullanim:
    python make_tables.py
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

KOD = Path(__file__).resolve().parent
RAPOR = KOD.parent / "rapor"
SON = KOD.parent / "sonuclar"
SEEDS = [7, 13, 42, 123, 2025]


def _n_ep(runs_root: Path, seed: int) -> int:
    p = runs_root / f"seed_{seed}" / "training_log.csv"
    if p.exists():
        return len(pd.read_csv(p))
    return 0


def ppo_summary():
    ev_path = SON / "eval_per_episode.csv"
    if not ev_path.exists():
        print("[tablo] eval_per_episode.csv yok, sonuclar_tablo atlandi")
        return
    ev = pd.read_csv(ev_path)
    runs = KOD / "runs"
    lines = [r"\begin{tabular}{@{}rrrrrr@{}}", r"\toprule",
             r"seed & n\_ep & eval getiri & eval std & başarı & kapsama \% \\", r"\midrule"]
    all_ret, all_succ, all_cov, all_nep = [], [], [], []
    for s in SEEDS:
        sub = ev[ev["seed"] == s]
        if sub.empty:
            continue
        nep = _n_ep(runs, s)
        mret, sret = sub["ep_return"].mean(), sub["ep_return"].std()
        succ, cov = sub["success"].mean(), sub["coverage_pct"].mean()
        lines.append(f"{s} & {nep} & {mret:.2f} & {sret:.2f} & {succ:.2f} & {cov:.2f} \\\\")
        all_ret.append(mret); all_succ.append(succ); all_cov.append(cov); all_nep.append(nep)
    lines.append(r"\midrule")
    lines.append(f"\\textbf{{Ort.}} & \\textbf{{{int(np.mean(all_nep))}}} & "
                 f"\\textbf{{{np.mean(all_ret):.1f}}} & -- & "
                 f"\\textbf{{{np.mean(all_succ):.2f}}} & \\textbf{{{np.mean(all_cov):.2f}}} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (RAPOR / "sonuclar_tablo.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[tablo] sonuclar_tablo.tex yazildi")



if __name__ == "__main__":
    ppo_summary()
    # NOT: karsilastirma_tablo.tex, M. A. Albayrak'in (220202082) teslimindeki
    # yayinlanmis SAC degerleriyle EL ile yazilir; bu script onu uretmez/ezmez.
