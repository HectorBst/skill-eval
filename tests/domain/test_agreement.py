import pytest

from skill_eval.domain.agreement import LabelledAnswer, cohen_kappa

AGREE_PASS = LabelledAnswer(judge_passed=True, person_passed=True)
AGREE_FAIL = LabelledAnswer(judge_passed=False, person_passed=False)
JUDGE_TOO_KIND = LabelledAnswer(judge_passed=True, person_passed=False)
JUDGE_TOO_HARSH = LabelledAnswer(judge_passed=False, person_passed=True)


def test_perfect_agreement() -> None:
    assert cohen_kappa([AGREE_PASS, AGREE_FAIL, AGREE_PASS]) == pytest.approx(1.0)


def test_agreement_no_better_than_chance() -> None:
    answers = [AGREE_PASS, JUDGE_TOO_KIND, JUDGE_TOO_HARSH, AGREE_FAIL]
    assert cohen_kappa(answers) == pytest.approx(0.0)


def test_raw_agreement_overstates_real_agreement() -> None:
    # 90 % raw agreement, but the judge passes almost everything.
    answers = [AGREE_PASS] * 85 + [AGREE_FAIL] * 5 + [JUDGE_TOO_KIND] * 10
    kappa = cohen_kappa(answers)
    assert kappa is not None
    assert kappa == pytest.approx(0.085 / 0.185)


def test_undefined_when_both_raters_always_give_one_grade() -> None:
    assert cohen_kappa([AGREE_PASS] * 5) is None


def test_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        cohen_kappa([])
