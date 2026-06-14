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


def _avg(csv_path: Path):
    if not csv_path.exists():
        return None
    d = pd.read_csv(csv_path)
    return dict(
        ret=d["ep_return"].mean(), succ=d["success"].mean(),
        cov=d["coverage_pct"].mean(), crash=d["crashed"].mean(),
    )


def comparison():
    ppo = _avg(SON / "eval_per_episode.csv")
    sac = _avg(SON / "sac_eval_per_episode.csv")
    if ppo is None:
        print("[tablo] PPO eval yok, karsilastirma atlandi")
        return
    # egitim adim/episode ortalamalari
    def steps_eps(runs_root):
        st, ep = [], []
        for s in SEEDS:
            p = runs_root / f"seed_{s}" / "training_log.csv"
            if p.exists():
                df = pd.read_csv(p)
                if len(df):
                    st.append(df["timestep"].iloc[-1]); ep.append(len(df))
        return (np.mean(st) if st else 0, np.mean(ep) if ep else 0)
    ppo_st, ppo_ep = steps_eps(KOD / "runs")
    sac_st, sac_ep = steps_eps(KOD / "runs_sac")

    def col(v, fmt="{:.1f}", bold=False):
        s = fmt.format(v)
        return f"\\textbf{{{s}}}" if bold else s

    sac_ret = col(sac["ret"]) if sac else "--"
    sac_succ = col(sac["succ"], "{:.2f}") if sac else "--"
    sac_cov = col(sac["cov"]) if sac else "--"
    sac_crash = col(sac["crash"], "{:.2f}") if sac else "--"
    # PPO genelde getiri/basari/kapsama/carpismada onde -> bold PPO ustunluklerini
    lines = [
        r"\begin{tabular}{@{}lcc@{}}", r"\toprule",
        r"Ölçüt & PPO (bu çalışma) & SAC (aynı ortam) \\", r"\midrule",
        r"Aile & on-policy & off-policy \\",
        r"Replay buffer & yok & var \\",
        f"Eğitim adımı (ort.) & {ppo_st/1e6:.1f}\\,M & {sac_st/1e3:.0f}\\,k \\\\",
        f"Eğitim episode (ort.) & $\\sim${int(ppo_ep)} & $\\sim${int(sac_ep)} \\\\",
        r"\midrule",
        f"Ort. eval getirisi & {col(ppo['ret'], bold=True)} & {sac_ret} \\\\",
        f"Eval başarı oranı (6 oda) & {col(ppo['succ'],'{:.2f}',bold=True)} & {sac_succ} \\\\",
        f"Ort. kapsama \\% & {col(ppo['cov'], bold=True)} & {sac_cov} \\\\",
        f"Eval çarpışma oranı & {col(ppo['crash'],'{:.2f}',bold=True)} & {sac_crash} \\\\",
        r"\bottomrule", r"\end{tabular}",
    ]
    (RAPOR / "karsilastirma_tablo.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[tablo] karsilastirma_tablo.tex yazildi"
          f" (SAC verisi {'VAR' if sac else 'YOK -- placeholder'})")


if __name__ == "__main__":
    ppo_summary()
    comparison()
