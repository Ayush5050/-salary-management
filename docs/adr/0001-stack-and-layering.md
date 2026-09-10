# ADR-0001 · Stack and layering

**Status:** Accepted · **Date:** 2026-09-10

## Context

The brief names Python/React as the preferred stack and asks for a fully functional system with
tests, seeded to 10,000 employees. The persona is a non-technical HR Manager whose core job is
answering questions about compensation.

## Decision

FastAPI + SQLAlchemy 2.0 + Pydantic v2 on the backend; React 19 + TypeScript + Vite + Mantine on the
frontend. The backend is layered **domain → repository → API**, with the domain layer holding no
dependency on SQLAlchemy, FastAPI or Pydantic.

## Why this layering, given the size

A three-layer split can easily be ceremony on a system this small. It earns its place here because
the interesting logic is *not* in the routes — it is in how money is represented, how a median is
computed, and how a filter is turned into a predicate. Isolating that:

- makes the compensation rules unit-testable with no database and no HTTP client, which is why the
  domain suite runs in ~20ms and never flakes;
- lets the same rules serve a future CSV importer — the actual migration path off spreadsheets, and
  the first deferred feature likely to be built — without routing it through a web request;
- keeps the one genuinely subtle query (the windowed median) in a module where it can be read on its
  own, rather than inline in a route handler.

What was *not* added: a service layer between routes and repositories, repository interfaces, or a
DI container. With one implementation and an already-injected session, those would be indirection
without a beneficiary.

## Alternatives considered

**Django + DRF.** Admin, auth and the ORM come free, and for a CRUD-heavy internal tool that is a
real argument. Rejected because the value here is in aggregate queries rather than in scaffolded
CRUD, and the ORM's defaults (lazy loading in particular) work against the explicit query control
this system needs.

**Flask.** Lighter, but request validation and OpenAPI generation would be hand-rolled. FastAPI's
typed dependencies are exactly what makes one filter-parsing dependency shareable across every
route, which is the mechanism the whole consistency guarantee rests on.

**Next.js full-stack.** One deployment and one language. Rejected because the JD names Python, and
because the numeric work — exact decimal arithmetic, windowed aggregates — is better served by
Python and SQLAlchemy than by a JavaScript ORM.

## Consequences

Two build toolchains and two test runners to keep green. Wire types are hand-maintained on the
client rather than generated (see [ADR-0008](0008-hand-written-wire-types.md)). In exchange, the
backend suite runs in about a second and the domain rules are testable in isolation.
