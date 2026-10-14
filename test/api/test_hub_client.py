"""The hub client, against a stand-in hub that records every request (httpx.MockTransport).

The platform's service token can manage every hub user and server. Code a student runs in their
notebook can see the requests that reach their notebook server, so the token must never be sent
there: each file operation gets a short-lived token of the student's own instead."""
import asyncio
import base64
import json
from urllib.parse import unquote

import httpx
import pytest
from fastapi import HTTPException

from app.jupyter import hub_client, launch

SERVICE_TOKEN = "service-token-of-the-tests"


class FakeHub:
    """Answers like JupyterHub and its proxy to one running notebook server do. `files` maps a path
    in the user's home to its bytes. Set `refuse_tokens`, `broken_server` or `broken_delete` to make
    that part fail."""

    def __init__(self):
        self.requests: list[dict] = []
        self.files: dict[str, bytes] = {}
        self.made: dict[str, str] = {}          # token id -> token
        self.deleted: list[str] = []            # token ids
        self.refuse_tokens = self.broken_server = self.broken_delete = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        body = json.loads(request.content) if request.content else None
        self.requests.append({"method": request.method, "path": path, "token": request.headers.get("authorization"), "json": body})

        if path.startswith("/hub/api/"):
            return self.hub_api(request.method, path.removeprefix("/hub/api"), body)
        if path.startswith("/user/"):
            # The proxied notebook server: only a token the hub made, and has not deleted, gets in
            if request.headers.get("authorization") not in {f"token {t}" for i, t in self.made.items() if i not in self.deleted}:
                return httpx.Response(403)
            if self.broken_server:
                return httpx.Response(500)
            return self.contents(request.method, path.split("/api/contents/", 1)[1], body, request.url.params)
        return httpx.Response(404)

    def hub_api(self, method, path, body):
        if path.endswith("/tokens") and method == "POST":
            if self.refuse_tokens:
                return httpx.Response(403, json={"message": "Action is not authorized with current scopes; requires any of [tokens]"})
            token_id = f"a{len(self.made) + 1}"
            self.made[token_id] = f"user-token-{len(self.made) + 1}"
            return httpx.Response(201, json={"id": token_id, "token": self.made[token_id], "kind": "api_token", "scopes": body["scopes"]})
        if "/tokens/" in path and method == "DELETE":
            if self.broken_delete:
                return httpx.Response(500)
            self.deleted.append(path.rsplit("/", 1)[1])
            return httpx.Response(204)
        if method == "GET":
            return httpx.Response(200, json={"name": path.rsplit("/", 1)[1], "groups": [], "servers": {}})
        return httpx.Response(201 if method == "POST" else 204)

    def contents(self, method, path, body, params):
        if method == "PUT":
            if body["type"] == "file":       # in one go, or in pieces: "chunk" 1, 2, ... -1
                before = b"" if body.get("chunk") in (None, 1) else self.files.get(path, b"")
                self.files[path] = before + base64.b64decode(body["content"])
            return httpx.Response(201, json={"path": path})
        if path not in self.files:
            return httpx.Response(404)
        model = {"path": path, "size": len(self.files[path])}
        if params.get("content") == "1":
            model["content"] = base64.b64encode(self.files[path]).decode()
        return httpx.Response(200, json=model)

    def to(self, prefix):
        return [r for r in self.requests if r["path"].startswith(prefix)]


