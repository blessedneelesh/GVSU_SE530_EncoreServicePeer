"""Integration tests for the profile API: HTTP -> FastAPI -> SQLAlchemy -> real Postgres."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.endpoints import users

# Exactly the fields each response may contain, so an accidental leak (like
# password_hash, or email on a public profile) fails the test.
PRIVATE_KEYS = {"id", "name", "username", "email", "bio", "joined_date"}
PUBLIC_KEYS = {"id", "name", "username", "bio", "joined_date"}


@pytest.fixture
def me(make_user):
    return make_user(name="Mario", bio="Rock fan")


@pytest.fixture
def client(make_app, me):
    """Client authenticated as `me` (auth is overridden; test_auth.py covers real tokens)."""
    app = make_app(users.router)
    app.dependency_overrides[get_current_user] = lambda: me
    return TestClient(app)


@pytest.fixture
def anon_client(make_app):
    return TestClient(make_app(users.router))


# ------------------------------------------------------------------ /users/me

def test_read_me_includes_email_but_not_password_hash(client, me):
    res = client.get("/api/v1/users/me")
    assert res.status_code == 200
    assert set(res.json()) == PRIVATE_KEYS
    assert res.json()["email"] == me.email


def test_me_routes_require_login(anon_client):
    assert anon_client.get("/api/v1/users/me").status_code == 401
    assert anon_client.patch("/api/v1/users/me", json={"bio": "x"}).status_code == 401


def test_update_changes_only_the_fields_sent(client, me, db):
    res = client.patch("/api/v1/users/me", json={"bio": "  Jazz now  "})

    assert res.status_code == 200
    assert res.json()["bio"] == "Jazz now"  # trimmed
    assert res.json()["name"] == "Mario"  # untouched
    db.refresh(me)
    assert me.bio == "Jazz now"


def test_update_null_means_no_change(client, me):
    res = client.patch("/api/v1/users/me", json={"name": None})
    assert res.status_code == 200
    assert res.json()["name"] == "Mario"


def test_update_empty_bio_clears_it(client):
    assert client.patch("/api/v1/users/me", json={"bio": ""}).json()["bio"] == ""


@pytest.mark.parametrize("body", [
    {"email": "new@example.com"},
    {"username": "new_name"},
    {"is_active": False},
    {"password_hash": "x"},
])
def test_update_rejects_fields_that_are_not_editable(client, body):
    assert client.patch("/api/v1/users/me", json=body).status_code == 422


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "x" * 101}, {"bio": "x" * 501}])
def test_update_enforces_lengths(client, body):
    assert client.patch("/api/v1/users/me", json=body).status_code == 422


# /users/{user_id}

def test_public_profile_hides_email(anon_client, make_user):
    other = make_user()
    res = anon_client.get(f"/api/v1/users/{other.id}")
    assert res.status_code == 200
    assert set(res.json()) == PUBLIC_KEYS


def test_unknown_user_is_404(anon_client):
    assert anon_client.get(f"/api/v1/users/{uuid.uuid4()}").status_code == 404


def test_deactivated_user_is_404(anon_client, make_user):
    gone = make_user(is_active=False)
    assert anon_client.get(f"/api/v1/users/{gone.id}").status_code == 404


def test_malformed_id_is_422(anon_client):
    assert anon_client.get("/api/v1/users/not-a-uuid").status_code == 422