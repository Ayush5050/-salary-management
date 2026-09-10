import dataclasses

import pytest

from app.domain.enums import Department
from app.domain.filters import EmployeeFilters


class TestUnfiltered:
    def test_selects_the_whole_population(self):
        assert EmployeeFilters.unfiltered().is_empty

    def test_any_constraint_makes_it_non_empty(self):
        narrowed = dataclasses.replace(
            EmployeeFilters.unfiltered(), departments=(Department.ENGINEERING,)
        )
        assert not narrowed.is_empty


class TestCompensationRangeValidation:
    def test_rejects_an_inverted_range(self):
        """Caught at construction so it cannot reach SQL and silently return nothing."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            dataclasses.replace(
                EmployeeFilters.unfiltered(),
                min_total_comp_usd_minor=200_000_00,
                max_total_comp_usd_minor=100_000_00,
            )

    def test_rejects_a_negative_bound(self):
        with pytest.raises(ValueError, match="non-negative"):
            dataclasses.replace(EmployeeFilters.unfiltered(), min_total_comp_usd_minor=-1)

    def test_accepts_an_open_ended_range(self):
        narrowed = dataclasses.replace(
            EmployeeFilters.unfiltered(), min_total_comp_usd_minor=200_000_00
        )
        assert narrowed.max_total_comp_usd_minor is None


class TestImmutability:
    def test_filters_cannot_be_mutated_in_place(self):
        """Filters are passed to several repositories; shared mutable state would
        let one query quietly change another's meaning."""
        filters = EmployeeFilters.unfiltered()
        with pytest.raises(dataclasses.FrozenInstanceError):
            filters.search = "ada"  # type: ignore[misc]
