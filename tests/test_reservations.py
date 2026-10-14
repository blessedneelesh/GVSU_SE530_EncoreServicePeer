"""Tests for the Reservations API.

Two kinds:
- API integration tests: HTTP -> FastAPI -> reservation_service -> real Postgres, rolled back per test.
- Concurrency tests: many threads, each with its own session and REAL commits, because a
  row lock only matters between separate transactions. A rolled-back shared session can't show it.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.api.deps import get_current_user
from app.api.v1.endpoints import invoices
from app.db.session import SessionLocal
from app.models.concert import Concert
from app.models.invoice import Invoice
from app.models.user import User
from app.services.reservation_service import create_reservation
from tests.conftest import new_concert, new_user

# Exactly the fields a client may see; a full-set assert also catches accidental new leaks.
RESERVATION_KEYS = {"id", "concert_id", "seats", "created_at"}


@pytest.fixture
def booker(make_user):
    return make_user()


@pytest.fixture
def client_as(make_app):
    """Build a client authenticated as the given real User row (auth overridden, not mocked)."""
    def _client(user: User) -> TestClient:
        app = make_app(invoices.router)
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    return _client


@pytest.fixture
def client(client_as, booker):
    return client_as(booker)


@pytest.fixture
def hold_seats(db):
    """Insert an existing reservation directly, so tests can start from 'user already holds N'."""
    def _hold(concert: Concert, user: User, seats: int) -> None:
        db.add(Invoice(concert_id=concert.id, user_id=user.id, seats=seats, created_at=date(2026, 1, 1)))
        concert.reserved_count += seats
        db.flush()

    return _hold


def url(concert_id) -> str:
    return f"/api/v1/concerts/{concert_id}/reservations"


def seats_held(db, concert_id: str, user_id: str | None = None) -> int:
    """SUM(seats) of reservations for a concert (optionally one user's). The ground truth."""
    query = select(func.coalesce(func.sum(Invoice.seats), 0)).where(Invoice.concert_id == concert_id)
    if user_id is not None:
        query = query.where(Invoice.user_id == user_id)
    return db.scalar(query)


# ---------------------------------------------------------------- happy path

def test_reserve_returns_201_and_increments_reserved_count(client, db, booker, make_concert):
    concert = make_concert(capacity=10)

    res = client.post(url(concert.id), json={"seats": 2})

    assert res.status_code == 201
    body = res.json()
    assert set(body) == RESERVATION_KEYS
    assert body["concert_id"] == concert.id
    assert body["seats"] == 2
    # Server-set date. Accepts local or UTC "today" so the test isn't flaky near midnight;
    # the team convention is UTC (date.today() is local; raised on PR #11).
    assert body["created_at"] in {date.today().isoformat(), datetime.now(UTC).date().isoformat()}
    # Persisted and owned by the authenticated user; count moved by exactly `seats`.
    assert db.get(Invoice, body["id"]).user_id == booker.id
    assert concert.reserved_count == 2
    assert seats_held(db, concert.id) == 2


@pytest.mark.parametrize("seats", [1, 4])
def test_seat_count_boundaries_are_accepted(client, make_concert, seats):
    assert client.post(url(make_concert().id), json={"seats": seats}).status_code == 201


def test_user_id_in_body_cannot_book_for_someone_else(client, db, booker, make_user, make_concert):
    # BOLA / mass-assignment check: identity must come from the token only.
    victim = make_user()
    concert = make_concert()

    res = client.post(url(concert.id), json={"seats": 1, "user_id": victim.id})

    # The schema ignores unknown fields (no extra="forbid"), so this succeeds, but for the caller.
    assert res.status_code == 201
    assert db.get(Invoice, res.json()["id"]).user_id == booker.id
    assert seats_held(db, concert.id, victim.id) == 0


def test_filling_exactly_to_capacity_is_allowed(client, make_concert, make_user, hold_seats):
    concert = make_concert(capacity=5)
    hold_seats(concert, make_user(), 4)  # someone else holds 4 of 5

    assert client.post(url(concert.id), json={"seats": 1}).status_code == 201
    assert concert.reserved_count == concert.capacity


def test_per_user_cap_is_per_user_not_global(client_as, make_user, make_concert, hold_seats):
    concert = make_concert()
    hold_seats(concert, make_user(), 4)  # another user is at their cap

    assert client_as(make_user()).post(url(concert.id), json={"seats": 4}).status_code == 201


# ---------------------------------------------------------------- rejections (nothing may change)

@pytest.mark.parametrize("body", [{"seats": 0}, {"seats": 5}, {"seats": -1}, {"seats": 2.5}, {"seats": "two"}, {}])
def test_invalid_seat_counts_are_422(client, db, make_concert, body):
    concert = make_concert()

    assert client.post(url(concert.id), json=body).status_code == 422
    assert seats_held(db, concert.id) == 0


def test_sold_out_is_409_and_changes_nothing(client, db, booker, make_concert, make_user, hold_seats):
    concert = make_concert(capacity=5)
    hold_seats(concert, make_user(), 4)

    res = client.post(url(concert.id), json={"seats": 2})  # 4 + 2 > 5

    assert res.status_code == 409
    assert concert.reserved_count == 4
    assert seats_held(db, concert.id, booker.id) == 0  # no orphan reservation


def test_exceeding_four_seats_per_user_is_409(client, db, booker, make_concert, hold_seats):
    concert = make_concert()
    hold_seats(concert, booker, 3)

    assert client.post(url(concert.id), json={"seats": 2}).status_code == 409  # 3 + 2 > 4
    assert seats_held(db, concert.id, booker.id) == 3
    assert concert.reserved_count == 3
    # Topping up to exactly 4 is still fine.
    assert client.post(url(concert.id), json={"seats": 1}).status_code == 201


def test_cancelled_concert_is_409(client, db, make_concert):
    concert = make_concert(cancelled=True)

    assert client.post(url(concert.id), json={"seats": 1}).status_code == 409
    assert seats_held(db, concert.id) == 0


@pytest.mark.xfail(strict=True, reason="Past-date rule not in reservation_service yet (asked Noah)")
def test_past_concert_is_409(client, make_concert):
    yesterday = datetime.now(UTC).date() - timedelta(days=1)

    assert client.post(url(make_concert(date=yesterday).id), json={"seats": 1}).status_code == 409


def test_unknown_concert_is_404(client):
    assert client.post(url(uuid.uuid4()), json={"seats": 1}).status_code == 404


def test_malformed_concert_id_is_422(client):
    # Rejected by the UUID path type before any DB query runs.
    assert client.post(url("not-a-uuid"), json={"seats": 1}).status_code == 422


def test_requires_authentication(make_app, make_concert):
    # No override: the real get_current_user runs and sees no Bearer token.
    anon = TestClient(make_app(invoices.router))

    assert anon.post(url(make_concert().id), json={"seats": 1}).status_code == 401


# ---------------------------------------------------------------- concurrency (real commits)

@pytest.fixture
def committed():
    """Insert rows with a real COMMIT (visible to every connection); delete them afterwards.

    Teardown deletes in reverse order: bookers (their reservations cascade), then the
    concert, then its owner (concerts.owner_id is ON DELETE RESTRICT).
    """
    created: list[tuple[type, str]] = []

    def _add(obj):
        with SessionLocal(expire_on_commit=False) as session:  # keep .id readable after commit
            session.add(obj)
            session.commit()
        created.append((type(obj), obj.id))
        return obj

    yield _add

    with SessionLocal() as session:
        for model, row_id in reversed(created):
            session.execute(delete(model).where(model.id == row_id))
        session.commit()


def book_concurrently(requests: list[tuple[str, str, int]]) -> list[int]:
    """Run create_reservation for each (concert_id, user_id, seats) in parallel threads.

    Each thread has its own session (= its own DB connection and transaction), like real
    concurrent HTTP requests. A barrier releases them all at once to maximise overlap,
    which is what makes a check-then-act race show up. Returns status codes (201 = booked).
    """
    barrier = threading.Barrier(len(requests))

    def book(concert_id: str, user_id: str, seats: int) -> int:
        with SessionLocal() as session:
            barrier.wait(timeout=10)
            try:
                create_reservation(session, concert_id, user_id, seats)
                return 201
            except HTTPException as exc:
                session.rollback()  # release the row lock for the next waiter
                return exc.status_code

    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        futures = [pool.submit(book, *r) for r in requests]
        return [f.result() for f in futures]  # re-raises any unexpected error (e.g. a 500 cause)


def test_concurrent_bookings_never_oversell(committed):
    owner = committed(new_user())
    concert = committed(new_concert(owner.id, capacity=4))
    bookers = [committed(new_user()) for _ in range(8)]

    results = book_concurrently([(concert.id, b.id, 1) for b in bookers])

    assert sorted(results) == [201] * 4 + [409] * 4
    with SessionLocal() as session:
        # reserved_count must equal the real seat total: catches lost updates, which the
        # DB CHECK (reserved_count <= capacity) alone would NOT catch.
        assert session.get(Concert, concert.id).reserved_count == 4
        assert seats_held(session, concert.id) == 4


def test_concurrent_bookings_by_one_user_respect_the_cap(committed):
    owner = committed(new_user())
    concert = committed(new_concert(owner.id, capacity=100))
    scalper = committed(new_user())

    # 5 parallel requests for 2 seats each: only 2 can fit under the 4-per-user cap.
    results = book_concurrently([(concert.id, scalper.id, 2)] * 5)

    assert sorted(results) == [201] * 2 + [409] * 3
    with SessionLocal() as session:
        assert seats_held(session, concert.id, scalper.id) == 4
        assert session.get(Concert, concert.id).reserved_count == 4
