#!/usr/bin/env python3
"""v4.x Pareto frontier: kapsama (union %) ve voxel vs çarpışma oranı.
Rapor figürü: docs/figures/fast_pareto.png
Veri: tüm v4.x deterministik 100-bölüm eval (ckpt sweep hariç) — elle tablolandı.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# (versiyon, collision_rate, voxels_mean, rooms_mean, union_pct, açıklama)
DATA = [
    ("v4.0", 0.32, 142, 2.00,  None, "taban"),
    ("v4.1", 0.02, 150, 2.00,  6.0,  "room30"),
    ("v4.2", 0.85, 143, 4.98,  None, "breadth push"),
    ("v4.3", 1.00,  37, 3.88,  5.9,  "denge(başarısız)"),
    ("v4.4", 0.97, 167, 4.94, 26.7,  "far1.0"),
    ("v4.5", 0.08, 114, 5.00, 15.6,  "coll30"),
    ("v4.6", 0.93, 176, 5.00, 30.9,  "far1.5+3M"),
    ("v4.7", 0.72,  72, 5.00,  9.4,  "idle↑+4M"),
    ("v4.8", 0.00, 117, 5.00, 13.8,  "coll25 ★GÜVENLİ"),
    ("v4.9", 0.37, 119, 2.00, 18.2,  "coll22"),
    ("v4.10",0.54, 281, 5.76, 44.5,  "5M ★KAPSAM"),
    ("v4.11",1.00, 147, 4.90, 27.3,  "5M+coll50"),
    ("v4.12",0.24,  90, 4.52, 13.2,  "curriculum"),
    ("v4.13",0.26, 134, 4.99, 15.6,  "8M (zirve geçti)"),
]

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# Sol: voxels vs collision
ax = axes[0]
for v, c, vox, rm, un, desc in DATA:
    color = "tab:green" if v == "v4.8" else ("tab:red" if v == "v4.10" else "tab:gray")
    sz = 220 if v in ("v4.8", "v4.10") else 90
    ax.scatter(c*100, vox, s=sz, color=color, zorder=3, edgecolors="black", linewidths=0.6)
    ax.annotate(v, (c*100, vox), textcoords="offset points", xytext=(6, 5), fontsize=9)
ax.set_xlabel("Çarpışma oranı (%)")
ax.set_ylabel("Voxel (ortalama / bölüm)")
ax.set_title("Voxel vs Çarpışma — düşük-sol = güvenli, yüksek = kapsamlı")
ax.grid(alpha=0.3)

# Sağ: union kapsama vs collision (None olanları atla)
ax = axes[1]
for v, c, vox, rm, un, desc in DATA:
    if un is None:
        continue
    color = "tab:green" if v == "v4.8" else ("tab:red" if v == "v4.10" else "tab:gray")
    sz = 220 if v in ("v4.8", "v4.10") else 90
    ax.scatter(c*100, un, s=sz, color=color, zorder=3, edgecolors="black", linewidths=0.6)
    ax.annotate(f"{v}\n({desc})" if v in ("v4.8","v4.10") else v,
                (c*100, un), textcoords="offset points", xytext=(6, 5), fontsize=9)
ax.set_xlabel("Çarpışma oranı (%)")
ax.set_ylabel("Union kapsama (%)")
ax.set_title("Kapsama vs Çarpışma — Pareto cephesi")
ax.grid(alpha=0.3)

fig.suptitle("v4.x Pareto Cephesi: Keşif Kapsamı ↔ Güvenlik Ödünleşimi (PPO, hızlı sim)", fontsize=13)
fig.tight_layout()
out = Path("docs/figures/fast_pareto.png")
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=130)
print(f"saved {out}")
