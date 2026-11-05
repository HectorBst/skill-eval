"""Three-state verdicts against a limit, decided on the whole confidence range.

A point estimate on the right side of the limit is not enough: the verdict is
``passed`` only when the whole range is on the right side, ``failed`` when the whole
range is on the wrong side, and ``inconclusive`` when the range straddles the limit.
"""

from dataclasses import dataclass
from enum import StrEnum

from skill_eval.domain.intervals import Interval


class Verdict(StrEnum):
    """Outcome of a gate."""

    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class Bound(StrEnum):
    """Whether a limit is a floor or a ceiling for the score."""

    MINIMUM = "minimum"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class Limit:
    """A floor or a ceiling for a score between 0 and 1."""

    bound: Bound
    value: float

    def __post_init__(self) -> None:
        """Reject limits a share can never meet or always meets."""
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"A limit must lie between 0 and 1, got {self.value}.")

    @property
    def higher_is_better(self) -> bool:
        """Tell in which direction the score improves."""
        return self.bound is Bound.MINIMUM

    def judge(self, interval: Interval) -> Verdict:
        """Decide the verdict of a confidence range against this limit.

        A minimum passes when the low bound reaches it and fails when the high bound
        stays below it. A maximum passes when the high bound stays at or below it and
        fails when the low bound exceeds it.
        """
        if self.bound is Bound.MINIMUM:
            if interval.low >= self.value:
                return Verdict.PASSED
            if interval.high < self.value:
                return Verdict.FAILED
            return Verdict.INCONCLUSIVE
        if interval.high <= self.value:
            return Verdict.PASSED
        if interval.low > self.value:
            return Verdict.FAILED
        return Verdict.INCONCLUSIVE
