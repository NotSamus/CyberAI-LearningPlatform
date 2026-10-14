"""Accounts, login and the account command line tool, on a real (throwaway) Postgres database."""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app import auth
from app.main import app
from app.models import LoginSession

API_DIR = Path(__file__).resolve().parents[2] / "api"
PASSWORD = "correct horse battery"
HUB_CALLBACK = "http://localhost:8081/hub/oauth_callback"
AUTHORIZE = dict(response_type="code", client_id="jupyterhub", redirect_uri=HUB_CALLBACK, state="xyz")


@pytest.fixture
def client(db):
    return TestClient(app, follow_redirects=False)


def login(client, username, password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def manage(*args: str, db_url: str, password: str = ""):
    """Runs the command line tool the way a script would: the password arrives on standard input."""
    return subprocess.run(
        [sys.executable, "-m", "app.manage", *args],
        cwd=API_DIR, env={**os.environ, "DATABASE_URL": db_url}, input=password + "\n", capture_output=True, text=True,
    )


def test_login_me_logout(client, db):
    user = auth.create_user(db, "Maria", PASSWORD, display_name="Maria Lopez")
    assert client.get("/api/me").status_code == 401
    assert login(client, "maria", "not her password").status_code == 401
    assert login(client, "nobody").status_code == 401

    r = login(client, "MARIA")                      # usernames are not case sensitive
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert client.get("/api/me").json() == {
        "id": user.id, "username": "maria", "name": "Maria Lopez", "role": "student", "is_admin": False, "can_teach": False, "gpu_enabled": False,
        "theme": "standard",
    }

    cookie = client.cookies[auth.COOKIE_NAME]
    assert client.post("/api/auth/logout").json() == {"logged_out": True}
    assert client.get("/api/me").status_code == 401
    # Logging out ends the session on the server too: a copy of the old cookie is useless.
    assert db.scalar(select(func.count()).select_from(LoginSession)) == 0
    assert TestClient(app, cookies={auth.COOKIE_NAME: cookie}).get("/api/me").status_code == 401


def test_expired_session_is_rejected(client, db):
    user = auth.create_user(db, "maria", PASSWORD)
    client.cookies.set(auth.COOKIE_NAME, auth.start_session(db, user))
    assert client.get("/api/me").status_code == 200
    db.execute(update(LoginSession).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db.commit()
    assert client.get("/api/me").status_code == 401


def test_account_rules(db):
    user = auth.create_user(db, "maria", PASSWORD)
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    for username, password in [
        ("Maria", PASSWORD),            # taken, whatever the capitals
        ("ab", PASSWORD),               # too short
        ("has space", PASSWORD),
        ("newuser", "short"),
    ]:
        with pytest.raises(auth.AccountError):
            auth.create_user(db, username, password)
    with pytest.raises(auth.AccountError):
        auth.create_user(db, "newuser", PASSWORD, role="principal")


def test_new_password_logs_out_everywhere(client, db):
    user = auth.create_user(db, "maria", PASSWORD)
    assert login(client, "maria").status_code == 200
    auth.set_password(db, user, "a brand new password")
    assert client.get("/api/me").status_code == 401
    assert login(client, "maria").status_code == 401
    assert login(client, "maria", "a brand new password").status_code == 200


def test_notebook_sign_in_uses_the_logged_in_account(client, db):
    # Logged out: the hub's sign-in is sent to the login page, with a path (never a full URL) to return to.
    r = client.get("/oauth/authorize", params=AUTHORIZE)
    assert r.status_code == 302 and r.headers["location"].startswith("/login?next=%2Foauth%2Fauthorize%3F")

    teacher = auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    login(client, "boss")
    r = client.get("/oauth/authorize", params=AUTHORIZE)
    assert r.status_code == 302 and r.headers["location"].startswith(HUB_CALLBACK)
    code = r.headers["location"].split("code=")[1].split("&")[0]
    form = dict(grant_type="authorization_code", code=code, redirect_uri=HUB_CALLBACK,
                client_id="jupyterhub", client_secret="dev-oauth-secret")
    token = client.post("/oauth/token", data=form).json()["access_token"]
    info = client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"}).json()
    assert info["username"] == f"t-{teacher.id}" and set(info["groups"]) == {"teachers", "gpu"}
    assert info["admin"] is True                    # platform admins are JupyterHub admins


def test_command_line_tool(client, db, migrated_db_url):
    r = manage("create-user", "Boss", "--role", "teacher", "--admin", db_url=migrated_db_url, password=PASSWORD)
    assert r.returncode == 0, r.stderr
    assert login(client, "boss").status_code == 200
    me = client.get("/api/me").json()
    assert me["is_admin"] is True and me["role"] == "teacher"

    taken = manage("create-user", "boss", db_url=migrated_db_url, password=PASSWORD)
    assert taken.returncode != 0 and "already taken" in taken.stderr
    weak = manage("create-user", "maria", db_url=migrated_db_url, password="short")
    assert weak.returncode != 0 and "characters" in weak.stderr

    assert manage("create-user", "maria", "--name", "Maria Lopez", db_url=migrated_db_url, password=PASSWORD).returncode == 0
    assert manage("set-admin", "maria", db_url=migrated_db_url).returncode == 0
    assert "maria (id 2; student, admin)" in manage("list-users", db_url=migrated_db_url).stdout
    assert manage("set-admin", "maria", "--remove", db_url=migrated_db_url).returncode == 0
    assert "maria (id 2; student)" in manage("list-users", db_url=migrated_db_url).stdout

    assert manage("set-password", "maria", db_url=migrated_db_url, password="a brand new password").returncode == 0
    assert login(client, "maria").status_code == 401
    assert login(client, "maria", "a brand new password").status_code == 200
    assert manage("set-admin", "nobody", db_url=migrated_db_url).returncode != 0
