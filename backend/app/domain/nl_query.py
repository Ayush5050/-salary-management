"""Translating a plain-English question into a validated filter.

The security-relevant design decision is what this produces. It emits an
:class:`~app.domain.filters.EmployeeFilters` — the same value object the filter
panel produces — and *never* SQL. Everything downstream is the ordinary,
already-tested query path, so a question cannot reach the database as anything
other than a parameterised predicate over known columns. A translator that
emitted SQL would make every parsing bug a potential injection.

The translation itself is a deterministic grammar rather than a language model,
which is a deliberate trade:

*   A compensation report has to be reproducible. The same question must give
    the same answer today and at quarter end, which a sampled model does not
    guarantee.
*   It is unit-testable, with no API key, no network call and no cost — so a
    reviewer can actually run it.
*   It fails honestly. Unrecognised words are *reported*, not quietly ignored,
    so the HR Manager never gets a confidently wrong answer to a question the
    system only half understood.

Swapping in a model is a contained change: :func:`parse_question` is the only
seam, and any replacement must return the same ``ParsedQuestion``. The
validation, the echoed interpretation and the filter model stay exactly as they
are — the guardrails live in the type, not in the translator.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from app.domain.enums import (
    DEPARTMENT_LABELS,
    LEVEL_LABELS,
    BreakdownDimension,
    Department,
    EmploymentStatus,
    EmploymentType,
    Level,
)
from app.domain.filters import DEFAULT_STATUSES, EmployeeFilters
from app.domain.money import MINOR_UNITS_PER_MAJOR


@dataclass(frozen=True, slots=True)
class QueryVocabulary:
    """The terms the parser can recognise.

    Built from live reference data rather than hardcoded, so adding a country to
    the database teaches the parser that country with no code change.
    """

    country_names: dict[str, str]
    """Lower-cased country name to ISO code, matched case-insensitively."""

    country_codes: tuple[str, ...]
    """ISO codes, matched **case-sensitively** against the original question.

    Two-letter codes collide with ordinary English words — ``IN`` is India and
    also the commonest preposition in these questions, so "salaries in Germany"
    would otherwise select India as well. Requiring the upper-case form matches
    how a person actually writes a country code and removes the ambiguity
    without a list of special cases.
    """

    @classmethod
    def from_countries(cls, countries_by_code: dict[str, str]) -> "QueryVocabulary":
        """``{"DE": "Germany"}`` becomes recognisers for the name and the code."""
        return cls(
            country_names={name.lower(): code for code, name in countries_by_code.items()},
            country_codes=tuple(countries_by_code),
        )


@dataclass(frozen=True, slots=True)
class ParsedQuestion:
    """What the parser understood, and what it did not."""

    filters: EmployeeFilters
    dimension: BreakdownDimension | None
    interpretation: str
    """A plain-English echo of the applied filters.

    Shown back to the user before they act on the answer. Without it, a
    misparse is indistinguishable from a surprising-but-correct result.
    """

    unrecognised_terms: tuple[str, ...]
    matched_anything: bool


_MONEY_PATTERN: Final = re.compile(
    r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|m|thousand|million)?\b", re.IGNORECASE
)
_MULTIPLIERS: Final[dict[str, int]] = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
}

_ABOVE_WORDS: Final = ("above", "over", "more than", "greater than", "at least", "earning over")
_BELOW_WORDS: Final = ("below", "under", "less than", "at most", "no more than")

_DIMENSION_WORDS: Final[dict[BreakdownDimension, tuple[str, ...]]] = {
    BreakdownDimension.COUNTRY: ("by country", "per country", "by location", "across countries"),
    BreakdownDimension.DEPARTMENT: (
        "by department",
        "per department",
        "by team",
        "across departments",
    ),
    BreakdownDimension.LEVEL: ("by level", "per level", "by seniority", "across levels"),
}

_INACTIVE_WORDS: Final = ("former", "inactive", "ex-employee", "who left", "leavers", "departed")
_ACTIVE_WORDS: Final = ("current", "active", "still here")
_ALL_STATUS_WORDS: Final = ("everyone ever", "including former", "all employees ever")

_EMPLOYMENT_TYPE_WORDS: Final[dict[EmploymentType, tuple[str, ...]]] = {
    EmploymentType.CONTRACT: ("contractor", "contractors", "contract"),
    EmploymentType.PART_TIME: ("part time", "part-time"),
    EmploymentType.FULL_TIME: ("full time", "full-time"),
}

# Words with no filtering meaning. Reporting these back as "not understood"
# would be noise, since dropping them changes nothing.
_STOP_WORD_TEXT: Final = (
    "a an and are as at be by do does for from get give how i in is it list me my of on or our "
    "people employees employee please salaries salary compensation comp pay paid show tell "
    "that the "
    "their them there they to us was we were what when where which who whom whose with you your "
    "average mean median total spend much many number count highest lowest top bottom sorted sort "
    "breakdown break down group grouped summary report earning earn earns make makes making paying"
)
_STOP_WORDS: Final[frozenset[str]] = frozenset(_STOP_WORD_TEXT.split())

_WORD_PATTERN: Final = re.compile(r"[a-z][a-z'\-]*")


def _normalise(question: str) -> str:
    return re.sub(r"\s+", " ", question.lower()).strip()


def _consume_matching(text: str, phrase: str, flags: int) -> tuple[bool, str]:
    """Remove ``phrase`` from ``text`` if present on word boundaries.

    Consuming rather than merely detecting is what stops one term being counted
    twice — "by country" is removed before country names are scanned, so the
    grouping request cannot also be read as a country.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", flags)
    if pattern.search(text) is None:
        return False, text
    return True, pattern.sub(" ", text, count=1)


