"""Attacks on the login, on passwords and on the admin API, on a real (throwaway) Postgres database.

Each test does what an attacker would do and checks that the server refuses it.
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import auth, config
from app.jupyter import hub_client
from app.main import app
from app.models import LoginSession, User

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db):
    return TestClient(app, follow_redirects=False)


def login(client, username, password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def client_at(address: str) -> TestClient:
    """A browser at another network address (the test client's own address is fixed)."""
    async def from_address(scope, receive, send):
        await app({**scope, "client": (address, 50000)}, receive, send)

    return TestClient(from_address)


# --- guessing passwords ---------------------------------------------------------------------------

def test_password_guessing_is_cut_off(client, db):
    auth.create_user(db, "maria", PASSWORD)
    for guess in range(auth.MAX_LOGIN_ATTEMPTS):
        assert login(client, "maria", f"guess number {guess}").status_code == 401
    r = login(client, "maria", "one more guess")
    assert r.status_code == 429 and "Too many failed login attempts" in r.json()["detail"]
    # Even the right password is refused now: otherwise the attacker could simply keep guessing.
    assert login(client, "maria").status_code == 429
    assert login(client, "MARIA ").status_code == 429            # same account, however it is typed
    assert db.scalar(select(func.count()).select_from(LoginSession)) == 0


def test_cut_off_does_not_reveal_which_usernames_exist(client, db):
    auth.create_user(db, "maria", PASSWORD)
    answers = {}
    for username in ("maria", "nobody"):
        answers[username] = [
            (r.status_code, r.json()) for r in (login(client, username, "a wrong guess") for _ in range(auth.MAX_LOGIN_ATTEMPTS + 1))
        ]
    assert answers["maria"] == answers["nobody"]                 # identical, attempt by attempt


def test_cut_off_is_per_username_and_per_client_and_ends(client, db, monkeypatch):
    auth.create_user(db, "maria", PASSWORD)
    auth.create_user(db, "jose", PASSWORD)
    for _ in range(auth.MAX_LOGIN_ATTEMPTS):
        login(client, "maria", "a wrong guess")
    assert login(client, "maria").status_code == 429
    assert login(client, "jose").status_code == 200              # other accounts are not affected
    # Someone else (another address) can still log in as maria: an attacker cannot lock her out from afar.
    assert login(client_at("203.0.113.9"), "maria").status_code == 200
    # And the cut-off ends by itself.
    later = auth.time.monotonic() + auth.LOGIN_ATTEMPT_WINDOW + 1
    monkeypatch.setattr(auth.time, "monotonic", lambda: later)
    assert login(client, "maria").status_code == 200


def test_a_successful_login_resets_the_count(client, db):
    auth.create_user(db, "maria", PASSWORD)
    for _ in range(3):                                           # more rounds than the limit in total
        for _ in range(auth.MAX_LOGIN_ATTEMPTS - 1):
            assert login(client, "maria", "a typo").status_code == 401
        assert login(client, "maria").status_code == 200


# --- malicious input ------------------------------------------------------------------------------

@pytest.mark.parametrize("username", [
    "' OR '1'='1", "maria' --", "maria'; DROP TABLE users; --", '" OR ""="', "admin'/*", "maria\x00", "%", "_____",
])
def test_sql_injection_gets_nowhere(client, db, username):
    auth.create_user(db, "maria", PASSWORD)
    assert login(client, username).status_code == 401
    assert login(client, "maria", "' OR '1'='1").status_code == 401
    assert db.scalar(select(func.count()).select_from(User)) == 1    # the table is still there, untouched


def test_oversized_and_malformed_requests(client, db):
    auth.create_user(db, "maria", PASSWORD)
    assert login(client, "maria", "x" * 500_000).status_code == 401      # refused without hashing half a megabyte
    assert login(client, "m" * 500_000).status_code == 401
    assert login(client, "maria", "x" * 2_000_000).status_code == 413    # and anything over 1 MB is not even read
    assert client.post("/api/auth/login", json={"username": "maria"}).status_code == 422
    assert client.post("/api/auth/login", json={"username": ["maria"], "password": {"$ne": ""}}).status_code == 422
    assert client.get("/api/auth/login").status_code == 405


def test_a_web_form_on_another_site_cannot_log_someone_in(client, db):
    # Browsers let any site submit a form to us, but only as form data or plain text, never as JSON.
    auth.create_user(db, "maria", PASSWORD)
    form = client.post("/api/auth/login", data={"username": "maria", "password": PASSWORD})
    text = client.post("/api/auth/login", content=f'{{"username": "maria", "password": "{PASSWORD}"}}',
                       headers={"Content-Type": "text/plain"})
    assert form.status_code == 422 and text.status_code == 422
    assert auth.COOKIE_NAME not in client.cookies


# --- the session cookie ---------------------------------------------------------------------------

def test_a_planted_cookie_is_not_adopted_at_login(client, db):
    # "Session fixation": the attacker plants a cookie value they know, then waits for the victim to log in.
    auth.create_user(db, "maria", PASSWORD)
    client.cookies.set(auth.COOKIE_NAME, "value-chosen-by-the-attacker")
    r = login(client, "maria")
    assert r.status_code == 200
    issued = r.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    assert issued != "value-chosen-by-the-attacker" and len(issued) >= 43     # 32 random bytes
    attacker = TestClient(app, cookies={auth.COOKIE_NAME: "value-chosen-by-the-attacker"})
    assert attacker.get("/api/me").status_code == 401


def test_logging_in_over_another_login_ends_the_old_one(client, db):
    auth.create_user(db, "maria", PASSWORD)
    auth.create_user(db, "jose", PASSWORD)
    login(client, "maria")
    marias_cookie = client.cookies[auth.COOKIE_NAME]
    login(client, "jose")                                        # same browser, no log out in between
    assert client.get("/api/me").json()["username"] == "jose"
    assert TestClient(app, cookies={auth.COOKIE_NAME: marias_cookie}).get("/api/me").status_code == 401
    assert db.scalar(select(func.count()).select_from(LoginSession)) == 1


def test_made_up_cookies_are_rejected(client, db):
    user = auth.create_user(db, "maria", PASSWORD)
    token = auth.start_session(db, user)
    stored = db.scalar(select(LoginSession.token_hash))
    assert stored != token                                       # the database only has the hash...
    for value in ["", "x", token[:-1], token + "x", stored, "' OR '1'='1"]:      # ...which is no use as a cookie
        assert TestClient(app, cookies={auth.COOKIE_NAME: value}).get("/api/me").status_code == 401


def test_cookie_is_https_only_in_production(client, db, monkeypatch):
    auth.create_user(db, "maria", PASSWORD)
    monkeypatch.setattr(config, "HTTPS", True)
    flags = login(client, "maria").headers["set-cookie"].lower()
    assert "secure" in flags and "httponly" in flags and "samesite=lax" in flags
    assert "domain=" not in flags                                # this host only: not sent to the notebook server


# --- the admin API --------------------------------------------------------------------------------

def test_admin_api_is_enforced_on_the_server(client, db):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    auth.create_user(db, "maria", PASSWORD, display_name="Maria Lopez")

    assert client.get("/api/admin/users").status_code == 401     # logged out

    login(client, "maria")
    r = client.get("/api/admin/users")                           # a student, asking directly
    assert r.status_code == 403 and "maria" not in r.text and "boss" not in r.text
    # Pretending in the request changes nothing: the admin flag is read from the database.
    for attempt in [
        dict(headers={"X-Admin": "true", "X-Is-Admin": "1"}),
        dict(params={"is_admin": "true", "role": "teacher"}),
        dict(cookies={"is_admin": "true", "role": "admin"}),
    ]:
        assert client.get("/api/admin/users", **attempt).status_code == 403
    assert client.get("/api/me").json()["is_admin"] is False

    client.post("/api/auth/logout")
    login(client, "boss")
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    assert [(u["username"], u["role"], u["is_admin"], u["hub_username"]) for u in r.json()] == [
        ("boss", "teacher", True, "t-1"), ("maria", "student", False, "s-2"),
    ]
    assert "password" not in r.text and "argon2" not in r.text  # hashes never leave the server


def test_losing_admin_rights_takes_effect_immediately(client, db):
    boss = auth.create_user(db, "boss", PASSWORD, is_admin=True)
    login(client, "boss")
    assert client.get("/api/admin/users").status_code == 200
    boss.is_admin = False
    db.commit()
    assert client.get("/api/admin/users").status_code == 403    # same session, checked again on every request


def test_admin_creates_a_student_account(client, db):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    auth.create_user(db, "maria", PASSWORD)
    new = {"username": "Jose.Perez", "name": "Jose Perez", "role": "student", "gpu_enabled": True}

    assert client.post("/api/admin/users", json=new).status_code == 401          # logged out
    login(client, "maria")
    assert client.post("/api/admin/users", json=new).status_code == 403          # a student
    assert client.post("/api/admin/users", json={**new, "is_admin": True}).status_code == 403
    assert db.scalar(select(func.count()).select_from(User)) == 2                # nothing was created
    client.post("/api/auth/logout")

    login(client, "boss")
    r = client.post("/api/admin/users", json={**new, "is_admin": True, "password": "chosen by the caller"})
    assert r.status_code == 201
    account = r.json()
    assert (account["username"], account["name"], account["role"], account["gpu_enabled"]) == ("jose.perez", "Jose Perez", "student", True)
    assert account["is_admin"] is False                          # admin rights cannot be handed out from the browser
    password = account["password"]
    assert password != "chosen by the caller" and len(password) >= 12   # generated on the server

    # Shown once, never again; the hash is not in any response either.
    listing = client.get("/api/admin/users")
    assert "jose.perez" in listing.text and password not in listing.text and "argon2" not in listing.text + r.text
    stored = db.scalar(select(User.password_hash).where(User.username == "jose.perez"))
    assert stored.startswith("$argon2id$") and password not in stored

    for bad, why in [
        ({**new}, "already taken"),                              # the same username again
        ({**new, "username": "x"}, "3 to 32 characters"),
        ({**new, "username": "bad name!"}, "3 to 32 characters"),
        ({**new, "username": "newone", "role": "principal"}, "role must be"),
    ]:
        refused = client.post("/api/admin/users", json=bad)
        assert refused.status_code == 400 and why in refused.json()["detail"]
    assert client.post("/api/admin/users", json={**new, "username": "newone", "name": "n" * 101}).status_code == 422
    assert client.post("/api/admin/users", data={"username": "newone"}).status_code == 422     # a web form, not JSON

    student = TestClient(app)
    assert login(student, "jose.perez", password).status_code == 200            # the new account works
    assert student.get("/api/admin/users").status_code == 403


# --- requests sent from other websites ------------------------------------------------------------

def test_writes_from_other_origins_are_refused(client, db):
    # A page on another address (a student's notebook runs on the hub's) can make the visitor's browser
    # send requests here, cookie included. Browsers label those with the Origin they came from.
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    login(client, "boss")
    for origin in ["http://localhost:8081", "https://evil.example", "http://localhost:3000.evil.example", "null"]:
        hostile = {"Origin": origin}
        assert client.post("/api/admin/users", json={"username": "planted"}, headers=hostile).status_code == 403
        assert client.post("/api/assignments/1/stop", headers=hostile).status_code == 403
        assert client.post("/api/auth/logout", headers=hostile).status_code == 403
        upload = dict(data={"title": "Planted"}, files={"file": ("lab.ipynb", b"{}")})
        assert client.post("/api/teach/assignments", headers=hostile, **upload).status_code == 403
        assert client.delete("/api/teach/assignments/1", headers=hostile).status_code == 403
        assert client.post("/api/auth/login", json={"username": "boss", "password": PASSWORD}, headers=hostile).status_code == 403
    assert client.get("/api/me").json()["username"] == "boss"   # still logged in: none of it happened
    assert db.scalar(select(func.count()).select_from(User)) == 1

    own = {"Origin": config.APP_ORIGIN}
    assert client.get("/api/me", headers={"Origin": "https://evil.example"}).status_code == 200    # reads change nothing
    assert client.post("/api/admin/users", json={"username": "maria"}, headers=own).status_code == 201
    assert client.post("/api/auth/logout", headers=own).status_code == 200


# --- changing passwords and removing accounts -----------------------------------------------------

def test_changing_your_own_password(client, db):
    auth.create_user(db, "maria", PASSWORD)
    new = "a brand new password"
    change = {"current_password": PASSWORD, "new_password": new}
    assert client.post("/api/auth/password", json=change).status_code == 401           # logged out
    login(client, "maria")
    elsewhere = TestClient(app)                                  # the same account on another device
    login(elsewhere, "maria")

    r = client.post("/api/auth/password", json={"current_password": "a wrong guess", "new_password": new})
    assert r.status_code == 400 and "current password is wrong" in r.json()["detail"]
    r = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 400 and "8 to 256 characters" in r.json()["detail"]
    assert elsewhere.get("/api/me").status_code == 200           # nothing changed so far

    assert client.post("/api/auth/password", json=change).json() == {"changed": True}
    assert client.get("/api/me").json()["username"] == "maria"   # this browser stays logged in...
    assert elsewhere.get("/api/me").status_code == 401           # ...every other session is over
    assert login(TestClient(app), "maria").status_code == 401 and login(TestClient(app), "maria", new).status_code == 200
    assert db.scalar(select(func.count()).select_from(LoginSession)) == 2


def test_guessing_the_current_password_is_cut_off(client, db):
    # Someone at a browser that was left logged in tries to find the password, to take the account over.
    auth.create_user(db, "maria", PASSWORD)
    login(client, "maria")
    for guess in range(auth.MAX_LOGIN_ATTEMPTS):
        r = client.post("/api/auth/password", json={"current_password": f"guess number {guess}", "new_password": "taken over now"})
        assert r.status_code == 400
    r = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "taken over now"})
    assert r.status_code == 429
    assert login(TestClient(app), "maria").status_code == 200    # the password is unchanged


