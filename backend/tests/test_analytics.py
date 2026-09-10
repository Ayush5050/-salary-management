"""Aggregate correctness.

The strategy throughout is differential: every SQL-computed figure is compared
against the same figure derived in Python from the raw rows. The SQL path uses
window functions and grouping; the reference path sorts a list. Agreement
between two genuinely different implementations is what makes the queries
trustworthy — asserting a hard-coded number would only pin today's seed.
"""

import dataclasses

import pytest
from sqlalchemy import select

from app.domain.enums import (
    BreakdownDimension,
    Department,
    EmployeeSortField,
    EmploymentStatus,
    SortDirection,
)
from app.domain.filters import EmployeeFilters
from app.domain.money import descale_fx
from app.domain.salary_bands import band_for
from app.domain.statistics import arithmetic_mean, median
from app.models import Employee
from app.repositories.analytics import (
    compensation_breakdown,
    compensation_summary,
    salary_distribution,
)
from app.repositories.employees import list_employees
from app.repositories.filtering import filter_conditions

ACTIVE_ONLY = dataclasses.replace(EmployeeFilters.unfiltered(), statuses=(EmploymentStatus.ACTIVE,))
ENGINEERING = dataclasses.replace(
    EmployeeFilters.unfiltered(), departments=(Department.ENGINEERING,)
)


def scaled_values(session, filters: EmployeeFilters) -> list[int]:
    """Raw FX-scaled totals for a selection, as the reference for every check."""
    return list(
        session.scalars(
            select(Employee.total_comp_usd_fx_scaled).where(*filter_conditions(filters))
        ).all()
    )


class TestSummary:
    @pytest.mark.parametrize(
        "filters",
        [EmployeeFilters.unfiltered(), ACTIVE_ONLY, ENGINEERING],
        ids=["everyone", "active-only", "engineering"],
    )
    def test_every_statistic_matches_an_independent_computation(self, seeded_session, filters):
        values = scaled_values(seeded_session, filters)
        stats = compensation_summary(seeded_session, filters)

        assert stats.headcount == len(values)
        assert stats.total_usd_minor == descale_fx(sum(values))
        assert stats.median_usd_minor == descale_fx(median(values))
        assert stats.min_usd_minor == descale_fx(min(values))
        assert stats.max_usd_minor == descale_fx(max(values))
        assert stats.average_usd_minor == arithmetic_mean(descale_fx(sum(values)), len(values))

    def test_a_filter_matching_nobody_reports_no_statistics(self, seeded_session):
        """Not zeros. Zero average pay and "nobody matched" are different facts."""
        impossible = dataclasses.replace(
            EmployeeFilters.unfiltered(), search="qwertyuiop-no-such-person"
        )
        stats = compensation_summary(seeded_session, impossible)

        assert stats.headcount == 0
        assert stats.total_usd_minor == 0
        assert stats.average_usd_minor is None
        assert stats.median_usd_minor is None

    def test_median_and_average_differ_on_real_data(self, seeded_session):
        """Confirms the two are computed differently, so the dashboard showing
        both is telling the HR Manager something."""
        stats = compensation_summary(seeded_session, ACTIVE_ONLY)
        assert stats.median_usd_minor != stats.average_usd_minor


class TestMedianAcrossGroupParities:
    """The window-function median is the least obvious query in the system."""

    def test_group_medians_match_the_reference_for_every_dimension(self, seeded_session):
        for dimension in BreakdownDimension:
            rows = compensation_breakdown(seeded_session, ACTIVE_ONLY, dimension)
            assert rows, f"{dimension} produced no groups"

            for row in rows:
                group_filter = _filter_for(dimension, row.key, ACTIVE_ONLY)
                expected = median(scaled_values(seeded_session, group_filter))
                assert row.stats.median_usd_minor == descale_fx(expected), f"{dimension}={row.key}"

    def test_both_odd_and_even_sized_groups_are_exercised(self, seeded_session):
        """Guards the test above from silently only covering one parity, which
        is precisely where the midpoint-rank condition could be wrong."""
        sizes = [
            row.stats.headcount
            for row in compensation_breakdown(seeded_session, ACTIVE_ONLY, BreakdownDimension.LEVEL)
        ]
        assert any(size % 2 == 0 for size in sizes)
        assert any(size % 2 == 1 for size in sizes)

    def test_a_single_employee_group_has_that_employee_as_its_median(self, seeded_session):
        one_person = dataclasses.replace(
            EmployeeFilters.unfiltered(), search=_any_employee_code(seeded_session)
        )
        stats = compensation_summary(seeded_session, one_person)

        assert stats.headcount == 1
        assert stats.median_usd_minor == stats.average_usd_minor == stats.min_usd_minor


