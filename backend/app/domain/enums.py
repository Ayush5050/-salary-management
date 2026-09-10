"""Controlled vocabularies for the employee record.

Departments and levels are modelled as enumerations rather than as reference
tables. The confirmed scope has no organisation-design features — the HR Manager
cannot create a department — so a table would add CRUD surface, a join and a
migration path for no behaviour the persona asked for. Promoting either to a
table later is additive: the column already stores the string value.

Levels use ``L1``..``L8`` values so that ordering by the stored column is also
ordering by seniority, without a join or a CASE expression.
"""

from enum import StrEnum
from typing import Final


class Department(StrEnum):
    ENGINEERING = "ENGINEERING"
    PRODUCT = "PRODUCT"
    DESIGN = "DESIGN"
    SALES = "SALES"
    MARKETING = "MARKETING"
    FINANCE = "FINANCE"
    PEOPLE = "PEOPLE"
    CUSTOMER_SUCCESS = "CUSTOMER_SUCCESS"
    LEGAL = "LEGAL"
    OPERATIONS = "OPERATIONS"


class Level(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"
    L7 = "L7"
    L8 = "L8"


class EmploymentType(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"


class EmploymentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class BreakdownDimension(StrEnum):
    """Columns the dashboard can group compensation by."""

    COUNTRY = "COUNTRY"
    DEPARTMENT = "DEPARTMENT"
    LEVEL = "LEVEL"


class EmployeeSortField(StrEnum):
    """Sortable columns, each backed by an index (see :mod:`app.models`)."""

    NAME = "NAME"
    HIRE_DATE = "HIRE_DATE"
    DEPARTMENT = "DEPARTMENT"
    LEVEL = "LEVEL"
    COUNTRY = "COUNTRY"
    TOTAL_COMP_USD = "TOTAL_COMP_USD"


class SortDirection(StrEnum):
    ASC = "ASC"
    DESC = "DESC"


DEPARTMENT_LABELS: Final[dict[Department, str]] = {
    Department.ENGINEERING: "Engineering",
    Department.PRODUCT: "Product",
    Department.DESIGN: "Design",
    Department.SALES: "Sales",
    Department.MARKETING: "Marketing",
    Department.FINANCE: "Finance",
    Department.PEOPLE: "People",
    Department.CUSTOMER_SUCCESS: "Customer Success",
    Department.LEGAL: "Legal",
    Department.OPERATIONS: "Operations",
}

LEVEL_LABELS: Final[dict[Level, str]] = {
    Level.L1: "L1 · Associate",
    Level.L2: "L2 · Engineer",
    Level.L3: "L3 · Senior",
    Level.L4: "L4 · Staff",
    Level.L5: "L5 · Principal",
    Level.L6: "L6 · Director",
    Level.L7: "L7 · Vice President",
    Level.L8: "L8 · Executive",
}

EMPLOYMENT_TYPE_LABELS: Final[dict[EmploymentType, str]] = {
    EmploymentType.FULL_TIME: "Full time",
    EmploymentType.PART_TIME: "Part time",
    EmploymentType.CONTRACT: "Contract",
}
