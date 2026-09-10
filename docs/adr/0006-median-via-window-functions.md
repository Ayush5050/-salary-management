# ADR-0006 · Median in SQL via window functions

**Status:** Accepted · **Date:** 2026-09-10

## Context

Compensation is right-skewed: a handful of executives pull the mean well above what a typical
employee earns. In the seeded data the average total comp is \$101,076 while the median is \$70,740.
Reporting only the average would systematically overstate what ACME pays people, so the dashboard
shows both.

SQLite has no `PERCENTILE_CONT` or `MEDIAN`.

## Decision

Compute the median in SQL with window functions: rank rows within each group by compensation, count
the group, and keep only the row (or two) straddling the midpoint. Reduce those to a median in the
domain layer with `median_of_middle_values`.

## The midpoint condition

The ranks wanted are `(n+1)//2` and `(n+2)//2` — the same row twice when `n` is odd, two adjacent
rows when even. Written directly that needs integer division, whose semantics vary across backends
and across SQLAlchemy's type coercion.

Multiplying it out removes the division entirely. `r == (n+1)//2` holds exactly when
`2r ≤ n+1 ≤ 2r+1`, and `r == (n+2)//2` when `2r ≤ n+2 ≤ 2r+1`. The union simplifies to:

```
2r − 2  ≤  n  ≤  2r
```

which is pure integer comparison, identical on every backend. It is one line of SQL with the
derivation in the docstring above it.

## Reasoning

The aggregation has to happen in the database. Pulling 10,000 rows into Python to sort them would
work at this size and stop working at the next, and it would put the arithmetic somewhere the query
planner cannot help. The same query shape serves the org-wide summary — using a constant group
column — so there is one code path rather than two subtly different ones.

## Verification

This is the least obvious query in the system, so it is tested differentially rather than against
fixed numbers: `tests/test_analytics.py` compares the SQL median against a plain Python reference
implementation, for **every group of every dimension**, and separately asserts that both odd and
even sized groups are present in the fixture — because the parity boundary is exactly where the
midpoint condition could be wrong. `tests/test_statistics.py` independently exercises the reduction
at every group size from 1 to 11.

## Alternatives considered

**Sort in Python.** Simplest to read; rejected on scale, as above.

**A SQLite extension or a user-defined aggregate.** Ties the query to one backend, which contradicts
[ADR-0002](0002-sqlite-over-postgres.md)'s goal of keeping the migration path open.

**Approximate quantiles (t-digest and similar).** Appropriate at millions of rows; unnecessary here,
and an approximate salary median is a strange thing to show someone making pay decisions.

## Consequences

The median costs a second query per panel — measured at roughly 11ms for a full breakdown across all
groups, well inside the 150ms target. `PERCENTILE_CONT` becomes available on a PostgreSQL migration
and would be a legitimate simplification then; the differential tests would catch any behaviour
change in the swap.
