from itertools import pairwise

import pytest

from app.domain.salary_bands import SALARY_BANDS, band_for


class TestBandTableIntegrity:
    def test_bands_are_contiguous_with_no_gaps_or_overlaps(self):
        """Every employee must land in exactly one bar of the histogram."""
        for lower_band, upper_band in pairwise(SALARY_BANDS):
            assert lower_band.upper_usd_minor == upper_band.lower_usd_minor

    def test_the_table_covers_every_possible_amount(self):
        assert SALARY_BANDS[0].lower_usd_minor == 0
        assert SALARY_BANDS[-1].upper_usd_minor is None


class TestBandAssignment:
    @pytest.mark.parametrize(
        ("amount_usd", "expected_label"),
        [
            (0, "< $25k"),
            (24_999, "< $25k"),
            (25_000, "$25k – $50k"),
            (99_999, "$75k – $100k"),
            (150_000, "$150k – $200k"),
            (1_000_000, "$300k+"),
        ],
    )
    def test_assigns_the_expected_band(self, amount_usd, expected_label):
        assert band_for(amount_usd * 100).label == expected_label

    def test_boundaries_are_half_open_so_they_belong_to_the_upper_band(self):
        """$50,000.00 belongs to "$50k – $75k", not to the band below it."""
        assert band_for(50_000_00).label == "$50k – $75k"
        assert band_for(50_000_00 - 1).label == "$25k – $50k"
