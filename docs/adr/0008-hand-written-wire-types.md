# ADR-0008 · Hand-written TypeScript wire types

**Status:** Accepted · **Date:** 2026-09-10

## Context

FastAPI publishes an OpenAPI document, so the client's types could be generated from it.

## Decision

Hand-write the wire types in `frontend/src/api/types.ts`, mirroring the Pydantic schemas.

## Reasoning

The decisive factor is units. Every monetary field in this system is an integer whose meaning
depends on a suffix — `base_salary_minor`, `total_comp_usd_minor`, `usd_rate_scaled`. A generator
renders all of them as `number`, and the one piece of information that stops a developer rendering
cents as dollars lives only in the field name and the surrounding comment. Hand-written types keep
the naming and the explanatory comments together, at the boundary where the mistake would be made.

At this size — roughly a dozen interfaces — the generator's toolchain (a build step, a checked-in
artifact, a CI job to detect staleness) costs more than it saves.

## Alternatives considered

**`openapi-typescript` in a build step.** Types can never drift. Worth adopting as soon as the API
surface grows, or the moment more than one client consumes it.

**Sharing types via a monorepo package.** Requires the backend to be TypeScript too, which
[ADR-0001](0001-stack-and-layering.md) already decided against.

## Consequences

A backend schema change must be mirrored by hand. What limits the risk: TypeScript's strictness
turns a missing or misspelled field into a build error rather than a runtime `undefined`; the API
tests assert the exact response fields; and the dashboard component tests exercise the real client
against fixtures shaped like real payloads. The residual risk is a *renamed* field — caught by the
build the moment a component reads it.
