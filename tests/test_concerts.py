"""Integration tests for the Concerts API: HTTP -> FastAPI -> SQLAlchemy -> real Postgres."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.endpoints import concerts
from app.models.concert import Concert

BASE = "/api/v1/concerts"

# Everything a client needs to see for a concert. A subset check (not equality) so
# adding a column later doesn't break these tests, but dropping one does.
CONCERT_KEYS = {
    "id", "title", "venue", "city", "state", "date", "time", "description", "genre",
    "owner_id", "capacity", "reserved_count", "image_url", "cancelled", "created_at", "mood",
}


def valid_payload(**overrides) -> dict:
    return {
        "title": "Midnight Riff Live",
        "venue": "The Roxy Hall",
        "city": "Chicago",
        "state": "IL",
        "date": "2099-11-14",
        "time": "20:00",
        "capacity": 100,
        "mood": "Happy",
        "description": "An evening of high-energy rock.",
        "genre": "Rock",
        **overrides,
    }


@pytest.fixture
def owner(make_user):
    return make_user(username="owner")


@pytest.fixture
def make_client(make_app):
    """Build a client authenticated as the given user (a real User row; auth is overridden, not mocked)."""
    def _make(user) -> TestClient:
        app = make_app(concerts.router)
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client, owner):
    return make_client(owner)


@pytest.fixture
def anon_client(make_app):
    """Client with no auth override, so the real get_current_user decides."""
    return TestClient(make_app(concerts.router))


# ---------------------------------------------------------------- POST

def test_create_returns_201_and_persists_the_concert(client, db, owner):
    res = client.post(f"{BASE}/", json=valid_payload())

    assert res.status_code == 201
    body = res.json()
    assert CONCERT_KEYS <= set(body)
    assert body["title"] == "Midnight Riff Live"
    assert body["mood"] == "Happy"
    assert body["capacity"] == 100
    assert body["reserved_count"] == 0
    assert body["cancelled"] is False
    # Persisted, not just echoed back.
    stored = db.get(Concert, body["id"])
    assert stored is not None
    assert stored.venue == "The Roxy Hall"
    assert stored.date == date(2099, 11, 14)


def test_create_takes_owner_from_auth(client, owner):
    res = client.post(f"{BASE}/", json=valid_payload())

    assert res.json()["owner_id"] == owner.id


def test_create_ignores_client_supplied_owner_id(client, owner, make_user):
    """The frontend must not be able to create a concert on someone else's behalf."""
    someone_else = make_user()

    res = client.post(f"{BASE}/", json=valid_payload(owner_id=someone_else.id))

    assert res.status_code == 201
    assert res.json()["owner_id"] == owner.id


def test_create_sets_created_at_to_today(client):
    res = client.post(f"{BASE}/", json=valid_payload(created_at="2000-01-01"))

    assert res.json()["created_at"] == date.today().isoformat()


def test_create_requires_authentication(anon_client, db):
    res = anon_client.post(f"{BASE}/", json=valid_payload())

    assert res.status_code == 401
    assert db.query(Concert).count() == 0


@pytest.mark.parametrize("mood", ["Excited", "happy", "", "HAPPY"])
def test_create_rejects_invalid_mood(client, mood):
    res = client.post(f"{BASE}/", json=valid_payload(mood=mood))

    assert res.status_code == 422


@pytest.mark.parametrize("mood", ["Sad", "Angry", "Happy"])
def test_create_accepts_each_allowed_mood(client, mood):
    res = client.post(f"{BASE}/", json=valid_payload(mood=mood))

    assert res.status_code == 201
    assert res.json()["mood"] == mood


@pytest.mark.parametrize("capacity", [0, -5])
def test_create_rejects_non_positive_capacity(client, capacity):
    res = client.post(f"{BASE}/", json=valid_payload(capacity=capacity))

    assert res.status_code == 422


@pytest.mark.parametrize("missing", ["title", "venue", "city", "state", "date", "time", "capacity", "mood"])
def test_create_rejects_missing_required_field(client, missing):
    payload = valid_payload()
    del payload[missing]

    res = client.post(f"{BASE}/", json=payload)

    assert res.status_code == 422


# ---------------------------------------------------------------- GET list

def test_list_returns_all_concerts(client, make_concert):
    first = make_concert(title="First")
    second = make_concert(title="Second")

    res = client.get(f"{BASE}/")

    assert res.status_code == 200
    ids = {c["id"] for c in res.json()}
    assert {first.id, second.id} <= ids


def test_list_is_public(anon_client, make_concert):
    concert = make_concert()

    res = anon_client.get(f"{BASE}/")

    assert res.status_code == 200
    assert concert.id in {c["id"] for c in res.json()}


# ---------------------------------------------------------------- GET one

def test_read_returns_the_concert(client, make_concert):
    concert = make_concert(title="Blue Note Sessions", mood="Sad")

    res = client.get(f"{BASE}/{concert.id}")

    assert res.status_code == 200
    body = res.json()
    assert CONCERT_KEYS <= set(body)
    assert body["id"] == concert.id
    assert body["title"] == "Blue Note Sessions"
    assert body["mood"] == "Sad"


def test_read_is_public(anon_client, make_concert):
    concert = make_concert()

    assert anon_client.get(f"{BASE}/{concert.id}").status_code == 200


def test_read_unknown_concert_returns_404(client):
    res = client.get(f"{BASE}/{uuid.uuid4()}")

    assert res.status_code == 404


def test_read_malformed_id_returns_422(client):
    res = client.get(f"{BASE}/not-a-uuid")

    assert res.status_code == 422


# ---------------------------------------------------------------- PATCH cancel

def test_cancel_by_owner_marks_concert_cancelled(client, db, owner, make_concert):
    concert = make_concert(owner_id=owner.id)

    res = client.patch(f"{BASE}/{concert.id}/cancel")

    assert res.status_code == 200
    assert res.json()["cancelled"] is True
    db.refresh(concert)
    assert concert.cancelled is True


def test_cancel_by_non_owner_returns_403_and_changes_nothing(make_client, db, owner, make_user, make_concert):
    concert = make_concert(owner_id=owner.id)
    intruder = make_user(username="intruder")

    res = make_client(intruder).patch(f"{BASE}/{concert.id}/cancel")

    assert res.status_code == 403
    db.refresh(concert)
    assert concert.cancelled is False


def test_cancel_twice_returns_409(client, owner, make_concert):
    concert = make_concert(owner_id=owner.id, cancelled=True)

    res = client.patch(f"{BASE}/{concert.id}/cancel")

    assert res.status_code == 409


def test_cancel_unknown_concert_returns_404(client):
    res = client.patch(f"{BASE}/{uuid.uuid4()}/cancel")

    assert res.status_code == 404


def test_cancel_requires_authentication(anon_client, db, make_concert):
    concert = make_concert()

    res = anon_client.patch(f"{BASE}/{concert.id}/cancel")

    assert res.status_code == 401
    db.refresh(concert)
    assert concert.cancelled is False


# ---------------------------------------------------------------- GET location-weather

def test_location_weather_unknown_concert_returns_404(client):
    """Only the not-found path is tested here: the happy path calls external APIs (Maps/weather)."""
    res = client.get(f"{BASE}/{uuid.uuid4()}/location-weather")

    assert res.status_code == 404
