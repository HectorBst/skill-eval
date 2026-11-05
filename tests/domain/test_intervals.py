import pytest
from hypothesis import given
from hypothesis import strategies as st

from skill_eval.domain.intervals import (
    Interval,
    IntervalMethod,
    estimate_difference,
    estimate_share,
)

shares = st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=40)


class TestInterval:
    def test_rejects_reversed_bounds(self) -> None:
        with pytest.raises(ValueError, match="reversed"):
            Interval(0.6, 0.4)

    def test_contains_its_bounds(self) -> None:
        interval = Interval(0.2, 0.4)
        assert interval.contains(0.2)
        assert interval.contains(0.4)
        assert not interval.contains(0.41)


class TestEstimateShare:
    def test_student_interval_on_per_case_values(self) -> None:
        # Recall of the example: 14 cases at 1.0, 4 at 0.8, one at 0.5, one at 0.3.
        values = [1.0] * 14 + [0.8] * 4 + [0.5, 0.3]
        estimate = estimate_share(values, 0.95)
        assert estimate.method is IntervalMethod.STUDENT_T_BY_CASE
        assert estimate.cases == 20
        assert estimate.value == pytest.approx(0.9)
        assert estimate.interval.low == pytest.approx(0.81017, abs=1e-5)
        assert estimate.interval.high == pytest.approx(0.98983, abs=1e-5)

    def test_clips_to_zero(self) -> None:
        estimate = estimate_share([0.0] * 17 + [0.2] * 3, 0.95)
        assert estimate.interval.low == 0.0
        assert estimate.interval.high == pytest.approx(0.0643, abs=1e-4)

    def test_wilson_when_every_case_has_the_same_value(self) -> None:
        estimate = estimate_share([0.0] * 20, 0.95)
        assert estimate.method is IntervalMethod.WILSON_BY_CASE
        assert estimate.interval.low == 0.0
        # z^2 / (n + z^2) with z = 1.95996 and n = 20 cases
        assert estimate.interval.high == pytest.approx(0.16113, abs=1e-5)

    def test_wilson_for_a_perfect_score(self) -> None:
        estimate = estimate_share([1.0] * 20, 0.95)
        assert estimate.interval.low == pytest.approx(0.83887, abs=1e-5)
        assert estimate.interval.high == 1.0

    def test_single_case_uses_wilson_with_one_case(self) -> None:
        estimate = estimate_share([1.0], 0.95)
        assert estimate.method is IntervalMethod.WILSON_BY_CASE
        assert estimate.interval.low == pytest.approx(0.20654, abs=1e-5)

    def test_higher_level_widens_the_range(self) -> None:
        values = [1.0, 0.9, 0.6, 0.8, 0.7]
        narrow = estimate_share(values, 0.80).interval
        wide = estimate_share(values, 0.99).interval
        assert wide.low < narrow.low
        assert wide.high > narrow.high

    @pytest.mark.parametrize("level", [0.0, 1.0, -0.5, 1.5])
    def test_rejects_invalid_level(self, level: float) -> None:
        with pytest.raises(ValueError, match="strictly between 0 and 1"):
            estimate_share([0.5, 0.6], level)

    def test_rejects_empty_values(self) -> None:
        with pytest.raises(ValueError, match="zero cases"):
            estimate_share([], 0.95)

    def test_rejects_values_outside_unit_range(self) -> None:
        with pytest.raises(ValueError, match="between 0 and 1"):
            estimate_share([0.5, 1.2], 0.95)

    @given(shares)
    def test_range_is_within_bounds_and_holds_the_mean(self, values: list[float]) -> None:
        estimate = estimate_share(values, 0.95)
        assert 0.0 <= estimate.interval.low <= estimate.interval.high <= 1.0
        assert estimate.interval.low - 1e-9 <= estimate.value <= estimate.interval.high + 1e-9


class TestEstimateDifference:
    def test_student_interval_on_differences(self) -> None:
        estimate = estimate_difference([0.1, 0.2, 0.0, 0.3], 0.95)
        assert estimate.value == pytest.approx(0.15)
        # 0.15 -/+ t(0.975, 3) * stdev / sqrt(4) = 0.15 -/+ 3.182446 * 0.0645497
        assert estimate.interval.low == pytest.approx(-0.055426, abs=1e-6)
        assert estimate.interval.high == pytest.approx(0.355426, abs=1e-6)

    def test_single_difference_gives_the_whole_range(self) -> None:
        assert estimate_difference([0.2], 0.95).interval == Interval(-1.0, 1.0)

    def test_identical_differences_give_a_point(self) -> None:
        interval = estimate_difference([0.1, 0.1, 0.1], 0.95).interval
        assert interval.low == pytest.approx(0.1)
        assert interval.high == pytest.approx(0.1)

    def test_rejects_empty_differences(self) -> None:
        with pytest.raises(ValueError, match="zero cases"):
            estimate_difference([], 0.95)
