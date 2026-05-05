#!/usr/bin/env bash
# Build the docker image. Pass UID/GID so the in-container user matches the host.
set -euo pipefail
cd "$(dirname "$0")/.."
UID_=$(id -u) GID_=$(id -g) docker compose -f docker/docker-compose.yml build \
  --build-arg USER_UID="$(id -u)" --build-arg USER_GID="$(id -g)"
