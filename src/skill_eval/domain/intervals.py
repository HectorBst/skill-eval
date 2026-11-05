"""Confidence ranges computed case by case.

Trials of one case are not independent: a phrasing the skill misses tends to be missed
again. Ranges are therefore computed on per-case values, with the case as the unit:

- Student interval with ``cases - 1`` degrees of freedom, clipped to the possible values;
- Wilson interval when every case has the same value, where Student would give a range
  of zero width.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from statistics import NormalDist, fmean, stdev

from scipy.stats import t as student_t


class IntervalMethod(StrEnum):
    """How a range was computed, recorded in the result for traceability."""

    STUDENT_T_BY_CASE = "student_t_by_case"
    WILSON_BY_CASE = "wilson_by_case"


@dataclass(frozen=True, slots=True)
class Interval:
    """Closed range ``[low, high]``."""

    low: float
    high: float

    def __post_init__(self) -> None:
        """Reject reversed bounds."""
        if self.low > self.high:
            raise ValueError(f"Interval bounds are reversed: [{self.low}, {self.high}].")

    def contains(self, value: float) -> bool:
        """Tell whether ``value`` lies within the range, bounds included."""
        return self.low <= value <= self.high


@dataclass(frozen=True, slots=True)
class Estimate:
    """A score with its confidence range.

    Attributes:
        value: Mean of the per-case values.
        interval: Confidence range of the mean.
        method: How the range was computed.
        cases: Number of cases the score is computed on.
    """

    value: float
    interval: Interval
    method: IntervalMethod
    cases: int


def estimate_share(values: Sequence[float], level: float) -> Estimate:
    """Estimate a mean of per-case values that each lie between 0 and 1.

    Args:
        values: One value per case (success rate, pass@k or pass^k of the case).
        level: Confidence level, strictly between 0 and 1.

    Returns:
        The mean with a Student range clipped to ``[0, 1]``, or a Wilson range when every
        case has the same value. Wilson then uses the number of cases as sample size.

    Raises:
        ValueError: If there is no value, a value is outside ``[0, 1]`` or the level is
            invalid.
    """
    _check_level(level)
    _check_not_empty(values)
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("Per-case values of a share must lie between 0 and 1.")
    mean = fmean(values)
    if _all_equal(values):
        return Estimate(
            mean, _wilson(mean, len(values), level), IntervalMethod.WILSON_BY_CASE, len(values)
        )
    interval = _student(values, level, lower=0.0, upper=1.0)
    return Estimate(mean, interval, IntervalMethod.STUDENT_T_BY_CASE, len(values))


def estimate_difference(differences: Sequence[float], level: float) -> Estimate:
    """Estimate a mean of paired per-case differences, each between -1 and 1.

    Used for the lift (with minus without the skill) and for the comparison with a
    previous version. When every difference is the same, the Student range has zero
    width; no fallback is defined by the method for differences.

    Args:
        differences: One difference per case, computed on the same cases.
        level: Confidence level, strictly between 0 and 1.

    Returns:
        The mean difference with a Student range clipped to ``[-1, 1]``. With a single
        case the range is the whole ``[-1, 1]``.

    Raises:
        ValueError: If there is no difference or the level is invalid.
    """
    _check_level(level)
    _check_not_empty(differences)
    mean = fmean(differences)
    interval = _student(differences, level, lower=-1.0, upper=1.0)
    return Estimate(mean, interval, IntervalMethod.STUDENT_T_BY_CASE, len(differences))


def _student(values: Sequence[float], level: float, *, lower: float, upper: float) -> Interval:
    if len(values) < 2:  # noqa: PLR2004 - Student needs one degree of freedom
        return Interval(lower, upper)
    mean = fmean(values)
    half_width = _t_critical(level, len(values) - 1) * stdev(values) / sqrt(len(values))
    return Interval(max(lower, mean - half_width), min(upper, mean + half_width))


def _wilson(share: float, size: int, level: float) -> Interval:
    z = _z_critical(level)
    z2 = z * z
    denominator = 1.0 + z2 / size
    centre = (share + z2 / (2 * size)) / denominator
    half_width = z * sqrt(share * (1.0 - share) / size + z2 / (4 * size * size)) / denominator
    # At 0 and 1 the bound is exact; the subtraction would leave a rounding residue.
    low = 0.0 if share == 0.0 else max(0.0, centre - half_width)
    high = 1.0 if share == 1.0 else min(1.0, centre + half_width)
    return Interval(low, high)


def _t_critical(level: float, degrees_of_freedom: int) -> float:
    return float(student_t.ppf(1.0 - (1.0 - level) / 2.0, degrees_of_freedom))


def _z_critical(level: float) -> float:
    return NormalDist().inv_cdf(1.0 - (1.0 - level) / 2.0)


def _all_equal(values: Sequence[float]) -> bool:
    return all(value == values[0] for value in values)


def _check_level(level: float) -> None:
    if not 0.0 < level < 1.0:
        raise ValueError(f"Confidence level must be strictly between 0 and 1, got {level}.")


def _check_not_empty(values: Sequence[float]) -> None:
    if not values:
        raise ValueError("Cannot estimate a score over zero cases.")
