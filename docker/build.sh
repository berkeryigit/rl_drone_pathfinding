#!/usr/bin/env bash
# Build the docker image. Pass UID/GID so the in-container user matches the host.
set -euo pipefail
cd "$(dirname "$0")/.."
REAL_USER=${SUDO_USER:-$USER}
USER_UID=$(id -u $REAL_USER)
USER_GID=$(id -g $REAL_USER)
UID_=$USER_UID GID_=$USER_GID docker compose -f docker/docker-compose.yml build \
  --build-arg USER_UID="$USER_UID" --build-arg USER_GID="$USER_GID"
