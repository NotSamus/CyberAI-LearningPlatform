"""Settings from environment variables, with defaults that work for local development.

Local dev layout:  Next.js :3000  |  uvicorn :8000  |  dev JupyterHub :8081  |  grader :8090  |  dev Postgres :5433  (./dev.sh)
`./dev.sh --lan` sets APP_ORIGIN and HUB_ORIGIN to this computer's network address instead of localhost.
Production values come from deploy/.env via docker-compose.
"""
import os

APP_ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost:3000")
HUB_ORIGIN = os.environ.get("HUB_ORIGIN", "http://localhost:8081")
HUB_API_URL = os.environ.get("HUB_API_URL", "http://localhost:8081/hub/api")
HUB_API_TOKEN = os.environ.get("HUB_API_TOKEN", "dev-hub-api-token")
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "jupyterhub")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "dev-oauth-secret")
# The grading service (grader/), which runs Otter-Grader in throwaway containers.
GRADER_URL = os.environ.get("GRADER_URL", "http://localhost:8090")
GRADER_TOKEN = os.environ.get("GRADER_TOKEN", "dev-grader-token")
# Local dev: the Postgres container from deploy/docker-compose.dev.yml (./dev.sh starts it).
# Production: the URL set in deploy/docker-compose.yml.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://platform:dev-db-password@localhost:5433/platform")

# Whether the site is served over HTTPS (production, behind Caddy). Plain http is local development,
# on this computer or, with `./dev.sh --lan`, for other devices on the same network.
HTTPS = APP_ORIGIN.startswith("https://")
# The defaults above are in the repository, so they are only good enough while nobody else can reach
# the backend and the hub. `./dev.sh --lan` generates random ones for that reason.
if not APP_ORIGIN.startswith("http://localhost") and "dev-" in (HUB_API_TOKEN + OAUTH_CLIENT_SECRET + GRADER_TOKEN):
    raise RuntimeError("Set real HUB_API_TOKEN, OAUTH_CLIENT_SECRET and GRADER_TOKEN when the site is reachable from other computers.")