@pytest.fixture
def fake(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr(hub_client, "HUB_API_URL", "http://hub.test/hub/api")
    monkeypatch.setattr(hub_client, "HUB_API_TOKEN", SERVICE_TOKEN)
    monkeypatch.setattr(hub_client, "_transport", httpx.MockTransport(hub))
    return hub


def test_file_operations_never_send_the_service_token_to_a_notebook_server(fake):
    path = "assignments/functions-lab-1/lab.ipynb"
    assert asyncio.run(hub_client.has_file("s-2", "cpu", path)) is False
    asyncio.run(hub_client.put_file("s-2", "cpu", path, b"her notebook"))
    assert asyncio.run(hub_client.has_file("s-2", "cpu", path)) is True
    assert asyncio.run(hub_client.get_file("s-2", "cpu", path, max_bytes=1000)) == b"her notebook"

    # Four operations: four tokens, each made for that one server, for a short time.
    mints = [r for r in fake.to("/hub/api/") if r["path"].endswith("/tokens")]
    assert [m["path"] for m in mints] == ["/hub/api/users/s-2/tokens"] * 4
    for mint in mints:
        assert mint["json"]["scopes"] == ["access:servers!server=s-2/cpu"]
        expires = mint["json"]["expires_in"]
        assert isinstance(expires, int) and not isinstance(expires, bool) and 0 < expires <= 300

    # The notebook server only ever sees a token made for the operation, never the service token.
    to_server = fake.to("/user/")
    assert to_server and all(r["path"].startswith("/user/s-2/cpu/api/contents/") for r in to_server)
    assert all(SERVICE_TOKEN not in (r["token"] or "") for r in to_server)
    assert {r["token"] for r in to_server} == {f"token {t}" for t in fake.made.values()}
    # get_file's two requests share one token
    assert [r["token"] for r in to_server[-2:]] == ["token user-token-4"] * 2

    # Every token is deleted once its operation is done, by the service, through the hub's API.
    assert fake.deleted == ["a1", "a2", "a3", "a4"]
    for r in fake.to("/hub/api/"):
        assert r["token"] == f"token {SERVICE_TOKEN}"
    order = [r["path"] for r in fake.requests]
    assert order.index("/hub/api/users/s-2/tokens/a2") > max(i for i, r in enumerate(fake.requests) if r["token"] == "token user-token-2")


def test_a_large_file_goes_in_pieces_with_one_token(fake, monkeypatch):
    monkeypatch.setattr(hub_client, "PIECE_BYTES", 3)
    asyncio.run(hub_client.put_file("t-1", "cpu", "submissions/lab/maria/lab.ipynb", b"0123456789"))
    assert fake.files["submissions/lab/maria/lab.ipynb"] == b"0123456789"
    assert len(fake.made) == 1 and fake.deleted == ["a1"]
    assert {r["token"] for r in fake.to("/user/")} == {"token user-token-1"} and len(fake.to("/user/")) == 3 + 4   # 3 folders, 4 pieces


def test_the_token_is_deleted_also_when_the_operation_fails(fake):
    fake.files["big.ipynb"] = b"x" * 5000
    with pytest.raises(hub_client.FileTooLarge):
        asyncio.run(hub_client.get_file("s-2", "cpu", "big.ipynb", max_bytes=1000))
    fake.broken_server = True
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(hub_client.put_file("s-2", "gpu", "a/b.ipynb", b"..."))
    assert fake.deleted == ["a1", "a2"]
    mints = [r for r in fake.to("/hub/api/users/s-2/tokens") if r["method"] == "POST"]
    assert mints[1]["json"]["scopes"] == ["access:servers!server=s-2/gpu"]

    # A delete that fails is let go (the token expires by itself) and does not hide the result.
    fake.broken_server, fake.broken_delete = False, True
    assert asyncio.run(hub_client.has_file("s-2", "cpu", "big.ipynb")) is True


def test_a_refused_token_stops_before_the_notebook_server(fake):
    fake.refuse_tokens = True
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(hub_client.put_file("s-2", "cpu", "lab.ipynb", b"..."))
    assert fake.to("/user/") == [] and fake.deleted == []

    # What the student is then told: the same message as for any other refusal by the hub.
    with pytest.raises(HTTPException) as refused:
        with launch.hub_errors():
            asyncio.run(hub_client.has_file("s-2", "cpu", "lab.ipynb"))
    assert refused.value.status_code == 502 and "notebook service returned an error (403)" in refused.value.detail
    assert fake.to("/user/") == []


def test_hub_api_calls_carry_the_service_token(fake):
    asyncio.run(hub_client.ensure_user("s-2", ["students"]))
    asyncio.run(hub_client.stop_server("s-2", "cpu"))
    asyncio.run(hub_client.delete_user("s-2"))
    assert fake.requests and fake.to("/user/") == []
    assert all(r["token"] == f"token {SERVICE_TOKEN}" for r in fake.requests)
    assert ("POST", "/hub/api/groups/students/users") in [(r["method"], r["path"]) for r in fake.requests]
