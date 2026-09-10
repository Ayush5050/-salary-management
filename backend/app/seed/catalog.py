"""Reference data and the parameters that shape the seeded population.

Kept as declarative tables rather than buried in generator logic, so the shape
of the synthetic organisation can be read and adjusted in one place. The
multipliers are deliberately plausible rather than authoritative: the goal is a
dataset where the dashboard shows the kind of structure an HR Manager would
actually interrogate — geographic pay differentials, a seniority pyramid,
department premia — not a claim about real market rates.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from app.domain.enums import Department, EmploymentType, Level


@dataclass(frozen=True, slots=True)
class CurrencySeed:
    code: str
    name: str
    symbol: str
    usd_per_unit: Decimal


@dataclass(frozen=True, slots=True)
class CountrySeed:
    code: str
    name: str
    region: str
    currency_code: str


RATES_AS_OF: Final[date] = date(2026, 6, 30)

CURRENCIES: Final[tuple[CurrencySeed, ...]] = (
    CurrencySeed("USD", "US Dollar", "$", Decimal("1.0")),
    CurrencySeed("GBP", "Pound Sterling", "£", Decimal("1.27")),
    CurrencySeed("EUR", "Euro", "€", Decimal("1.09")),
    CurrencySeed("INR", "Indian Rupee", "₹", Decimal("0.012")),
    CurrencySeed("SGD", "Singapore Dollar", "S$", Decimal("0.74")),
    CurrencySeed("AUD", "Australian Dollar", "A$", Decimal("0.66")),
    CurrencySeed("CAD", "Canadian Dollar", "C$", Decimal("0.73")),
    CurrencySeed("BRL", "Brazilian Real", "R$", Decimal("0.185")),
    CurrencySeed("JPY", "Japanese Yen", "¥", Decimal("0.0067")),
)

COUNTRIES: Final[tuple[CountrySeed, ...]] = (
    CountrySeed("US", "United States", "Americas", "USD"),
    CountrySeed("CA", "Canada", "Americas", "CAD"),
    CountrySeed("BR", "Brazil", "Americas", "BRL"),
    CountrySeed("GB", "United Kingdom", "EMEA", "GBP"),
    CountrySeed("DE", "Germany", "EMEA", "EUR"),
    CountrySeed("FR", "France", "EMEA", "EUR"),
    CountrySeed("IN", "India", "APAC", "INR"),
    CountrySeed("SG", "Singapore", "APAC", "SGD"),
    CountrySeed("AU", "Australia", "APAC", "AUD"),
    CountrySeed("JP", "Japan", "APAC", "JPY"),
)

# Headcount distribution. A US-headquartered company with a large India
# engineering presence — a common enough shape to make the country breakdown
# interesting rather than uniform.
COUNTRY_WEIGHTS: Final[dict[str, int]] = {
    "US": 30,
    "IN": 22,
    "GB": 10,
    "DE": 9,
    "CA": 6,
    "BR": 5,
    "SG": 5,
    "AU": 5,
    "FR": 5,
    "JP": 3,
}

DEPARTMENT_WEIGHTS: Final[dict[Department, int]] = {
    Department.ENGINEERING: 34,
    Department.SALES: 14,
    Department.CUSTOMER_SUCCESS: 10,
    Department.OPERATIONS: 8,
    Department.MARKETING: 7,
    Department.PRODUCT: 7,
    Department.FINANCE: 6,
    Department.PEOPLE: 6,
    Department.DESIGN: 5,
    Department.LEGAL: 3,
}

# A seniority pyramid: many juniors, few executives.
LEVEL_WEIGHTS: Final[dict[Level, int]] = {
    Level.L1: 180,
    Level.L2: 260,
    Level.L3: 220,
    Level.L4: 140,
    Level.L5: 90,
    Level.L6: 60,
    Level.L7: 35,
    Level.L8: 15,
}

EMPLOYMENT_TYPE_WEIGHTS: Final[dict[EmploymentType, int]] = {
    EmploymentType.FULL_TIME: 88,
    EmploymentType.PART_TIME: 6,
    EmploymentType.CONTRACT: 6,
}

INACTIVE_RATE: Final[float] = 0.06
"""Share of records that are former employees.