def _consume(text: str, phrase: str) -> tuple[bool, str]:
    """Consume a phrase regardless of casing — the usual case."""
    return _consume_matching(text, phrase, re.IGNORECASE)


def _consume_exact(text: str, phrase: str) -> tuple[bool, str]:
    """Consume a phrase only in the exact casing given.

    Used for country codes, where matching case-insensitively would read the
    preposition "in" as India.
    """
    return _consume_matching(text, phrase, 0)


def _amount_to_usd_minor(digits: str, suffix: str | None) -> int:
    amount = Decimal(digits.replace(",", ""))
    if suffix is not None:
        amount *= _MULTIPLIERS[suffix.lower()]
    return int(amount * MINOR_UNITS_PER_MAJOR)


def _parse_compensation_bounds(text: str) -> tuple[int | None, int | None, str]:
    """Extract a compensation range, returning bounds and the remaining text.

    ``between X and Y`` is handled before the one-sided comparators, because
    "between" also contains no comparator word and would otherwise leave both
    amounts unclaimed.
    """
    between = re.search(
        rf"between\s+{_MONEY_PATTERN.pattern}\s+and\s+{_MONEY_PATTERN.pattern}",
        text,
        re.IGNORECASE,
    )
    if between is not None:
        lower = _amount_to_usd_minor(between.group(1), between.group(2))
        upper = _amount_to_usd_minor(between.group(3), between.group(4))
        remaining = text[: between.start()] + " " + text[between.end() :]
        return min(lower, upper), max(lower, upper), remaining

    minimum: int | None = None
    maximum: int | None = None
    remaining = text

    for words, is_lower_bound in ((_ABOVE_WORDS, True), (_BELOW_WORDS, False)):
        for word in words:
            match = re.search(rf"{re.escape(word)}\s+{_MONEY_PATTERN.pattern}", remaining)
            if match is None:
                continue
            amount = _amount_to_usd_minor(match.group(1), match.group(2))
            if is_lower_bound:
                minimum = amount
            else:
                maximum = amount
            remaining = remaining[: match.start()] + " " + remaining[match.end() :]
            break

    return minimum, maximum, remaining


def _describe(filters: EmployeeFilters, dimension: BreakdownDimension | None) -> str:
    """Render the applied filters as a sentence the HR Manager can check."""
    parts: list[str] = []

    if filters.statuses == (EmploymentStatus.ACTIVE,):
        parts.append("Current employees")
    elif filters.statuses == (EmploymentStatus.INACTIVE,):
        parts.append("Former employees")
    else:
        parts.append("All employees, current and former")

    if filters.employment_types:
        types = ", ".join(t.value.replace("_", " ").lower() for t in filters.employment_types)
        parts.append(f"on {types} contracts")
    if filters.departments:
        parts.append(f"in {', '.join(DEPARTMENT_LABELS[d] for d in filters.departments)}")
    if filters.levels:
        parts.append(
            f"at {', '.join(LEVEL_LABELS[level].split(' · ')[0] for level in filters.levels)}"
        )
    if filters.countries:
        parts.append(f"based in {', '.join(filters.countries)}")

    lower, upper = filters.min_total_comp_usd_minor, filters.max_total_comp_usd_minor
    if lower is not None and upper is not None:
        parts.append(
            f"earning between ${lower // MINOR_UNITS_PER_MAJOR:,} "
            f"and ${upper // MINOR_UNITS_PER_MAJOR:,}"
        )
    elif lower is not None:
        parts.append(f"earning over ${lower // MINOR_UNITS_PER_MAJOR:,}")
    elif upper is not None:
        parts.append(f"earning under ${upper // MINOR_UNITS_PER_MAJOR:,}")

    if filters.search is not None:
        parts.append(f'matching "{filters.search}"')
    if dimension is not None:
        parts.append(f"grouped by {dimension.value.lower()}")

    return " ".join(parts)


