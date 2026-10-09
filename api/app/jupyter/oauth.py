"""Minimal OAuth2 authorization-code provider with exactly one client: JupyterHub.

Endpoints (mounted at the site root, not under /api):
    GET  /oauth/authorize   browser; requires the platform session cookie
    POST /oauth/token       hub -> backend, server to server
    GET  /oauth/userinfo    hub -> backend, server to server

Codes and tokens live in memory, which is fine for one uvicorn worker. With several
workers, move `_codes` / `_tokens` to Redis or a DB table. If you later need more
clients, PKCE or refresh tokens, switch to Authlib instead of growing this file.
"""
import base64
import hmac
import secrets
import time
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import config
from .deps import PlatformUser, get_current_user_optional

router = APIRouter(prefix="/oauth", tags=["oauth"])

CLIENT_ID = config.OAUTH_CLIENT_ID
CLIENT_SECRET = config.OAUTH_CLIENT_SECRET
REDIRECT_URI = f"{config.HUB_ORIGIN}/hub/oauth_callback"   # exact match only

CODE_TTL = 60            # seconds; single use
TOKEN_TTL = 300          # the hub only needs it for the userinfo call right after login

_codes: dict[str, tuple[PlatformUser, float]] = {}
_tokens: dict[str, tuple[PlatformUser, float]] = {}


def _purge(store: dict) -> None:
    now = time.time()
    for key in [k for k, (_, exp) in store.items() if exp < now]:
        store.pop(key, None)


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str = "",
    user: PlatformUser | None = Depends(get_current_user_optional),
):
    # Validate the client BEFORE redirecting anywhere (prevents open redirects)
    if client_id != CLIENT_ID or redirect_uri != REDIRECT_URI:
        raise HTTPException(400, "unknown client or redirect_uri")
    if response_type != "code":
        raise HTTPException(400, "unsupported response_type")

    if user is None:
        # Not logged in to the platform: log in first, then come back here. `next` is a path, not a
        # full URL, so the login page can refuse anything that would leave this site.
        back = f"{request.url.path}?{request.url.query}"
        return RedirectResponse(f"/login?next={quote(back, safe='')}", status_code=302)

    _purge(_codes)
    code = secrets.token_urlsafe(32)
    _codes[code] = (user, time.time() + CODE_TTL)
    # No consent screen: first-party client, single school
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302)


def _check_client(client_id: str | None, client_secret: str | None, authorization: str | None) -> None:
    if authorization and authorization.lower().startswith("basic "):
        try:
            client_id, _, client_secret = base64.b64decode(authorization[6:]).decode().partition(":")
        except Exception:
            raise HTTPException(401, "invalid_client")
    ok = hmac.compare_digest(client_id or "", CLIENT_ID) and hmac.compare_digest(
        client_secret or "", CLIENT_SECRET
    )
    if not ok:
        raise HTTPException(401, "invalid_client")


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    authorization: str | None = Header(None),
):
    _check_client(client_id, client_secret, authorization)
    if grant_type != "authorization_code" or redirect_uri != REDIRECT_URI:
        raise HTTPException(400, "invalid_request")

    entry = _codes.pop(code, None)            # pop = single use
    if entry is None or entry[1] < time.time():
        raise HTTPException(400, "invalid_grant")

    _purge(_tokens)
    access_token = secrets.token_urlsafe(32)
    _tokens[access_token] = (entry[0], time.time() + TOKEN_TTL)
    return {"access_token": access_token, "token_type": "Bearer", "expires_in": TOKEN_TTL}


@router.get("/userinfo")
async def userinfo(authorization: str = Header(...)):
    scheme, _, value = authorization.partition(" ")
    entry = _tokens.get(value) if scheme.lower() == "bearer" else None
    if entry is None or entry[1] < time.time():
        raise HTTPException(401, "invalid_token")
    user = entry[0]
    return {
        "sub": str(user.id),
        "username": user.hub_username,        # GenericOAuthenticator.username_claim
        "name": user.display_name,
        "groups": user.hub_groups,            # GenericOAuthenticator.auth_state_groups_key
        "admin": user.is_admin,               # platform admins are hub admins: post_auth_hook in jupyterhub_config.py
    }
