import dataclasses
from datetime import date

import pytest
from sqlalchemy import select

from app.domain.compensation import Compensation
from app.domain.employee import EmployeeDraft
from app.domain.enums import (
    Department,
    EmployeeSortField,
    EmploymentStatus,
    EmploymentType,
    Level,
    SortDirection,
)
from app.domain.filters import EmployeeFilters
from app.domain.money import descale_fx
from app.errors import (
    DuplicateEmployeeFieldError,
    EmployeeNotFoundError,
    InvalidManagerError,
    UnknownReferenceError,
)
from app.models import Currency, Employee
from app.repositories.employees import (
    create_employee,
    get_employee,
    list_employees,
    replace_employee,
    set_employee_status,
)
from tests.conftest import SEEDED_EMPLOYEE_COUNT

UNFILTERED = EmployeeFilters.unfiltered()


def draft(**overrides) -> EmployeeDraft:
    base = EmployeeDraft(
        employee_code="ACME-90001",
        first_name="Ada",
        last_name="Lovelace",
        email="ada.lovelace@acme.example",
        country_code="GB",
        department=Department.ENGINEERING,
        job_title="Principal Engineer",
        level=Level.L5,
        employment_type=EmploymentType.FULL_TIME,
        status=EmploymentStatus.ACTIVE,
        hire_date=date(2024, 3, 1),
        manager_id=None,
        compensation=Compensation(
            base_salary_minor=150_000_00, bonus_minor=20_000_00, currency_code="GBP"
        ),
    )
    return dataclasses.replace(base, **overrides)


class TestPagination:
    def test_the_total_is_the_full_match_count_not_the_page_size(self, seeded_session):
        page = list_employees(
            seeded_session, UNFILTERED, EmployeeSortField.NAME, SortDirection.ASC, 1, 10
        )
        assert len(page.items) == 10
        assert page.total == SEEDED_EMPLOYEE_COUNT
        assert page.total_pages == SEEDED_EMPLOYEE_COUNT // 10

    def test_paging_a_heavily_tied_sort_visits_everyone_exactly_once(self, seeded_session):
        """The bug a stable tiebreaker prevents.

        Sorting by department leaves large blocks of tied rows. Without a unique
        final sort term the database may order ties differently per query, so
        paging would repeat some employees and skip others — and nobody notices
        until an employee is missing from a report.
        """
        page_size = 40
        seen: list[int] = []
        page_number = 1
        while True:
            page = list_employees(
                seeded_session,
                UNFILTERED,
                EmployeeSortField.DEPARTMENT,
                SortDirection.ASC,
                page_number,
                page_size,
            )
            if not page.items:
                break
            seen.extend(employee.id for employee in page.items)
            page_number += 1

        assert len(seen) == SEEDED_EMPLOYEE_COUNT
        assert len(set(seen)) == SEEDED_EMPLOYEE_COUNT

    def test_rejects_a_page_below_one(self, seeded_session):
        with pytest.raises(ValueError, match="page must be 1 or greater"):
            list_employees(
                seeded_session, UNFILTERED, EmployeeSortField.NAME, SortDirection.ASC, 0, 10
            )

    def test_a_page_beyond_the_end_is_empty_rather_than_an_error(self, seeded_session):
        page = list_employees(
            seeded_session, UNFILTERED, EmployeeSortField.NAME, SortDirection.ASC, 9_999, 10
        )
        assert page.items == ()
        assert page.total == SEEDED_EMPLOYEE_COUNT


class TestSorting:
    @pytest.mark.parametrize("direction", list(SortDirection))
    def test_sorts_by_compensation_in_both_directions(self, seeded_session, direction):
        page = list_employees(
            seeded_session, UNFILTERED, EmployeeSortField.TOTAL_COMP_USD, direction, 1, 50
        )
        totals = [employee.total_comp_usd_fx_scaled for employee in page.items]
        assert totals == sorted(totals, reverse=direction is SortDirection.DESC)

    def test_sorts_by_name_using_last_name_first(self, seeded_session):
        page = list_employees(
            seeded_session, UNFILTERED, EmployeeSortField.NAME, SortDirection.ASC, 1, 50
        )
        names = [(e.last_name, e.first_name) for e in page.items]
        assert names == sorted(names)

    def test_the_highest_paid_employee_is_the_summary_maximum(self, seeded_session):
        from app.repositories.analytics import compensation_summary

        page = list_employees(
            seeded_session, UNFILTERED, EmployeeSortField.TOTAL_COMP_USD, SortDirection.DESC, 1, 1
        )
        summary = compensation_summary(seeded_session, UNFILTERED)
        assert descale_fx(page.items[0].total_comp_usd_fx_scaled) == summary.max_usd_minor


