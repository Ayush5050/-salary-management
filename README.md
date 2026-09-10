# ACME Salary Management

Web-based salary management for an HR Manager responsible for ~10,000 employees across ten
countries — replacing the spreadsheets they currently maintain, and letting them answer questions
about how the organisation pays people without exporting anything.

Built for the Incubyte engineering assessment.

> **Deployed demo:** <https://salary-management-qw64.onrender.com>

---

## Run it

Needs Python 3.12+ and Node 20+. No database server, no Docker required.

```bash
make setup && make seed
```

Then, in two terminals:

```bash
make dev-api
```

```bash
make dev-ui
```

Open <http://localhost:5173>. The seed loads 10,000 employees in under a second and is
deterministic, so your data matches the screenshots and the demo exactly.

<details>
<summary>Docker instead</summary>

```bash
docker compose up --build
```

Serves on <http://localhost:8080>. One image runs the API and the built UI from a single origin.

**Caveat, stated honestly:** Docker is not installed on the machine this was developed on, so the
Compose setup is written but has not been executed. What *has* been verified locally is the mode it
depends on — a production frontend build served by FastAPI from one origin, with SPA deep links,
working API routes and correct 404s on unknown `/api` paths. The `make` path above is the one to
trust if you hit trouble.
</details>

<details>
<summary>Deploying it</summary>

`render.yaml` is a Render blueprint for the combined image. In the Render dashboard: **New →
Blueprint**, point it at this repository, and deploy. It builds the Dockerfile and seeds 10,000
employees on first boot — so the first deploy takes a couple of minutes before the health check
passes.

The committed blueprint targets Render's **free** tier for a zero-cost live demo: no persistent
disk, so `/data` is ephemeral. The deterministic seed re-runs on each cold start, so the 10,000
employees are always present, but anything added through the UI lasts only until the instance
restarts (and free instances spin down after inactivity, adding a cold-start delay on the next
visit). For a persistent deployment, switch the blueprint to the `starter` plan and add a `disk:`
mounted at `/data` — SQLite then keeps everything across restarts. The reasoning is in
[ADR-0002](docs/adr/0002-sqlite-over-postgres.md).

Any host that runs a Dockerfile works the same way — the image reads `PORT` from the environment.

</details>

## Everything else

```bash
make test     # 209 backend tests + 58 frontend tests, ~3s total
make lint     # ruff, ruff format, mypy --strict, tsc --noEmit
make bench    # endpoint latency against the full 10,000 rows
make help     # all targets
```

API documentation is generated at <http://localhost:8000/docs> while the backend runs.

---

## What it does

**Dashboard — "how we pay people."** Total annual payroll spend, headcount, and average *and* median
total compensation, all normalised to USD. Breakdowns by country, department or level. A salary-band
distribution over fixed bands, so the shape stays comparable as filters change.

**Employees.** Server-side paginated, sorted, searched and multi-facet filtered over all 10,000
records. Full detail, create, edit, and deactivate.

**Ask a question in plain English.** "What do we pay engineering in Germany over $150k by level?"
translates into a filter selection, echoes back what it understood, and updates the visible filter
controls so every part of the interpretation is adjustable. It emits a *validated filter object,
never SQL*, and returns the query string the question means rather than results — so an answered
question lands on exactly the same view a person would have built by hand.

**Two details that carry most of the product thinking:**

- *Every dashboard figure links to the people behind it.* "$85.9M in India" is one click from the
  2,088 employees it is the sum of, under exactly the same filters. A number nobody can verify is a
  number nobody should act on.
- *Average and median sit side by side.* Compensation is right-skewed — in the seeded data the mean
  is \$101,076 and the median \$70,740. Showing only the average would overstate what ACME pays a
  typical person by 43%.

## How it's built

