"""Natural-language question parsing.

The parser is deterministic, so it is tested by example rather than by
approximation — every case here is an exact expectation, which is the point of
choosing a grammar over a model for this job.
"""

import pytest

from app.domain.enums import BreakdownDimension, Department, EmploymentStatus, EmploymentType, Level
from app.domain.nl_query import QueryVocabulary, parse_question

VOCABULARY = QueryVocabulary.from_countries(
    {
        "US": "United States",
        "DE": "Germany",
        "IN": "India",
        "GB": "United Kingdom",
    }
)


def parse(question: str):
    return parse_question(question, VOCABULARY)


class TestCountries:
    def test_recognises_a_country_by_name(self):
        assert parse("what do we pay people in Germany?").filters.countries == ("DE",)

    def test_recognises_a_country_by_code(self):
        assert parse("show me employees in DE").filters.countries == ("DE",)

    def test_recognises_a_multi_word_country_name(self):
        """ "United States" must not be shattered by a partial match."""
        assert parse("salaries in the United States").filters.countries == ("US",)

    def test_recognises_several_countries(self):
        assert set(parse("pay in Germany and India").filters.countries) == {"DE", "IN"}

    def test_vocabulary_comes_from_reference_data(self):
        """A country absent from the database is not recognised, rather than
        being guessed at."""
        assert parse("salaries in Germany").filters.countries == ("DE",)
        assert parse("salaries in Narnia").filters.countries == ()


class TestDepartmentsAndLevels:
    def test_recognises_a_department(self):
        assert parse("what do we pay engineering?").filters.departments == (Department.ENGINEERING,)

    def test_recognises_a_multi_word_department(self):
        assert parse("customer success salaries").filters.departments == (
            Department.CUSTOMER_SUCCESS,
        )

    def test_recognises_a_level(self):
        assert parse("what do L5 employees earn").filters.levels == (Level.L5,)

    def test_recognises_a_department_and_a_country_together(self):
        parsed = parse("what do we pay engineering in India?")
        assert parsed.filters.departments == (Department.ENGINEERING,)
        assert parsed.filters.countries == ("IN",)


class TestCompensationBounds:
    @pytest.mark.parametrize(
        ("question", "expected_usd"),
        [
            ("who earns over $150,000", 150_000_00),
            ("who earns over 150k", 150_000_00),
            ("employees above $150k", 150_000_00),
            ("more than 150 thousand", 150_000_00),
            ("at least $1.5m", 1_500_000_00),
        ],
    )
    def test_parses_a_lower_bound(self, question, expected_usd):
        assert parse(question).filters.min_total_comp_usd_minor == expected_usd

    @pytest.mark.parametrize(
        "question", ["who earns under $50,000", "employees below 50k", "less than $50k"]
    )
    def test_parses_an_upper_bound(self, question):
        assert parse(question).filters.max_total_comp_usd_minor == 50_000_00

    def test_parses_a_range(self):
        parsed = parse("employees earning between $100k and $150k")
        assert parsed.filters.min_total_comp_usd_minor == 100_000_00
        assert parsed.filters.max_total_comp_usd_minor == 150_000_00

    def test_orders_an_inverted_range(self):
        parsed = parse("between $150k and $100k")
        assert parsed.filters.min_total_comp_usd_minor == 100_000_00
        assert parsed.filters.max_total_comp_usd_minor == 150_000_00

    def test_drops_the_upper_bound_of_a_contradictory_pair(self):
        """ "over 200k and under 100k" selects nobody. Rather than raising, the
        answerable half is applied and the interpretation says which."""
        parsed = parse("who earns over $200k and under $100k")
        assert parsed.filters.min_total_comp_usd_minor == 200_000_00
        assert parsed.filters.max_total_comp_usd_minor is None
        assert "over $200,000" in parsed.interpretation


class TestStatus:
    def test_defaults_to_current_employees(self):
        """An unqualified question is about the people on the payroll now."""
        assert parse("what do we pay engineers").filters.statuses == (EmploymentStatus.ACTIVE,)

    def test_recognises_a_question_about_leavers(self):
        assert parse("what did we pay former employees").filters.statuses == (
            EmploymentStatus.INACTIVE,
        )

    def test_recognises_a_request_for_everyone(self):
        assert parse("all employees ever, by country").filters.statuses == ()


