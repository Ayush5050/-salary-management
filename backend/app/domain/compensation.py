"""How an employee's stored salary becomes a comparable number.

Every write path that touches salary or currency goes through
:func:`total_comp_usd_fx_scaled` to recompute the derived column on
:class:`app.models.Employee`. Concentrating that here is what keeps the
denormalised column honest: there is exactly one expression in the codebase that
can produce it, so it cannot drift from the inputs it is derived from.
"""

from dataclasses import dataclass

from app.domain.money import descale_fx


@dataclass(frozen=True, slots=True)
class Compensation:
    """An employee's pay, as stored: local currency, integer minor units."""

    base_salary_minor: int
    bonus_minor: int
    currency_code: str

    def __post_init__(self) -> None:
        if self.base_salary_minor < 0:
            raise ValueError(f"base salary must be non-negative, got {self.base_salary_minor}")
        if self.bonus_minor < 0:
            raise ValueError(f"bonus must be non-negative, got {self.bonus_minor}")

    @property
    def total_minor(self) -> int:
        """Total annual compensation in the employee's own currency.

        Base plus bonus. The organisation compares people on total cash
        compensation, because a bonus-weighted sales package and a
        base-weighted engineering package are not comparable on base alone.
        """
        return self.base_salary_minor + self.bonus_minor


def total_comp_usd_fx_scaled(compensation: Compensation, usd_rate_scaled: int) -> int:
    """The value stored in ``Employee.total_comp_usd_fx_scaled``."""
    if usd_rate_scaled <= 0:
        raise ValueError(f"FX rate must be positive, got {usd_rate_scaled}")
    return compensation.total_minor * usd_rate_scaled


def total_comp_usd_minor(compensation: Compensation, usd_rate_scaled: int) -> int:
    """The same total, expressed in plain USD minor units for display."""
    return descale_fx(total_comp_usd_fx_scaled(compensation, usd_rate_scaled))
