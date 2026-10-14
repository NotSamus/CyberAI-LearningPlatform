"""JupyterHub config: OAuth login against the platform, DockerSpawner,
CPU and GPU profiles selected by named server ("cpu" / "gpu").

All site-specific values come from environment variables (see deploy/.env.example).
"""
import os
import sqlite3
import sys

import docker
from jupyterhub.app import JupyterHub

c = get_config()  # noqa: F821

APP_ORIGIN = os.environ["APP_ORIGIN"]            # https://app.school.example
HUB_ORIGIN = os.environ["HUB_ORIGIN"]            # https://hub.school.example
PLATFORM_INTERNAL = os.environ.get("PLATFORM_INTERNAL_URL", "http://backend:8000")

# --------------------------------------------------------------------------
# Hub basics
# --------------------------------------------------------------------------
c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "jupyterhub"        # compose service name
c.JupyterHub.db_url = "sqlite:////data/jupyterhub.sqlite"
c.JupyterHub.cookie_secret_file = "/data/jupyterhub_cookie_secret"
# Production keeps students' servers running across hub restarts. Local dev sets CLEANUP_SERVERS=1
# (docker-compose.dev.yml) so stopping the hub also stops every notebook container.
# Student files survive either way: they live in the jupyterhub-user-* volumes.
c.JupyterHub.cleanup_servers = os.environ.get("CLEANUP_SERVERS", "") == "1"

# One named server per profile. Both mount the same home volume.
c.JupyterHub.allow_named_servers = True
c.JupyterHub.named_server_limit_per_user = 2

# --------------------------------------------------------------------------
# Authentication: the platform is the OAuth2 provider
# --------------------------------------------------------------------------
c.JupyterHub.authenticator_class = "generic-oauth"
c.GenericOAuthenticator.login_service = "cyberAI Platform"
c.GenericOAuthenticator.client_id = os.environ["OAUTH_CLIENT_ID"]
c.GenericOAuthenticator.client_secret = os.environ["OAUTH_CLIENT_SECRET"]
c.GenericOAuthenticator.oauth_callback_url = f"{HUB_ORIGIN}/hub/oauth_callback"

# Browser-facing URL (student's browser is redirected here)
c.GenericOAuthenticator.authorize_url = f"{APP_ORIGIN}/oauth/authorize"
# Server-to-server URLs (hub container -> backend container, stays inside Docker)
c.GenericOAuthenticator.token_url = f"{PLATFORM_INTERNAL}/oauth/token"
c.GenericOAuthenticator.userdata_url = f"{PLATFORM_INTERNAL}/oauth/userinfo"

c.GenericOAuthenticator.scope = ["openid", "profile"]
c.GenericOAuthenticator.username_claim = "username"   # e.g. "s-1042": stable, lowercase, no email

# Hub groups (students / teachers / gpu) are set by the platform backend through the REST API
# before every launch (api/app/jupyter/hub_client.py: ensure_user), so GPU entitlement is right
# even before a student's first hub login. manage_groups must stay off: when it is on, JupyterHub
# rejects all group changes made through the API. (allowed_groups / admin_groups need it on.)
c.GenericOAuthenticator.manage_groups = False
# The platform is the only identity provider and only signs in its own students and teachers.
c.GenericOAuthenticator.allow_all = True


def _hub_admins(authenticator, handler, authentication):
    """Hub admins are teachers, and platform admins (the `admin` claim from /oauth/userinfo), who see
    the hub's admin panel inside the platform's Settings page. Decided at hub login: a change on the
    platform reaches the hub the next time that person's hub session starts."""
    oauth_user = authentication.get("auth_state", {}).get("oauth_user", {})
    authentication["admin"] = "teachers" in oauth_user.get("groups", []) or oauth_user.get("admin") is True
    return authentication


c.Authenticator.post_auth_hook = _hub_admins

