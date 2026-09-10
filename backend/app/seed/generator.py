"""Deterministic generation of the synthetic employee population.

Pure: given a seed and a count, this produces the same list of records every
time, with no database involved. That separation buys three things — the
distribution can be unit-tested directly, the demo data is identical everywhere
the seed runs, and tests can build a small population without paying for 10,000
inserts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from random import Random

from app.domain.compensation import Compensation
from app.domain.enums import Department, EmploymentStatus, EmploymentType, Level
from app.domain.money import to_minor_units
from app.seed.catalog import (
    BASE_USD_BY_LEVEL,
    BONUS_RATE_BY_LEVEL,
    COUNTRIES,
    COUNTRY_PAY_FACTOR,
    COUNTRY_WEIGHTS,
    CURRENCIES,
    DEPARTMENT_PAY_FACTOR,
    DEPARTMENT_WEIGHTS,
    EMAIL_DOMAIN,
    EMPLOYMENT_TYPE_WEIGHTS,
    FIRST_NAMES,
    HIRING_WINDOW_END,
    HIRING_WINDOW_START,
    INACTIVE_RATE,
    JOB_TITLES,
    LAST_NAMES,
    LEVEL_WEIGHTS,
    PART_TIME_FACTOR,
    SALES_BONUS_UPLIFT,
    TITLE_PREFIX_BY_LEVEL,
)

_CURRENCY_BY_CODE = {currency.code: currency for currency in CURRENCIES}
_COUNTRY_BY_CODE = {country.code: country for country in COUNTRIES}

_PAY_JITTER_SPREAD = 0.12
"""Standard deviation of the individual pay multiplier.

