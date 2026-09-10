"""Command-line entry point: ``python -m app.seed``."""

import argparse
import time

from app.db import SessionFactory, engine
from app.seed.run import (
    DEFAULT_EMPLOYEE_COUNT,
    DEFAULT_RANDOM_SEED,
    reset_schema,
    seed_database,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="Drop, recreate and populate the salary database.",
    )
    parser.add_argument("--count", type=int, default=DEFAULT_EMPLOYEE_COUNT)
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="RNG seed; the same value always produces the same dataset",
    )
    arguments = parser.parse_args()

    started = time.perf_counter()
    reset_schema(engine)
    with SessionFactory() as session:
        summary = seed_database(session, arguments.count, arguments.seed)
    elapsed = time.perf_counter() - started

    print(
        f"Seeded {summary.employees:,} employees "
        f"({summary.managed_employees:,} with a reporting line), "
        f"{summary.countries} countries, {summary.currencies} currencies "
        f"in {elapsed:.2f}s"
    )


if __name__ == "__main__":
    main()
