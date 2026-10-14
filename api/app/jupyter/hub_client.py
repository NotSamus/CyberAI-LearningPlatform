"""Thin async client for the JupyterHub REST API, authenticated as the `platform` service.

`has_file`, `get_file` and `put_file` go one step further: through the hub's proxy to one user's running
notebook server (Jupyter's contents API). They never send the service token there: code a student runs
in their notebook can see what reaches their server, and the service token can manage every user and
every server. Each of these operations gets a token of that user's own instead, which opens only the
one server it needs and is deleted afterwards (`_notebook_server`).
"""
import asyncio
import base64
import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx

from .. import config

HUB_API_URL = config.HUB_API_URL
HUB_API_TOKEN = config.HUB_API_TOKEN
PIECE_BYTES = 3 * 1024 * 1024       # a multiple of 3: each piece is then complete base64 on its own
# How long the token for one file operation lives. It is deleted as soon as the operation is done;
# this is only the backstop when that delete fails. Long enough for a large upload in pieces: the
# notebook server checks a token with the hub once and then remembers the answer for five minutes.
FILE_TOKEN_SECONDS = 120

# Set by the tests (httpx.MockTransport) to stand in for the hub. None: the real network.
_transport: httpx.AsyncBaseTransport | None = None

log = logging.getLogger(__name__)


def _client() -> httpx.AsyncClient:
    """The service's own client, for the hub's REST API (/hub/api/...) only, never for a /user/... URL."""
    return httpx.AsyncClient(
        base_url=HUB_API_URL,
        headers={"Authorization": f"token {HUB_API_TOKEN}"},
        timeout=30,
        transport=_transport,
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


@asynccontextmanager
async def _notebook_server(username: str, server: str):
    """A client for one operation on `username`'s running `server`, through the hub's proxy.

    It carries a token the hub makes for this operation: owned by that user, able to open only this
    one server, expiring after FILE_TOKEN_SECONDS, and deleted when the operation is done. Code the
    student runs on that server may see it; it gives them nothing they do not already have.

    If the hub refuses to make the token, this raises httpx.HTTPStatusError before anything is sent
    to the notebook server; callers turn that into a message (launch.hub_errors)."""
    async with _client() as hub:
        r = await hub.post(f"/users/{username}/tokens", json={
            "scopes": [f"access:servers!server={username}/{server}"],
            "expires_in": FILE_TOKEN_SECONDS,      # never 0 or left out: that would be a token that never expires
            "note": "cyberAI platform: notebook files",
        })
        if not r.is_success:
            # Most likely jupyterhub_config.py is older than this code (the `tokens` scope is missing)
            log.warning("The hub refused to make a token for %s/%s (%s).", username, server, r.status_code)
            r.raise_for_status()
        try:
            made = r.json()
            token, token_id = made["token"], made["id"]
        except (ValueError, KeyError, TypeError):
            raise HubError(502, "The notebook service did not give access to the notebook server.")
        try:
            async with httpx.AsyncClient(
                headers={"Authorization": f"token {token}"}, timeout=30, transport=_transport,
            ) as notebook_server:
                yield notebook_server
        finally:
            # Whatever happened above. Never let a failed clean-up hide what went wrong there: the
            # token expires by itself, and the hub removes expired tokens every hour.
            try:
                gone = await hub.delete(f"/users/{username}/tokens/{token_id}")
                if gone.is_error and gone.status_code != 404:
                    log.warning("Could not delete the file token %s of %s (%s).", token_id, username, gone.status_code)
            except httpx.HTTPError as e:
                log.warning("Could not delete the file token %s of %s (%s).", token_id, username, type(e).__name__)


async def has_file(username: str, server: str, path: str) -> bool:
    """Whether `path` (relative to the user's home) exists. The server must be running."""
    async with _notebook_server(username, server) as notebook_server:
        r = await notebook_server.get(_contents_url(username, server, path), params={"content": "0"})
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


async def get_file(username: str, server: str, path: str, max_bytes: int) -> bytes | None:
    """The file as it is saved in the user's home right now, or None when it is not there.
    Raises FileTooLarge instead of reading a file bigger than `max_bytes`."""
    async with _notebook_server(username, server) as notebook_server:
        about = await notebook_server.get(_contents_url(username, server, path), params={"content": "0"})
        if about.status_code == 404:
            return None
        about.raise_for_status()
        if (about.json().get("size") or 0) > max_bytes:
            raise FileTooLarge(path)
        r = await notebook_server.get(
            _contents_url(username, server, path), params={"type": "file", "format": "base64", "content": "1"}, timeout=120,
        )
        r.raise_for_status()
    return base64.b64decode(r.json()["content"])


async def put_file(username: str, server: str, path: str, content: bytes) -> None:
    """Writes a file into the user's home, creating its folders. Replaces a file already there, so
    callers that must not overwrite a student's work check `has_file` first.

    A large file goes in pieces (Jupyter's own way of uploading large files: "chunk" 1, 2, ... and
    -1 for the last), so neither side has to handle a large notebook as one request."""
    folders = path.split("/")[:-1]
    pieces = [content[start:start + PIECE_BYTES] for start in range(0, len(content), PIECE_BYTES)] or [b""]
    async with _notebook_server(username, server) as notebook_server:
        for depth in range(1, len(folders) + 1):
            r = await notebook_server.put(_contents_url(username, server, "/".join(folders[:depth])), json={"type": "directory"})
            r.raise_for_status()
        for number, piece in enumerate(pieces, start=1):
            model = {"type": "file", "format": "base64", "content": base64.b64encode(piece).decode()}
            if len(pieces) > 1:
                model["chunk"] = -1 if number == len(pieces) else number
            r = await notebook_server.put(_contents_url(username, server, path), json=model, timeout=120)
            r.raise_for_status()


class HubError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class FileTooLarge(Exception):
    pass
