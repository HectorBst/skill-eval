"""Paired, case-by-case comparisons on the same cases.

The lift (with minus without the skill) and the comparison with a previous version of
the skill both difference per-case values of the same cases, which removes the
case-to-case variation from the comparison.
"""

from collections.abc import Mapping
from enum import StrEnum

from skill_eval.domain.intervals import Estimate, estimate_difference


class Change(StrEnum):
    """Direction of a change between two versions, read on its confidence range."""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    NO_CLEAR_CHANGE = "no_clear_change"


def paired_difference(
    current: Mapping[str, float], reference: Mapping[str, float], level: float
) -> Estimate:
    """Estimate ``current - reference`` case by case, on the cases both share.

    Args:
        current: Per-case values of the run being judged, by case name.
        reference: Per-case values of the run it is compared with, by case name.
        level: Confidence level, strictly between 0 and 1.

    Returns:
        Mean of the differences and its Student range; ``cases`` counts shared cases.

    Raises:
        ValueError: If the two runs share no case.
    """
    shared = [name for name in current if name in reference]
    if not shared:
        raise ValueError("The two runs share no case: a paired comparison is impossible.")
    return estimate_difference([current[name] - reference[name] for name in shared], level)


def read_change(difference: Estimate, *, higher_is_better: bool) -> Change:
    """Read the direction of a change on the whole range of the difference.

    Args:
        difference: Estimate of ``current - reference``.
        higher_is_better: False for scores where lower is better, such as the false
            trigger rate.

    Returns:
        ``improved`` or ``regressed`` when the whole range excludes zero, otherwise
        ``no_clear_change``.
    """
    if difference.interval.low > 0.0:
        return Change.IMPROVED if higher_is_better else Change.REGRESSED
    if difference.interval.high < 0.0:
        return Change.REGRESSED if higher_is_better else Change.IMPROVED
    return Change.NO_CLEAR_CHANGE
