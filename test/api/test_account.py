"""What a person changes about their own account, apart from the password (see test_security.py)."""
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from conftest import PASSWORD, browser


def test_choosing_a_theme(db):
    auth.create_user(db, "maria", PASSWORD)
    auth.create_user(db, "jose", PASSWORD)
    maria, jose = browser("maria"), browser("jose")
    assert maria.get("/api/me").json()["theme"] == "standard"                     # where everyone starts

    assert maria.put("/api/auth/theme", json={"theme": "halloween"}).json() == {"theme": "halloween", "mode": "device"}
    assert maria.get("/api/me").json()["theme"] == "halloween"
    assert browser("maria").get("/api/me").json()["theme"] == "halloween"         # on every device: it is the account's
    assert jose.get("/api/me").json()["theme"] == "standard"                      # and nobody else's

    r = maria.put("/api/auth/theme", json={"theme": "<script>"})
    assert r.status_code == 400 and maria.get("/api/me").json()["theme"] == "halloween"
    assert TestClient(app).put("/api/auth/theme", json={"theme": "retro"}).status_code == 401     # logged out


def test_choosing_light_or_dark(db):
    auth.create_user(db, "maria", PASSWORD)
    auth.create_user(db, "jose", PASSWORD)
    maria, jose = browser("maria"), browser("jose")
    assert maria.get("/api/me").json()["mode"] == "device"                        # as the device is set, to begin with

    # Each on its own: the other stays as it was.
    assert maria.put("/api/auth/theme", json={"mode": "dark"}).json() == {"theme": "standard", "mode": "dark"}
    assert maria.put("/api/auth/theme", json={"theme": "retro"}).json() == {"theme": "retro", "mode": "dark"}
    assert browser("maria").get("/api/me").json()["mode"] == "dark"               # on every device
    assert jose.get("/api/me").json()["mode"] == "device"

    for bad in ({"mode": "sepia"}, {"theme": "retro", "mode": "<script>"}):
        assert maria.put("/api/auth/theme", json=bad).status_code == 400
    assert maria.put("/api/auth/theme", json={}).status_code == 422
    assert maria.get("/api/me").json()["mode"] == "dark"
    assert TestClient(app).put("/api/auth/theme", json={"mode": "light"}).status_code == 401
