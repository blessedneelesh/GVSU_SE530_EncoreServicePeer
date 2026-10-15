"""Integration tests for the auth API: HTTP -> FastAPI -> SQLAlchemy -> real Postgres."""
from datetime import timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.v1.endpoints import auth
from app.core.security import hash_password, hash_refresh_token, utcnow
from app.models.auth import RefreshToken
from app.models.user import User

PASSWORD = "Encore123"
USER_KEYS = {"id", "name", "username", "email", "bio", "joined_date"}

# A tiny protected route, so tests can check whether an access token still works.
probe = APIRouter()


@probe.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id}


@pytest.fixture
def client(make_app):
    return TestClient(make_app(auth.router, probe))


@pytest.fixture
def account(make_user):
    """A user with a real password hash, so login can succeed."""
    return make_user(email="mario@example.com", password_hash=hash_password(PASSWORD))


def login(client, email="mario@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def signup_body(**overrides):
    return {"name": "Mario", "username": "mario_o", "email": "Mario@Example.com", "password": PASSWORD, **overrides}


# ------------------------------------------------------------------ register

def test_register_creates_user_with_hashed_password(client, db):
    res = client.post("/api/v1/auth/register", json=signup_body())

    assert res.status_code == 201
    body = res.json()
    assert set(body) == USER_KEYS  # password_hash never appears
    assert body["email"] == "mario@example.com"  # lowercased

    stored = db.get(User, body["id"])
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash


def test_register_duplicate_email_is_409(client, make_user):
    make_user(email="mario@example.com")
    res = client.post("/api/v1/auth/register", json=signup_body())
    assert res.status_code == 409


def test_register_duplicate_username_is_409(client, make_user):
    make_user(username="mario_o")
    res = client.post("/api/v1/auth/register", json=signup_body())
    assert res.status_code == 409


def test_register_weak_password_is_422(client):
    res = client.post("/api/v1/auth/register", json=signup_body(password="password"))
    assert res.status_code == 422


def test_register_rejects_extra_fields(client):
    res = client.post("/api/v1/auth/register", json=signup_body(is_active=False))
    assert res.status_code == 422


# --------------------------------------------------------------------- login

def test_login_returns_working_tokens(client, account, db):
    res = login(client)

    assert res.status_code == 200
    tokens = res.json()
    assert tokens["token_type"] == "bearer"
    assert client.get("/api/v1/me", headers=bearer(tokens["access_token"])).json() == {"id": account.id}

    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == account.id))
    assert stored.token_hash == hash_refresh_token(tokens["refresh_token"])
    assert stored.token_hash != tokens["refresh_token"]  # raw token is never stored
    assert account.last_login_at is not None


def test_login_accepts_email_in_any_case(client, account):
    assert login(client, email="MARIO@example.com").status_code == 200


@pytest.mark.parametrize("email,password", [
    ("mario@example.com", "WrongPass1"),
    ("nobody@example.com", PASSWORD),
])
def test_login_failures_look_identical(client, account, email, password):
    res = login(client, email=email, password=password)
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid email or password"}


def test_login_inactive_user_is_401(client, account, db):
    account.is_active = False
    db.flush()
    assert login(client).status_code == 401


# ------------------------------------------------------------------- refresh

def test_refresh_rotates_tokens(client, account):
    old = login(client).json()

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})

    assert res.status_code == 200
    new = res.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert client.get("/api/v1/me", headers=bearer(new["access_token"])).status_code == 200


def test_reused_refresh_token_revokes_every_session(client, account):
    old = login(client).json()
    new = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).json()

    # Someone replays the old (already rotated) token...
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert replay.status_code == 401

    # ...so the legitimate new token is revoked too.
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert after.status_code == 401


def test_refresh_unknown_token_is_401(client):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "made-up"})
    assert res.status_code == 401


def test_refresh_expired_token_is_401(client, account, db):
    tokens = login(client).json()
    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == account.id))
    stored.expires_at = utcnow() - timedelta(seconds=1)
    db.flush()

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401


# -------------------------------------------------------------------- logout

def test_logout_revokes_access_and_refresh_tokens(client, account):
    tokens = login(client).json()
    headers = bearer(tokens["access_token"])

    res = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers)

    assert res.status_code == 204
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_logout_requires_access_token(client):
    res = client.post("/api/v1/auth/logout", json={"refresh_token": "anything"})
    assert res.status_code == 401


def test_logout_cannot_revoke_another_users_refresh_token(client, account, make_user):
    other = make_user(email="other@example.com", password_hash=hash_password(PASSWORD))
    mine = login(client).json()
    theirs = login(client, email=other.email).json()

    client.post("/api/v1/auth/logout", json={"refresh_token": theirs["refresh_token"]},
                headers=bearer(mine["access_token"]))

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": theirs["refresh_token"]})
    assert res.status_code == 200