"""Every figure of docs/skill-eval-result.example.yaml, recomputed from per-case counts.

Values are compared at the precision the example publishes them: three decimals for
scores, two for ranges.
"""

from collections.abc import Callable, Sequence

import pytest

from skill_eval.domain.agreement import cohen_kappa
from skill_eval.domain.comparison import Change, paired_difference, read_change
from skill_eval.domain.estimators import CaseCount, mean_over_cases, pass_at_k, pass_hat_k
from skill_eval.domain.intervals import Estimate, estimate_difference, estimate_share
from skill_eval.domain.verdicts import Bound, Limit, Verdict
from tests.support import example

LEVEL = 0.95


def _estimate(cases: Sequence[CaseCount], score: Callable[[CaseCount], float]) -> Estimate:
    return estimate_share([score(case) for case in cases], LEVEL)


def _published(estimate: Estimate) -> tuple[float, tuple[float, float]]:
    return round(estimate.value, 3), (
        round(estimate.interval.low, 2),
        round(estimate.interval.high, 2),
    )


def _started_rate(case: CaseCount) -> float:
    return case.failures / case.runs


def _rate(case: CaseCount) -> float:
    return case.success_rate


class TestInvocation:
    def test_counts(self) -> None:
        positive, negative = example.POSITIVE_HOLDOUT, example.NEGATIVE_HOLDOUT
        assert sum(case.successes for case in positive) == 180
        assert sum(case.failures for case in positive) == 20
        assert sum(case.failures for case in negative) == 6

    def test_recall(self) -> None:
        assert _published(_estimate(example.POSITIVE_HOLDOUT, _rate)) == (0.900, (0.81, 0.99))

    def test_false_trigger_rate(self) -> None:
        estimate = _estimate(example.NEGATIVE_HOLDOUT, _started_rate)
        assert _published(estimate) == (0.030, (0.00, 0.06))

    def test_precision(self) -> None:
        justified = sum(case.successes for case in example.POSITIVE_HOLDOUT)
        mistaken = sum(case.failures for case in example.NEGATIVE_HOLDOUT)
        assert round(justified / (justified + mistaken), 3) == 0.968

    def test_pass_hat_k_on_positive_cases(self) -> None:
        estimate = _estimate(example.POSITIVE_HOLDOUT, lambda case: pass_hat_k(case, 5))
        assert _published(estimate) == (0.745, (0.56, 0.93))

    def test_pass_hat_k_on_negative_cases(self) -> None:
        estimate = _estimate(example.NEGATIVE_HOLDOUT, lambda case: pass_hat_k(case, 5))
        assert _published(estimate) == (0.883, (0.75, 1.00))

    def test_tuning_point_scores(self) -> None:
        recall = mean_over_cases(_rate(case) for case in example.POSITIVE_TUNING)
        false_triggers = mean_over_cases(_started_rate(case) for case in example.NEGATIVE_TUNING)
        assert round(recall, 3) == 0.947
        assert round(false_triggers, 3) == 0.023


class TestQuality:
    def test_successful_runs(self) -> None:
        assert sum(case.successes for case in example.QUALITY_HOLDOUT) == 122

    def test_pass_at_1(self) -> None:
        assert _published(_estimate(example.QUALITY_HOLDOUT, _rate)) == (0.813, (0.65, 0.98))

    def test_pass_at_k(self) -> None:
        estimate = _estimate(example.QUALITY_HOLDOUT, lambda case: pass_at_k(case, 3))
        assert _published(estimate) == (0.917, (0.77, 1.00))

    def test_pass_hat_k(self) -> None:
        estimate = _estimate(example.QUALITY_HOLDOUT, lambda case: pass_hat_k(case, 5))
        assert _published(estimate) == (0.611, (0.36, 0.86))

    def test_pass_hat_k_by_uses(self) -> None:
        curve = [
            round(mean_over_cases(pass_hat_k(case, k) for case in example.QUALITY_HOLDOUT), 3)
            for k in range(1, 11)
        ]
        assert curve == [0.813, 0.735, 0.681, 0.642, 0.611, 0.587, 0.567, 0.551, 0.540, 0.533]

    def test_failures_are_concentrated(self) -> None:
        spread_evenly = (122 / 150) ** 5
        assert round(spread_evenly, 3) == 0.356

    def test_without_skill(self) -> None:
        without = [
            CaseCount(name, example.RUNS, value)
            for name, value in example.QUALITY_WITHOUT_SKILL.items()
        ]
        assert sum(case.successes for case in without) == 79
        assert _published(_estimate(without, _rate)) == (0.527, (0.40, 0.66))

    def test_lift(self) -> None:
        differences = [
            case.success_rate - example.QUALITY_WITHOUT_SKILL[case.name] / example.RUNS
            for case in example.QUALITY_HOLDOUT
        ]
        assert _published(estimate_difference(differences, LEVEL)) == (0.287, (0.19, 0.38))

    def test_judge_agreement(self) -> None:
        kappa = cohen_kappa(example.JUDGE_ANSWERS)
        assert kappa is not None
        assert len(example.JUDGE_ANSWERS) == 24
        assert round(kappa, 2) == 0.78

    def test_tuning_point_score(self) -> None:
        assert round(mean_over_cases(_rate(case) for case in example.QUALITY_TUNING), 3) == 0.896


class TestComparedWithPreviousVersion:
    def test_invocation_recall(self) -> None:
        current = {case.name: case.success_rate for case in example.POSITIVE_HOLDOUT}
        previous = {name: value / 10 for name, value in example.POSITIVE_PREVIOUS_STARTED.items()}
        difference = paired_difference(current, previous, LEVEL)
        assert _published(difference) == (0.055, (0.01, 0.10))
        assert read_change(difference, higher_is_better=True) is Change.IMPROVED

    def test_quality_pass_at_1(self) -> None:
        current = {case.name: case.success_rate for case in example.QUALITY_HOLDOUT}
        previous = {name: value / 10 for name, value in example.QUALITY_PREVIOUS.items()}
        difference = paired_difference(current, previous, LEVEL)
        assert _published(difference) == (0.020, (-0.02, 0.06))
        assert read_change(difference, higher_is_better=True) is Change.NO_CLEAR_CHANGE


@pytest.mark.parametrize(
    ("cases", "score", "limit", "expected"),
    [
        (example.POSITIVE_HOLDOUT, _rate, Limit(Bound.MINIMUM, 0.85), Verdict.INCONCLUSIVE),
        (
            example.NEGATIVE_HOLDOUT,
            _started_rate,
            Limit(Bound.MAXIMUM, 0.10),
            Verdict.PASSED,
        ),
        (
            example.POSITIVE_HOLDOUT,
            lambda case: pass_hat_k(case, 5),
            Limit(Bound.MINIMUM, 0.50),
            Verdict.PASSED,
        ),
        (example.QUALITY_HOLDOUT, _rate, Limit(Bound.MINIMUM, 0.75), Verdict.INCONCLUSIVE),
        (
            example.QUALITY_HOLDOUT,
            lambda case: pass_hat_k(case, 5),
            Limit(Bound.MINIMUM, 0.60),
            Verdict.INCONCLUSIVE,
        ),
    ],
    ids=[
        "invocation_recall",
        "invocation_false_trigger_rate",
        "invocation_pass_hat_k",
        "quality_pass_at_1",
        "quality_pass_hat_k",
    ],
)
def test_gate_verdicts(
    cases: Sequence[CaseCount],
    score: Callable[[CaseCount], float],
    limit: Limit,
    expected: Verdict,
) -> None:
    assert limit.judge(_estimate(cases, score).interval) is expected
