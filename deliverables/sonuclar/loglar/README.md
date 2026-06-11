# loglar/

Ham egitim loglari (ZORUNLU). `run_all.sh` sonunda buraya kopyalanir:

- `training_log_seed_<N>.csv` — her seed icin per-episode ham log (grafikler bundan dogrulanir)
- `tb_seed_<N>/` — TensorBoard tfevents kayitlari

Grafikler bu loglardan yeniden uretilebilir:
`cd ../../kod && python plot_results.py`
