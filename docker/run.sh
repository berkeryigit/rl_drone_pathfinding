#!/usr/bin/env bash
# Bring the container up (with X11 access) and drop into a shell.
set -euo pipefail
cd "$(dirname "$0")/.."
xhost +local:docker >/dev/null 2>&1 || true
UID_=$(id -u) GID_=$(id -g) DISPLAY="${DISPLAY:-:0}" \
  docker compose -f docker/docker-compose.yml up -d
docker exec -it rl_drone bash
