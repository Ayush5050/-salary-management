# ADR-0003 · Money as integer minor units, FX rates as scaled integers

**Status:** Accepted · **Date:** 2026-09-10

## Context

The single most common operation in this system is summing salaries — 10,000 of them for the payroll
KPI, and again for every group of every breakdown. Those figures are what the HR Manager takes into
budget conversations, so they have to be exact and reproducible.

Salaries also arrive in nine currencies and must be normalised to USD for any org-wide comparison.

## Decision

1. Monetary amounts are stored, aggregated and transmitted as **integer counts of minor units**
   (cents, pence, paise).
2. FX rates are stored as **integers scaled by 10⁶** (`FX_SCALE`).
3. The database aggregates in *FX-scaled minor units* — the product of an amount and a rate — and
   **descaling happens once per aggregate**, not once per row.
4. The average is computed in Python from the integer total and count, never with SQL `AVG`.

## Reasoning

**Floats drift.** `0.01` has no finite binary representation, so error compounds once per addition.
Accumulating `83,333.33` ten thousand times in float gives `833,333,300.0001175` rather than
`833,333,300.00`. That is asserted in `tests/test_money.py`, and it is the whole justification for
the representation. On SQLite the problem is worse than usual, because `Numeric` round-trips through
float anyway.

**Descaling once matters at this scale.** Truncating each row's converted amount loses up to one
minor unit per employee; over 10,000 employees that is a visibly wrong payroll total. Aggregating in
scaled space and dividing once bounds the loss to a single minor unit for the entire figure. The
difference is measured in a test rather than asserted in prose.

**`AVG` would undo the whole thing.** It returns a float, so using it would reintroduce the drift the
representation exists to avoid — which is why `arithmetic_mean` takes an integer total and count.

**Integers survive the wire.** JSON numbers are IEEE doubles in every browser. Sending `170000.50`
invites the same class of rounding on the client, so the API sends integers and the frontend
converts in exactly one module.

## Alternatives considered

**`Decimal`/`Numeric` columns.** The obvious choice, and correct on PostgreSQL. Rejected because
SQLite has no native decimal type, so SQLAlchemy would convert through float on the way in and out —
the precision would be theatre.

**Floats with rounding on display.** Cheapest to write. Rejected: rounding at the end does not undo
error accumulated during aggregation, and the failure is silent — the number simply looks plausible
and is wrong.

**Storing a plain USD column alongside the local amount.** Simpler to read, but summing per-row
truncated values reintroduces the per-row error described above.

## Consequences

Every boundary needs an explicit conversion, and the units are carried in the names
(`base_salary_minor`, `total_comp_usd_fx_scaled`, `usd_rate_scaled`) so a bare `int` is never
ambiguous. `MINOR_UNITS_PER_MAJOR` is fixed at 100, so a genuinely zero-decimal currency like JPY is
stored on a 100:1 basis with a zero fraction and formatted without decimals; supporting variable
currency exponents would need a per-currency exponent column, which is noted as a future increment.
