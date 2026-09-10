# ADR-0004 · A stored, indexed USD total on the employee row

**Status:** Accepted · **Date:** 2026-09-10

## Context

Total compensation in USD is the system's most-used number. It is sorted by (the default question is
"who are the highest paid?"), range-filtered on, summed, and used for every median and every
histogram bucket.

Computing it requires joining `currencies` and multiplying: `(base + bonus) × usd_rate_scaled`.

## Decision

Store the derived value on the employee row as `total_comp_usd_fx_scaled`, index it, and maintain it
in exactly one function — `app.domain.compensation.total_comp_usd_fx_scaled` — which every write path
funnels through.

## Reasoning

A computed expression across a join cannot be served by an index. Sorting the employee list by USD
compensation would mean the database joins, multiplies and sorts all 10,000 rows for **every page**,
and the same for every range filter. With the column stored, `EXPLAIN QUERY PLAN` confirms:

```
sort by USD comp    SCAN employees USING INDEX ix_employees_total_comp_usd_fx_scaled
comp range filter   SEARCH employees USING COVERING INDEX ix_employees_total_comp_usd_fx_scaled
```

The column is kept in FX-scaled space rather than plain USD minor units so `SUM` over it stays exact
— see [ADR-0003](0003-money-as-integer-minor-units.md).

## The risk, and what contains it

Derived stored state can go stale. Three things keep it honest:

1. **One writer.** A single function computes it; `_apply_draft` is the only code that assigns it,
   and both create and replace go through `_apply_draft`. There is no second expression to drift.
2. **Every input change triggers recomputation.** Including the subtle case — the salary numbers
   unchanged but the currency changed — which has its own test.
3. **A test re-derives it for every seeded row** from that row's own salary and its currency's rate
   (`tests/test_seed.py::TestDerivedColumnInvariant`). If the two ever disagree, the suite fails.

## Alternatives considered

**Compute on read.** Always correct, never stale. Rejected on measurement: it makes the primary
sort and the range filter unindexable at exactly the scale the brief specifies.

**A generated/computed column.** Attractive, but it would have to reference another table, which
neither SQLite nor PostgreSQL permits in a generated column.

**Denormalise the rate onto the employee row.** Would allow a generated column, but then a rate
refresh means rewriting every employee row and the rate is duplicated 10,000 times.

## Consequences

An FX rate change requires a backfill of this column — a migration script, not a data edit. That is
an acceptable cost given rates are seeded reference data in this scope, and it is called out in
[requirements.md](../requirements.md) as a consideration for making rates live.
