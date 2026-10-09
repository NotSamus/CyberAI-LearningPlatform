#!/usr/bin/env bash
# Full reset of one student's environment. Their files are archived first, never just deleted.
# Usage: ./reset-student.sh s-1042        (run on the server, from deploy/, with .env present)
set -euo pipefail
USERNAME="$1"
source .env
VOL="jupyterhub-user-${USERNAME}"
BACKUP_DIR="/srv/backups/student-homes"

for server in cpu gpu; do
  docker compose exec -T jupyterhub python3 - "$USERNAME" "$server" "$PLATFORM_HUB_API_TOKEN" <<'PY' || true
import sys, urllib.request, urllib.error
user, server, token = sys.argv[1:4]
req = urllib.request.Request(
    f"http://localhost:8000/hub/api/users/{user}/servers/{server}",
    method="DELETE", headers={"Authorization": f"token {token}"})
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    if e.code not in (400, 404):   # not running / never created
        raise
PY
done
sleep 5

if docker volume inspect "$VOL" >/dev/null 2>&1; then
  sudo mkdir -p "$BACKUP_DIR"
  docker run --rm -v "$VOL":/home:ro -v "$BACKUP_DIR":/backup alpine \
    tar czf "/backup/${USERNAME}-$(date +%Y%m%d-%H%M%S).tgz" -C /home .
  docker volume rm "$VOL"
fi
echo "Reset done. ${USERNAME} gets a fresh home (with starter files) at next launch."
