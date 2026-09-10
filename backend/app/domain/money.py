"""Money arithmetic.

Two deliberate representation choices underpin this module, both aimed at making
aggregate figures over 10,000 salaries exactly reproducible:

1.  **Monetary amounts are integer minor units** (cents, pence, paise). Binary
    floats cannot represent 0.01, so summing 10,000 float salaries accumulates
    drift. Integers sum exactly, in SQL and in Python alike.

2.  **FX rates are integers scaled by** :data:`FX_SCALE`. This keeps the
    normalisation of local salaries into USD inside integer arithmetic, so the
    database can aggregate converted amounts without ever producing a float.

The database therefore aggregates in *FX-scaled minor units* — the product of a
minor-unit amount and a scaled rate. :func:`descale_fx` converts such an
aggregate back to plain USD minor units at the boundary, in one single division
rather than once per row.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

MINOR_UNITS_PER_MAJOR: Final[int] = 100
"""Minor units in one major unit.

Every currency in the seeded catalogue is a two-decimal currency. JPY is
formally zero-decimal; it is stored on the same 100:1 basis with a zero
fractional part, and formatted without decimals in the UI. Supporting genuinely
variable currency exponents would require a per-currency exponent column, which
is noted as a future increment rather than modelled here.
"""

FX_SCALE: Final[int] = 1_000_000
"""Fixed-point scale for FX rates: a rate of 0.012 USD/INR is stored as 12_000."""

_MAJOR_UNIT_QUANTUM: Final[Decimal] = Decimal("0.01")


def to_minor_units(amount: Decimal) -> int:
    """Convert a major-unit amount (``1234.56``) to minor units (``123456``)."""
    if amount < 0:
        raise ValueError(f"monetary amount must be non-negative, got {amount}")
    scaled = amount * MINOR_UNITS_PER_MAJOR
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


def to_major_units(minor_units: int) -> Decimal:
    """Convert minor units (``123456``) back to a major-unit amount (``1234.56``)."""
    if minor_units < 0:
        raise ValueError(f"monetary amount must be non-negative, got {minor_units} minor units")
    return (Decimal(minor_units) / MINOR_UNITS_PER_MAJOR).quantize(_MAJOR_UNIT_QUANTUM)


def fx_rate_to_scaled(usd_per_unit: Decimal) -> int:
    """Convert a decimal FX rate to its stored fixed-point integer form.

    ``usd_per_unit`` is how many USD one unit of the currency buys, so USD itself
    has a rate of exactly ``1``.
    """
    if usd_per_unit <= 0:
        raise ValueError(f"FX rate must be positive, got {usd_per_unit}")
    scaled = usd_per_unit * FX_SCALE
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


def descale_fx(fx_scaled_minor_units: int) -> int:
    """Convert an FX-scaled aggregate back to USD minor units.

    The database aggregates ``amount_minor_units * fx_rate_scaled`` so that every
    intermediate value stays an integer. Dividing once here, rather than per row,
    also keeps the truncation error bounded to a single minor unit for the whole
    aggregate instead of one per employee.
    """
    if fx_scaled_minor_units < 0:
        raise ValueError(f"FX-scaled amount must be non-negative, got {fx_scaled_minor_units}")
    return fx_scaled_minor_units // FX_SCALE


def to_fx_scaled(usd_minor_units: int) -> int:
    """Lift a plain USD minor-unit amount into FX-scaled space.

    Needed when comparing a user-supplied bound (say, "at least $100,000")
    against the FX-scaled column the database stores and indexes.
    """
    if usd_minor_units < 0:
        raise ValueError(f"monetary amount must be non-negative, got {usd_minor_units}")
    return usd_minor_units * FX_SCALE


def convert_to_usd_minor_units(amount_minor_units: int, fx_rate_scaled: int) -> int:
    """Convert a single local-currency amount into USD minor units."""
    if amount_minor_units < 0:
        raise ValueError(f"monetary amount must be non-negative, got {amount_minor_units}")
    if fx_rate_scaled <= 0:
        raise ValueError(f"FX rate must be positive, got {fx_rate_scaled}")
    return descale_fx(amount_minor_units * fx_rate_scaled)
