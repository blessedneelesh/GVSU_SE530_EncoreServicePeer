# Encore Service

## Running tests

Tests run against a real Postgres database named `encore_test` (separate from `encore_db`).
The test DB URL is your `.env` `DATABASE_URL` with the database name swapped to `encore_test`
(set `TEST_DATABASE_URL` to override). Tests refuse to run against any DB whose name doesn't end in `_test`.

One-time setup (after `.env` exists and `docker compose up -d` is running):

```bash
pip install -r requirements-dev.txt
docker compose exec db createdb -U postgres encore_test
```

Run:

```bash
pytest -q
```

The test run applies the Alembic migrations to `encore_test` itself. Most tests roll back their data afterwards;
the concurrency tests in `tests/test_reservations.py` commit real rows (row locks only work across transactions)
and delete them afterwards.
