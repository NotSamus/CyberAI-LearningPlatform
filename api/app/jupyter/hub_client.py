"""Thin async client for the JupyterHub REST API, authenticated as the `platform` service.

`has_file`, `get_file` and `put_file` go one step further: through the hub's proxy to one user's running
notebook server (Jupyter's contents API), which the `access:servers` scope in
deploy/jupyterhub/jupyterhub_config.py allows.
"""
import asyncio
import base64
from urllib.parse import quote

import httpx

from .. import config

HUB_API_URL = config.HUB_API_URL
HUB_API_TOKEN = config.HUB_API_TOKEN
PIECE_BYTES = 3 * 1024 * 1024       # a multiple of 3: each piece is then complete base64 on its own


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=HUB_API_URL,
        headers={"Authorization": f"token {HUB_API_TOKEN}"},
        timeout=30,
    )


async def ensure_user(username: str, groups: list[str]) -> None:
    """Create the hub user if missing and make hub groups match the platform (no re-login needed)."""
    async with _client() as hub:
        r = await hub.post(f"/users/{username}")
        if r.status_code not in (201, 409):           # 409 = already exists
            r.raise_for_status()
        current = set((await hub.get(f"/users/{username}")).json().get("groups", []))
        for g in set(groups) - current:
            await hub.post(f"/groups/{g}")            # 409 if it exists: fine
            (await hub.post(f"/groups/{g}/users", json={"users": [username]})).raise_for_status()
        for g in current - set(groups):
            await hub.request("DELETE", f"/groups/{g}/users", json={"users": [username]})


async def start_server(username: str, server: str, wait_seconds: int = 90) -> bool:
    """Start the named server ("cpu" or "gpu"). Returns True once it is ready."""
    async with _client() as hub:
        r = await hub.post(f"/users/{username}/servers/{server}", json={})
        if r.status_code == 400 and "already running" in r.text:
            return True
        if r.status_code not in (201, 202):
            # pre_spawn_hook refusals (no GPU entitlement, all GPU slots busy) land here
            detail = r.json().get("message", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
            raise HubError(r.status_code, detail)
        for _ in range(wait_seconds):
            info = (await hub.get(f"/users/{username}")).json()
            srv = info.get("servers", {}).get(server)
            if srv and srv.get("ready"):
                return True
            if not srv:                                # spawn failed and was cleaned up
                raise HubError(500, "The notebook server failed to start.")
            await asyncio.sleep(1)
    return False


async def stop_server(username: str, server: str) -> None:
    async with _client() as hub:
        r = await hub.delete(f"/users/{username}/servers/{server}")
        if r.status_code not in (202, 204, 400, 404):
            r.raise_for_status()


async def delete_user(username: str) -> None:
    """Stops the user's servers and removes them from the hub, which also ends their hub login.
    Their files (the home volume) are not touched."""
    async with _client() as hub:
        info = await hub.get(f"/users/{username}")
        if info.status_code == 404:                    # never opened a notebook
            return
        info.raise_for_status()
        for server in info.json().get("servers", {}):
            r = await hub.delete(f"/users/{username}/servers/{server}")
            if r.status_code not in (202, 204, 400, 404):
                r.raise_for_status()
        for _ in range(30):                            # a stopping server takes a few seconds
            r = await hub.delete(f"/users/{username}")
            if r.status_code != 400:
                break
            await asyncio.sleep(1)
        if r.status_code != 404:
            r.raise_for_status()


def _contents_url(username: str, server: str, path: str) -> str:
    hub_url = HUB_API_URL.rstrip("/").removesuffix("/hub/api")
    return f"{hub_url}/user/{username}/{server}/api/contents/{quote(path)}"


async def has_file(username: str, server: str, path: str) -> bool:
    """Whether `path` (relative to the user's home) exists. The server must be running."""
    async with _client() as hub:
        r = await hub.get(_contents_url(username, server, path), params={"content": "0"})
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


async def get_file(username: str, server: str, path: str, max_bytes: int) -> bytes | None:
    """The file as it is saved in the user's home right now, or None when it is not there.
    Raises FileTooLarge instead of reading a file bigger than `max_bytes`."""
    async with _client() as hub:
        about = await hub.get(_contents_url(username, server, path), params={"content": "0"})
        if about.status_code == 404:
            return None
        about.raise_for_status()
        if (about.json().get("size") or 0) > max_bytes:
            raise FileTooLarge(path)
        r = await hub.get(_contents_url(username, server, path), params={"type": "file", "format": "base64", "content": "1"}, timeout=120)
        r.raise_for_status()
    return base64.b64decode(r.json()["content"])


async def put_file(username: str, server: str, path: str, content: bytes) -> None:
    """Writes a file into the user's home, creating its folders. Replaces a file already there, so
    callers that must not overwrite a student's work check `has_file` first.

    A large file goes in pieces (Jupyter's own way of uploading large files: "chunk" 1, 2, ... and
    -1 for the last), so neither side has to handle a large notebook as one request."""
    folders = path.split("/")[:-1]
    pieces = [content[start:start + PIECE_BYTES] for start in range(0, len(content), PIECE_BYTES)] or [b""]
    async with _client() as hub:
        for depth in range(1, len(folders) + 1):
            r = await hub.put(_contents_url(username, server, "/".join(folders[:depth])), json={"type": "directory"})
            r.raise_for_status()
        for number, piece in enumerate(pieces, start=1):
            model = {"type": "file", "format": "base64", "content": base64.b64encode(piece).decode()}
            if len(pieces) > 1:
                model["chunk"] = -1 if number == len(pieces) else number
            r = await hub.put(_contents_url(username, server, path), json=model, timeout=120)
            r.raise_for_status()


async def list_active_servers() -> list[dict]:
    """For a teacher dashboard: who is running what, since when."""
    async with _client() as hub:
        users = (await hub.get("/users", params={"state": "active"})).json()
    return [
        {"username": u["name"], "server": name, "started": s.get("started"), "last_activity": s.get("last_activity")}
        for u in users
        for name, s in u.get("servers", {}).items()
    ]


class HubError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class FileTooLarge(Exception):
    pass