c.Authenticator.auto_login = True          # skip the hub's own login page -> seamless
c.Authenticator.enable_auth_state = True   # needs JUPYTERHUB_CRYPT_KEY in the environment
# No re-checks of the user's platform OAuth token after login. Platform access tokens live 5 minutes
# and have no refresh token, so a re-check can only fail: before a spawn it would refuse every
# launch (servers are started by the platform backend, which has already checked the user), and
# the periodic one would log students out of their running notebooks every few minutes.
# Revoking access is done from the platform side (stop the user's servers through the hub API).
c.GenericOAuthenticator.refresh_pre_spawn = False
c.GenericOAuthenticator.auth_refresh_age = 0

# --------------------------------------------------------------------------
# iframe embedding: only the platform origin may frame the hub
# --------------------------------------------------------------------------
CSP = f"frame-ancestors 'self' {APP_ORIGIN}"
c.JupyterHub.tornado_settings = {
    "headers": {"Content-Security-Policy": CSP},
}
# The single-user servers set the same header from FRAME_ANCESTORS
# (see deploy/images/common/jupyter_server_config.py).

# --------------------------------------------------------------------------
# Spawner
# --------------------------------------------------------------------------
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.network_name = os.environ.get("DOCKER_NETWORK_NAME", "jupyter-users")
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True                 # container is disposable; the home volume is not
c.DockerSpawner.name_template = "jupyter-{username}--{servername}"
c.DockerSpawner.notebook_dir = "/home/jovyan"
c.DockerSpawner.default_url = "/lab"
c.DockerSpawner.volumes = {
    # No {servername}: the CPU and GPU servers share one home directory.
    # Assignment notebooks are not mounted: the platform backend puts each one into the home of
    # the students it was given to, when they open it (api/app/jupyter/launch.py).
    "jupyterhub-user-{username}": "/home/jovyan",
}
c.Spawner.start_timeout = 120
c.Spawner.http_timeout = 60
# Notebook servers ignore Jupyter config files in the student's home (~/.jupyter), so a student
# cannot change how their server is set up that way. Only an extra layer: Python packages the
# student installs in their home (~/.local) still load, and anything a student runs can see what
# reaches their server. What keeps the hub safe is that the platform never sends its service token
# to a notebook server (api/app/jupyter/hub_client.py).
c.Spawner.disable_user_config = True

# Local development on a machine without an NVIDIA GPU: the "gpu" profile still exists and keeps
# its entitlement and slot checks, but no device is attached to the container.
FAKE_GPU = os.environ.get("DEV_FAKE_GPU", "") == "1"

GPU_IDS = [g for g in os.environ.get("GPU_IDS", "0").split(",") if g]
MAX_SESSIONS_PER_GPU = int(os.environ.get("MAX_SESSIONS_PER_GPU", "4"))

PROFILES = {
    "cpu": {
        "image": os.environ.get("CPU_IMAGE", "cyberai/notebook-cpu:latest"),
        "cpu_limit": 1.0,
        "mem_limit": "2G",
        "gpu": False,
    },
    "gpu": {
        "image": os.environ.get("GPU_IMAGE", "cyberai/notebook-gpu:latest"),
        "cpu_limit": 4.0,
        "mem_limit": os.environ.get("GPU_PROFILE_MEM", "12G"),
        "gpu": True,
    },
}

BASE_HOST_CONFIG = {
    "pids_limit": 512,                          # fork-bomb protection
    "security_opt": ["no-new-privileges"],
    "cap_drop": ["ALL"],
}


def _active_gpu_spawners(exclude):
    hub = JupyterHub.instance()
    return [
        s
        for u in hub.users.values()
        for s in u.spawners.values()
        if s.name == "gpu" and s.active and s is not exclude
    ]