def parse_question(question: str, vocabulary: QueryVocabulary) -> ParsedQuestion:
    """Translate a question into a validated filter selection.

    The one seam a language-model translator would replace. Any replacement must
    return this same type, so the validation and the echoed interpretation apply
    regardless of how the terms were recognised.
    """
    if not question.strip():
        raise ValueError("question is empty")

    # Country codes are matched first, against the original casing, before the
    # question is lower-cased for everything else. See QueryVocabulary.
    countries: list[str] = []
    cased_text = question
    for code in sorted(vocabulary.country_codes, key=len, reverse=True):
        found, cased_text = _consume_exact(cased_text, code)
        if found and code not in countries:
            countries.append(code)

    text = _normalise(cased_text)

    dimension: BreakdownDimension | None = None
    for candidate, phrases in _DIMENSION_WORDS.items():
        for phrase in phrases:
            found, text = _consume(text, phrase)
            if found:
                dimension = candidate
                break
        if dimension is not None:
            break

    minimum, maximum, text = _parse_compensation_bounds(text)

    # Longest name first, so "united states" is not shattered by a stray match.
    for phrase in sorted(vocabulary.country_names, key=len, reverse=True):
        found, text = _consume(text, phrase)
        if found:
            code = vocabulary.country_names[phrase]
            if code not in countries:
                countries.append(code)

    departments: list[Department] = []
    for department, label in sorted(
        DEPARTMENT_LABELS.items(), key=lambda item: len(item[1]), reverse=True
    ):
        for phrase in (label.lower(), department.value.lower().replace("_", " ")):
            found, text = _consume(text, phrase)
            if found and department not in departments:
                departments.append(department)

    levels: list[Level] = []
    for level in Level:
        found, text = _consume(text, level.value.lower())
        if found:
            levels.append(level)

    employment_types: list[EmploymentType] = []
    for employment_type, phrases in _EMPLOYMENT_TYPE_WORDS.items():
        for phrase in phrases:
            found, text = _consume(text, phrase)
            if found and employment_type not in employment_types:
                employment_types.append(employment_type)

    statuses: tuple[EmploymentStatus, ...] = DEFAULT_STATUSES
    for phrase in _ALL_STATUS_WORDS:
        found, text = _consume(text, phrase)
        if found:
            statuses = ()
    for phrase in _INACTIVE_WORDS:
        found, text = _consume(text, phrase)
        if found:
            statuses = (EmploymentStatus.INACTIVE,)
    for phrase in _ACTIVE_WORDS:
        found, text = _consume(text, phrase)
        if found:
            statuses = (EmploymentStatus.ACTIVE,)

    leftover = [
        word for word in _WORD_PATTERN.findall(text) if word not in _STOP_WORDS and len(word) > 1
    ]

    matched_anything = (
        bool(countries or departments or levels or employment_types or dimension)
        or minimum is not None
        or maximum is not None
    )

    # Only fall back to free-text search when nothing structured was recognised.
    # Doing it alongside a structured match would silently intersect a name
    # search with a department filter and return nothing, which reads as "no
    # such people" rather than "I misunderstood you".
    search = " ".join(leftover) if leftover and not matched_anything else None

    # A question like "over $200k and under $100k" is contradictory and would be
    # rejected by the filter model. Dropping the upper bound before constructing
    # it keeps the question answerable, and the echoed interpretation shows the
    # user which half was applied.
    if minimum is not None and maximum is not None and minimum > maximum:
        maximum = None

    filters = EmployeeFilters(
        search=search,
        countries=tuple(countries),
        departments=tuple(departments),
        levels=tuple(levels),
        employment_types=tuple(employment_types),
        statuses=statuses,
        min_total_comp_usd_minor=minimum,
        max_total_comp_usd_minor=maximum,
    )

    return ParsedQuestion(
        filters=filters,
        dimension=dimension,
        interpretation=_describe(filters, dimension),
        unrecognised_terms=() if search is not None else tuple(leftover),
        matched_anything=matched_anything or search is not None,
    )
