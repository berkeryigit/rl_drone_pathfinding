from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "rl_drone_pathfinding"))

from rl_drone_pathfinding.agents.train_sac_fast_2d import main


if __name__ == "__main__":
    main()