def pre_spawn_hook(spawner):
    """Apply the profile named by the server name; enforce GPU entitlement and capacity."""
    profile_name = spawner.name or "cpu"
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown server name {profile_name!r}; expected one of {sorted(PROFILES)}")
    profile = PROFILES[profile_name]

    spawner.image = profile["image"]
    spawner.cpu_limit = profile["cpu_limit"]
    spawner.mem_limit = profile["mem_limit"]
    host_config = dict(BASE_HOST_CONFIG)
    spawner.environment = {
        "FRAME_ANCESTORS": f"'self' {APP_ORIGIN}",
        "GPU_MEM_FRACTION": str(round(1 / MAX_SESSIONS_PER_GPU, 3)),
    }

    if profile["gpu"]:
        # 1. Entitlement: group membership is controlled by the platform
        groups = {g.name for g in spawner.user.groups}
        if not ({"gpu", "teachers"} & groups):
            raise PermissionError("This account is not enabled for GPU assignments.")

        # 2. Capacity: pick the least-loaded GPU, refuse when all are full
        load = {gid: 0 for gid in GPU_IDS}
        for s in _active_gpu_spawners(exclude=spawner):
            gid = getattr(s, "gpu_id", None)
            if gid in load:
                load[gid] += 1
        gid = min(load, key=load.get)
        if load[gid] >= MAX_SESSIONS_PER_GPU:
            raise RuntimeError("All GPU slots are in use. Try again in a few minutes.")
        spawner.gpu_id = gid

        # Equivalent of `docker run --gpus device=<gid>`.
        # Alternative if you prefer the runtime flag:
        #   host_config["runtime"] = "nvidia"
        #   spawner.environment["NVIDIA_VISIBLE_DEVICES"] = gid
        if not FAKE_GPU:
            host_config["device_requests"] = [
                docker.types.DeviceRequest(device_ids=[gid], capabilities=[["gpu"]])
            ]
        host_config["shm_size"] = "2g"          # PyTorch DataLoader workers need /dev/shm

    spawner.extra_host_config = host_config


c.Spawner.pre_spawn_hook = pre_spawn_hook

# --------------------------------------------------------------------------
# Services and API roles
# --------------------------------------------------------------------------
def _forget_stored_service_tokens(path="/data/jupyterhub.sqlite"):
    """JupyterHub keeps every API token a service was ever given: a new PLATFORM_HUB_API_TOKEN is
    added next to the old one, and the old one goes on working. So, before the hub opens its
    database, the stored service tokens are removed; the hub adds the current ones (below) again as
    it starts. Tokens of users and of their running notebook servers are not touched."""
    if not os.path.exists(path):        # very first start: no database yet
        return
    with sqlite3.connect(path) as db:
        try:
            db.execute("DELETE FROM api_tokens WHERE service_id IS NOT NULL")
        except sqlite3.OperationalError:
            pass                        # no such table yet


_forget_stored_service_tokens()

c.JupyterHub.services = [
    # The platform backend: starts/stops servers, manages users and groups
    {"name": "platform", "api_token": os.environ["PLATFORM_HUB_API_TOKEN"]},
    # Stops servers idle for 30 min, and any server older than 4 h
    {
        "name": "idle-culler",
        "command": [
            sys.executable, "-m", "jupyterhub_idle_culler",
            "--timeout=1800", "--max-age=14400", "--cull-every=300",
        ],
    },
]
c.JupyterHub.load_roles = [
    {
        "name": "platform-role",
        "services": ["platform"],
        # What the backend (api/app/jupyter/hub_client.py) and deploy/scripts/reset-student.sh need:
        #   admin:users   create, look up and delete hub users
        #   servers       start and stop their notebook servers, and see whether one is ready
        #   admin:groups  keep each user's hub groups (students, teachers, gpu) in step with the platform
        #   list:users    list the hub's users (no call needs it today; admin:users includes it too)
        #   tokens        make, and then delete, a short-lived token of a user's own for one file
        #                 operation on that user's server (has_file, get_file, put_file). The hub only
        #                 gives such a token what its owner may do anyway, so it opens their own server.
        # No access:servers: the service token never goes to a notebook server, where code a student
        # runs could read it.
        "scopes": ["admin:users", "servers", "admin:groups", "list:users", "tokens"],
    },
    {
        "name": "idle-culler-role",
        "services": ["idle-culler"],
        "scopes": ["list:users", "read:users:activity", "read:servers", "delete:servers"],
    },
]
