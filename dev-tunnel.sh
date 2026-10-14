#!/usr/bin/env bash
# Runs the site on a server whose firewall only lets SSH through, and shares it on this computer's
# network: starts ./dev.sh --lan on the server and forwards the site (:3000) and JupyterHub (:8081)
# through SSH, so people on the same Wi-Fi open http://<this computer's address>:3000.
#
#   ./dev-tunnel.sh iqsec.cs.utep.edu     the server as named in ~/.ssh/config (or user@host)
#
# Ctrl+C stops the tunnel and dev.sh on the server, containers included. This computer has to stay
# on, awake and connected the whole time, and its address changes with the network: run this again
# after moving. Same warnings as ./dev.sh --lan (plain http, test accounts only; see README.md).
# Can be set: REMOTE_DIR (the project on the server, from the home folder; default
# CyberAI-LearningPlatform), CONDA_ENV (default CyberP), FRONTEND_PORT (default 3000), DEV_HOST.
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: ./dev-tunnel.sh <server>     for example:  ./dev-tunnel.sh iqsec.cs.utep.edu" >&2
  exit 1
fi
SERVER="$1"
REMOTE_DIR="${REMOTE_DIR:-CyberAI-LearningPlatform}"
CONDA_ENV="${CONDA_ENV:-CyberP}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
HUB_PORT=8081                       # fixed in dev.sh and deploy/docker-compose.dev.yml

lan_address() {
  if command -v ipconfig >/dev/null 2>&1; then    # macOS: Wi-Fi or Ethernet (en0, en1, ...), not a VPN tunnel
    for interface in en0 en1 en2 en3 en4 en5; do
      ipconfig getifaddr "$interface" 2>/dev/null && return
    done
  else
    hostname -I 2>/dev/null | awk '{print $1}'
  fi
}

port_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
  fi
}

# The address people type. dev.sh on the server is started with it, or every login is refused.
DEV_HOST="${DEV_HOST:-$(lan_address)}"
if [ -z "$DEV_HOST" ]; then
  echo "Could not find this computer's network address. Pass it:  DEV_HOST=192.168.x.x ./dev-tunnel.sh $SERVER" >&2
  exit 1
fi

# Checked before ssh asks for a password: the tunnel listens on these ports here.
for port in "$FRONTEND_PORT" "$HUB_PORT"; do
  if port_in_use "$port"; then
    echo "Port $port is in use on this computer (a local ./dev.sh?). Stop it first: the tunnel needs it." >&2
    exit 1
  fi
done

# On the server: stop if a site already runs on the port (it would keep its old address and refuse
# every login), then start dev.sh. In an interactive shell, because conda is set up in .bashrc or
# .zshrc; with exec, so Ctrl+C and a dropped connection reach dev.sh, which then stops its containers.
START="cd $REMOTE_DIR && conda activate $CONDA_ENV && exec env DEV_HOST=$DEV_HOST FRONTEND_PORT=$FRONTEND_PORT ./dev.sh --lan"
REMOTE="if curl -s -o /dev/null -m 3 http://localhost:$FRONTEND_PORT; then echo 'Port $FRONTEND_PORT is already in use on $SERVER. Stop the ./dev.sh running there (Ctrl+C), then run this again.'; exit 1; fi; exec \"\$SHELL\" -ic '$START'"

echo "==> Starting the site on $SERVER, shared at http://$DEV_HOST:$FRONTEND_PORT"
echo "    Open that address on every computer, this one too (not localhost). Ctrl+C stops everything."
ssh -t \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -L "0.0.0.0:$FRONTEND_PORT:localhost:$FRONTEND_PORT" \
  -L "0.0.0.0:$HUB_PORT:localhost:$HUB_PORT" \
  "$SERVER" "$REMOTE"
