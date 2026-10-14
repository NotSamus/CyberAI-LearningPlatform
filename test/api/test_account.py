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

    assert maria.put("/api/auth/theme", json={"theme": "halloween"}).json() == {"theme": "halloween"}
    assert maria.get("/api/me").json()["theme"] == "halloween"
    assert browser("maria").get("/api/me").json()["theme"] == "halloween"         # on every device: it is the account's
    assert jose.get("/api/me").json()["theme"] == "standard"                      # and nobody else's

    r = maria.put("/api/auth/theme", json={"theme": "<script>"})
    assert r.status_code == 400 and maria.get("/api/me").json()["theme"] == "halloween"
    assert TestClient(app).put("/api/auth/theme", json={"theme": "retro"}).status_code == 401     # logged out
