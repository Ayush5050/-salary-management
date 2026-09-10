"""Descriptive statistics over monetary amounts.

These functions operate on integer minor units and return integer minor units,
so they compose with :mod:`app.domain.money` without ever touching a float.

The median helpers exist in two forms on purpose. :func:`median` is a
straightforward reference implementation used by the tests; the database uses a
windowed SQL query that cannot return a list of values, only the one or two
values that straddle the midpoint, which :func:`median_of_middle_values` then
reduces. Testing the SQL path against the reference implementation over the same
data is what makes the SQL trustworthy.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal


def arithmetic_mean(total: int, count: int) -> int | None:
    """Mean of ``count`` values summing to ``total``, or ``None`` for an empty set.

    An empty set has no mean; returning ``None`` forces callers to handle the
    "no employees matched" case rather than silently reporting zero, which would
    be indistinguishable from a real average of zero.
    """
    if count < 0:
        raise ValueError(f"count must be non-negative, got {count}")
    if count == 0:
        return None
    return int((Decimal(total) / count).to_integral_value(rounding=ROUND_HALF_UP))


def median_of_middle_values(middle_total: int, middle_count: int) -> int | None:
    """Reduce the one or two midpoint values of an ordered set to a median.

    An odd-sized set has a single midpoint value; an even-sized set has two,
    whose mean is the median. ``middle_count`` is therefore 1 or 2 for a
    non-empty set, and 0 when nothing matched.
    """
    if middle_count not in (0, 1, 2):
        raise ValueError(f"expected 0, 1 or 2 midpoint values, got {middle_count}")
    if middle_count == 0:
        return None
    return arithmetic_mean(middle_total, middle_count)


def median(values: Sequence[int]) -> int | None:
    """Reference median over an unordered sequence, or ``None`` when empty."""
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return arithmetic_mean(ordered[midpoint - 1] + ordered[midpoint], 2)
