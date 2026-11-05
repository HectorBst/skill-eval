"""Per-case success counts and the pass@k and pass^k estimators.

Every score of the method is first computed for each test case, then averaged over
cases. Applying ``p ** k`` to an average success rate is wrong as soon as failures
concentrate on a few cases, which is the usual situation.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import comb
from statistics import fmean

MAX_NAME_LENGTH = 255
"""Case names name files and appear in results: one printable line, of reasonable length."""


@dataclass(frozen=True, slots=True)
class CaseCount:
    """Outcome of one test case run several times, each time in a new conversation.

    Attributes:
        name: Case identifier, unique within its set of cases.
        runs: Number of trials of the case.
        successes: Number of trials with the desired outcome.
    """

    name: str
    runs: int
    successes: int

    def __post_init__(self) -> None:
        """Reject counts that cannot come from real trials."""
        if not self.name:
            raise ValueError("A case needs a non-empty name.")
        if not self.name.isprintable() or len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(
                f"Case name {self.name[:40]!r} must be one printable line of at most "
                f"{MAX_NAME_LENGTH} characters."
            )
        if self.runs < 1:
            raise ValueError(f"Case {self.name!r} needs at least one run, got {self.runs}.")
        if not 0 <= self.successes <= self.runs:
            raise ValueError(
                f"Case {self.name!r} has {self.successes} successes for {self.runs} runs."
            )

    @property
    def failures(self) -> int:
        """Number of trials without the desired outcome."""
        return self.runs - self.successes

    @property
    def success_rate(self) -> float:
        """Share of trials with the desired outcome (pass@1 of the case)."""
        return self.successes / self.runs

    def inverted(self) -> "CaseCount":
        """Swap successes and failures, for example to read negative cases as triggers."""
        return CaseCount(self.name, self.runs, self.failures)


def pass_at_k(case: CaseCount, k: int) -> float:
    """Estimate the probability that at least one of ``k`` trials succeeds.

    Unbiased estimator ``1 - C(n - c, k) / C(n, k)`` (Chen et al., 2021, arXiv 2107.03374),
    with ``n`` runs and ``c`` successes.

    Args:
        case: Success count of one case.
        k: Number of tries a user would accept, between 1 and ``case.runs``.

    Returns:
        The estimate, between 0 and 1.
    """
    _check_k(case, k)
    return 1.0 - comb(case.failures, k) / comb(case.runs, k)


def pass_hat_k(case: CaseCount, k: int) -> float:
    """Estimate the probability that ``k`` trials in a row all succeed (pass^k).

    Combinatorial estimator ``C(c, k) / C(n, k)`` (Yao et al., 2024, arXiv 2406.12045),
    with ``n`` runs and ``c`` successes. With ``n == k`` it can only be 0 or 1, hence the
    advice to run each case at least ``2 * k`` times.

    Args:
        case: Success count of one case.
        k: Number of uses in a row the skill must hold over, between 1 and ``case.runs``.

    Returns:
        The estimate, between 0 and 1.
    """
    _check_k(case, k)
    return comb(case.successes, k) / comb(case.runs, k)


def mean_over_cases(values: Iterable[float]) -> float:
    """Average per-case values, each case weighing the same.

    Raises:
        ValueError: If there is no value to average.
    """
    collected = list(values)
    if not collected:
        raise ValueError("Cannot average over zero cases.")
    return fmean(collected)


def _check_k(case: CaseCount, k: int) -> None:
    if not 1 <= k <= case.runs:
        raise ValueError(f"k must be between 1 and {case.runs} runs of {case.name!r}, got {k}.")
