# grafikler/

5 zorunlu grafik (PNG) buraya `plot_results.py` tarafindan uretilir:

1. `1_ogrenme_egrisi.png` — egitim episode getirisi (mean +/- std, >=5 seed)
2. `2_eval_egrisi.png` — deterministik/greedy eval getirisi
3. `3_loss_egrisi.png` — actor & critic loss
4. `4_hiperparametre_duyarlilik.png` — 2 param x 3 deger (`sweep.sh` gerekir)
5. `5_baseline_karsilastirma.png` — random/heuristic vs ajan

Her grafigin altina rapora 4 cumlelik yorum eklenecek:
**Gozlem -> Karsilastirma -> Aciklama -> Sonuc.**

Uretmek icin: `cd ../../kod && bash run_all.sh` (ve Grafik 4 icin `bash sweep.sh`).
