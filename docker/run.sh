#!/usr/bin/env bash
# Bring the container up (with X11 access) and drop into a shell.
set -euo pipefail
cd "$(dirname "$0")/.."
xhost +local:docker >/dev/null 2>&1 || true
REAL_USER=${SUDO_USER:-$USER}
USER_UID=$(id -u $REAL_USER)
USER_GID=$(id -g $REAL_USER)
UID_=$USER_UID GID_=$USER_GID DISPLAY="${DISPLAY:-:0}" \
  docker compose -f docker/docker-compose.yml up -d
docker exec -it rl_drone bash