@pytest.fixture
def no_hub(monkeypatch):
    """The hub side of removing an account, recorded instead of done."""
    removed = []

    async def delete_user(username):
        removed.append(username)

    monkeypatch.setattr(hub_client, "delete_user", delete_user)
    return removed


def test_admin_edits_resets_and_removes_accounts(client, db, no_hub):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    auth.create_user(db, "maria", PASSWORD, display_name="Maria Lopez")
    auth.create_user(db, "chief", PASSWORD, role="teacher", is_admin=True)
    maria = TestClient(app)
    login(maria, "maria")

    for attempt in [
        lambda c: c.patch("/api/admin/users/1", json={"name": "Hacked"}),
        lambda c: c.post("/api/admin/users/1/reset-password"),
        lambda c: c.delete("/api/admin/users/1"),
    ]:
        assert attempt(client).status_code == 401 and attempt(maria).status_code == 403
    assert no_hub == [] and db.scalar(select(func.count()).select_from(User)) == 3

    login(client, "boss")
    r = client.patch("/api/admin/users/2", json={"name": "Maria L. Lopez", "gpu_enabled": True, "role": "teacher", "is_admin": True})
    account = r.json()
    assert (account["name"], account["gpu_enabled"]) == ("Maria L. Lopez", True)
    assert (account["role"], account["is_admin"]) == ("student", False)      # neither can be changed from the browser
    assert client.patch("/api/admin/users/2", json={"name": ""}).status_code == 422
    assert client.patch("/api/admin/users/99", json={"name": "x"}).status_code == 404

    r = client.post("/api/admin/users/2/reset-password")
    password = r.json()["password"]
    assert r.status_code == 200 and len(password) >= 12
    assert maria.get("/api/me").status_code == 401               # logged out everywhere
    assert login(TestClient(app), "maria").status_code == 401 and login(maria, "maria", password).status_code == 200
    assert "argon2" not in r.text

    # Admin accounts are only handled on the server itself: not another admin's, not your own.
    for admin_id in (1, 3):
        assert client.post(f"/api/admin/users/{admin_id}/reset-password").status_code == 403
        assert client.delete(f"/api/admin/users/{admin_id}").status_code == 403
    assert login(TestClient(app), "chief").status_code == 200

    assert client.delete("/api/admin/users/2").json() == {"deleted": True}
    assert no_hub == ["s-2"]                                     # their notebook servers and hub login went too
    assert maria.get("/api/me").status_code == 401 and login(TestClient(app), "maria", password).status_code == 401
    assert client.delete("/api/admin/users/2").status_code == 404
    assert [u["username"] for u in client.get("/api/admin/users").json()] == ["boss", "chief"]