Non-zero on purpose: it makes the "active only" default filter meaningful, and
surfaces the bug where headcount and payroll spend disagree about who counts.
"""

# Reference annual base compensation in USD, before location and department
# adjustment.
BASE_USD_BY_LEVEL: Final[dict[Level, int]] = {
    Level.L1: 48_000,
    Level.L2: 72_000,
    Level.L3: 104_000,
    Level.L4: 142_000,
    Level.L5: 186_000,
    Level.L6: 245_000,
    Level.L7: 330_000,
    Level.L8: 470_000,
}

# Location factors relative to the US.
COUNTRY_PAY_FACTOR: Final[dict[str, Decimal]] = {
    "US": Decimal("1.00"),
    "CA": Decimal("0.80"),
    "GB": Decimal("0.84"),
    "DE": Decimal("0.82"),
    "FR": Decimal("0.76"),
    "SG": Decimal("0.79"),
    "AU": Decimal("0.86"),
    "JP": Decimal("0.72"),
    "IN": Decimal("0.30"),
    "BR": Decimal("0.34"),
}

DEPARTMENT_PAY_FACTOR: Final[dict[Department, Decimal]] = {
    Department.ENGINEERING: Decimal("1.10"),
    Department.PRODUCT: Decimal("1.06"),
    Department.LEGAL: Decimal("1.04"),
    Department.SALES: Decimal("1.00"),
    Department.FINANCE: Decimal("0.96"),
    Department.DESIGN: Decimal("0.95"),
    Department.MARKETING: Decimal("0.90"),
    Department.PEOPLE: Decimal("0.86"),
    Department.OPERATIONS: Decimal("0.85"),
    Department.CUSTOMER_SUCCESS: Decimal("0.82"),
}

# Bonus as a share of base. Rises with seniority; sales carries a commission-like
# uplift, which is why the dashboard compares total compensation rather than base.
BONUS_RATE_BY_LEVEL: Final[dict[Level, Decimal]] = {
    Level.L1: Decimal("0.04"),
    Level.L2: Decimal("0.06"),
    Level.L3: Decimal("0.09"),
    Level.L4: Decimal("0.12"),
    Level.L5: Decimal("0.16"),
    Level.L6: Decimal("0.22"),
    Level.L7: Decimal("0.30"),
    Level.L8: Decimal("0.45"),
}

SALES_BONUS_UPLIFT: Final[Decimal] = Decimal("0.18")
PART_TIME_FACTOR: Final[Decimal] = Decimal("0.60")

JOB_TITLES: Final[dict[Department, tuple[str, ...]]] = {
    Department.ENGINEERING: (
        "Software Engineer",
        "Backend Engineer",
        "Frontend Engineer",
        "Platform Engineer",
        "Data Engineer",
        "Site Reliability Engineer",
        "QA Engineer",
        "Mobile Engineer",
    ),
    Department.PRODUCT: ("Product Manager", "Technical Product Manager", "Product Analyst"),
    Department.DESIGN: ("Product Designer", "UX Researcher", "Design Systems Designer"),
    Department.SALES: (
        "Account Executive",
        "Sales Development Representative",
        "Solutions Engineer",
        "Enterprise Account Executive",
    ),
    Department.MARKETING: (
        "Marketing Manager",
        "Content Strategist",
        "Demand Generation Manager",
        "Product Marketing Manager",
    ),
    Department.FINANCE: ("Financial Analyst", "Accountant", "Treasury Analyst", "Controller"),
    Department.PEOPLE: (
        "People Partner",
        "Talent Acquisition Specialist",
        "Compensation Analyst",
        "People Operations Specialist",
    ),
    Department.CUSTOMER_SUCCESS: (
        "Customer Success Manager",
        "Support Engineer",
        "Onboarding Specialist",
        "Renewals Manager",
    ),
    Department.LEGAL: ("Counsel", "Contracts Manager", "Compliance Specialist"),
    Department.OPERATIONS: (
        "Business Operations Analyst",
        "Workplace Coordinator",
        "Procurement Specialist",
        "Program Manager",
    ),
}

# Seniority prefixes applied to the department's base title.
TITLE_PREFIX_BY_LEVEL: Final[dict[Level, str]] = {
    Level.L1: "Associate ",
    Level.L2: "",
    Level.L3: "Senior ",
    Level.L4: "Staff ",
    Level.L5: "Principal ",
    Level.L6: "Director of ",
    Level.L7: "VP of ",
    Level.L8: "Chief ",
}

FIRST_NAMES: Final[tuple[str, ...]] = (
    "Aarav",
    "Ada",
    "Adeola",
    "Ahmed",
    "Aiko",
    "Alejandro",
    "Amelia",
    "Ana",
    "Anders",
    "Anika",
    "Antoine",
    "Beatriz",
    "Bilal",
    "Camila",
    "Carlos",
    "Chen",
    "Chloe",
    "Daniel",
    "Diego",
    "Elena",
    "Elias",
    "Emeka",
    "Emma",
    "Farah",
    "Felix",
    "Fatima",
    "Gabriel",
    "Grace",
    "Hannah",
    "Hiroshi",
    "Ines",
    "Isabel",
    "Ivan",
    "Jasmine",
    "Javier",
    "Jonas",
    "Julia",
    "Kaito",
    "Karin",
    "Kavya",
    "Kwame",
    "Laura",
    "Leon",
    "Liam",
    "Lucia",
    "Mateo",
    "Maya",
    "Mei",
    "Mohammed",
    "Naomi",
    "Nikhil",
    "Noah",
    "Olivia",
    "Omar",
    "Priya",
    "Rafael",
    "Rahul",
    "Rania",
    "Ravi",
    "Rosa",
    "Sofia",
    "Sanjay",
    "Sven",
    "Tariq",
    "Thomas",
    "Yuki",
    "Zara",
    "Zoe",
)

LAST_NAMES: Final[tuple[str, ...]] = (
    "Almeida",
    "Andersson",
    "Bakker",
    "Bianchi",
    "Chatterjee",
    "Chen",
    "Costa",
    "Dubois",
    "Eriksson",
    "Ferreira",
    "Fischer",
    "Garcia",
    "Gupta",
    "Haddad",
    "Hoffmann",
    "Ibrahim",
    "Iyer",
    "Jensen",
    "Kaur",
    "Khan",
    "Kimura",
    "Kowalski",
    "Lambert",
    "Lindqvist",
    "Lopez",
    "Martins",
    "Mehta",
    "Mendes",
    "Moreau",
    "Mueller",
    "Nakamura",
    "Nguyen",
    "Novak",
    "Okafor",
    "Oliveira",
    "Osei",
    "Patel",
    "Pereira",
    "Petrov",
    "Rahman",
    "Ramirez",
    "Reddy",
    "Ribeiro",
    "Rossi",
    "Saito",
    "Santos",
    "Schneider",
    "Sharma",
    "Silva",
    "Singh",
    "Sorensen",
    "Suzuki",
    "Tanaka",
    "Torres",
    "Vargas",
    "Verma",
    "Wagner",
    "Walsh",
    "Wang",
    "Weber",
    "Yamamoto",
    "Zhang",
)

EMAIL_DOMAIN: Final[str] = "acme.example"

HIRING_WINDOW_START: Final[date] = date(2015, 1, 5)
HIRING_WINDOW_END: Final[date] = date(2026, 6, 30)
