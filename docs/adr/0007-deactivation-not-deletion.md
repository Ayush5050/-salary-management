# ADR-0007 · Employees are deactivated, never deleted

**Status:** Accepted · **Date:** 2026-09-10

## Context

People leave. The obvious CRUD reflex is a `DELETE` endpoint and a delete button.

## Decision

There is no delete operation anywhere in the system — not in the repository, not in the API.
Employees carry a `status` of `ACTIVE` or `INACTIVE`, changed through
`PATCH /api/employees/{id}/status`.

## Reasoning

Compensation records are financial history. A leaver still belongs in last year's payroll total, in
the department's spend for the quarter they worked, and in any answer to "what did we spend on
engineering in 2025?". Deleting the row does not just lose a person — it silently and retroactively
changes numbers the organisation has already reported.

There are also obligations a salary record is likely to fall under (payroll retention, audit) that
make hard deletion the wrong default regardless of what the UI offers.

The absence is enforced rather than merely conventional: `tests/test_api.py` asserts that
`DELETE /api/employees/{id}` returns 405, so the endpoint cannot reappear unnoticed.

## Consequences

Inactive employees must be excluded from "how do we pay people *now*", so the default filter is
`status=ACTIVE`, seeded into the URL on first load rather than applied as invisible magic — the
applied selection is always visible and shareable. The seed generates a 6% inactive population
specifically so that this filter is meaningful and testable rather than a no-op.

Genuine erasure — a GDPR right-to-be-forgotten request, say — is a separate, deliberate operation
with its own authorisation and audit requirements. It is out of scope here, and it should never share
a code path with "this person left the company".
