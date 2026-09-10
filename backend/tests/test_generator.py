from collections import Counter

import pytest

from app.domain.enums import Department, EmploymentType, Level
from app.domain.statistics import median
from app.seed.generator import assign_managers, generate_employees

SAMPLE_SIZE = 800
SAMPLE_SEED = 1


@pytest.fixture(scope="module")
def sample():
    return generate_employees(SAMPLE_SIZE, SAMPLE_SEED)


class TestDeterminism:
    def test_the_same_seed_produces_the_same_population(self):
        """The property the demo, the deployed data and the tests all rely on."""
        assert generate_employees(50, seed=99) == generate_employees(50, seed=99)

    def test_a_different_seed_produces_a_different_population(self):
        assert generate_employees(50, seed=99) != generate_employees(50, seed=100)

    def test_generating_zero_employees_is_allowed(self):
        assert generate_employees(0, seed=1) == []

    def test_rejects_a_negative_count(self):
        with pytest.raises(ValueError, match="non-negative"):
            generate_employees(-1, seed=1)


class TestIdentity:
    def test_employee_codes_are_unique_and_sequential(self, sample):
        codes = [employee.employee_code for employee in sample]
        assert codes == [f"ACME-{n:05d}" for n in range(1, SAMPLE_SIZE + 1)]

    def test_emails_are_unique(self, sample):
        """The database enforces this too; generating a duplicate would abort the
        entire seed, so uniqueness is resolved during generation instead."""
        emails = [employee.email for employee in sample]
        assert len(set(emails)) == len(emails)

    def test_collision_suffixes_only_appear_on_repeated_names(self):
        employees = generate_employees(SAMPLE_SIZE, SAMPLE_SEED)
        seen_names: set[tuple[str, str]] = set()
        for employee in employees:
            name = (employee.first_name, employee.last_name)
            expected_stem = f"{employee.first_name}.{employee.last_name}".lower()
            if name not in seen_names:
                assert employee.email.startswith(f"{expected_stem}@")
            seen_names.add(name)


class TestCompensationShape:
    def test_pay_rises_monotonically_with_level_within_one_country(self, sample):
        """Compared inside a single country so the result is about seniority
        rather than about currency or location factors."""
        by_level: dict[Level, list[int]] = {}
        for employee in sample:
            if (
                employee.country_code == "US"
                and employee.employment_type is EmploymentType.FULL_TIME
            ):
                by_level.setdefault(employee.level, []).append(employee.compensation.total_minor)

        medians = [
            median(by_level[level]) for level in sorted(by_level) if len(by_level[level]) >= 3
        ]
        assert medians == sorted(medians)

    def test_contractors_receive_no_bonus(self, sample):
        contractors = [e for e in sample if e.employment_type is EmploymentType.CONTRACT]
        assert contractors, "sample should contain contractors"
        assert all(e.compensation.bonus_minor == 0 for e in contractors)

    def test_sales_carries_a_higher_bonus_ratio_than_engineering(self, sample):
        """Total compensation, not base, is the comparable figure — this is the
        structural reason why."""

        def bonus_ratios(department: Department) -> list[float]:
            return [
                e.compensation.bonus_minor / e.compensation.base_salary_minor
                for e in sample
                if e.department is department and e.employment_type is not EmploymentType.CONTRACT
            ]

        sales = bonus_ratios(Department.SALES)
        engineering = bonus_ratios(Department.ENGINEERING)
        assert sum(sales) / len(sales) > sum(engineering) / len(engineering)

    def test_every_employee_has_a_positive_base_salary(self, sample):
        assert all(e.compensation.base_salary_minor > 0 for e in sample)

    def test_salaries_are_rounded_to_plausible_increments(self, sample):
        """Nobody is paid $124,378.41. Round figures make the demo data credible."""
        assert all(e.compensation.base_salary_minor % 100 == 0 for e in sample)


class TestPopulationDistribution:
    def test_the_seniority_pyramid_is_wider_at_the_bottom(self, sample):
        counts = Counter(employee.level for employee in sample)
        assert counts[Level.L2] > counts[Level.L5] > counts[Level.L8]

    def test_the_population_spans_every_country_and_department(self, sample):
        assert len({e.country_code for e in sample}) == 10
        assert len({e.department for e in sample}) == len(Department)

    def test_some_employees_are_inactive(self, sample):
        """Otherwise the "active only" default filter would be untestable."""
        inactive = [e for e in sample if e.status == "INACTIVE"]
        assert 0 < len(inactive) < len(sample) // 2


class TestReportingLines:
    def test_managers_are_senior_to_their_reports(self, sample):
        manager_of = assign_managers(sample, SAMPLE_SEED)
        by_code = {employee.employee_code: employee for employee in sample}
        levels = list(Level)

        for code, manager_code in manager_of.items():
            report, manager = by_code[code], by_code[manager_code]
            assert levels.index(manager.level) > levels.index(report.level)

    def test_managers_share_their_reports_department(self, sample):
        manager_of = assign_managers(sample, SAMPLE_SEED)
        by_code = {employee.employee_code: employee for employee in sample}

        for code, manager_code in manager_of.items():
            assert by_code[code].department is by_code[manager_code].department

    def test_the_most_senior_people_have_no_manager(self, sample):
        manager_of = assign_managers(sample, SAMPLE_SEED)
        top_level = [e for e in sample if e.level is Level.L8]
        assert top_level, "sample should contain executives"
        assert all(e.employee_code not in manager_of for e in top_level)

    def test_assignment_is_deterministic(self, sample):
        assert assign_managers(sample, SAMPLE_SEED) == assign_managers(sample, SAMPLE_SEED)
