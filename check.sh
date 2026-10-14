#!/usr/bin/env bash
# Every check, in one go: Python lint (ruff), the backend's tests, then the frontend's type check
# and lint (ESLint). The tests run on a Postgres of their own (deploy/docker-compose.test.yml),
# started here and removed afterwards: they never reach the platform's own database.
#   conda activate CyberP && ./check.sh          (needs Docker running)
#   ./check.sh -k lessons                         extra arguments go to pytest
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python}"
test_db() { docker compose -f "$ROOT_DIR/deploy/docker-compose.test.yml" "$@"; }

echo "==> Python lint (ruff)"
(cd "$ROOT_DIR" && "$PYTHON" -m ruff check api test grader deploy)

echo "==> Backend tests, on the test Postgres (localhost:5434)"
test_db up -d --wait >/dev/null
trap 'test_db down >/dev/null 2>&1 || true' EXIT
(cd "$ROOT_DIR" && "$PYTHON" -m pytest -q test "$@")

echo "==> Frontend type check and lint"
(cd "$ROOT_DIR/frontend" && npx tsc --noEmit && npx eslint .)

echo "==> All checks passed"
