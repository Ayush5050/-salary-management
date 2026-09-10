# Performance

The 10,000-employee requirement is what makes performance a design input rather than an afterthought,
so pagination, indexing and SQL-side aggregation were built in from the first query rather than
retrofitted. This records what was measured and what the numbers mean.

## Method

Measured against the full seeded dataset (10,000 employees, 9,381 active) on the development
machine: Python 3.12.10, SQLite 3.49.1, uvicorn single worker, macOS. Each endpoint was warmed with
3 requests, then timed over 40, end-to-end over HTTP — so the figures include routing, validation,
query execution and JSON serialisation, not just the SQL.

Reproduce with `make bench` (backend running).

## Results

| Endpoint | p50 | p95 | max |
|---|---:|---:|---:|
| List, page 1, name ascending | 1.9 ms | 2.3 ms | 2.5 ms |
| List, page 150 (deep offset) | 4.5 ms | 5.1 ms | 13.5 ms |
| List, sorted by USD compensation | 1.8 ms | 2.1 ms | 2.1 ms |
| List, free-text search | 7.4 ms | 7.6 ms | 7.7 ms |
| List, multi-facet filter | 3.6 ms | 3.9 ms | 3.9 ms |
| Analytics summary (all) | 5.9 ms | 6.3 ms | 6.9 ms |
| Analytics summary (filtered) | 3.7 ms | 3.9 ms | 4.1 ms |
| Breakdown by country | 10.3 ms | 10.6 ms | 10.7 ms |
| Breakdown by level | 11.2 ms | 11.8 ms | 12.1 ms |
| Salary distribution | 2.7 ms | 2.9 ms | 2.9 ms |
| Reference data | 0.9 ms | 1.0 ms | 1.1 ms |

Worst p95 across every endpoint: **11.8 ms**, against the 150 ms target in
[requirements.md](requirements.md).

## Index usage

Verified with `EXPLAIN QUERY PLAN` rather than inferred from timings — at 10,000 rows a full scan is
fast enough to hide a missing index, so the plan is the real check:

| Query | Plan |
|---|---|
| Filter by status + department | `SEARCH USING INDEX ix_employees_status_department (status=? AND department=?)` |
| Sort by USD compensation | `SCAN USING INDEX ix_employees_total_comp_usd_fx_scaled` |
| Compensation range filter | `SEARCH USING COVERING INDEX ix_employees_total_comp_usd_fx_scaled` |
| Sort by name | `SCAN USING INDEX ix_employees_last_name_first_name` |
| Group by country | `SEARCH USING INDEX ix_employees_status_country_code (status=?)` |
| Free-text search | `SCAN employees` |

Every intended index is used. The single scan is the free-text search, which is expected and
discussed below.

## The decisions behind the numbers

**Aggregation in SQL.** No endpoint loads rows into Python to aggregate them. This is the difference
between a dashboard that stays flat as the organisation grows and one that degrades linearly.

**A derived, indexed USD total.** Sorting and range-filtering by USD compensation would otherwise
require a join and a multiplication, which no index can serve — the database would sort all 10,000
rows on every page. See [ADR-0004](adr/0004-denormalised-usd-total.md).

**Status-led composite indexes.** The dashboard's default posture is "active employees, grouped by a
dimension", so `(status, department)`, `(status, country_code)` and `(status, level)` serve the
filter and the grouping in one pass.

**A stable sort tiebreaker.** Every ordering ends with the primary key. Without it, ties under a
low-cardinality sort (department has ten distinct values across 10,000 rows) can be returned in a
different order per query, so paging would duplicate some employees and skip others — a correctness
bug that presents as a performance-shaped detail. Covered by
`test_paging_a_heavily_tied_sort_visits_everyone_exactly_once`.

**A page-size ceiling.** `page_size` is capped at 100. Without a limit, a client could request all
10,000 rows and defeat the pagination the read path is built around.

**Two queries per list request.** A `COUNT` plus a page, rather than deriving the total from the
rows, so the UI can show "1–25 of 9,381" without fetching 9,381 records.

## Known limits, and when they would matter

**Free-text search scans.** `LIKE '%token%'` cannot use a B-tree index. At 10,000 rows this costs
~7ms, which is the right trade against maintaining a search index. At roughly 100,000 rows it would
become noticeable, and the fix is SQLite FTS5 (or a PostgreSQL trigram/tsvector index) over the
searchable columns.

**Deep offsets grow linearly.** `OFFSET 3725` costs ~4.5ms against ~1.9ms for page 1, because SQLite
walks the skipped rows. It is bounded and irrelevant here — nobody pages to record 3,725 by hand,
they filter — but keyset pagination would be the fix if an export path ever needed to walk the whole
table.

**Single-writer concurrency.** SQLite serialises writes. Correct for one HR Manager; the trigger to
move to PostgreSQL is a second concurrent editor, not a row count.

**Frontend bundle: 1.0 MB raw, 303 KB gzipped.** Mantine, Recharts and the icon set dominate. For an
internal tool loaded once and used for hours this is an acceptable trade for component quality; the
lever if it mattered would be route-level code splitting, since Recharts is only needed on the
dashboard.

## Test suite performance

Fast tests get run; slow ones get skipped. The backend suite is **209 tests in ~1.5s** and the
frontend **58 tests in ~2.1s**. Two choices keep it there: the domain layer is pure, so most tests
touch no database at all; and database-backed tests seed 250 employees rather than 10,000, since
query *correctness* does not depend on scale. Scale is verified by the measurements above instead —
a benchmark's job, not a unit test's.
