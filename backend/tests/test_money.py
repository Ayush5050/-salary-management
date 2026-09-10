from decimal import Decimal

import pytest

from app.domain.money import (
    FX_SCALE,
    convert_to_usd_minor_units,
    descale_fx,
    fx_rate_to_scaled,
    to_major_units,
    to_minor_units,
)


class TestMinorUnitConversion:
    def test_round_trips_a_typical_salary(self):
        assert to_major_units(to_minor_units(Decimal("125000.50"))) == Decimal("125000.50")

    def test_rounds_half_up_at_the_sub_cent_boundary(self):
        assert to_minor_units(Decimal("0.005")) == 1
        assert to_minor_units(Decimal("0.004")) == 0

    def test_rejects_negative_amounts(self):
        with pytest.raises(ValueError, match="non-negative"):
            to_minor_units(Decimal("-1.00"))


class TestIntegerRepresentationAvoidsDrift:
    """The reason minor units exist at all.

    Summing 10,000 salaries is the single most common operation in this system,
    and it is exactly where binary floating point fails: 0.01 has no finite
    binary representation, so the error compounds once per employee.
    """

    def test_summing_ten_thousand_salaries_is_exact(self):
        salary = Decimal("83333.33")
        headcount = 10_000

        integer_total = 0
        float_total = 0.0
        for _ in range(headcount):
            integer_total += to_minor_units(salary)
            float_total += float(salary)

        assert to_major_units(integer_total) == Decimal("833333300.00")
        assert float_total == pytest.approx(833_333_300.0)
        assert float_total != 833_333_300.0, "the float sum has drifted off the exact total"


class TestFxRates:
    def test_usd_is_the_identity_rate(self):
        assert fx_rate_to_scaled(Decimal("1")) == FX_SCALE
        assert convert_to_usd_minor_units(500_00, FX_SCALE) == 500_00

    def test_converts_a_local_salary_into_usd(self):
        inr_rate = fx_rate_to_scaled(Decimal("0.012"))
        # ₹2,500,000.00 at 0.012 USD/INR is $30,000.00
        assert convert_to_usd_minor_units(2_500_000_00, inr_rate) == 30_000_00

    def test_rejects_a_non_positive_rate(self):
        with pytest.raises(ValueError, match="positive"):
            fx_rate_to_scaled(Decimal("0"))


class TestDescaling:
    def test_descaling_inverts_the_sql_side_scaling(self):
        amount_minor, rate = 1_234_56, fx_rate_to_scaled(Decimal("1.25"))
        assert descale_fx(amount_minor * rate) == convert_to_usd_minor_units(amount_minor, rate)

    def test_aggregate_then_descale_beats_descale_then_aggregate(self):
        """Why the division happens once, at the boundary, and not per row.

        Truncating each row loses up to one minor unit per employee; over 10,000
        employees that is a visible error in the payroll total. Aggregating in
        scaled space and truncating once bounds the loss to a single minor unit.
        """
        rate = fx_rate_to_scaled(Decimal("0.777777"))
        salaries = [100_00 + n for n in range(10_000)]

        descale_last = descale_fx(sum(s * rate for s in salaries))
        descale_first = sum(convert_to_usd_minor_units(s, rate) for s in salaries)

        assert descale_last - descale_first > 1_000
