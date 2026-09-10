# ADR-0002 · SQLite rather than PostgreSQL

**Status:** Accepted · **Date:** 2026-09-10

## Context

The brief allows any relational database and names SQLite explicitly. The dataset is 10,000
employees with a single-user persona. The system must also be trivially runnable by a reviewer.

## Decision

SQLite, accessed through SQLAlchemy Core/ORM using portable SQL, with `foreign_keys=ON` and WAL
journalling applied per connection.

## Reasoning

At 10,000 rows the entire table is a few megabytes; the measured p95 across every endpoint is under
12ms (see [performance.md](../performance.md)). PostgreSQL would add a service to run, a container
to orchestrate, and a connection-pooling story, and would not make a single query in this system
faster at this scale.

More importantly for a take-home: `git clone && make setup && make seed` has to work on a reviewer's
machine without Docker or a database daemon. SQLite makes that a hard guarantee rather than a hope.

## Keeping the exit open

The swap is a connection-string change, and the code is written so nothing else has to move:

- No SQLite-specific SQL. The one place where dialects genuinely differ — integer division inside
  the median query — is written to avoid division entirely
  (see [ADR-0006](0006-median-via-window-functions.md)).
- The pragma hook is registered per engine and gated on the driver, so a PostgreSQL URL is a no-op
  there rather than an error.
- Every engine is built by one factory, so tests and production cannot diverge in configuration.
  This was not hypothetical: an earlier class-level pragma listener meant foreign keys were enforced
  only when `app.db` happened to have been imported, and were silently off in tests. A test caught
  it, and the single-factory design is the fix.

## Consequences

Single-writer concurrency, which is correct for one HR Manager and wrong for a team — the trigger to
migrate. No native `PERCENTILE_CONT`, hence the windowed median. `Numeric` on SQLite would round-trip
through float, which is one of several reasons money is stored as integers
([ADR-0003](0003-money-as-integer-minor-units.md)).
