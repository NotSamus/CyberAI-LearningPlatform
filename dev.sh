#!/usr/bin/env bash
# Starts everything: Postgres, JupyterHub and the grader (Docker), backend (:8003) and frontend (:3000),
# and applies database migrations. Ctrl+C (or closing the terminal) stops all of it, including
# every student notebook container. Database contents and student files are kept.
# The backend moves to the next free port when 8003 is taken (BACKEND_PORT=... picks where it starts).
# When 3000 is taken by another project:  FRONTEND_PORT=3001 ./dev.sh
#
# ./dev.sh --lan   lets other devices on the same network (Wi-Fi) open the site, at
#                  http://<this computer's address>:3000. For trying it out with people you trust:
#                  it is plain http, so passwords cross the network unencrypted. See README.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/api"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT="${BACKEND_PORT:-8003}"     # not 8000: other projects on the same computer often have it
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

lan_address() {
  if command -v ipconfig >/dev/null 2>&1; then    # macOS: Wi-Fi or Ethernet (en0, en1, ...), not a VPN tunnel
    for interface in en0 en1 en2 en3 en4 en5; do
      ipconfig getifaddr "$interface" 2>/dev/null && return
    done
  else
    hostname -I 2>/dev/null | awk '{print $1}'
  fi
}

# The name browsers use for this computer: localhost, or with --lan its address on the network
# (DEV_HOST=... overrides the address that was found).
if [ "${1:-}" = "--lan" ]; then
  DEV_HOST="${DEV_HOST:-$(lan_address)}"
  if [ -z "$DEV_HOST" ]; then
    echo "Could not find this computer's network address. Pass it:  DEV_HOST=192.168.x.x ./dev.sh --lan" >&2
    exit 1
  fi
  # Others can now reach the hub and the backend, so the secrets written in this repository will
  # not do: make new ones for this run (the hub container picks them up when it starts).
  export HUB_API_TOKEN="$(openssl rand -hex 32)"
  export OAUTH_CLIENT_SECRET="$(openssl rand -hex 32)"
  export GRADER_TOKEN="$(openssl rand -hex 32)"
fi
export DEV_HOST="${DEV_HOST:-localhost}"                                   # frontend (next.config.ts)

port_in_use() {
  # Only a listening server counts; Docker Desktop keeps closed client sockets to these ports around.
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null   # no lsof (some Linux servers): does anything answer?
  fi
}

# The backend takes the first free port from BACKEND_PORT up. Decided before the exports below, so
# the frontend and the hub are told the port it really runs on.
REQUESTED_BACKEND_PORT="$BACKEND_PORT"
while port_in_use "$BACKEND_PORT"; do
  BACKEND_PORT=$((BACKEND_PORT + 1))
done

# The backend, the frontend and the hub each need to know where the others are.
export APP_ORIGIN="http://$DEV_HOST:$FRONTEND_PORT"                        # backend, hub
export HUB_ORIGIN="http://$DEV_HOST:8081"                                  # backend, hub
export NEXT_PUBLIC_HUB_ORIGIN="$HUB_ORIGIN"                                # frontend
export BACKEND_URL="http://localhost:$BACKEND_PORT"                        # frontend (next.config.ts)
export PLATFORM_INTERNAL_URL="http://host.docker.internal:$BACKEND_PORT"   # hub -> backend

compose_dev() {
  docker compose -f "$ROOT_DIR/deploy/docker-compose.dev.yml" "$@"
}

cleanup() {
  trap - INT TERM HUP EXIT
  echo ""
  echo "==> Shutting down..."
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  if [ -n "${DOCKER_RUNNING:-}" ]; then
    echo "   Stopping JupyterHub, all notebook containers and Postgres (data and student files are kept)..."
    compose_dev down || true
  fi
}
trap cleanup INT TERM HUP EXIT

echo "==> Starting cyberAI-Platform dev servers..."

if docker info >/dev/null 2>&1; then
  DOCKER_RUNNING=1
  if compose_dev up -d --wait db; then
    echo "   Postgres -> localhost:5433  (applying migrations)"
    (cd "$ROOT_DIR/sql" && alembic upgrade head) || echo "   Migrations failed - see the error above."
  else
    echo "   Postgres failed to start - continuing without a database."
  fi
  if ! "$ROOT_DIR/dev-hub.sh"; then
    echo "   JupyterHub failed to start - continuing without it."
  fi
  if compose_dev up -d --build grader; then
    echo "   Grader   -> localhost:8090  (autograding with Otter)"
  else
    echo "   The grader failed to start - continuing without autograding."
  fi
else
  echo "   Docker is not running - skipping Postgres and JupyterHub (no database; Open Notebook will report it unreachable)."
fi

(cd "$BACKEND_DIR" && uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT) &
BACKEND_PID=$!
if [ "$BACKEND_PORT" != "$REQUESTED_BACKEND_PORT" ]; then
  echo "   Backend  -> http://localhost:$BACKEND_PORT  (docs at /docs; $REQUESTED_BACKEND_PORT was taken)"
else
  echo "   Backend  -> http://localhost:$BACKEND_PORT  (docs at /docs)"
fi

if port_in_use $FRONTEND_PORT; then
  echo "   Frontend port $FRONTEND_PORT already in use - skipping next."
else
  (cd "$FRONTEND_DIR" && npx next dev -p "$FRONTEND_PORT") &
  FRONTEND_PID=$!
  echo "   Frontend -> $APP_ORIGIN"
fi
if [ "$DEV_HOST" != localhost ]; then
  echo ""
  echo "==> Open $APP_ORIGIN on this computer and on other devices on this network."
  echo "    (Not http://localhost:$FRONTEND_PORT: logging in only works at the address above.)"
fi

wait
