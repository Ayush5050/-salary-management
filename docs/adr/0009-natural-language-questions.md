# ADR-0009 · Natural-language questions translate to filters, not to answers

**Status:** Accepted · **Date:** 2026-09-10 · *Stretch feature, built after the core was complete*

## Context

The persona's job is answering questions about pay, and they are not technical. A question bar is
the obvious affordance. It is also the easiest place in this system to do real damage: a
compensation figure produced by a misread question looks exactly like a correct one, and the HR
Manager has no way to tell the difference.

## Decision

Three constraints, in order of importance:

1. **The parser emits a validated `EmployeeFilters`, never SQL.** A question can only ever reach the
   database as a parameterised predicate over known columns, through the same tested query path
   everything else uses.
2. **The endpoint returns the query string the question *means*, not results.** The client navigates
   to it, so an answered question lands on the same view a person would have built by hand, served
   by the same endpoints. There is no parallel "answered" code path that could disagree with the
   filters on screen.
3. **The interpretation is echoed in plain English, and the filter controls update to match.** The
   answer arrives with its working shown, and every part of it is adjustable with the normal
   controls.

## Why a deterministic grammar rather than a language model

This is the decision most likely to be questioned, so the reasoning is explicit:

- **Reproducibility.** A compensation report must give the same answer today and at quarter end. A
  sampled model does not guarantee that, and "the number changed and nobody knows why" is fatal to
  trust in a tool whose only job is to be trusted.
- **Testability.** The parser is unit-tested by exact example — 43 cases — with no API key, no
  network call and no cost. A reviewer can run it.
- **Honest failure.** Unrecognised words are *reported* ("Ignored: tuesdays"), not quietly dropped.
  A model asked to produce structured output will confidently invent a plausible filter for a
  question it did not understand, which is the worst possible failure here.
- **Latency and cost.** Sub-millisecond, and free.

The trade is real: the grammar handles the phrasings it knows and no others. It will not understand
"how does our pay compare to market" or resolve a typo. That is an acceptable floor for a stretch
feature, and the failure is visible rather than silent.

**The seam is deliberate.** `parse_question` is the only function a model-backed translator would
replace, and any replacement must return the same `ParsedQuestion`. The validation, the echoed
interpretation, the filter model and every downstream query stay exactly as they are — the
guardrails live in the type, not in the translator. That is the point of the design: swapping in an
LLM is a contained change to *one function*, not a rewrite, and it inherits the safety properties
automatically.

## A bug worth recording

The first implementation matched country codes case-insensitively, so "salaries **in** Germany"
selected India as well — `IN` is both an ISO code and the commonest preposition in these questions.
Country codes are now matched case-sensitively against the original text, which matches how people
actually write them and removes the ambiguity without a list of special cases. Caught by a test
asserting that a question naming one country selects exactly one country.

## Consequences

Adding a recognised phrase is a one-line change to a table. Country vocabulary is built from the
database, so adding a country teaches the parser that country with no code change. Departments and
levels come from the same enums the rest of the system uses, so they cannot drift.

The feature is additive: removing it would not touch a single line of the core dashboards.
