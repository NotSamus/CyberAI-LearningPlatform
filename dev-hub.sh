#!/usr/bin/env bash
# Local JupyterHub on http://localhost:8081 (needs Docker Desktop running).
#   ./dev-hub.sh          build the CPU notebook image if missing, then start the hub
#   ./dev-hub.sh down     stop the hub and every student notebook container (files are kept)
# ./dev.sh runs both of these for you, and also starts and stops the dev Postgres.
# GPU assignments open in the CPU image here, so install torch in it if you want to run such a
# notebook locally:  GPU_IMAGE=<an image with torch> ./dev-hub.sh
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/deploy"

if [ "${1:-}" = "down" ]; then
  docker compose -f docker-compose.dev.yml stop jupyterhub
  exit 0
fi

if ! docker image inspect cyberai/notebook-cpu:latest >/dev/null 2>&1; then
  echo "==> Building the student notebook image (first time only, a few minutes)..."
  docker build -f images/cpu/Dockerfile -t cyberai/notebook-cpu:latest images
fi
docker compose -f docker-compose.dev.yml up -d --build jupyterhub
echo "==> JupyterHub: http://localhost:8081   logs: docker compose -f deploy/docker-compose.dev.yml logs -f"
