#!/usr/bin/env python3
"""
Plots training metrics (Episode Rewards and Episode Lengths) 
from the Stable-Baselines3 Monitor CSV log.
"""
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
from stable_baselines3.common import results_plotter

def plot_results(log_folder, title="DQN Drone Training Metrics"):
    # Monitor logs are typically saved as `monitor.csv`
    log_file = os.path.join(log_folder, "monitor.csv")
    if not os.path.exists(log_file):
        print(f"Error: {log_file} not found.")
        print("Make sure you have started training and it has completed at least one episode.")
        return

    # Use SB3's built in plotter for rewards over time
    results_plotter.plot_results([log_folder], 300000, results_plotter.X_TIMESTEPS, title)
    plt.savefig(os.path.join(log_folder, "episode_rewards.png"))
    plt.close()
    
    # Read the raw CSV for custom plots (e.g., episode lengths or moving averages)
    # The monitor.csv has a header row with metadata, actual columns start at row 2
    # columns: r (reward), l (length), t (time)
    df = pd.read_csv(log_file, skiprows=1)
    
    # Plot moving average of rewards
    plt.figure(figsize=(10, 5))
    rolling_mean_rew = df['r'].rolling(window=50).mean()
    plt.plot(df.index, df['r'], alpha=0.3, label="Episode Reward")
    plt.plot(df.index, rolling_mean_rew, color="red", label="Moving Average (50 eps)")
    plt.title("Episode Rewards vs Episodes")
    plt.xlabel("Episode")
    plt.ylabel("Reward")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(log_folder, "episode_rewards_ma.png"))
    plt.close()

    # Plot Episode Lengths
    plt.figure(figsize=(10, 5))
    rolling_mean_len = df['l'].rolling(window=50).mean()
    plt.plot(df.index, df['l'], alpha=0.3, label="Episode Length (Steps)")
    plt.plot(df.index, rolling_mean_len, color="green", label="Moving Average (50 eps)")
    plt.title("Episode Length vs Episodes")
    plt.xlabel("Episode")
    plt.ylabel("Steps")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(log_folder, "episode_lengths_ma.png"))
    plt.close()

    # Plot Explored Voxels
    if 'explored_voxels' in df.columns:
        plt.figure(figsize=(10, 5))
        rolling_mean_exp = df['explored_voxels'].rolling(window=50).mean()
        plt.plot(df.index, df['explored_voxels'], alpha=0.3, label="Explored Voxels")
        plt.plot(df.index, rolling_mean_exp, color="purple", label="Moving Average (50 eps)")
        plt.title("Explored Voxels vs Episodes")
        plt.xlabel("Episode")
        plt.ylabel("Voxels Count")
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(log_folder, "explored_voxels_ma.png"))
        plt.close()
        print(f"  - explored_voxels_ma.png")

    # Plot Visited Rooms
    if 'visited_rooms' in df.columns:
        plt.figure(figsize=(10, 5))
        rolling_mean_rooms = df['visited_rooms'].rolling(window=50).mean()
        plt.plot(df.index, df['visited_rooms'], alpha=0.3, label="Visited Rooms")
        plt.plot(df.index, rolling_mean_rooms, color="orange", label="Moving Average (50 eps)")
        plt.title("Visited Rooms vs Episodes")
        plt.xlabel("Episode")
        plt.ylabel("Rooms Count")
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(log_folder, "visited_rooms_ma.png"))
        plt.close()
        print(f"  - visited_rooms_ma.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", type=str, default="./runs/dqn_obstacles",
                        help="Path to the training log directory containing monitor.csv")
    args = parser.parse_args()
    
    plot_results(args.log_dir)
