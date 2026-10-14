"""Shared pytest fixtures: a real Postgres test database, per-test isolation, and data factories.

Tests run against a real Postgres database (no DB mocks) so that constraints,
foreign keys, and SQL behaviour match production.
"""
import os
import uuid
from datetime import date, time

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# --- Point the app at the TEST database BEFORE anything imports app.db.session. ---
# session.py reads DATABASE_URL at import time, and load_dotenv() never overrides a
# variable that is already set, so setting it here wins over the dev URL in .env.
# Default: reuse .env's DATABASE_URL (works on 5432 or 5433 setups) but swap the DB
# name to "encore_test". TEST_DATABASE_URL overrides that if someone needs to.
_dev_url = os.getenv("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
_test_url = os.getenv("TEST_DATABASE_URL") or (
    make_url(_dev_url).set(database="encore_test").render_as_string(hide_password=False)
    if _dev_url
    else None
)
if not _test_url:
    raise RuntimeError("Set DATABASE_URL in .env (or TEST_DATABASE_URL) to run the tests.")

# Safety guard: the fixtures below create and roll back data freely. Refusing any
# database not named *_test makes it impossible to run them against dev/prod data.
if not make_url(_test_url).database.endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against non-test database {make_url(_test_url).database!r}")
os.environ["DATABASE_URL"] = _test_url

# These imports must come after DATABASE_URL is set (see above).
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import engine, get_db  # noqa: E402
from app.models.concert import Concert  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_schema():
    """Build the schema with the real Alembic migrations, once per test run.

    Using migrations (not Base.metadata.create_all) means tests see exactly the
    schema production gets, including any constraints added by later migrations.
    alembic/env.py reads DATABASE_URL, which now points at the test DB.
    """
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db():
    """A session whose work is rolled back after each test, so tests never see each other's data.

    The outer transaction is never committed. "create_savepoint" makes any
    session.commit() inside app code commit only a SAVEPOINT, which the final
    rollback still undoes.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def make_app(db):
    """Build a FastAPI app with the given routers, wired to the rolled-back test session.

    Routers are included directly (rather than via app.main) so these tests don't
    depend on main.py/router.py wiring being finished.
    """
    def _make(*routers) -> FastAPI:
        app = FastAPI()
        for router in routers:
            app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: db
        return app

    return _make


# --- Data factories: real rows in the test DB, with valid defaults that tests can override. ---

@pytest.fixture
def make_user(db):
    def _make(**overrides) -> User:
        suffix = uuid.uuid4().hex[:8]  # unique username/email per call
        user = User(**{
            "name": "Test User",
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "password_hash": "not-a-real-hash",
            "joined_date": date(2026, 1, 1),
            **overrides,
        })
        db.add(user)
        db.flush()  # assigns the row in this transaction so FKs can reference it
        return user

    return _make


@pytest.fixture
def make_concert(db, make_user):
    def _make(**overrides) -> Concert:
        concert = Concert(**{
            "title": "Test Concert",
            "venue": "Test Venue",
            "city": "Grand Rapids",
            "state": "MI",
            "date": date(2026, 12, 1),
            "time": time(19, 30),
            "description": "A test concert.",
            "genre": "Rock",
            "owner_id": overrides.pop("owner_id", None) or make_user().id,
            "capacity": 100,
            "created_at": date(2026, 1, 1),
            "mood": "Happy",  # schema.sql's intended CHECK allows only Sad/Angry/Happy
            **overrides,
        })
        db.add(concert)
        db.flush()
        return concert

    return _make
