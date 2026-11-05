import pytest

from skill_eval.domain.comparison import Change, paired_difference, read_change
from skill_eval.domain.intervals import Estimate, Interval, IntervalMethod


def _difference(low: float, high: float) -> Estimate:
    return Estimate((low + high) / 2, Interval(low, high), IntervalMethod.STUDENT_T_BY_CASE, 10)


def test_pairs_cases_by_name_and_ignores_unshared_ones() -> None:
    current = {"a": 1.0, "b": 0.5, "new": 0.0}
    reference = {"b": 0.25, "a": 0.75, "removed": 1.0}
    estimate = paired_difference(current, reference, 0.95)
    assert estimate.cases == 2
    assert estimate.value == pytest.approx(0.25)


def test_rejects_runs_without_shared_cases() -> None:
    with pytest.raises(ValueError, match="share no case"):
        paired_difference({"a": 1.0}, {"b": 1.0}, 0.95)


@pytest.mark.parametrize(
    ("low", "high", "higher_is_better", "expected"),
    [
        (0.01, 0.10, True, Change.IMPROVED),
        (-0.02, 0.06, True, Change.NO_CLEAR_CHANGE),
        (0.00, 0.06, True, Change.NO_CLEAR_CHANGE),
        (-0.10, -0.01, True, Change.REGRESSED),
        (0.01, 0.10, False, Change.REGRESSED),
        (-0.10, -0.01, False, Change.IMPROVED),
    ],
)
def test_read_change(low: float, high: float, *, higher_is_better: bool, expected: Change) -> None:
    assert read_change(_difference(low, high), higher_is_better=higher_is_better) is expected
