"""Shared fixtures. Tests that need a database get a throwaway one on the dev Postgres
(./dev.sh starts it) and are skipped when that is not running."""
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app import auth, submissions
from app.config import DATABASE_URL
from app.db import get_db
from app.jupyter import hub_client
from app.main import app

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def run_alembic(*args: str, db_url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SQL_DIR, env={**os.environ, "DATABASE_URL": db_url}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@contextmanager
def throwaway_database():
    """A new, empty database on the same server as DATABASE_URL, dropped afterwards."""
    url = make_url(DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    name = f"test_{uuid.uuid4().hex[:8]}"
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        admin.dispose()
        pytest.skip(f"Postgres is not reachable at {url.host}:{url.port} (start it with ./dev.sh)")
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