Real salary bands have within-band spread from negotiation, tenure and
performance. Without it every employee at a given level and location would earn
an identical amount, the median would equal the mean exactly, and the
distribution chart would be a handful of spikes rather than a distribution.
"""

_PAY_JITTER_MIN = 0.72
_PAY_JITTER_MAX = 1.45


@dataclass(frozen=True, slots=True)
class EmployeeSeed:
    """One generated employee, before it is given a database identity."""

    employee_code: str
    first_name: str
    last_name: str
    email: str
    country_code: str
    department: Department
    job_title: str
    level: Level
    employment_type: EmploymentType
    status: EmploymentStatus
    hire_date: date
    compensation: Compensation


def _weighted_choice[T](rng: Random, weights: dict[T, int]) -> T:
    population = list(weights.keys())
    return rng.choices(population, weights=[weights[key] for key in population], k=1)[0]


def _round_to_step(amount: Decimal, step: Decimal) -> Decimal:
    """Round to a realistic pay increment.

    Salaries are negotiated to round numbers, not to arbitrary cents. The step
    scales with the currency so that ₹2,480,000 and $124,000 are both plausible.
    """
    return (amount / step).to_integral_value(rounding=ROUND_HALF_UP) * step


def _pay_step_for(usd_per_unit: Decimal) -> Decimal:
    """A rounding increment worth roughly USD 100 in the local currency."""
    step = Decimal(100) / usd_per_unit
    magnitude = Decimal(10) ** (len(str(int(step))) - 1)
    return magnitude


def _job_title(rng: Random, department: Department, level: Level) -> str:
    return f"{TITLE_PREFIX_BY_LEVEL[level]}{rng.choice(JOB_TITLES[department])}"


def _hire_date(rng: Random) -> date:
    """Sample a hire date skewed toward recent years.

    Squaring a uniform draw biases toward the end of the window, reproducing the
    tenure profile of a growing company: more recent joiners than long-tenured
    staff.
    """
    span_days = (HIRING_WINDOW_END - HIRING_WINDOW_START).days
    recency_bias = rng.random() ** 0.55
    return HIRING_WINDOW_START + timedelta(days=int(span_days * recency_bias))


def _compensation(
    rng: Random,
    country_code: str,
    department: Department,
    level: Level,
    employment_type: EmploymentType,
) -> Compensation:
    currency = _CURRENCY_BY_CODE[_COUNTRY_BY_CODE[country_code].currency_code]

    jitter = min(max(rng.normalvariate(1.0, _PAY_JITTER_SPREAD), _PAY_JITTER_MIN), _PAY_JITTER_MAX)
    base_usd = (
        Decimal(BASE_USD_BY_LEVEL[level])
        * COUNTRY_PAY_FACTOR[country_code]
        * DEPARTMENT_PAY_FACTOR[department]
        * Decimal(str(round(jitter, 4)))
    )
    if employment_type is EmploymentType.PART_TIME:
        base_usd *= PART_TIME_FACTOR

    base_local = _round_to_step(
        base_usd / currency.usd_per_unit, _pay_step_for(currency.usd_per_unit)
    )

    # Contractors are paid a rate, not a bonus — a small but real structural
    # difference that shows up when comparing total compensation across types.
    if employment_type is EmploymentType.CONTRACT:
        bonus_local = Decimal(0)
    else:
        bonus_rate = BONUS_RATE_BY_LEVEL[level]
        if department is Department.SALES:
            bonus_rate += SALES_BONUS_UPLIFT
        bonus_local = _round_to_step(base_local * bonus_rate, _pay_step_for(currency.usd_per_unit))

    return Compensation(
        base_salary_minor=to_minor_units(base_local),
        bonus_minor=to_minor_units(bonus_local),
        currency_code=currency.code,
    )


def _unique_email(first_name: str, last_name: str, taken: set[str]) -> str:
    stem = f"{first_name}.{last_name}".lower()
    candidate = f"{stem}@{EMAIL_DOMAIN}"
    suffix = 1
    while candidate in taken:
        suffix += 1
        candidate = f"{stem}{suffix}@{EMAIL_DOMAIN}"
    taken.add(candidate)
    return candidate


def generate_employees(count: int, seed: int) -> list[EmployeeSeed]:
    """Generate ``count`` employees reproducibly from ``seed``."""
    if count < 0:
        raise ValueError(f"employee count must be non-negative, got {count}")

    rng = Random(seed)
    taken_emails: set[str] = set()
    employees: list[EmployeeSeed] = []

    for ordinal in range(1, count + 1):
        country_code = _weighted_choice(rng, COUNTRY_WEIGHTS)
        department = _weighted_choice(rng, DEPARTMENT_WEIGHTS)
        level = _weighted_choice(rng, LEVEL_WEIGHTS)
        employment_type = _weighted_choice(rng, EMPLOYMENT_TYPE_WEIGHTS)
        status = (
            EmploymentStatus.INACTIVE if rng.random() < INACTIVE_RATE else EmploymentStatus.ACTIVE
        )
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)

        employees.append(
            EmployeeSeed(
                employee_code=f"ACME-{ordinal:05d}",
                first_name=first_name,
                last_name=last_name,
                email=_unique_email(first_name, last_name, taken_emails),
                country_code=country_code,
                department=department,
                job_title=_job_title(rng, department, level),
                level=level,
                employment_type=employment_type,
                status=status,
                hire_date=_hire_date(rng),
                compensation=_compensation(rng, country_code, department, level, employment_type),
            )
        )

    return employees


def assign_managers(employees: Sequence[EmployeeSeed], seed: int) -> dict[str, str]:
    """Map each employee's code to their manager's code.

    Reporting lines run to someone more senior in the same department, which is
    what makes the manager field usable for a "show me this team" question. The
    most senior person in each department reports to nobody, and employees in a
    department with no one above them are left unmanaged rather than being given
    an implausible cross-department manager.
    """
    rng = Random(seed)
    by_department_level: dict[tuple[Department, Level], list[str]] = {}
    for employee in employees:
        by_department_level.setdefault((employee.department, employee.level), []).append(
            employee.employee_code
        )

    ordered_levels = list(Level)
    manager_of: dict[str, str] = {}

    for employee in employees:
        level_index = ordered_levels.index(employee.level)
        candidates = [
            code
            for senior_level in ordered_levels[level_index + 1 :]
            for code in by_department_level.get((employee.department, senior_level), [])
        ]
        if candidates:
            manager_of[employee.employee_code] = rng.choice(candidates)

    return manager_of
