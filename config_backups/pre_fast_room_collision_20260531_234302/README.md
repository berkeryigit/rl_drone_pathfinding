Backup taken before the fast room-exploration / immediate-collision-stop changes.

Restore these files if you want to return to that exact state:

- configs/sac.yaml
- ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/envs/drone_exploration_env.py
- ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/train_sac.py
- ros2_ws/src/rl_drone_pathfinding/rl_drone_pathfinding/agents/eval_sac.py
- ros2_ws/src/rl_drone_pathfinding/worlds/multi_room.sdf

Example restore commands from repo root:

```powershell
Copy-Item config_backups\pre_fast_room_collision_20260531_234302\sac.yaml configs\sac.yaml
Copy-Item config_backups\pre_fast_room_collision_20260531_234302\drone_exploration_env.py ros2_ws\src\rl_drone_pathfinding\rl_drone_pathfinding\envs\drone_exploration_env.py
Copy-Item config_backups\pre_fast_room_collision_20260531_234302\train_sac.py ros2_ws\src\rl_drone_pathfinding\rl_drone_pathfinding\agents\train_sac.py
Copy-Item config_backups\pre_fast_room_collision_20260531_234302\eval_sac.py ros2_ws\src\rl_drone_pathfinding\rl_drone_pathfinding\agents\eval_sac.py
Copy-Item config_backups\pre_fast_room_collision_20260531_234302\multi_room.sdf ros2_ws\src\rl_drone_pathfinding\worlds\multi_room.sdf
```
