import pytest
from hypothesis import given
from hypothesis import strategies as st

from skill_eval.domain.intervals import Interval
from skill_eval.domain.verdicts import Bound, Limit, Verdict

MINIMUM = Limit(Bound.MINIMUM, 0.85)
MAXIMUM = Limit(Bound.MAXIMUM, 0.10)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        (Interval(0.86, 0.99), Verdict.PASSED),
        (Interval(0.85, 0.99), Verdict.PASSED),  # the low bound reaches the limit
        (Interval(0.81, 0.99), Verdict.INCONCLUSIVE),
        (Interval(0.70, 0.85), Verdict.INCONCLUSIVE),  # the high bound is not below
        (Interval(0.70, 0.84), Verdict.FAILED),
    ],
)
def test_minimum(interval: Interval, expected: Verdict) -> None:
    assert MINIMUM.judge(interval) is expected


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        (Interval(0.00, 0.06), Verdict.PASSED),
        (Interval(0.00, 0.10), Verdict.PASSED),
        (Interval(0.05, 0.16), Verdict.INCONCLUSIVE),
        (Interval(0.10, 0.20), Verdict.INCONCLUSIVE),
        (Interval(0.11, 0.20), Verdict.FAILED),
    ],
)
def test_maximum(interval: Interval, expected: Verdict) -> None:
    assert MAXIMUM.judge(interval) is expected


def test_direction() -> None:
    assert MINIMUM.higher_is_better
    assert not MAXIMUM.higher_is_better


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_rejects_limits_outside_unit_range(value: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        Limit(Bound.MINIMUM, value)


_RANK = {Verdict.FAILED: 0, Verdict.INCONCLUSIVE: 1, Verdict.PASSED: 2}


@given(
    st.floats(min_value=0, max_value=1),
    st.floats(min_value=0, max_value=0.5),
    st.floats(min_value=0, max_value=0.5),
)
def test_raising_a_minimum_score_never_worsens_the_verdict(
    low: float, width: float, shift: float
) -> None:
    high = min(1.0, low + width)
    shifted = Interval(min(1.0, low + shift), min(1.0, high + shift))
    assert _RANK[MINIMUM.judge(shifted)] >= _RANK[MINIMUM.judge(Interval(low, high))]
