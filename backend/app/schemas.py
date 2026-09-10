"""HTTP request and response models.

**Money on the wire is always an integer count of minor units**, in both
directions, with the currency alongside it. JSON numbers are IEEE doubles in
every JavaScript client, so sending ``170000.50`` invites exactly the rounding
the backend works to avoid. Integers up to 2^53 are exact in JavaScript, and the
largest value here — a payroll total in FX-scaled minor units — stays far below
that. The frontend has a single pair of helpers for the conversion.
"""

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.deps import filters_to_query_string
from app.domain.enums import (
    DEPARTMENT_LABELS,
    EMPLOYMENT_TYPE_LABELS,
    LEVEL_LABELS,
    BreakdownDimension,
    Department,
    EmploymentStatus,
    EmploymentType,
    Level,
)
from app.domain.money import descale_fx
from app.domain.nl_query import ParsedQuestion
from app.models import Country, Currency, Employee
from app.repositories.analytics import BandCount, CompensationStats


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ManagerRef(ApiModel):
    id: int
    employee_code: str
    full_name: str

    @classmethod
    def of(cls, manager: Employee) -> Self:
        return cls(
            id=manager.id,
            employee_code=manager.employee_code,
            full_name=f"{manager.first_name} {manager.last_name}",
        )


class EmployeeRow(ApiModel):
    """An employee as shown in the list."""

    id: int
    employee_code: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    country_code: str
    country_name: str
    department: Department
    department_label: str
    job_title: str
    level: Level
    level_label: str
    employment_type: EmploymentType
    employment_type_label: str
    status: EmploymentStatus
    hire_date: date

    currency_code: str
    currency_symbol: str
    base_salary_minor: int
    bonus_minor: int
    total_comp_local_minor: int
    total_comp_usd_minor: int

    @classmethod
    def of(cls, employee: Employee) -> Self:
        return cls(
            id=employee.id,
            employee_code=employee.employee_code,
            first_name=employee.first_name,
            last_name=employee.last_name,
            full_name=f"{employee.first_name} {employee.last_name}",
            email=employee.email,
            country_code=employee.country_code,
            country_name=employee.country.name,
            department=employee.department,
            department_label=DEPARTMENT_LABELS[employee.department],
            job_title=employee.job_title,
            level=employee.level,
            level_label=LEVEL_LABELS[employee.level],
            employment_type=employee.employment_type,
            employment_type_label=EMPLOYMENT_TYPE_LABELS[employee.employment_type],
            status=employee.status,
            hire_date=employee.hire_date,
            currency_code=employee.currency_code,
            currency_symbol=employee.currency.symbol,
            base_salary_minor=employee.base_salary_minor,
            bonus_minor=employee.bonus_minor,
            total_comp_local_minor=employee.base_salary_minor + employee.bonus_minor,
            total_comp_usd_minor=descale_fx(employee.total_comp_usd_fx_scaled),
        )


class EmployeeDetail(EmployeeRow):
    manager: ManagerRef | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, employee: Employee) -> Self:
        return cls(
            **EmployeeRow.of(employee).model_dump(),
            manager=None if employee.manager is None else ManagerRef.of(employee.manager),
            created_at=employee.created_at,
            updated_at=employee.updated_at,
        )


class EmployeeWrite(ApiModel):
    """The body accepted by create and replace.

    Validation here is about shape and range; identity conflicts and reference
    integrity are the repository's to enforce, because only it can see the rest
    of the table.
    """

    employee_code: str = Field(min_length=1, max_length=16)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    country_code: str = Field(min_length=2, max_length=2)
    department: Department
    job_title: str = Field(min_length=1, max_length=120)
    level: Level
    employment_type: EmploymentType
    status: EmploymentStatus
    hire_date: date
    manager_id: int | None
    currency_code: str = Field(min_length=3, max_length=3)
    base_salary_minor: int = Field(ge=0)
    bonus_minor: int = Field(ge=0)


class StatusChange(ApiModel):
    status: EmploymentStatus


class PageMeta(ApiModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class EmployeeListResponse(ApiModel):
    items: list[EmployeeRow]
    meta: PageMeta


class StatsResponse(ApiModel):
    """Compensation statistics, all in USD minor units.

    Everything but headcount and total is nullable, because a selection matching
    nobody has no average or median — a distinction the UI renders as "—"
    rather than as a misleading zero.
    """

    headcount: int
    total_usd_minor: int
    average_usd_minor: int | None
    median_usd_minor: int | None
    min_usd_minor: int | None
    max_usd_minor: int | None

    @classmethod
    def of(cls, stats: CompensationStats) -> Self:
        return cls(
            headcount=stats.headcount,
            total_usd_minor=stats.total_usd_minor,
            average_usd_minor=stats.average_usd_minor,
            median_usd_minor=stats.median_usd_minor,
            min_usd_minor=stats.min_usd_minor,
            max_usd_minor=stats.max_usd_minor,
        )


class BreakdownGroup(ApiModel):
    key: str
    label: str
    stats: StatsResponse


class BandResponse(ApiModel):
    label: str
    lower_usd_minor: int
    upper_usd_minor: int | None
    headcount: int

    @classmethod
    def of(cls, band: BandCount) -> Self:
        return cls(
            label=band.label,
            lower_usd_minor=band.lower_usd_minor,
            upper_usd_minor=band.upper_usd_minor,
            headcount=band.headcount,
        )


class QuestionRequest(ApiModel):
    question: str = Field(min_length=1, max_length=500)


class ParsedQueryResponse(ApiModel):
    """What a question was understood to mean.

    ``query_string`` is the whole point: the client navigates to it, so an
    answered question lands on the same filtered view a person would have built
    by hand, served by the same endpoints. There is no parallel "AI answer" path
    that could disagree with the rest of the app.
    """

    interpretation: str
    query_string: str
    dimension: BreakdownDimension | None
    unrecognised_terms: list[str]
    understood: bool

    @classmethod
    def of(cls, parsed: ParsedQuestion) -> Self:
        return cls(
            interpretation=parsed.interpretation,
            query_string=filters_to_query_string(parsed.filters),
            dimension=parsed.dimension,
            unrecognised_terms=list(parsed.unrecognised_terms),
            understood=parsed.matched_anything,
        )


class CountryOption(ApiModel):
    code: str
    name: str
    region: str
    default_currency_code: str

    @classmethod
    def of(cls, country: Country) -> Self:
        return cls(
            code=country.code,
            name=country.name,
            region=country.region,
            default_currency_code=country.default_currency_code,
        )


class CurrencyOption(ApiModel):
    code: str
    name: str
    symbol: str

    @classmethod
    def of(cls, currency: Currency) -> Self:
        return cls(code=currency.code, name=currency.name, symbol=currency.symbol)


class LabelledOption(ApiModel):
    value: str
    label: str


class ReferenceData(ApiModel):
    """Everything the filter panel and the employee form need, in one request.

    Bundled deliberately: these lists change with a deployment, not with the
    data, so the client fetches them once instead of making five requests every
    time a form opens.
    """

    countries: list[CountryOption]
    currencies: list[CurrencyOption]
    departments: list[LabelledOption]
    levels: list[LabelledOption]
    employment_types: list[LabelledOption]
    statuses: list[LabelledOption]
    base_currency: str
