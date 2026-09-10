"""Endpoint latency benchmark against a running backend.

Measures end to end over HTTP, so the figures include routing, validation, query
execution and JSON serialisation rather than SQL alone. Run with the backend up
and the full dataset seeded:

    python -m app.seed && uvicorn app.main:app --port 8000 &
    python scripts/benchmark.py

The numbers in ``docs/performance.md`` were produced by this script.
"""

import argparse
import statistics
import time
import urllib.request

WARMUP_REQUESTS = 3
MEASURED_REQUESTS = 40

CASES: dict[str, str] = {
    "list page 1 (name asc)": "/api/employees?page_size=50",
    "list page 150 (deep offset)": "/api/employees?page_size=50&page=150",
    "list sorted by USD comp": "/api/employees?page_size=50&sort=TOTAL_COMP_USD&direction=DESC",
    "list free-text search": "/api/employees?page_size=50&search=engineer",
    "list multi-facet filter": (
        "/api/employees?page_size=50&status=ACTIVE&country=IN&country=US&department=ENGINEERING"
    ),
    "summary (all)": "/api/analytics/summary",
    "summary (filtered)": "/api/analytics/summary?status=ACTIVE&department=ENGINEERING",
    "breakdown by country": "/api/analytics/breakdown?dimension=COUNTRY&status=ACTIVE",
    "breakdown by level": "/api/analytics/breakdown?dimension=LEVEL&status=ACTIVE",
    "distribution": "/api/analytics/distribution?status=ACTIVE",
    "reference data": "/api/reference",
}


def time_endpoint(url: str) -> list[float]:
    """Return per-request durations in milliseconds, after warming up."""
    for _ in range(WARMUP_REQUESTS):
        urllib.request.urlopen(url).read()

    durations: list[float] = []
    for _ in range(MEASURED_REQUESTS):
        started = time.perf_counter()
        urllib.request.urlopen(url).read()
        durations.append((time.perf_counter() - started) * 1000)
    return durations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    arguments = parser.parse_args()

    print(f"{'endpoint':<32}{'p50':>10}{'p95':>10}{'max':>10}")
    print("-" * 62)

    worst_p95 = 0.0
    for name, path in CASES.items():
        durations = sorted(time_endpoint(arguments.base_url + path))
        p50 = statistics.median(durations)
        p95 = durations[int(len(durations) * 0.95)]
        worst_p95 = max(worst_p95, p95)
        print(f"{name:<32}{p50:>9.1f}ms{p95:>9.1f}ms{max(durations):>9.1f}ms")

    print("-" * 62)
    print(f"worst p95 across all endpoints: {worst_p95:.1f}ms")


if __name__ == "__main__":
    main()
