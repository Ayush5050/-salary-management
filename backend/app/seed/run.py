"""Loading the generated population into the database.

Kept separate from :mod:`app.seed.generator` so that generation stays pure and
this module holds all the persistence concerns: schema creation, bulk insert,
and the second pass that wires up reporting lines once rows have identities.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, insert, select, update
from sqlalchemy.orm import Session

from app.domain.compensation import total_comp_usd_fx_scaled
from app.domain.money import fx_rate_to_scaled
from app.models import Base, Country, Currency, Employee
from app.seed.catalog import COUNTRIES, CURRENCIES, RATES_AS_OF
from app.seed.generator import assign_managers, generate_employees

DEFAULT_EMPLOYEE_COUNT = 10_000
DEFAULT_RANDOM_SEED = 20260910
"""Fixed so that the deployed demo, a local run and the test fixtures all hold
identical data. A screenshot of the dashboard is reproducible from the seed."""

_INSERT_CHUNK_SIZE = 1_000
"""Rows per executemany batch.

Chunking keeps the parameter list well inside SQLite's variable limit and keeps
peak memory flat, at no measurable cost against a single large batch.
"""


@dataclass(frozen=True, slots=True)
class SeedSummary:
    currencies: int
    countries: int
    employees: int
    managed_employees: int


def _chunked(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[start : start + size] for start in range(0, len(rows), size)]


def reset_schema(engine: Engine) -> None:
    """Drop and recreate every table.

    Seeding is destructive by design — it exists to produce a known dataset, not
    to merge into an existing one — so it says so plainly rather than leaving
    stale rows behind.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _seed_reference_data(session: Session) -> tuple[int, int]:
    session.execute(
        insert(Currency),
        [
            {
                "code": currency.code,
                "name": currency.name,
                "symbol": currency.symbol,
                "usd_rate_scaled": fx_rate_to_scaled(currency.usd_per_unit),
                "rate_as_of": RATES_AS_OF,
            }
            for currency in CURRENCIES
        ],
    )
    session.execute(
        insert(Country),
        [
            {
                "code": country.code,
                "name": country.name,
                "region": country.region,
                "default_currency_code": country.currency_code,
            }
            for country in COUNTRIES
        ],
    )
    return len(CURRENCIES), len(COUNTRIES)


def seed_database(session: Session, employee_count: int, random_seed: int) -> SeedSummary:
    """Populate an empty schema. Assumes :func:`reset_schema` has just run."""
    currency_count, country_count = _seed_reference_data(session)

    rate_by_currency = {
        code: rate
        for code, rate in session.execute(select(Currency.code, Currency.usd_rate_scaled))
    }

    employees = generate_employees(employee_count, random_seed)
    rows: list[dict[str, Any]] = [
        {
            "employee_code": employee.employee_code,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "country_code": employee.country_code,
            "department": employee.department,
            "job_title": employee.job_title,
            "level": employee.level,
            "employment_type": employee.employment_type,
            "status": employee.status,
            "hire_date": employee.hire_date,
            "currency_code": employee.compensation.currency_code,
            "base_salary_minor": employee.compensation.base_salary_minor,
            "bonus_minor": employee.compensation.bonus_minor,
            "total_comp_usd_fx_scaled": total_comp_usd_fx_scaled(
                employee.compensation, rate_by_currency[employee.compensation.currency_code]
            ),
        }
        for employee in employees
    ]
    for chunk in _chunked(rows, _INSERT_CHUNK_SIZE):
        session.execute(insert(Employee), chunk)

    manager_of = assign_managers(employees, random_seed)
    id_by_code = {
        code: employee_id
        for code, employee_id in session.execute(select(Employee.employee_code, Employee.id))
    }
    manager_rows: list[dict[str, Any]] = [
        {"id": id_by_code[code], "manager_id": id_by_code[manager_code]}
        for code, manager_code in manager_of.items()
    ]
    for chunk in _chunked(manager_rows, _INSERT_CHUNK_SIZE):
        session.execute(update(Employee), chunk)

    session.commit()
    return SeedSummary(
        currencies=currency_count,
        countries=country_count,
        employees=len(rows),
        managed_employees=len(manager_rows),
    )