```
backend/    FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite
  app/domain/        pure compensation rules — no DB, no HTTP
  app/repositories/  SQL; filtering.py is the only place filters become SQL
  app/api/           routes: parse, delegate, serialise
  app/seed/          deterministic 10,000-employee generator
frontend/   React 19 · TypeScript · Vite · Mantine · TanStack Query · Recharts
  src/lib/           pure formatting, filter serialisation, form rules
  src/api/           typed client and query hooks
  src/components/    presentation
```

Three decisions shape most of the code:

**One filter model, shared everywhere.** `EmployeeFilters` is a single immutable value object, and
`filter_conditions()` is the only function that turns it into SQL — the list query, the count, and
all three analytics queries call it. On the client, filter state lives in the URL under the exact
parameter names the API accepts, so the query string is forwarded verbatim. The dashboard and the
list therefore *cannot* disagree; it is structural, not a matter of being careful. It also makes any
filtered view a shareable link.

**Money is integer minor units; FX rates are scaled integers.** Binary floats cannot represent 0.01,
so a float `SUM` over 10,000 salaries drifts measurably — there is a test that demonstrates it.
Descaling happens once per aggregate rather than once per row, bounding truncation error to a single
minor unit for a whole payroll figure instead of one per employee. The average is computed from an
integer total and count, never with SQL `AVG`, which would hand back a float.

**Aggregation happens in SQL.** Nothing loads 10,000 rows into Python to add them up. SQLite has no
median function, so it is computed with window functions, using a midpoint condition written to
avoid integer division entirely so it behaves identically on any backend.

The question parser is a deterministic grammar rather than a language model — a compensation report
has to give the same answer twice, and a model asked for structured output will confidently invent a
filter for a question it did not understand. `parse_question` is the single seam a model-backed
translator would replace, and it would inherit the validation and the echoed interpretation
unchanged. The reasoning is in [ADR-0009](docs/adr/0009-natural-language-questions.md).

## Performance

Worst p95 across every endpoint is **11.8 ms** against the full dataset, versus a 150 ms target.
Index usage is verified with `EXPLAIN QUERY PLAN` rather than inferred from timings — at 10,000 rows
a full scan is fast enough to hide a missing index. Measurements, query plans, and the known limits
(free-text search scans; deep offsets grow linearly) are in
[docs/performance.md](docs/performance.md).

## Testing

267 tests, running in about three seconds.

The approach that matters: **anything subtle is tested differentially.** The windowed SQL median is
checked against a plain Python implementation for every group of every dimension, and the fixture is
asserted to contain both odd- and even-sized groups — the parity boundary is exactly where the
midpoint condition could be wrong. Two genuinely different implementations agreeing is evidence; one
implementation agreeing with a hard-coded number is not.

Other things deliberately pinned down: that paging a heavily tied sort visits every employee exactly
once; that the derived USD column matches a recomputation for every seeded row; that a reporting
cycle is rejected; that `DELETE /api/employees/{id}` returns 405; and that the same query string
yields the same headcount from the list and from the dashboard.

Frontend tests stub only `fetch`, so hooks, client, URL building and components all run for real —
which is what lets them assert that a filter actually reaches the backend.

## Documents

| | |
|---|---|
| [Requirements](docs/requirements.md) | Goal, scope, and what is excluded with reasoning — written before any code |
| [Architecture](docs/architecture.md) | Diagrams, layering, request paths, data model |
| [Performance](docs/performance.md) | Measurements, query plans, known limits |
| [AI usage](docs/ai-usage.md) | How AI was used, and every place it had to be corrected |
| [ADRs](docs/adr/) | Nine decision records, each with the alternatives rejected |

## Scope

Confirmed with Incubyte before building: no authentication or RBAC, no salary revision history, and
seeded rather than live FX rates. Also excluded: payroll execution, approval workflows, and CSV
import — the last being the highest-value next increment, since it is the actual migration path off
spreadsheets. Every exclusion is reasoned in [docs/requirements.md](docs/requirements.md) rather
than left implicit.

The optional natural-language query interface was scoped as a stretch and *is* included, built only
after the core was complete and fully tested. It is additive: removing it would not touch a line of
the dashboards.
