import pytest

from app.domain.statistics import arithmetic_mean, median, median_of_middle_values


class TestArithmeticMean:
    def test_averages_a_populated_set(self):
        assert arithmetic_mean(300_00, 3) == 100_00

    def test_rounds_half_up_to_the_nearest_minor_unit(self):
        assert arithmetic_mean(5, 2) == 3

    def test_returns_none_for_an_empty_set(self):
        """A filter matching nobody has no average, which is not the same as zero."""
        assert arithmetic_mean(0, 0) is None


class TestMedian:
    def test_odd_sized_set_takes_the_middle_value(self):
        assert median([300_00, 100_00, 200_00]) == 200_00

    def test_even_sized_set_averages_the_two_middle_values(self):
        assert median([100_00, 200_00, 300_00, 400_00]) == 250_00

    def test_returns_none_for_an_empty_set(self):
        assert median([]) is None

    def test_resists_the_outlier_that_skews_the_mean(self):
        """Why the dashboard shows median alongside average.

        One executive's compensation drags the average above what almost anyone
        in the sample actually earns; the median stays representative.
        """
        salaries = [80_000_00] * 9 + [5_000_000_00]

        assert median(salaries) == 80_000_00
        assert arithmetic_mean(sum(salaries), len(salaries)) == 572_000_00


class TestMedianOfMiddleValues:
    """The reduction applied to what the windowed SQL query returns."""

    def test_single_midpoint_value_is_the_median(self):
        assert median_of_middle_values(200_00, 1) == 200_00

    def test_two_midpoint_values_are_averaged(self):
        assert median_of_middle_values(200_00 + 300_00, 2) == 250_00

    def test_no_midpoint_values_means_no_median(self):
        assert median_of_middle_values(0, 0) is None

    def test_rejects_an_impossible_midpoint_count(self):
        with pytest.raises(ValueError, match="0, 1 or 2"):
            median_of_middle_values(100_00, 3)

    @pytest.mark.parametrize("size", range(1, 12))
    def test_agrees_with_the_reference_median_at_every_size(self, size):
        """Ties the SQL-shaped reduction to the plain implementation.

        The SQL query selects rows whose 1-based rank is ``(n+1)//2`` or
        ``(n+2)//2`` — one row when ``n`` is odd, two when even. Reproducing that
        selection here proves the reduction handles both parities.
        """
        values = [(n + 1) * 1_000_00 for n in range(size)]
        ranks = {(size + 1) // 2, (size + 2) // 2}
        middle = [value for rank, value in enumerate(values, start=1) if rank in ranks]

        assert median_of_middle_values(sum(middle), len(middle)) == median(values)