def test_an_account_is_not_removed_while_the_hub_is_unreachable(client, db, monkeypatch):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    auth.create_user(db, "maria", PASSWORD)

    async def unreachable(username):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(hub_client, "delete_user", unreachable)
    login(client, "boss")
    r = client.delete("/api/admin/users/2")
    assert r.status_code == 503 and "was not removed" in r.json()["detail"]
    assert login(TestClient(app), "maria").status_code == 200


# --- secrets --------------------------------------------------------------------------------------

def test_the_backend_refuses_placeholder_secrets_once_others_can_reach_it():
    long_one = "0123456789abcdef" * 4                            # like `openssl rand -hex 32`
    placeholders = {"HUB_API_TOKEN": "dev-hub-api-token", "OAUTH_CLIENT_SECRET": "change-me", "GRADER_TOKEN": ""}
    # On this computer only, the defaults in the repository are fine.
    for origin in ("http://localhost:3000", "http://127.0.0.1:3001"):
        assert config.weak_secrets(origin, placeholders) == []
    # Anywhere else (a server, or ./dev.sh --lan): each secret must be long and not a placeholder.
    for origin in ("https://cyberai.utep.edu", "http://192.168.1.20:3000", "http://localhost.evil.example"):
        assert config.weak_secrets(origin, placeholders) == ["HUB_API_TOKEN", "OAUTH_CLIENT_SECRET", "GRADER_TOKEN"]
    assert config.weak_secrets("https://cyberai.utep.edu", {"A": long_one, "B": "x" * 31, "C": f"dev-{long_one}"}) == ["B", "C"]
    assert config.weak_secrets("http://192.168.1.20:3000", {"HUB_API_TOKEN": long_one}) == []    # what dev.sh --lan makes
