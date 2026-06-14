"""PPO (bu calisma) vs SAC (M. A. Albayrak, 220202082) YAN-YANA kiyas figurleri.

Akif'in SAC sunumundaki (220202082_sunum.pdf) grafikleri, bizim ayni tip PPO
grafigimizin YANINA koyar. Boylece ust-uste bindirme yerine ayni tip iki sonucu
gorsel kiyaslariz. Akif zaten 200k+ bircok versiyon denedigi icin onun yayinlanmis
grafiklerini kullaniriz (kendi SAC'imizi tekrar egitmeye gerek yok).

Cikti: ../sunum/grafikler/KIYAS_*.png
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

GR = Path(__file__).resolve().parent.parent / "sunum" / "grafikler"
AKIF = GR / "akif_sac"
PPO_LBL = "PPO — bu çalışma (Berker, 220202046)"
SAC_LBL = "SAC — M. A. Albayrak (220202082)"

# (cikti, baslik, bizim_png, akif_png)
PAIRS = [
    ("KIYAS_1_ogrenme.png", "Öğrenme Eğrisi (episode getirisi)",
     "1_ogrenme_egrisi.png", "sac_ogrenme_seed123.png"),
    ("KIYAS_2_loss.png", "Loss Eğrisi (actor & critic)",
     "3_loss_egrisi.png", "sac_loss_seed123.png"),
    ("KIYAS_3_perseed.png", "Tohum 123 Detay Paneli (getiri / eval / kapsama / oda)",
     "per_seed_123.png", "sac_perseed_seed123.png"),
    ("KIYAS_4_hiperparametre.png", "Hiperparametre Duyarlılığı",
     "4_hiperparametre_duyarlilik.png", "sac_hiperparametre.png"),
    ("KIYAS_5_baseline.png", "Baseline Karşılaştırma (görev metrikleri)",
     "5b_baseline_4metrik.png", "sac_baseline_4metrik.png"),
    ("KIYAS_6_heatmap.png", "γ × learning_rate Hiperparametre Arama",
     "10_gamma_lr_heatmap.png", "sac_gamma_lr_heatmap.png"),
]


def build(out_name, title, ppo_png, sac_png):
    pp, sp = GR / ppo_png, AKIF / sac_png
    if not (pp.exists() and sp.exists()):
        print(f"[kiyas] ATLA {out_name} (eksik: {pp.exists()=} {sp.exists()=})")
        return
    li, ri = mpimg.imread(str(pp)), mpimg.imread(str(sp))
    la = li.shape[1] / li.shape[0]      # en/boy oran
    ra = ri.shape[1] / ri.shape[0]
    H = 5.2
    fig, axes = plt.subplots(1, 2, figsize=((la + ra) * H * 0.5 + 0.6, H + 0.7),
                             gridspec_kw={"width_ratios": [la, ra]})
    for ax, img, lbl, color in ((axes[0], li, PPO_LBL, "#1565c0"),
                                (axes[1], ri, SAC_LBL, "#e65100")):
        ax.imshow(img)
        ax.set_title(lbl, fontsize=11, fontweight="bold", color=color, pad=6)
        ax.axis("off")
    fig.suptitle(f"PPO ↔ SAC  —  {title}", fontsize=13, fontweight="bold", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(str(GR / out_name), dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"[kiyas] {out_name}")


if __name__ == "__main__":
    plt.rcParams["font.family"] = "DejaVu Sans"
    for args in PAIRS:
        build(*args)