class TestSearch:
    def test_finds_an_employee_by_code(self, seeded_session):
        target = seeded_session.scalar(select(Employee))
        filters = dataclasses.replace(UNFILTERED, search=target.employee_code)
        page = list_employees(
            seeded_session, filters, EmployeeSortField.NAME, SortDirection.ASC, 1, 10
        )

        assert page.total == 1
        assert page.items[0].id == target.id

    def test_finds_an_employee_by_partial_name(self, seeded_session):
        target = seeded_session.scalar(select(Employee))
        filters = dataclasses.replace(UNFILTERED, search=target.last_name)
        page = list_employees(
            seeded_session, filters, EmployeeSortField.NAME, SortDirection.ASC, 1, 100
        )

        assert page.total >= 1
        assert all(
            target.last_name.lower()
            in f"{e.first_name} {e.last_name} {e.email} {e.job_title}".lower()
            for e in page.items
        )

    def test_extra_tokens_narrow_rather_than_widen(self, seeded_session):
        """Typing more must never return more; tokens are conjunctive."""
        target = seeded_session.scalar(select(Employee))
        one_token = dataclasses.replace(UNFILTERED, search=target.last_name)
        two_tokens = dataclasses.replace(
            UNFILTERED, search=f"{target.last_name} {target.employee_code}"
        )

        broad = list_employees(
            seeded_session, one_token, EmployeeSortField.NAME, SortDirection.ASC, 1, 1
        )
        narrow = list_employees(
            seeded_session, two_tokens, EmployeeSortField.NAME, SortDirection.ASC, 1, 1
        )
        assert narrow.total <= broad.total

    def test_a_whitespace_only_search_is_treated_as_no_search(self, seeded_session):
        filters = dataclasses.replace(UNFILTERED, search="   ")
        page = list_employees(
            seeded_session, filters, EmployeeSortField.NAME, SortDirection.ASC, 1, 1
        )
        assert page.total == SEEDED_EMPLOYEE_COUNT


class TestGet:
    def test_raises_a_named_error_for_a_missing_employee(self, seeded_session):
        with pytest.raises(EmployeeNotFoundError, match="no employee with id 999999"):
            get_employee(seeded_session, 999_999)

    def test_loads_the_manager_without_a_lazy_load(self, seeded_session):
        managed = seeded_session.scalar(select(Employee).where(Employee.manager_id.is_not(None)))
        employee = get_employee(seeded_session, managed.id)
        assert employee.manager is not None


class TestCreate:
    def test_creates_an_employee_and_derives_the_usd_total(self, seeded_session):
        created = create_employee(seeded_session, draft())

        gbp_rate = seeded_session.scalar(
            select(Currency.usd_rate_scaled).where(Currency.code == "GBP")
        )
        assert created.total_comp_usd_fx_scaled == 170_000_00 * gbp_rate
        assert descale_fx(created.total_comp_usd_fx_scaled) == 215_900_00

    def test_rejects_a_duplicate_email_and_names_the_holder(self, seeded_session):
        existing = seeded_session.scalar(select(Employee))
        with pytest.raises(DuplicateEmployeeFieldError) as caught:
            create_employee(seeded_session, draft(email=existing.email))

        assert caught.value.existing_employee_code == existing.employee_code

    def test_rejects_a_duplicate_employee_code(self, seeded_session):
        existing = seeded_session.scalar(select(Employee))
        with pytest.raises(DuplicateEmployeeFieldError, match="employee code"):
            create_employee(seeded_session, draft(employee_code=existing.employee_code))

    def test_rejects_an_unknown_currency(self, seeded_session):
        with pytest.raises(UnknownReferenceError, match="unknown currency"):
            create_employee(
                seeded_session,
                draft(
                    compensation=Compensation(
                        base_salary_minor=1000, bonus_minor=0, currency_code="XXX"
                    )
                ),
            )

    def test_rejects_an_unknown_country(self, seeded_session):
        with pytest.raises(UnknownReferenceError, match="unknown country"):
            create_employee(seeded_session, draft(country_code="ZZ"))

    def test_rejects_a_negative_salary_before_it_reaches_the_database(self):
        with pytest.raises(ValueError, match="non-negative"):
            Compensation(base_salary_minor=-1, bonus_minor=0, currency_code="USD")


