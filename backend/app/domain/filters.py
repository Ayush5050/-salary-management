"""The shared filter model.

One of the load-bearing product decisions: the employee list and the analytics
dashboard consume the *same* filter object. A number on the dashboard is
therefore always the aggregate of a list the HR Manager can navigate to and
inspect — "€4.2M in Germany" is one click away from the 340 people it is the sum
of. Two separate filter models would let those two views drift apart, and an
unverifiable dashboard is worse than no dashboard.

The model is a frozen dataclass rather than a Pydantic model because it is a
domain value, not a wire format: the HTTP layer parses query parameters into it,
and the repositories translate it into SQL predicates. Neither layer owns it.
"""

from dataclasses import dataclass
from typing import Final, Self

from app.domain.enums import Department, EmploymentStatus, EmploymentType, Level

DEFAULT_STATUSES: Final[tuple[EmploymentStatus, ...]] = (EmploymentStatus.ACTIVE,)
"""The selection an unqualified question implies.

"What do we pay engineers?" means the people on the payroll now. Former
employees stay one filter away, but including them by default would silently
inflate every headline figure.
"""


@dataclass(frozen=True, slots=True)
class EmployeeFilters:
    """A selection over the employee population.

    Every collection field is conjunctive across fields and disjunctive within
    one: ``countries=("DE", "FR")`` with ``departments=("SALES",)`` selects sales
    employees in Germany *or* France. An empty collection means "no constraint on
    this field", which is the natural reading of an untouched filter control.
    """

    search: str | None
    countries: tuple[str, ...]
    departments: tuple[Department, ...]
    levels: tuple[Level, ...]
    employment_types: tuple[EmploymentType, ...]
    statuses: tuple[EmploymentStatus, ...]
    min_total_comp_usd_minor: int | None
    max_total_comp_usd_minor: int | None

    def __post_init__(self) -> None:
        lower = self.min_total_comp_usd_minor
        upper = self.max_total_comp_usd_minor
        if lower is not None and lower < 0:
            raise ValueError(f"minimum compensation must be non-negative, got {lower}")
        if upper is not None and upper < 0:
            raise ValueError(f"maximum compensation must be non-negative, got {upper}")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(
                f"minimum compensation {lower} exceeds maximum {upper}; "
                "the range would select no employees"
            )

    @classmethod
    def unfiltered(cls) -> Self:
        """The whole population — the dashboard's default view."""
        return cls(
            search=None,
            countries=(),
            departments=(),
            levels=(),
            employment_types=(),
            statuses=(),
            min_total_comp_usd_minor=None,
            max_total_comp_usd_minor=None,
        )

    @property
    def is_empty(self) -> bool:
        """Whether this selects the whole population, used to label the UI."""
        return self == type(self).unfiltered()