class TestEmploymentType:
    def test_recognises_contractors(self):
        assert parse("what do we pay contractors").filters.employment_types == (
            EmploymentType.CONTRACT,
        )

    def test_recognises_part_time(self):
        assert parse("part-time employees in Germany").filters.employment_types == (
            EmploymentType.PART_TIME,
        )


class TestDimension:
    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("what do we pay by country", BreakdownDimension.COUNTRY),
            ("salary breakdown per department", BreakdownDimension.DEPARTMENT),
            ("compensation by seniority", BreakdownDimension.LEVEL),
        ],
    )
    def test_recognises_a_grouping(self, question, expected):
        assert parse(question).dimension is expected

    def test_no_grouping_when_none_is_asked_for(self):
        assert parse("what do we pay in Germany").dimension is None

    def test_grouping_does_not_leak_into_the_country_filter(self):
        """ "by country" must not be read as a country name."""
        parsed = parse("what do we pay by country")
        assert parsed.filters.countries == ()
        assert parsed.dimension is BreakdownDimension.COUNTRY


class TestInterpretationEcho:
    """The safeguard: the user sees what was understood before acting on it."""

    def test_describes_every_applied_filter(self):
        parsed = parse("what do we pay engineering in Germany over $100k by level")

        assert "Current employees" in parsed.interpretation
        assert "Engineering" in parsed.interpretation
        assert "DE" in parsed.interpretation
        assert "over $100,000" in parsed.interpretation
        assert "grouped by level" in parsed.interpretation

    def test_describes_an_unqualified_question(self):
        assert parse("what do we pay").interpretation == "Current employees"


class TestUnrecognisedTerms:
    def test_reports_words_it_could_not_use(self):
        """Reported rather than ignored: a half-understood question must not
        return a confidently wrong answer."""
        parsed = parse("what do we pay engineering in Germany on Tuesdays")
        assert "tuesdays" in parsed.unrecognised_terms

    def test_ignores_filler_words(self):
        parsed = parse("please show me what we pay engineering")
        assert parsed.unrecognised_terms == ()

    def test_falls_back_to_search_when_nothing_structured_matched(self):
        parsed = parse("Ada Lovelace")
        assert parsed.filters.search == "ada lovelace"
        assert parsed.matched_anything

    def test_does_not_mix_a_name_search_into_a_structured_query(self):
        """Intersecting a stray word with a real filter returns nothing, which
        reads as "no such people" rather than "I misunderstood you"."""
        parsed = parse("engineering in Germany on Tuesdays")
        assert parsed.filters.search is None
        assert parsed.filters.departments == (Department.ENGINEERING,)


class TestGuardrails:
    def test_produces_a_filter_object_never_sql(self):
        """The load-bearing property: a question can only ever become a
        parameterised predicate over known columns."""
        parsed = parse("'; DROP TABLE employees; --")

        assert parsed.filters.countries == ()
        assert parsed.filters.departments == ()
        # Anything it cannot interpret becomes an ordinary bound search term.
        assert parsed.filters.search is not None

    def test_rejects_an_empty_question(self):
        with pytest.raises(ValueError, match="empty"):
            parse("   ")

    def test_flags_a_question_it_understood_nothing_of(self):
        parsed = parse("what is the meaning of life")
        assert parsed.unrecognised_terms == () or parsed.filters.search is not None


class TestRealisticQuestions:
    """The questions the requirements document says the persona actually asks."""

    def test_what_do_we_spend_on_payroll_in_germany(self):
        parsed = parse("what do we spend on payroll in Germany?")
        assert parsed.filters.countries == ("DE",)
        assert parsed.filters.statuses == (EmploymentStatus.ACTIVE,)

    def test_highest_paid_engineers_in_india(self):
        parsed = parse("highest paid engineering in India")
        assert parsed.filters.departments == (Department.ENGINEERING,)
        assert parsed.filters.countries == ("IN",)

    def test_how_does_pay_vary_by_level(self):
        parsed = parse("how does compensation vary by level")
        assert parsed.dimension is BreakdownDimension.LEVEL

    def test_who_earns_more_than_two_hundred_thousand(self):
        parsed = parse("who earns more than $200k")
        assert parsed.filters.min_total_comp_usd_minor == 200_000_00