def _filter_for(dimension: BreakdownDimension, key: str, base: EmployeeFilters) -> EmployeeFilters:
    if dimension is BreakdownDimension.COUNTRY:
        return dataclasses.replace(base, countries=(key,))
    if dimension is BreakdownDimension.DEPARTMENT:
        return dataclasses.replace(base, departments=(Department(key),))
    return dataclasses.replace(base, levels=(key,))


def _any_employee_code(session) -> str:
    return session.scalar(select(Employee.employee_code).limit(1))


class TestBreakdown:
    @pytest.mark.parametrize("dimension", list(BreakdownDimension))
    def test_groups_partition_the_population_exactly(self, seeded_session, dimension):
        """No employee counted twice, none dropped — the failure mode that makes
        a breakdown quietly disagree with the KPI above it."""
        summary = compensation_summary(seeded_session, ACTIVE_ONLY)
        rows = compensation_breakdown(seeded_session, ACTIVE_ONLY, dimension)

        assert sum(row.stats.headcount for row in rows) == summary.headcount

    @pytest.mark.parametrize("dimension", list(BreakdownDimension))
    def test_group_totals_reconcile_with_the_headline_total(self, seeded_session, dimension):
        """Allows a per-group rounding unit, since each group descales its own
        sum; the drift is bounded by the number of groups, not by headcount."""
        summary = compensation_summary(seeded_session, ACTIVE_ONLY)
        rows = compensation_breakdown(seeded_session, ACTIVE_ONLY, dimension)

        assert abs(sum(row.stats.total_usd_minor for row in rows) - summary.total_usd_minor) <= len(
            rows
        )

    def test_groups_are_ordered_by_spend_so_the_largest_cost_leads(self, seeded_session):
        rows = compensation_breakdown(seeded_session, ACTIVE_ONLY, BreakdownDimension.COUNTRY)
        totals = [row.stats.total_usd_minor for row in rows]
        assert totals == sorted(totals, reverse=True)

    def test_filters_narrow_the_breakdown(self, seeded_session):
        everyone = compensation_breakdown(
            seeded_session, EmployeeFilters.unfiltered(), BreakdownDimension.DEPARTMENT
        )
        engineering = compensation_breakdown(
            seeded_session, ENGINEERING, BreakdownDimension.DEPARTMENT
        )

        assert len(engineering) == 1
        assert engineering[0].key == Department.ENGINEERING
        assert len(everyone) > 1


class TestDistribution:
    def test_band_counts_sum_to_the_headcount(self, seeded_session):
        summary = compensation_summary(seeded_session, ACTIVE_ONLY)
        bands = salary_distribution(seeded_session, ACTIVE_ONLY)

        assert sum(band.headcount for band in bands) == summary.headcount

    def test_every_band_is_returned_even_when_empty(self, seeded_session):
        """A stable axis: filtering to one country must not silently drop bars."""
        one_country = dataclasses.replace(ACTIVE_ONLY, countries=("JP",))
        bands = salary_distribution(seeded_session, one_country)

        assert len(bands) == len(salary_distribution(seeded_session, ACTIVE_ONLY))
        assert any(band.headcount == 0 for band in bands)

    def test_sql_bucketing_agrees_with_the_domain_band_assignment(self, seeded_session):
        """The CASE expression and band_for() must classify identically."""
        values = scaled_values(seeded_session, ACTIVE_ONLY)
        expected: dict[str, int] = {}
        for scaled in values:
            label = band_for(descale_fx(scaled)).label
            expected[label] = expected.get(label, 0) + 1

        for band in salary_distribution(seeded_session, ACTIVE_ONLY):
            assert band.headcount == expected.get(band.label, 0), band.label


class TestDashboardAndListAgree:
    """The product promise: a number on the dashboard is the list beneath it."""

    @pytest.mark.parametrize(
        "filters",
        [ACTIVE_ONLY, ENGINEERING, dataclasses.replace(ACTIVE_ONLY, countries=("IN", "DE"))],
        ids=["active-only", "engineering", "two-countries"],
    )
    def test_summary_headcount_equals_the_list_total(self, seeded_session, filters):
        summary = compensation_summary(seeded_session, filters)
        page = list_employees(
            seeded_session,
            filters,
            EmployeeSortField.NAME,
            SortDirection.ASC,
            page=1,
            page_size=1,
        )
        assert page.total == summary.headcount

    def test_a_compensation_range_filter_selects_the_same_people_in_both(self, seeded_session):
        band = dataclasses.replace(
            ACTIVE_ONLY,
            min_total_comp_usd_minor=100_000_00,
            max_total_comp_usd_minor=150_000_00,
        )
        summary = compensation_summary(seeded_session, band)
        page = list_employees(
            seeded_session, band, EmployeeSortField.TOTAL_COMP_USD, SortDirection.ASC, 1, 200
        )

        assert page.total == summary.headcount
        assert summary.headcount > 0
        for employee in page.items:
            usd = descale_fx(employee.total_comp_usd_fx_scaled)
            assert 100_000_00 <= usd <= 150_000_00
