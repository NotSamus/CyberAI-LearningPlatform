"""Students have a username and no name, and admins can have a username made up for them
("swiftfalcon482"), on a real (throwaway) Postgres database."""
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import auth, usernames
from app.main import app
from app.models import User

PASSWORD = "correct horse battery"
GAMERTAG = re.compile(r"([a-z]+)([1-9][0-9]{1,3})")


@pytest.fixture
def client(db):
    return TestClient(app, follow_redirects=False)


def login(client, username, password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# --- the made-up usernames ------------------------------------------------------------------------

def test_every_pair_of_words_makes_a_harmless_valid_username():
    for words in (usernames.ADJECTIVES, usernames.NOUNS):
        assert len(set(words)) == len(words) >= 50
        assert all(re.fullmatch(r"[a-z]+", word) for word in words)
    for adjective in usernames.ADJECTIVES:
        for noun in usernames.NOUNS:
            joined = adjective + noun
            assert auth.USERNAME_RE.fullmatch(joined + "9999")             # the longest it gets still fits
            assert not [word for word in usernames.BLOCKED if word in joined], joined


def test_suggestions_look_like_gamertags_and_vary(db):
    made = [usernames.suggest(db) for _ in range(300)]
    for username in made:
        assert GAMERTAG.fullmatch(username) and auth.USERNAME_RE.fullmatch(username)
        assert not [word for word in usernames.BLOCKED if word in username], username
    assert {len(GAMERTAG.fullmatch(u).group(2)) for u in made} == {2, 3, 4}  # two to four digits
    assert len(set(made)) > 290


def test_a_suggestion_is_never_a_username_that_is_taken(db, monkeypatch):
    auth.create_user(db, "swiftfalcon482", PASSWORD)
    made_up = iter(["swiftfalcon482", "calmcomet69", "swiftfalcon482", "calmcomet77"])
    monkeypatch.setattr(usernames, "_made_up", lambda: next(made_up))
    assert usernames.suggest(db) == "calmcomet77"                          # taken, blocked digits, taken, free

    monkeypatch.setattr(usernames, "_made_up", lambda: "swiftfalcon482")
    with pytest.raises(RuntimeError):                                     # gives up rather than looping for ever
        usernames.suggest(db)


def test_only_admins_get_suggestions(client, db):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    auth.create_user(db, "mrsmith", PASSWORD, role="teacher", display_name="Mr Smith")
    auth.create_user(db, "calmcomet77", PASSWORD)

    assert client.get("/api/admin/username-suggestion").status_code == 401         # logged out
    for someone in ("calmcomet77", "mrsmith"):                                       # a student, a teacher
        login(client, someone)
        r = client.get("/api/admin/username-suggestion")
        assert r.status_code == 403 and "username" not in r.json()
        client.post("/api/auth/logout")

    login(client, "boss")
    made = client.get("/api/admin/username-suggestion").json()["username"]
    assert GAMERTAG.fullmatch(made) and made not in ("boss", "mrsmith", "calmcomet77")
    r = client.post("/api/admin/users", json={"username": made})
    assert r.status_code == 201 and r.json()["name"] == made


# --- students have no name ------------------------------------------------------------------------

def test_students_are_known_by_their_username_only(client, db):
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    login(client, "boss")

    r = client.post("/api/admin/users", json={"username": "calmcomet77", "name": "Maria Lopez"})
    assert r.status_code == 400 and "only a username" in r.json()["detail"]
    r = client.post("/api/admin/users", json={"username": "calmcomet77", "name": "Maria Lopez", "role": "student"})
    assert r.status_code == 400
    assert db.scalar(select(func.count()).select_from(User)) == 1                   # nothing was created

    student = client.post("/api/admin/users", json={"username": "calmcomet77", "name": "  "}).json()
    assert student["name"] == "calmcomet77"
    teacher = client.post("/api/admin/users", json={"username": "mrsmith", "name": "Mr Smith", "role": "teacher"}).json()
    assert teacher["name"] == "Mr Smith"                                             # teachers keep theirs

    r = client.patch(f"/api/admin/users/{student['id']}", json={"name": "Maria Lopez"})
    assert r.status_code == 400 and "only a username" in r.json()["detail"]
    assert client.patch(f"/api/admin/users/{student['id']}", json={"gpu_enabled": True}).json()["gpu_enabled"] is True
    assert client.patch(f"/api/admin/users/{teacher['id']}", json={"name": "Mr J. Smith"}).json()["name"] == "Mr J. Smith"

    with pytest.raises(auth.AccountError):                                           # the same rule below the API
        auth.create_user(db, "jose", PASSWORD, display_name="Jose Perez")
    stored = db.execute(select(User.username, User.display_name).where(User.role == "student")).all()
    assert stored == [("calmcomet77", "calmcomet77")]
    assert client.get("/api/admin/users").text.count("Maria") == 0