class TestReplace:
    def test_recomputes_the_usd_total_when_the_salary_changes(self, seeded_session):
        created = create_employee(seeded_session, draft())
        before = created.total_comp_usd_fx_scaled

        updated = replace_employee(
            seeded_session,
            created.id,
            draft(
                compensation=Compensation(
                    base_salary_minor=200_000_00, bonus_minor=0, currency_code="GBP"
                )
            ),
        )
        assert updated.total_comp_usd_fx_scaled != before
        assert descale_fx(updated.total_comp_usd_fx_scaled) == 254_000_00

    def test_recomputes_the_usd_total_when_only_the_currency_changes(self, seeded_session):
        """The subtle staleness case: identical numbers, different money."""
        created = create_employee(seeded_session, draft())
        updated = replace_employee(
            seeded_session,
            created.id,
            draft(
                country_code="US",
                compensation=Compensation(
                    base_salary_minor=150_000_00, bonus_minor=20_000_00, currency_code="USD"
                ),
            ),
        )
        assert descale_fx(updated.total_comp_usd_fx_scaled) == 170_000_00

    def test_keeping_your_own_email_is_not_a_duplicate(self, seeded_session):
        created = create_employee(seeded_session, draft())
        updated = replace_employee(seeded_session, created.id, draft(job_title="Staff Engineer"))
        assert updated.job_title == "Staff Engineer"

    def test_raises_for_an_unknown_employee(self, seeded_session):
        with pytest.raises(EmployeeNotFoundError):
            replace_employee(seeded_session, 999_999, draft())


class TestManagerValidation:
    def test_rejects_an_employee_managing_themselves(self, seeded_session):
        created = create_employee(seeded_session, draft())
        with pytest.raises(InvalidManagerError, match="cannot manage themselves"):
            replace_employee(seeded_session, created.id, draft(manager_id=created.id))

    def test_rejects_an_unknown_manager(self, seeded_session):
        with pytest.raises(InvalidManagerError, match="no such employee"):
            create_employee(seeded_session, draft(manager_id=999_999))

    def test_rejects_a_reporting_cycle(self, seeded_session):
        """Two records are enough: A reports to B, then point B at A."""
        alice = create_employee(seeded_session, draft())
        bob = create_employee(
            seeded_session,
            draft(
                employee_code="ACME-90002",
                email="bob@acme.example",
                first_name="Bob",
                manager_id=alice.id,
            ),
        )

        with pytest.raises(InvalidManagerError, match="reporting cycle"):
            replace_employee(seeded_session, alice.id, draft(manager_id=bob.id))


class TestStatusChanges:
    def test_deactivates_an_employee(self, seeded_session):
        created = create_employee(seeded_session, draft())
        deactivated = set_employee_status(seeded_session, created.id, EmploymentStatus.INACTIVE)
        assert deactivated.status == EmploymentStatus.INACTIVE

    def test_a_deactivated_employee_leaves_the_active_selection(self, seeded_session):
        from app.repositories.analytics import compensation_summary

        active_only = dataclasses.replace(UNFILTERED, statuses=(EmploymentStatus.ACTIVE,))
        before = compensation_summary(seeded_session, active_only)

        created = create_employee(seeded_session, draft())
        set_employee_status(seeded_session, created.id, EmploymentStatus.INACTIVE)
        after = compensation_summary(seeded_session, active_only)

        assert after.headcount == before.headcount

    def test_the_record_survives_deactivation(self, seeded_session):
        """Compensation data is financial history; there is no delete."""
        created = create_employee(seeded_session, draft())
        set_employee_status(seeded_session, created.id, EmploymentStatus.INACTIVE)

        assert get_employee(seeded_session, created.id).base_salary_minor == 150_000_00
