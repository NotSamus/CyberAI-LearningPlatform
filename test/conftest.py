"""Shared fixtures.

The tests never reach the platform's own database, in development or on the server. They run on a
Postgres of their own (deploy/docker-compose.test.yml; ./check.sh starts it), where each run makes
a throwaway database and drops it afterwards. Tests that need a database are skipped when that
Postgres is not running."""
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

# The test Postgres, and the platform's database as the app would find it (dev's when nothing is set).
TEST_SERVER_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://test:test-only-password@localhost:5434/postgres")
PLATFORM_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://platform:dev-db-password@localhost:5433/platform")


def _server(url: str) -> tuple:
    parsed = make_url(url)
    host = "localhost" if parsed.host in (None, "", "127.0.0.1", "::1") else parsed.host
    return host, parsed.port or 5432


if _server(TEST_SERVER_URL) == _server(PLATFORM_URL):
    pytest.exit("TEST_DATABASE_URL points at the platform's own Postgres: the tests must never run there.", returncode=2)
# Before the app is imported: everything in it that opens a database (its engine, background
# grading, the command line tool run by some tests) then finds the test Postgres, never another.
os.environ["DATABASE_URL"] = TEST_SERVER_URL

from fastapi.testclient import TestClient  # noqa: E402  (after DATABASE_URL is set, on purpose)

from app import auth, submissions  # noqa: E402
from app.db import get_db  # noqa: E402
from app.jupyter import hub_client  # noqa: E402
from app.main import app  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def run_alembic(*args: str, db_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SQL_DIR, env={**os.environ, "DATABASE_URL": db_url}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@contextmanager
def throwaway_database():
    """A new, empty database on the test Postgres, dropped afterwards."""
    url = make_url(TEST_SERVER_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    name = f"test_{uuid.uuid4().hex[:8]}"
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        admin.dispose()
        pytest.skip(f"The test Postgres is not reachable at {url.host}:{url.port} (./check.sh starts it, or: "
                    "docker compose -f deploy/docker-compose.test.yml up -d --wait)")
    try:
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def notebook_file(*cells: str) -> bytes:
    """A small valid .ipynb file with one code cell per argument."""
    return json.dumps({
        "cells": [
            {"cell_type": "code", "id": f"cell-{n}", "metadata": {}, "source": source, "outputs": [], "execution_count": None}
            for n, source in enumerate(cells or ("print('hello')",))
        ],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
    }).encode()


@pytest.fixture(autouse=True)
def no_leftover_login_attempts():
    """The login attempt counters live in memory: start every test with none."""
    auth._attempts.clear()


@pytest.fixture(scope="session")
def alembic():
    return run_alembic


@pytest.fixture
def empty_db_url():
    with throwaway_database() as url:
        yield url


@pytest.fixture(scope="session")
def migrated_db_url():
    with throwaway_database() as url:
        run_alembic("upgrade", "head", db_url=url)
        yield url


@pytest.fixture
def db(migrated_db_url, monkeypatch):
    """A session on the migrated test database. The app uses that database too for this test, and
    every table is emptied afterwards."""
    engine = create_engine(migrated_db_url)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def get_test_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    monkeypatch.setattr(submissions, "session_factory", TestSession)     # background grading uses this database too
    with TestSession() as session:
        yield session
    app.dependency_overrides.pop(get_db, None)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, sessions, assignments, assignment_students, assignment_opens, courses, course_students, announcements, submissions, "
                          "lessons, lesson_images, lesson_progress, lesson_answers RESTART IDENTITY CASCADE"))
    engine.dispose()


# --- people and a stand-in hub, for the tests of assignments, courses and grading -------------------

PASSWORD = "correct horse battery"
API_DIR = Path(__file__).resolve().parents[1] / "api"


def browser(username: str) -> TestClient:
    """A separate browser, logged in as `username`."""
    client = TestClient(app, follow_redirects=False)
    assert client.post("/api/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return client


@pytest.fixture
def people(db):
    """A teacher (id 1) and two students, maria (id 2) and jose (id 3), each in their own browser."""
    auth.create_user(db, "teacher", PASSWORD, role="teacher")
    auth.create_user(db, "maria", PASSWORD, display_name="Maria Lopez")
    auth.create_user(db, "jose", PASSWORD, display_name="Jose Perez")
    return browser("teacher"), browser("maria"), browser("jose")


@pytest.fixture
def hub(monkeypatch):
    """Stands in for JupyterHub: `files` maps (hub username, path in their home) to the file's bytes."""
    files: dict[tuple[str, str], bytes] = {}

    async def ensure_user(username, groups):
        pass

    async def start_server(username, server, wait_seconds=90):
        return True

    async def has_file(username, server, path):
        return (username, path) in files

    async def put_file(username, server, path, content):
        files[(username, path)] = content

    async def get_file(username, server, path, max_bytes):
        content = files.get((username, path))
        if content is not None and len(content) > max_bytes:
            raise hub_client.FileTooLarge(path)
        return content

    for fake in (ensure_user, start_server, has_file, put_file, get_file):
        monkeypatch.setattr(hub_client, fake.__name__, fake)
    return files


def upload(client, title="Loops", name="lab.ipynb", content=None, **fields):
    return client.post(
        "/api/teach/assignments",
        data={"title": title, **fields},
        files={"file": (name, notebook_file() if content is None else content)},
    )
