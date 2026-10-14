"""Integration tests for the Comments API: HTTP -> FastAPI -> SQLAlchemy -> real Postgres."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.endpoints import comments
from app.models.comment import Comment

# Exactly the fields a client may see. Asserting the full key set (not just "email
# is absent") also catches any future field that leaks by accident.
COMMENT_KEYS = {"id", "concert_id", "user_id", "username", "text", "created_at"}


@pytest.fixture
def author(make_user):
    return make_user(username="alice")


@pytest.fixture
def client(make_app, author):
    """Client authenticated as `author` (a real User row; auth is overridden, not mocked)."""
    app = make_app(comments.router)
    app.dependency_overrides[get_current_user] = lambda: author
    return TestClient(app)


@pytest.fixture
def anon_client(make_app):
    """Client with no auth override, so the real get_current_user decides."""
    return TestClient(make_app(comments.router))


@pytest.fixture
def make_comment(db, author):
    """Insert a comment directly so tests control created_at precisely."""
    def _make(concert, text="hi", created_at=None, user=None) -> Comment:
        comment = Comment(
            concert_id=concert.id,
            user_id=(user or author).id,
            text=text,
            created_at=created_at or datetime(2026, 10, 1, 12, 0),
        )
        db.add(comment)
        db.flush()
        return comment

    return _make


def url(concert_id) -> str:
    return f"/api/v1/concerts/{concert_id}/comments"


# ---------------------------------------------------------------- POST

def test_create_returns_201_with_author_taken_from_auth(client, db, author, make_concert):
    concert = make_concert()

    res = client.post(url(concert.id), json={"text": "  Great show!  "})

    assert res.status_code == 201
    body = res.json()
    assert set(body) == COMMENT_KEYS
    assert body["concert_id"] == concert.id
    assert body["user_id"] == author.id
    assert body["username"] == "alice"
    assert body["text"] == "Great show!"  # surrounding whitespace stripped
    # Persisted, not just echoed back.
    assert db.get(Comment, body["id"]).text == "Great show!"


def test_create_sets_created_at_server_side_in_utc(client, make_concert):
    before = datetime.now(UTC)
    res = client.post(url(make_concert().id), json={"text": "hi"})
    created = datetime.fromisoformat(res.json()["created_at"])

    # Timezone-aware (so clients don't misread it as local time) and roughly "now".
    assert created.utcoffset() == timedelta(0)
    assert before - timedelta(seconds=5) <= created <= datetime.now(UTC) + timedelta(seconds=5)


@pytest.mark.parametrize("extra", [
    {"user_id": str(uuid.uuid4())},       # impersonate another user (mass assignment / BOLA)
    {"created_at": "2000-01-01T00:00:00"},  # backdate a comment
    {"id": str(uuid.uuid4())},             # choose our own primary key
])
def test_create_rejects_client_supplied_server_fields(client, make_concert, extra):
    res = client.post(url(make_concert().id), json={"text": "hi", **extra})
    assert res.status_code == 422


def test_create_requires_auth(anon_client, make_concert):
    res = anon_client.post(url(make_concert().id), json={"text": "hi"})
    assert res.status_code == 401


def test_create_on_unknown_concert_returns_404(client):
    res = client.post(url(uuid.uuid4()), json={"text": "hi"})
    # Check the detail too: a missing *route* is also a 404, so status alone can pass vacuously.
    assert res.status_code == 404
    assert res.json() == {"detail": "Concert not found"}


def test_create_on_cancelled_concert_is_allowed(client, make_concert):
    # Product rule: the thread stays open after a show ends or is cancelled.
    res = client.post(url(make_concert(cancelled=True).id), json={"text": "Refund?"})
    assert res.status_code == 201


@pytest.mark.parametrize("payload", [
    {},                        # missing text
    {"text": None},
    {"text": 123},             # no silent int -> str coercion
    {"text": ""},
    {"text": "   \n\t "},      # whitespace only becomes empty after stripping
    {"text": "x" * 1001},      # one over the limit
    {"text": "bad\x00byte"},   # Postgres TEXT cannot store NUL; must be a 422, not a 500
])
def test_create_rejects_invalid_text(client, make_concert, payload):
    res = client.post(url(make_concert().id), json=payload)
    assert res.status_code == 422


def test_create_accepts_text_at_max_length(client, make_concert):
    res = client.post(url(make_concert().id), json={"text": "x" * 1000})
    assert res.status_code == 201


# ---------------------------------------------------------------- GET

def test_list_is_public_and_newest_first(anon_client, make_concert, make_comment):
    concert = make_concert()
    make_comment(concert, "old", datetime(2026, 10, 1, 9, 0))
    make_comment(concert, "new", datetime(2026, 10, 1, 11, 0))
    make_comment(concert, "mid", datetime(2026, 10, 1, 10, 0))

    res = anon_client.get(url(concert.id))

    assert res.status_code == 200
    assert [c["text"] for c in res.json()] == ["new", "mid", "old"]
    assert all(set(c) == COMMENT_KEYS for c in res.json())


def test_list_breaks_timestamp_ties_by_id_deterministically(client, make_concert, make_comment):
    concert = make_concert()
    same_time = datetime(2026, 10, 1, 12, 0)
    ids = [make_comment(concert, f"c{i}", same_time).id for i in range(3)]

    first = [c["id"] for c in client.get(url(concert.id)).json()]
    second = [c["id"] for c in client.get(url(concert.id)).json()]

    # Without the id tiebreaker Postgres may return ties in any order, which would make
    # pagination skip or repeat comments.
    assert first == second == sorted(ids, reverse=True)


def test_list_only_includes_this_concerts_comments(client, make_concert, make_comment):
    mine, other = make_concert(), make_concert()
    make_comment(mine, "mine")
    make_comment(other, "other")

    assert [c["text"] for c in client.get(url(mine.id)).json()] == ["mine"]


def test_list_paginates_with_limit_and_offset(client, make_concert, make_comment):
    concert = make_concert()
    for hour in range(5):  # c0 oldest ... c4 newest
        make_comment(concert, f"c{hour}", datetime(2026, 10, 1, hour, 0))

    page = client.get(url(concert.id), params={"limit": 2, "offset": 1}).json()
    past_end = client.get(url(concert.id), params={"offset": 5}).json()

    assert [c["text"] for c in page] == ["c3", "c2"]
    assert past_end == []


def test_list_defaults_to_20_items(client, make_concert, make_comment):
    concert = make_concert()
    for minute in range(25):
        make_comment(concert, f"c{minute}", datetime(2026, 10, 1, 12, minute))

    assert len(client.get(url(concert.id)).json()) == 20


@pytest.mark.parametrize("params", [
    {"limit": 0},
    {"limit": 101},            # cap prevents one request dumping a huge thread
    {"offset": -1},
    {"offset": 10**20},        # beyond Postgres BIGINT; must be a 422, not a 500
    {"limit": "abc"},
])
def test_list_rejects_bad_pagination(client, make_concert, params):
    res = client.get(url(make_concert().id), params=params)
    assert res.status_code == 422


def test_list_on_unknown_concert_returns_404(client):
    res = client.get(url(uuid.uuid4()))
    assert res.status_code == 404
    assert res.json() == {"detail": "Concert not found"}


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_non_uuid_concert_id_returns_422(client, method):
    res = client.request(method, url("not-a-uuid"), json={"text": "hi"})
    assert res.status_code == 422
