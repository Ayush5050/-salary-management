# ADR-0005 · One filter model, shared by the dashboard and the list

**Status:** Accepted · **Date:** 2026-09-10

## Context

The persona's job is answering questions about how the organisation pays people. The failure mode
that makes such a tool untrustworthy is subtle: a KPI card says one thing, the list beneath it says
another, and nobody can tell which is right. It usually happens because the dashboard's "active
employees" and the list's "active employees" were implemented separately and drifted — one counts
contractors, the other does not.

Once an HR Manager catches that once, they go back to the spreadsheet.

## Decision

There is exactly one filter model, threaded through both the backend and the frontend:

- **`EmployeeFilters`** — one immutable value object in the domain layer.
- **`filter_conditions()`** — the only function that turns it into SQL. Called by the list query, the
  count query, the summary, the breakdown, and the distribution.
- **One FastAPI dependency** parses query parameters into it; every route depends on that dependency.
- **The URL is the client's filter state**, using the parameter names the API already accepts, so
  the query string is forwarded verbatim.

## Reasoning

This makes agreement *structural* rather than something to be careful about. The dashboard and the
list cannot diverge, because there is no second predicate-builder to diverge from.

It also produces the feature that makes the dashboard genuinely useful: every figure links to the
people behind it. "€100.3M in Germany" carries the current selection plus `country=DE` into the
employee list. The number is not something to trust — it is something to open.

Keeping the client's state in the URL adds three things beyond consistency: a filtered view becomes
a shareable link, navigating between the two pages preserves the selection, and the applied filter
is visible rather than being hidden state.

## Verification

`tests/test_api.py::TestFilterConsistencyOverHttp` asserts, over several query strings, that the
list's `meta.total` equals the summary's `headcount`, and that breakdown headcounts sum to it.
`src/lib/filters.test.ts` asserts the client's serialisation round-trips and produces exactly the
backend's parameter names. `DashboardPage.test.tsx` asserts the URL's filters actually reach every
analytics endpoint.

## Alternatives considered

**Separate filter shapes per endpoint.** More flexible per endpoint; rejected because flexibility is
precisely what allows drift, and no endpoint here needs a facet the others lack.

**Filter state in React state or a store.** Conventional. Rejected because it makes a filtered view
unshareable and loses the selection on navigation — both of which the persona would notice daily.

## Consequences

Adding a facet means touching the dataclass, the predicate builder, the dependency and the panel —
four places, but all four are required for it to work end to end, so none can be forgotten silently.
An endpoint needing a genuinely different selection would need a second model, and that would be the
point to revisit this.
