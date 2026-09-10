"""Salary bands used by the dashboard's distribution chart.

Bands are fixed rather than derived from the data (e.g. by quantile) so that the
histogram's shape is comparable across filter selections. If the bands moved with
the filter, switching from "all employees" to "Germany" would change both the
bars and the axis, and the HR Manager could not tell which had moved.

Boundaries are expressed in USD minor units because that is the unit every
aggregate in the system is already denominated in.
"""

from dataclasses import dataclass
from typing import Final

from app.domain.money import MINOR_UNITS_PER_MAJOR


@dataclass(frozen=True, slots=True)
class SalaryBand:
    """A half-open USD band ``[lower, upper)``; ``upper`` of ``None`` is unbounded."""

    label: str
    lower_usd_minor: int
    upper_usd_minor: int | None


def _usd(major: int) -> int:
    return major * MINOR_UNITS_PER_MAJOR


SALARY_BANDS: Final[tuple[SalaryBand, ...]] = (
    SalaryBand("< $25k", 0, _usd(25_000)),
    SalaryBand("$25k – $50k", _usd(25_000), _usd(50_000)),
    SalaryBand("$50k – $75k", _usd(50_000), _usd(75_000)),
    SalaryBand("$75k – $100k", _usd(75_000), _usd(100_000)),
    SalaryBand("$100k – $150k", _usd(100_000), _usd(150_000)),
    SalaryBand("$150k – $200k", _usd(150_000), _usd(200_000)),
    SalaryBand("$200k – $300k", _usd(200_000), _usd(300_000)),
    SalaryBand("$300k+", _usd(300_000), None),
)


def band_for(total_comp_usd_minor: int) -> SalaryBand:
    """Return the band a USD amount falls into.

    Raises if no band matches, which can only happen if the band table is edited
    into a state with a gap — an error worth surfacing loudly rather than
    silently dropping employees out of the histogram.
    """
    for band in SALARY_BANDS:
        above_lower = total_comp_usd_minor >= band.lower_usd_minor
        below_upper = band.upper_usd_minor is None or total_comp_usd_minor < band.upper_usd_minor
        if above_lower and below_upper:
            return band
    raise ValueError(f"no salary band covers {total_comp_usd_minor} USD minor units")
