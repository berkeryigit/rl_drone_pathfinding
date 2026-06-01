import os
import argparse
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing import event_accumulator

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-dir', required=True, help="TensorBoard klasorunun yolu (DQN_1 vb. iceren)")
    args = parser.parse_args()
    
    tb_dir = args.log_dir
    if not os.path.isdir(tb_dir):
        print(f"Klasor bulunamadi: {tb_dir}")
        return
        
    print(f"{tb_dir} klasorundeki loglar okunuyor...")
    ea = event_accumulator.EventAccumulator(tb_dir, size_guidance={event_accumulator.SCALARS: 0})
    ea.Reload()
    
    tags = ea.Tags().get('scalars', [])
    
    if not tags:
        print("Grafik (scalar) verisi bulunamadi!")
        return
        
    print(f"Bulunan metrikler: {tags}")
    
    for tag in tags:
        if "mean" not in tag and "loss" not in tag:
            continue
            
        filename = tag.split('/')[-1] + '_v1.png'
        save_path = os.path.join(tb_dir, filename)
        
        events = ea.Scalars(tag)
        steps = [e.step for e in events]
        values = [e.value for e in events]
        
        plt.figure(figsize=(8, 5))
        plt.plot(steps, values, color='blue', linewidth=2)
        plt.xlabel('Timesteps (Eğitim Adımları)', fontsize=12)
        plt.ylabel(tag.split('/')[-1], fontsize=12)
        plt.title(f"{tag.split('/')[-1]} - v1 Model", fontsize=14, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close()
        print(f"Grafik kaydedildi: {save_path}")

if __name__ == '__main__':
    main()
