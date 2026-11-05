from math import comb

import pytest
from hypothesis import given
from hypothesis import strategies as st

from skill_eval.domain.estimators import CaseCount, mean_over_cases, pass_at_k, pass_hat_k


@st.composite
def case_and_k(draw: st.DrawFn) -> tuple[CaseCount, int]:
    runs = draw(st.integers(min_value=1, max_value=30))
    successes = draw(st.integers(min_value=0, max_value=runs))
    k = draw(st.integers(min_value=1, max_value=runs))
    return CaseCount("case", runs, successes), k


class TestCaseCount:
    def test_accepts_unicode_names(self) -> None:
        assert CaseCount("q-résumé-✓", 10, 1).name == "q-résumé-✓"

    def test_derived_counts(self) -> None:
        case = CaseCount("pos-01", 10, 7)
        assert case.failures == 3
        assert case.success_rate == pytest.approx(0.7)
        assert case.inverted() == CaseCount("pos-01", 10, 3)

    @pytest.mark.parametrize(
        ("name", "runs", "successes", "message"),
        [
            ("", 10, 1, "non-empty name"),
            ("c", 0, 0, "at least one run"),
            ("c", 10, 11, "11 successes for 10 runs"),
            ("c", 10, -1, "-1 successes"),
            ("two\nlines", 10, 1, "one printable line"),
            ("line\u2028separator", 10, 1, "one printable line"),
            ("x" * 256, 10, 1, "at most 255 characters"),
        ],
    )
    def test_rejects_impossible_counts(
        self, name: str, runs: int, successes: int, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            CaseCount(name, runs, successes)


class TestPassAtK:
    def test_matches_combinatorial_formula(self) -> None:
        # 1 - C(5, 3) / C(10, 3) = 1 - 10 / 120
        assert pass_at_k(CaseCount("c", 10, 5), 3) == pytest.approx(1 - 10 / 120)

    def test_is_one_when_failures_are_fewer_than_k(self) -> None:
        assert pass_at_k(CaseCount("c", 10, 8), 3) == 1.0

    def test_pass_at_1_is_the_success_rate(self) -> None:
        assert pass_at_k(CaseCount("c", 10, 4), 1) == pytest.approx(0.4)

    @pytest.mark.parametrize("k", [0, 11])
    def test_rejects_k_outside_runs(self, k: int) -> None:
        with pytest.raises(ValueError, match="k must be between 1 and 10"):
            pass_at_k(CaseCount("c", 10, 4), k)

    @given(case_and_k())
    def test_is_a_probability_that_grows_with_k(self, drawn: tuple[CaseCount, int]) -> None:
        case, k = drawn
        value = pass_at_k(case, k)
        assert 0.0 <= value <= 1.0
        if k < case.runs:
            assert pass_at_k(case, k + 1) >= value - 1e-12


class TestPassHatK:
    def test_matches_combinatorial_formula(self) -> None:
        assert pass_hat_k(CaseCount("c", 10, 8), 5) == pytest.approx(comb(8, 5) / comb(10, 5))

    def test_is_zero_or_one_when_runs_equal_k(self) -> None:
        assert pass_hat_k(CaseCount("c", 5, 5), 5) == 1.0
        assert pass_hat_k(CaseCount("c", 5, 4), 5) == 0.0

    def test_rejects_k_outside_runs(self) -> None:
        with pytest.raises(ValueError, match="k must be between 1 and 10"):
            pass_hat_k(CaseCount("c", 10, 4), 11)

    @given(case_and_k())
    def test_is_a_probability_that_shrinks_with_k(self, drawn: tuple[CaseCount, int]) -> None:
        case, k = drawn
        value = pass_hat_k(case, k)
        assert 0.0 <= value <= 1.0
        assert value <= pass_at_k(case, k) + 1e-12
        if k < case.runs:
            assert pass_hat_k(case, k + 1) <= value + 1e-12

    @given(case_and_k())
    def test_pass_hat_1_equals_pass_at_1(self, drawn: tuple[CaseCount, int]) -> None:
        case, _ = drawn
        assert pass_hat_k(case, 1) == pytest.approx(pass_at_k(case, 1))


class TestMeanOverCases:
    def test_weighs_cases_equally(self) -> None:
        assert mean_over_cases([1.0, 0.0, 0.5]) == pytest.approx(0.5)

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="zero cases"):
            mean_over_cases([])

    def test_differs_from_power_of_the_mean_when_failures_concentrate(self) -> None:
        cases = [CaseCount("a", 10, 10), CaseCount("b", 10, 0)]
        per_case = mean_over_cases(pass_hat_k(case, 2) for case in cases)
        naive = mean_over_cases(case.success_rate for case in cases) ** 2
        assert per_case == pytest.approx(0.5)
        assert naive == pytest.approx(0.25)
