# Salary Management — Requirements

**Author:** Ayush Kumar · **Date:** 2026-09-10 · **Status:** Approved scope (clarifications confirmed with Incubyte)

## 1. Goal

ACME's HR team manages compensation for ~10,000 employees across multiple countries in spreadsheets.
Spreadsheets do not enforce structure, do not answer aggregate questions reliably, and cannot be
trusted as a single source of truth once several people edit them.

This software replaces those spreadsheets with a web application that lets the HR Manager

1. **maintain** the employee compensation record (the system of record), and
2. **answer questions about how the org pays people** without exporting anything.

Success means: an HR Manager can answer "what do we spend on payroll in Germany?" or "who are the
five highest-paid engineers in India?" in under ten seconds, and can correct an employee's salary in
under thirty — with numbers they trust.

## 2. Persona and primary jobs

**HR Manager at ACME.** Not technical. Lives in the data daily. Three recurring jobs:

| Job | Trigger | What the software must do |
|---|---|---|
| Answer a compensation question | Leadership asks, budget cycle | Dashboard: KPIs + breakdowns by country/department/level, all cross-filterable |
| Find and fix one record | Employee query, correction, promotion | Fast search + filter over 10k rows, inline detail, edit |
| Onboard / offboard | Joiner, leaver | Create employee; mark inactive (never hard-delete) |

## 3. Scope — what is being built

**Employee record management**
- Full CRUD over employees: name, email, employee code, country, department, job title, level,
  employment type, hire date, manager, status (active/inactive).
- Compensation stored as **base salary + bonus in the employee's local currency**.
- List view over 10,000 records with **server-side** pagination, sorting, free-text search, and
  multi-facet filtering (country, department, level, status, salary range).
- Deactivation instead of deletion — payroll data is financial history.

**Compensation analytics ("how do we pay people")**
- KPI cards: total annual payroll spend, active headcount, average salary, **median** salary.
- Breakdowns by country, department, and level: headcount, total spend, average, median, min/max.
- Salary band distribution (histogram) to spot compression and outliers.
- Every analytic respects the currently applied filters — the dashboard and the employee list share
  one filter model, so a number on screen is always traceable to a list of people.

**Multi-currency**
- Salaries are stored and displayed in **local currency** (what the employee is actually paid).
- A seeded `fx_rates` table normalizes to a **base reporting currency (USD)** for org-wide rollups.
- Rates are versioned data rows, not hardcoded constants, so a rate refresh is a data change.

**Data**
- Deterministic seed script producing 10,000 employees across ~10 countries and ~8 departments,
  with realistic country/level-dependent salary distributions.

## 4. Explicitly out of scope — and why

| Excluded | Reasoning |
|---|---|
| **Authentication, SSO, RBAC** | Confirmed out of scope. Single trusted internal persona. Auth is well-understood, adds no signal about compensation-domain design, and would consume budget better spent on query performance and analytics correctness. Documented as a production prerequisite — the API is designed so an auth dependency drops in at the router layer without touching domain code. |
| **Salary revision history / effective dating** | Confirmed: current-state snapshot is sufficient for MVP. Effective-dated compensation is a genuinely different data model (bitemporal), and building it "just in case" would double the model's complexity for a question the persona has not asked. The migration path is additive: a `salary_revisions` table plus a view for current state. |
| **Payroll execution, payslips, tax, benefits** | This is a *management and analysis* tool, not a payroll engine. Tax and statutory deductions are per-country regulatory work that dwarfs the rest of the system. |
| **Live FX rates** | Confirmed as unnecessary. A live dependency makes reports non-reproducible — the same query would return different numbers on different days — and adds an external failure mode. Seeded rates are deterministic and testable. |
| **Approval workflows / audit trail** | Real need in production (compensation changes are sensitive), but workflow modelling is its own project. Noted as the highest-value next increment. |
| **Bulk CSV import/export** | Highest-value deferred feature, since it is the actual migration path off spreadsheets. Excluded only because a correct importer needs validation, partial-failure reporting, and dry-run semantics — a meaningful slice on its own rather than a bolt-on. |
| **PostgreSQL** | SQLite is sufficient and appropriate at this scale (see ADR-0002). All data access is through SQLAlchemy with portable SQL, so the swap is a connection-string change. |

**Stretch, only after the core is complete and tested:** a natural-language query bar that
translates a plain-English question into a *validated structured filter* (never raw SQL). Confirmed
as strictly optional; would have been dropped rather than allowed to compromise core quality.

*Outcome: built, after the core was complete and green. See
[ADR-0009](adr/0009-natural-language-questions.md) for the design and for why the translator is a
deterministic grammar rather than a language model.*

## 5. Non-functional requirements

- **Performance:** list and aggregate endpoints must stay responsive at 10,000 rows. Pagination and
  filtering are server-side; aggregations are computed in SQL, never by loading rows into Python.
  Indexes on every filterable/sortable column. Target: p95 < 150 ms for list and dashboard endpoints.
- **Correctness:** monetary arithmetic must be exact — never binary float. *Implemented as integer
  minor units with integer-scaled FX rates rather than `Decimal`, because SQLite has no native
  decimal type and would round-trip `Numeric` through float anyway; see
  [ADR-0003](adr/0003-money-as-integer-minor-units.md).* Median is computed on the real
  distribution, not approximated.
- **Testability:** currency conversion and statistics are pure functions, unit-testable without a
  database. Tests are deterministic — the seed uses a fixed RNG seed.
- **Maintainability:** layered backend (domain → repository → API), fully type-annotated, with the
  compensation rules isolated from both HTTP and SQL.

## 6. Acceptance criteria

- [x] Seed loads 10,000 employees reproducibly with one command.
- [x] Employee list paginates, sorts, searches, and filters server-side over the full dataset.
- [x] An employee can be created, edited, and deactivated through the UI.
- [x] Dashboard shows total spend, headcount, average and median salary, normalized to USD.
- [x] Breakdowns by country, department, and level are correct against independently computed values.
- [x] Filters apply consistently to both the dashboard and the employee list.
- [x] Backend and frontend test suites pass; core compensation logic covered by unit tests.
- [x] App runs locally with one command. *Deployment config (Docker, `render.yaml`) is ready; the
      public URL needs a hosting account to point it at.*
- [x] *Stretch:* plain-English questions translate to a validated filter selection.
