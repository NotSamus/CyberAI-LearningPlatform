"""Notebook API tests. Run from the project root:  pytest test"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import assignments, auth
from app.db import get_db
from app.jupyter import hub_client
from app.jupyter.deps import PlatformUser, get_current_user_optional
from app.main import app
from conftest import notebook_file

client = TestClient(app, follow_redirects=False)
STUDENT = PlatformUser(id=1, username="student", display_name="Test Student", role="student", gpu_enabled=True)


@pytest.fixture(autouse=True)
def logged_in():
    """These tests are about notebooks, not accounts (see test_auth.py): every request comes from
    STUDENT, who has no row in the users table."""
    app.dependency_overrides[get_current_user_optional] = lambda: STUDENT
    yield
    app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.fixture
def fake_hub(monkeypatch):
    calls = []

    async def ensure_user(username, groups):
        calls.append(("ensure", username, tuple(groups)))

    async def start_server(username, server, wait_seconds=90):
        calls.append(("start", username, server))
        return True

    async def has_file(username, server, path):
        return True                 # the student already has their copy (test_assignments.py covers the copying)

    monkeypatch.setattr(hub_client, "ensure_user", ensure_user)
    monkeypatch.setattr(hub_client, "start_server", start_server)
    monkeypatch.setattr(hub_client, "has_file", has_file)
    return calls


@pytest.fixture
def two_assignments(db):
    """Published to every student: "Python basics" (id 1) and "Hello GPU" (id 2, needs a GPU).
    STUDENT gets a row in the users table too (id 1), for what is recorded about them."""
    auth.create_user(db, "student", "a long password")
    for title, gpu in [("Python basics", False), ("Hello GPU", True)]:
        assignments.create(
            db, title=title, filename="lab1.ipynb", notebook=notebook_file(), requires_gpu=gpu,
            published=True, for_everyone=True,
        )


def test_me_and_assignments(two_assignments):
    me = client.get("/api/me").json()
    assert me["name"] == "Test Student" and me["can_teach"] is False
    listed = client.get("/api/assignments").json()
    assert [(a["id"], a["title"], a["requires_gpu"]) for a in listed] == [(1, "Python basics", False), (2, "Hello GPU", True)]
    assert client.get("/api/assignments/1").json()["title"] == "Python basics"
    assert client.get("/api/assignments/99").status_code == 404
    assert client.get("/api/assignments/nope").status_code == 422


def test_database_down_is_reported(monkeypatch):
    engine = create_engine("postgresql+psycopg://nobody:nothing@localhost:1/nowhere")

    def unreachable_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db, unreachable_db)
    r = client.post("/api/auth/login", json={"username": "maria", "password": "her password"})
    assert r.status_code == 503 and "database is not reachable" in r.json()["detail"]


def test_launch_cpu_and_gpu(fake_hub, two_assignments):
    r = client.post("/api/assignments/1/launch").json()
    assert r["profile"] == "cpu"
    assert r["url"] == "http://localhost:8081/user/s-1/cpu/lab/tree/assignments/python-basics-1/lab1.ipynb"
    r = client.post("/api/assignments/2/launch").json()
    assert r["profile"] == "gpu"
    assert ("start", "s-1", "gpu") in fake_hub


def test_environment_still_starting(monkeypatch, fake_hub, two_assignments):
    async def slow(*a, **k):
        return False                # not ready within the wait

    monkeypatch.setattr(hub_client, "start_server", slow)
    r = client.post("/api/assignments/1/launch")
    assert r.status_code == 503 and "still starting" in r.json()["detail"]


def test_launch_when_hub_is_down(monkeypatch, two_assignments):
    async def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(hub_client, "ensure_user", boom)
    r = client.post("/api/assignments/1/launch")
    assert r.status_code == 503 and "not reachable" in r.json()["detail"]


def test_hub_error_response_is_not_called_unreachable(monkeypatch, two_assignments):
    async def refused(*a, **k):
        req = httpx.Request("POST", "http://hub/hub/api/groups/students/users")
        raise httpx.HTTPStatusError("400", request=req, response=httpx.Response(400, request=req))

    monkeypatch.setattr(hub_client, "ensure_user", refused)
    r = client.post("/api/assignments/1/launch")
    assert r.status_code == 502 and "returned an error (400)" in r.json()["detail"]


def test_hub_refusal_is_passed_to_student(monkeypatch, fake_hub, two_assignments):
    async def full(*a, **k):
        raise hub_client.HubError(500, "All GPU slots are in use. Try again in a few minutes.")

    monkeypatch.setattr(hub_client, "start_server", full)
    r = client.post("/api/assignments/2/launch")
    assert r.status_code == 503 and "GPU slots" in r.json()["detail"]


def test_oauth_flow():
    cb = "http://localhost:8081/hub/oauth_callback"
    q = dict(response_type="code", client_id="jupyterhub", redirect_uri=cb, state="xyz")
    r = client.get("/oauth/authorize", params=q)
    assert r.status_code == 302 and r.headers["location"].startswith(cb) and "state=xyz" in r.headers["location"]
    code = r.headers["location"].split("code=")[1].split("&")[0]

    assert client.get("/oauth/authorize", params={**q, "redirect_uri": "https://evil.example/cb"}).status_code == 400

    form = dict(grant_type="authorization_code", code=code, redirect_uri=cb, client_id="jupyterhub")
    assert client.post("/oauth/token", data={**form, "client_secret": "wrong"}).status_code == 401
    tok = client.post("/oauth/token", data={**form, "client_secret": "dev-oauth-secret"})
    assert tok.status_code == 200
    assert client.post("/oauth/token", data={**form, "client_secret": "dev-oauth-secret"}).status_code == 400  # single use

    info = client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {tok.json()['access_token']}"}).json()
    assert info["username"] == "s-1" and set(info["groups"]) == {"students", "gpu"}
    assert client.get("/oauth/userinfo", headers={"Authorization": "Bearer nope"}).status_code == 401
