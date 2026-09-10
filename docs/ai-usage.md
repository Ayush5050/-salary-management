# How AI was used on this project

The brief asks for intentional AI use with correctness and quality maintained. This is an honest
account of how the work was actually done, including where AI got things wrong.

The whole implementation was built in a single session with Claude Code (Claude Opus 5) driving the
edits. That makes the interesting question not *whether* AI was used but **what I kept
responsibility for** — because an agent will happily produce a plausible, wrong salary system.

## What I decided, and did not delegate

These were settled by me before or during the build, and the agent implemented them:

- **Clarifying the brief before building.** I sent six scoping questions to Incubyte covering the
  analytics-vs-NL-query ambiguity, multi-currency handling, salary history, auth, deployment and
  what the 10,000 figure was actually testing — each with the default I would proceed on. That
  exchange is what set the scope; the requirements document was written before any code.
- **The money representation** (integer minor units, scaled FX, descale-once) — the decision most
  likely to be got wrong by defaulting to floats or `Numeric`.
- **The shared filter model** as the core product guarantee, which is what makes the dashboard's
  numbers verifiable rather than merely displayed.
- **Storing a derived, indexed USD total**, and the three mechanisms that keep it from going stale.
- **Deactivation rather than deletion**, and enforcing the absence with a test.
- **Scope discipline** — no salary history, no auth, no CSV import, each with reasoning recorded.

## Where AI was genuinely fast

- **Mechanical breadth**: the seed catalogue, the ~15-field employee form, the Mantine layout, the
  wire types. Work that is tedious and low-risk.
- **Boilerplate with a spec**: given the decision "median via window functions, no integer
  division", generating the SQLAlchemy expression was quick.
- **Test enumeration**: once the *shape* of a test was set (differential — SQL against a Python
  reference), producing thorough coverage across dimensions and parities was fast.
- **Documentation drafting**: these ADRs, from decisions already made.

## Where I had to correct it — the useful part

**A float-drift test that didn't test drift.** The first version multiplied a salary by 10,000 and
asserted the float result differed from the exact one. It doesn't — a single multiplication is
exact. Drift comes from repeated *addition*, which is what a SQL `SUM` actually does. The test now
accumulates in a loop and demonstrates real drift. A green suite proving nothing is worse than no
suite.

**Foreign keys silently unenforced.** The SQLite pragma listener was registered against the
`Engine` class, so it only applied once `app.db` had been imported — which tests never did. Foreign
keys were off in every test. A test I'd written for the failure case caught it. The fix was
structural: one engine factory that tests and production both use, so configuration cannot diverge.

**Two lint false positives that were worth fixing anyway.** Ruff flagged `_VALUE < upper_bound` as a
Yoda condition because the uppercase name looked like a constant. It was a column expression, so I
renamed it — the linter was wrong about the rule and right that the name was misleading.

**A test that passed for the wrong reason.** A dashboard assertion matched `$101,076` anywhere on the
page, and the breakdown fixture happened to contain the same number. Fixed twice over: the fixtures
now carry distinct figures, and the assertion is scoped to the KPI card — which meant giving those
cards `role="group"` and an accessible label, a real improvement for screen-reader users that the
test pressure produced.

**A country code that was also a preposition.** The question parser matched ISO codes
case-insensitively, so "salaries **in** Germany" selected India too — `IN` is both. Caught by a
test asserting that a question naming one country selects exactly one. Fixed by matching codes
case-sensitively, which is how people actually write them, rather than by special-casing `IN`.

**A dead ternary.** `ZERO_DECIMAL_CURRENCIES.has(code) ? 0 : 0` — both branches identical, an
abandoned idea left in place. Removed, and the actual intent documented.

**Layout only a browser reveals.** The status filter truncated its chips. Tests and types both
passed; I found it by opening the app and looking at it, which is why the browser verification step
is not optional.

## The workflow that made this work

1. **Clarify the brief before writing anything.** Six questions, each with a stated default.
2. **Requirements document first**, including what is deliberately excluded and why.
3. **Domain layer first, with its tests** — the pure functions where correctness lives, provable
   without a database.
4. **Differential testing for anything subtle.** The windowed median is checked against a plain
   Python implementation over every group of every dimension, and the fixture is asserted to contain
   both odd and even group sizes. Two implementations agreeing is evidence; one implementation
   agreeing with a hard-coded number is not.
5. **Strict gates, always on.** `mypy --strict`, `ruff`, and pytest's `filterwarnings = ["error"]`.
   That last one caught a deprecated Starlette constant I would otherwise have shipped. Strict
   tooling is how you keep AI-generated volume honest.
6. **Run it and look at it.** Servers up, real seeded data, clicking through in a browser.
7. **Incremental commits** at each coherent slice, so the evolution is legible.

## What I would not use AI for here

Deciding *what to build*. The exclusions in [requirements.md](requirements.md) are the highest-value
decisions in this submission, and an agent asked to build "salary management software" will happily
build salary history, approval workflows, and an org chart nobody asked for. Scope came from the
brief and the clarifying exchange; AI executed against it.

Equally: accepting a passing test as proof. Two of the corrections above were tests that were green
while asserting nothing real. The judgment about whether a test could actually fail is not something to
delegate.
